import json, logging, logging.config
from pathlib import Path

from config import LOGGING_CONFIG


class Base:
    def log(self, message: str, level: str = "INFO") -> None:
        logger = LoggingConfig.get_logger()
        level = getattr(logging, level)
        logger.log(level, message)


class LoggingConfig:
    @classmethod
    def get_logger(cls) -> logging.Logger:
        cls.load_config()
        return logging.getLogger("scriptorium")

    @staticmethod
    def load_config() -> None:
        config = ReaderJSON(LOGGING_CONFIG).load()
        logging.config.dictConfig(config)


class ReaderJSON:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def load(self) -> dict:
        with open(self.file_path) as file:
            content = json.load(file)
        return content

    def dump(self, data: dict) -> None:
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)


class OnlyInfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO
