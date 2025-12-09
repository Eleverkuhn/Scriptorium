import re
from pathlib import Path
from typing import override

from playwright.sync_api import sync_playwright, Page, Playwright

from config import CACHE_FILE, DOWNLOAD_DIR, ITERATIONS
from utils import Base, ReaderJSON, LoggingConfig


class Scriptorium:
    def exec(self) -> None:
        pass


class Scraper(Base):
    base_url = "https://www.list-org.com"
    pages_to_inspect = ITERATIONS  # Мы делаем 4 реквеста из 10 возможных для сбора данных
    download_button = "a.btn.btn-outline-secondary.m-1"

    def __init__(self) -> None:
        self.company_ids = []
        self.link_constructor = LinkConstructor()
        self.cache = Cache()

    @property
    def inspection_range(self) -> range:
        return range(1, self.pages_to_inspect + 1)

    def exec(self) -> None:
        """
        Главный метод. Запускает механизм поиска ID организаций с сайта
        list-org.com и сохраняет их в файле cache.json
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

    def setup_browser(self, pw: Playwright) -> Page:
        self.log("Setting up playwright")
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        return page

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


class LinkConstructor:
    base_url = "https://www.list-org.com"
    okved = 62  # Сюда включены все подкоды 'Разработка компьютерного программного обеспечения, консультационные услуги в данной области и другие сопутствующие услуги (62)'
    cache_slice = ITERATIONS * 100

    def __init__(self) -> None:
        self.cache = Cache()

    @property
    def download_link_prefix(self) -> str:
        return "".join([self.base_url, "/excel_list.php?ids="])

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
        LoggingConfig.get_logger().debug(f"company_ids: {company_ids}")
        for id in company_ids.split(","):
            LoggingConfig.get_logger().debug(f"id: {id}")
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
