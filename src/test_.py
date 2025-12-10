import os
from pathlib import Path

import pytest

from config import BASE_DIR, TEST_DATA, CACHE_FILE, ITERATIONS, DOWNLOAD_DIR
from app import Scraper, LinkConstructor, Cache, CompanyDataDownloader
from utils import ReaderJSON


@pytest.fixture
def constructor() -> LinkConstructor:
    return LinkConstructor()


@pytest.fixture
def download_links() -> dict[str, list[str]]:
    test_data = ReaderJSON(TEST_DATA).load()
    return test_data["download_links"]


@pytest.fixture
def company_ids(constructor: LinkConstructor, download_links: list[str]) -> list[str]:
    return [constructor.get_company_ids(elem) for elem in download_links]


@pytest.fixture
def mock_cache_file() -> Path:
    mock_cache_file = BASE_DIR.joinpath("mock_cache.json")
    yield mock_cache_file
    os.remove(mock_cache_file)


@pytest.fixture
def cache_reader(mock_cache_file: Path) -> ReaderJSON:
    return ReaderJSON(mock_cache_file)


@pytest.fixture
def cache(mock_cache_file: Path, cache_reader: ReaderJSON) -> Path:
    cache_file_structure = {
        "referers": [],
        "company_ids": []
    }
    cache_reader.dump(cache_file_structure)
    return mock_cache_file


@pytest.fixture
def mock_company_ids() -> list[str]:
    return [str(x) for x in range(100)]


@pytest.fixture
def cache_with_ids(cache: Path, cache_reader: ReaderJSON, mock_company_ids: list[str]):
    content = cache_reader.load()
    content["company_ids"].extend(mock_company_ids)
    cache_reader.dump(content)


@pytest.fixture
def cache_with_multiple_ids(
        cache: Path, cache_reader: ReaderJSON, mock_company_ids: list[str]
) -> None:
    content = cache_reader.load()
    for _ in range(ITERATIONS):
        content["company_ids"].extend(mock_company_ids)
    cache_reader.dump(content)


@pytest.fixture(scope="class")
def scraper_result() -> Scraper:
    scraper = Scraper()
    scraper.exec()
    return scraper


@pytest.fixture
def user_cookie(scraper_result: Scraper) -> str:
    return scraper_result.user_cookie


@pytest.fixture
def real_download_links(constructor: LinkConstructor) -> list[str]:
    return constructor.get_download_links()
    # real_company_id = Cache(CACHE_FILE).first_company_id
    # return "".join([constructor.download_link_prefix, real_company_id])


@pytest.mark.skip(reason="Execution time")
@pytest.mark.usefixtures("scraper_result")
class TestScraper:
    def test_cache_is_set(self) -> None:
        cache = ReaderJSON(CACHE_FILE).load()
        assert len(cache["referers"]) == 4
        assert len(cache["company_ids"]) == 200

    def test_user_cookie_is_set(self, scraper_result: Scraper) -> None:
        assert scraper_result.user_cookie


class TestCompanyDataDownloader:
    def test_amount_of_downloaded_files(
            self, user_cookie: str, real_download_links: list[str]
    ) -> None:
        CompanyDataDownloader(user_cookie, real_download_links).exec()
        downloaded_files = [
            file for file
            in DOWNLOAD_DIR.iterdir()
            if file.is_file()
        ]
        assert len(downloaded_files) == 2


class TestLinkConstructor:
    @pytest.fixture(autouse=True)
    def setUp(self, constructor: LinkConstructor, download_links: list[str]) -> None:
        self.constructor = constructor
        self.download_links = download_links

    def test_get_company_ids_regex_pattern_re(self) -> None:
        download_link = self.download_links[0]
        result = self.constructor.get_company_ids(download_link)
        assert len(result.split(",")) == 50

    @pytest.mark.usefixtures("cache_with_multiple_ids")
    def test_get_download_links(self, cache_reader: ReaderJSON) -> None:
        self.constructor.cache = cache_reader
        download_links = self.constructor.get_download_links()
        assert len(download_links) == 2

    @pytest.mark.usefixtures("cache_with_ids")
    def test_construct_download_link(
            self, cache_reader: ReaderJSON, mock_company_ids: list[str]
    ) -> None:
        self.constructor.cache = cache_reader
        ids_string = ",".join(mock_company_ids)
        prefix = self.constructor.download_link_prefix

        link = self.constructor.construct_download_link(mock_company_ids)

        expected_result = "".join([prefix, ids_string])
        assert link == expected_result


class TestCache:
    @pytest.fixture(autouse=True)
    def setUp(self, cache) -> None:
        self.cache_file = cache
        self.cache = Cache(cache)

    def test_saves_url_to_cache_file(self) -> None:
        mock_url = "https://mockurl?mock_param=fake"
        self.cache.save_url(mock_url)
        content = self.cache.load()
        assert mock_url in content["referers"]

    def test_save_company_ids_saves_in_a_proper_format(
            self, mock_company_ids: list[str]
    ) -> None:
        for id in mock_company_ids:
            self.cache.save_company_ids(id)
        content = self.cache.load()

        for elem in content["company_ids"]:
            assert elem in mock_company_ids
