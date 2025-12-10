import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import override

import requests
import pandas
from playwright.sync_api import sync_playwright, Page, Playwright, Cookie

from config import CACHE_FILE, DOWNLOAD_DIR, EXPORT_DIR, ITERATIONS
from utils import Base, ReaderJSON, LoggingConfig

type NormalizedData = list[dict[str, str | int]]


class Scriptorium:
    def __init__(self) -> None:
        self.scraper = Scraper()
        self.link_constructor = LinkConstructor()

    def exec(self) -> None:
        self.scraper.exec()
        user_cookie = self.scraper.user_cookie
        download_links = self.link_constructor.get_download_links()
        CompanyDataDownloader(user_cookie, download_links).exec()


class Scraper(Base):
    base_url = "https://www.list-org.com"
    pages_to_inspect = ITERATIONS  # Мы делаем 4 реквеста из 10 возможных для сбора данных
    download_button = "a.btn.btn-outline-secondary.m-1"

    def __init__(self) -> None:
        self.company_ids = []
        self.link_constructor = LinkConstructor()
        self.cache = Cache()
        self.user_cookie: str | None = None  # User cookie собирается через playwright для дальнейших HTTP реквестов

    @property
    def inspection_range(self) -> range:
        return range(1, self.pages_to_inspect + 1)

    def exec(self) -> None:
        """
        Главный метод. Запускает механизм поиска ID организаций с сайта
        list-org.com, сохраняет их в файле cache.json и достаёт user cookie
        из request headers для дальнейшего использования при загрузке xlsx
        файлов с данными о компаниях
        """
        self.find_company_ids()
        self.log("Company IDS collected")

    def find_company_ids(self) -> None:
        with sync_playwright() as pw:
            page = self.setup_browser(pw)
            for page_number in self.inspection_range:
                try:
                    self.inspect_page(page, page_number)
                except ValueError:
                    continue
            self.set_user_cookie(page)

    def setup_browser(self, pw: Playwright) -> Page:
        self.log("Setting up playwright")
        browser = pw.chromium.launch(headless=False)
        page = browser.new_page()
        return page

    # TODO: split page inspection into a distinct class
    def inspect_page(self, page: Page, page_number: int) -> None:
        query_link = self.link_constructor.query_link(page_number)
        self.cache.save_url(query_link)
        self.log(f"Inspecting {query_link}")

        page.goto(query_link, timeout=0)
        download_link = self.find_download_link(page)

        self.company_ids.append(self.link_constructor.get_company_ids(download_link))

    def find_download_link(self, page: Page) -> str:
        link_elem = page.wait_for_selector(self.download_button, timeout=0)
        href = link_elem.get_attribute("href")
        download_link = f"{self.base_url}{href}"
        self.link_constructor.save_company_ids(download_link)
        self.log(f"Found download link: {download_link}")
        return download_link

    def set_user_cookie(self, page: Page) -> None:
        user_cookie = self.get_user_cookie(page)
        if not user_cookie:
            self.update_cookies(page)
            user_cookie = self.get_user_cookie(page)
        self.user_cookie = user_cookie

    def update_cookies(self, page: Page) -> None:
        company_page = self.link_constructor.random_company_page_link
        page.goto(company_page, timeout=0)

    def get_user_cookie(self, page: Page) -> str | None:
        cookies = page.context.cookies()
        user_cookie = self.get_user_cookie_from_headers(cookies)
        return user_cookie

    def get_user_cookie_from_headers(self, cookies: list[Cookie]) -> str | None:
        cookie = next((c for c in cookies if c.get("name") == "user"), None)
        if cookie:
            return cookie.get("value")


class LinkConstructor:
    base_url = "https://www.list-org.com"
    okved = 62  # Сюда включены все подкоды 'Разработка компьютерного программного обеспечения, консультационные услуги в данной области и другие сопутствующие услуги (62)'

    def __init__(self) -> None:
        self.cache = Cache()

    @property
    def download_link_prefix(self) -> str:
        return "".join([self.base_url, "/excel_list.php?ids="])

    @property
    def random_company_page_link(self) -> str:
        """
        list-org.com отдаёт cookie только при открытии страницы с детальной
        информацией о компании
        """
        # id = self.cache.load()["company_ids"][0]
        return "".join([self.base_url, "/company/", self.cache.first_company_id])

    def query_link(self, page: int) -> str:
        query_link = (
            f"{self.base_url}/"
            f"search?type=all&work=on&staff_min=100&"
            f"okved={self.okved}&"
            f"sort=staff&page={page}"
        )
        return query_link

    def save_company_ids(self, download_link: str) -> None:
        company_ids = self.get_company_ids(download_link)
        for id in company_ids.split(","):
            self.cache.save_company_ids(id)

    def get_company_ids(self, download_link: str) -> str:
        """
        По умолчанию ссылка для скачивания файла с информацией об организации
        загружает в Excel файл только 50 записей (их скрипт, как я понял,
        берёт все ID для каждой организации, отображаемой на странице). Их
        сервис позволяет передать в параметр ?ids= более 50 значений по
        умолчанию, поэтому я достаю значения IDS из полученной ссылки, а не
        просто сохраняю их
        """
        match = re.search(r"=(.*)", download_link)
        company_ids = match.group(1)
        return company_ids

    def get_download_links(self, amount: int = 200) -> list[str]:
        company_ids = self.cache.load()["company_ids"]
        download_links = []
        iterations = amount // 100
        for iteration in range(iterations):
            self.populate_download_links(company_ids, iteration, download_links)
        return download_links

    def populate_download_links(
            self, company_ids: list[str], iteration: int, download_links: list
    ) -> None:
        start = iteration * 100
        end = (iteration + 1) * 100
        link = self.construct_download_link(company_ids[start:end])
        download_links.append(link)

    def construct_download_link(self, company_ids: list[str]) -> str:
        joined_ids = ",".join(company_ids)
        return "".join([self.download_link_prefix, joined_ids])


class Cache(Base, ReaderJSON):
    @override
    def __init__(self, file_path: Path = CACHE_FILE) -> None:
        super().__init__(file_path)

    @property
    def first_company_id(self) -> str:
        return self.load()["company_ids"][0]

    def save_url(self, url: str) -> None:
        content = self.load()
        if url not in content["referers"]:
            content["referers"].append(url)
        else:
            raise ValueError("Url is visited")
        self.dump(content)

    def save_company_ids(self, id: str) -> None:
        content = self.load()
        if id not in content["company_ids"]:
            content["company_ids"].append(id)
        self.dump(content)


class CompanyDataDownloader(Base):
    dir = DOWNLOAD_DIR

    def __init__(self, user_cookie: str, download_links: list[str]) -> None:
        self.user_cookie = user_cookie
        self.download_links = download_links

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Cookie": f"user={self.user_cookie}"
        }
        return headers

    def exec(self) -> None:
        for number, download_link in enumerate(self.download_links):
            response = self.make_request(download_link)
            self.save_file(response, number)

    def make_request(self, download_link: str) -> requests.Response:
        return requests.get(download_link, stream=True, headers=self.headers)

    def save_file(self, response: requests.Response, number: int) -> None:
        file_name = f"data_{number}.xlsx"
        with open(self.dir.joinpath(file_name), "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
        self.log(f"File {file_name} successfully downloaded in {self.dir}")


class CompanySourceData:
    source_columns = [
        "ИНН",
        "Юридическое наименование",
        "Сотрудников",
        "Сайт",
        "Юридический адрес",
        "Телефон (один из)",
    ]


class ReaderExcel(CompanySourceData):
    dir = DOWNLOAD_DIR

    def exec(self) -> pandas.DataFrame:
        files = self.get_company_data_files()
        company_data = pandas.concat(files, ignore_index=True)
        return company_data

    def get_company_data_files(self) -> list[pandas.DataFrame]:
        return [
            pandas.read_excel(file, usecols=self.source_columns)
            for file
            in self.dir.iterdir()
            if file.is_file() and file.suffix == ".xlsx"
        ]


class Normalizer(CompanySourceData):
    blank = "—"

    def __init__(self, company_data: pandas.DataFrame) -> None:
        self.company_data = company_data

    def exec(self) -> NormalizedData:
        normalized_data = [
            asdict(self.normalize_row(row))
            for _, row
            in self.company_data.iterrows()
        ]
        return normalized_data

    def normalize_row(self, row: pandas.Series) -> "CompanyData":
        return CompanyData(
            inn=self.normalize_field(row, 0),
            name=self.normalize_field(row, 1),
            employees=int(self.normalize_field(row, 2)),
            region=self.normalize_region(row, 4),
            contacts=self.normalize_phone(row, 5),
            site=self.normalize_field(row, 3),
        )

    def normalize_region(self, row: pandas.Series, index: int) -> str:
        normalized_field = self.normalize_field(row, index).split(", ")
        city, region = normalized_field[1], normalized_field[2]
        if self.check_moscow_in_city_field(city):
            return "Г. МОСКВА"
        elif self.check_spb_in_city_field(city):
            return "Г. САНКТ-ПЕТЕРБУРГ"
        else:
            return ",".join([city, region])

    def normalize_phone(self, row: pandas.Series, index: int) -> str:
        normalized_field = self.normalize_field(row, index)
        normalized_phone = normalized_field.replace(" ", "").replace("(", "-").replace(")", "-")
        return normalized_phone

    def normalize_field(self, row: pandas.Series, index: int) -> str:
        source_row = row[self.source_columns[index]]
        if pandas.notna(source_row):
            return source_row
        return self.blank

    def check_moscow_in_city_field(self, city: str) -> bool:
        pattern = re.compile(
            r"(?:г\.?\s*)?Москва",
            re.IGNORECASE
        )
        return bool(pattern.search(city))

    def check_spb_in_city_field(self, city: str) -> bool:
        pattern = re.compile(
            r"(?:г\.?\s*)?Санкт[-\s]?Петербург",
            re.IGNORECASE
        )
        return bool(pattern.search(city))


@dataclass
class CompanyData:
    inn: str
    name: str
    employees: int
    region: str
    contacts: str
    site: str
    source: str = "www.list-org.com"
    okved_main: int = 62  # Т.к. мы делали запрос к list-org.com по ОКВЭД коду
                          # мы гарантированно знаем, что компания занимается
                          # смежной детяельностью


class Exporter:
    columns_order = [
        "inn",
        "name",
        "employees",
        "okved_main",
        "region",
        "contacts",
        "site",
        "source"
    ]

    def __init__(self, normalized_data: NormalizedData) -> None:
        self.normalized_data = normalized_data

    @property
    def file_path(self) -> Path:
        return EXPORT_DIR.joinpath("companies.csv")

    def exec(self) -> None:
        data_frame = pandas.DataFrame(
            self.normalized_data, columns=self.columns_order
        )
        data_frame.to_csv(self.file_path, index=False, encoding="utf-8")
