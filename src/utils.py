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
        config = ReaderJSON.load(LOGGING_CONFIG)
        logging.config.dictConfig(config)


class ReaderJSON:
    @staticmethod
    def load(file_path: Path) -> dict:
        with open(file_path) as file:
            content = json.load(file)
        return content


class OnlyInfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO
