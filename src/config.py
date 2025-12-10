from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

CACHE_FILE = BASE_DIR.joinpath("cache.json")
DOWNLOAD_DIR = BASE_DIR.joinpath("company_data")
LOGGING_CONFIG = BASE_DIR.joinpath("logger_config.json")
EXPORT_DIR = BASE_DIR.parent.joinpath("data")

ITERATIONS = 4

TEST_DATA = BASE_DIR.joinpath("test_data.json")
