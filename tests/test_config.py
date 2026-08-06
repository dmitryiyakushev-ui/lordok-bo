"""Настройки не должны падать из-за переменных для docker-compose."""

import os

from bot.config import Settings


def test_extra_env_vars_are_ignored(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASSWORD", "infra-only")
    monkeypatch.setenv("REDIS_PASSWORD", "infra-only")
    settings = Settings(_env_file=None)
    assert settings.bot_token
