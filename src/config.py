from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CACHE_FILE = BASE_DIR.joinpath("cache.json")
DOWNLOAD_DIR = BASE_DIR.joinpath("data")

TEST_DATA = BASE_DIR.joinpath("test_data.json")
