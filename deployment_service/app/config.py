# File with environment variables and general configuration logic.
# Env variables are combined in nested groups like "Security" etc.
# So environment variable (case-insensitive) for "webhook_secret" will be "security__webhook_secret"
#
# Pydantic priority ordering:
#
# 1. (Most important, will overwrite everything) - environment variables
# 2. `.env` file in root folder of project
# 3. Default values
#
#
# See https://pydantic-docs.helpmanual.io/usage/settings/
# Note, complex types like lists are read as json-encoded strings.

import logging.config
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, FilePath, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_DIR = Path(__file__).parent.parent.parent


class Security(BaseModel):
    """Settings related to security and authentication."""

    webhook_secret: SecretStr
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "nginx"]


class Docker(BaseModel):
    """Settings related to Docker and Docker Compose."""

    compose_file_path: FilePath
    compose_env_file: FilePath | None = None


class Settings(BaseSettings):
    security: Security
    docker: Docker
    debug: bool = False
    log_level: str = "INFO"
    health_check_timeout: int = 90

    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=f"{PROJECT_DIR}/.env",
        case_sensitive=False,
        env_nested_delimiter="__",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore


def logging_config(log_level: str) -> None:
    conf = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "verbose": {
                "format": "{asctime} [{levelname}] {name}: {message}",
                "style": "{",
            },
        },
        "handlers": {
            "stream": {
                "class": "logging.StreamHandler",
                "formatter": "verbose",
                "level": "DEBUG",
            },
        },
        "loggers": {
            "": {
                "level": log_level,
                "handlers": ["stream"],
                "propagate": True,
            },
        },
    }
    logging.config.dictConfig(conf)


logging_config(log_level=get_settings().log_level)
