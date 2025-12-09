import re
from pathlib import Path
from typing import override

from playwright.sync_api import sync_playwright, Page, Playwright

from config import CACHE_FILE, DOWNLOAD_DIR
from utils import Base, ReaderJSON


class Scriptorium:
    def exec(self) -> None:
        pass


class Scraper(Base):
    pages_to_inspect = 4
    download_button = "a.btn.btn-outline-secondary.m-1"

    def __init__(self) -> None:
        self.company_ids = []
        self.link_constructor = LinkConstructor()
        self.cache = Cache()

    @property
    def inspection_range(self) -> range:
        return range(1, self.pages_to_inspect + 1)

    def exec(self) -> list[str]:
        self.find_company_ids()
        self.log("Company IDS collected")

        self.log("Creating bulk download links")
        download_links = self.link_constructor.get_download_links(self.company_ids)

        return download_links

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
        self.log(f"Found download link: {download_link}")
        return download_link


class LinkConstructor:
    base_url = "https://www.list-org.com"
    download_link_prefix = "excel_list.php?ids="
    okved = 62  # Сюда включены все подкоды 'Разработка компьютерного программного обеспечения, консультационные услуги в данной области и другие сопутствующие услуги (62)'

    def __init__(self) -> None:
        self.cache = Cache()

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
        for id in company_ids.strip():
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

    def get_download_links(self, company_ids: list[str]) -> list[str]:
        """
        list-org позволяет передавать в ?ids= не более 100 значений, поэтому
        я создаю комплексную ссылку, совмещая два значения из уже сохранённых
        ids с помощью 'get_company_ids'. Это позволяет в два раза уменьшить
        количество запросов к их серверу
        """
        download_links = []
        company_ids_copy = company_ids.copy()

        while company_ids_copy:
            elem = company_ids_copy.pop(0)
            if company_ids_copy:
                next_elem = company_ids_copy.pop(0)
                compound_company_ids = ",".join([elem, next_elem])
                download_link = self.construct_download_link(compound_company_ids)
                download_links.append(download_link)
            else:
                download_links.append(self.construct_download_link(elem))
        return download_links

    def construct_download_link(self, company_ids: str) -> str:
        return "".join([self.download_link_prefix, company_ids])


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
