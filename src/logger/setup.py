import json, logging, logging.config
from logging import Logger

from config import LOGGING_CONFIG


class OnlyInfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO


def load_config() -> None:
    with open(LOGGING_CONFIG) as config_file:
        config = json.load(config_file)
    logging.config.dictConfig(config)


def get_logger() -> Logger:
    load_config()
    return logging.getLogger("scriptorium")
