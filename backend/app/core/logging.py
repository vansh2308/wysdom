import logging
import logging.config
from typing import Any

from app.core.config import Settings, get_settings


LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        }
    },
    "loggers": {
        "wysdom": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}


def configure_logging(settings: Settings | None = None) -> None:
    resolved_settings = settings or get_settings()
    LOGGING_CONFIG["loggers"]["wysdom"]["level"] = resolved_settings.log_level.upper()
    LOGGING_CONFIG["loggers"]["uvicorn"]["level"] = resolved_settings.log_level.upper()
    LOGGING_CONFIG["root"]["level"] = resolved_settings.log_level.upper()
    logging.config.dictConfig(LOGGING_CONFIG)


def get_logger(name: str = "wysdom") -> logging.Logger:
    return logging.getLogger(name)
