import json

import pytest

from config import TEST_DATA
from app import Scraper


@pytest.fixture
def scraper() -> Scraper:
    return Scraper()


@pytest.fixture
def download_links() -> dict[str, list[str]]:
    with open(TEST_DATA) as file:
        test_data = json.load(file)
    return test_data["download_links"]


@pytest.fixture
def company_ids_from_download_links(
        scraper: Scraper, download_links: list[str]
) -> list[str]:
    return [scraper.get_company_ids(elem) for elem in download_links]


class TestScraper:
    @pytest.fixture(autouse=True)
    def setUp(self, scraper: Scraper, download_links: list[str]) -> None:
        self.scraper = scraper
        self.download_links = download_links

    def test_exec(self, company_ids_from_download_links: list[str]) -> None:
        bulk_download_links = self.scraper.exec()
        for company_id in company_ids_from_download_links:
            assert company_id in " ".join(bulk_download_links)

    def test_get_company_ids_regex_pattern_re(self) -> None:
        download_link = self.download_links[0]
        result = self.scraper.get_company_ids(download_link)
        assert len(result.split(",")) == 50

    def test_construct_bulk_download_link_for_odd_ids_amount(
            self, company_ids_from_download_links: list[str]
    ) -> None:
        self.scraper.company_ids = company_ids_from_download_links
        download_links = self.scraper.construct_bulk_download_links()
        assert len(download_links) == 2

    def test_construct_bulk_download_link_for_even_ids_amoint(
            self, company_ids_from_download_links: list[str]
    ) -> None:
        self.scraper.company_ids = company_ids_from_download_links
        additional_ids = self.scraper.get_company_ids(self.download_links[0])
        self.scraper.company_ids.append(additional_ids)

        download_links = self.scraper.construct_bulk_download_links()
        assert len(download_links) == 3
