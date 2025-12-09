import os
from pathlib import Path

import pytest

from config import BASE_DIR, TEST_DATA
from app import Scraper, Cache
from utils import ReaderJSON


@pytest.fixture
def scraper() -> Scraper:
    return Scraper()


@pytest.fixture
def download_links() -> dict[str, list[str]]:
    test_data = ReaderJSON(TEST_DATA).load()
    return test_data["download_links"]


@pytest.fixture
def company_ids_from_download_links(
        scraper: Scraper, download_links: list[str]
) -> list[str]:
    return [scraper.get_company_ids(elem) for elem in download_links]


@pytest.fixture
def mock_cache_file() -> Path:
    mock_cache_file = BASE_DIR.joinpath("mock_cache.json")
    cache_file_structure = {
        "referers": [],
        "company_ids": []
    }
    ReaderJSON(mock_cache_file).dump(cache_file_structure)
    yield mock_cache_file
    os.remove(mock_cache_file)


class TestScraper:
    @pytest.fixture(autouse=True)
    def setUp(self, scraper: Scraper, download_links: list[str]) -> None:
        self.scraper = scraper
        self.download_links = download_links

    @pytest.mark.skip(reason="Execution time")
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


class TestCache:
    @pytest.fixture(autouse=True)
    def setUp(self, mock_cache_file: Path) -> None:
        self.mock_cache_file = mock_cache_file
        self.cache = Cache(mock_cache_file)

    def test_saves_url_to_cache_file(self) -> None:
        mock_url = "https://mockurl?mock_param=fake"
        self.cache.save_url(mock_url)
        content = self.cache.load()
        assert mock_url in content["referers"]

    def test_save_company_ids_saves_in_a_proper_format(self) -> None:
        mock_ids = "213424,324242,23424,1111,123213"
        self.cache.save_company_ids(mock_ids)
        content = self.cache.load()

        for elem in content["company_ids"]:
            assert elem in mock_ids
