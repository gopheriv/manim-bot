"""Owner-gate for privileged commands (/restart): config parsing + _is_admin."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


def test_id_set_parses_comma_and_semicolon(monkeypatch):
    monkeypatch.setenv("ADMIN_CHAT_IDS", "111, 222 ;333")
    monkeypatch.delenv("WATCHDOG_NOTIFY_CHAT", raising=False)
    assert config._get_id_set("ADMIN_CHAT_IDS") == frozenset({111, 222, 333})


def test_id_set_ignores_junk_and_empty(monkeypatch):
    monkeypatch.setenv("ADMIN_CHAT_IDS", "abc, , 42, x9")
    assert config._get_id_set("ADMIN_CHAT_IDS") == frozenset({42})


def test_id_set_merges_multiple_keys(monkeypatch):
    monkeypatch.setenv("ADMIN_CHAT_IDS", "1")
    monkeypatch.setenv("WATCHDOG_NOTIFY_CHAT", "2")
    assert config._get_id_set("ADMIN_CHAT_IDS", "WATCHDOG_NOTIFY_CHAT") == frozenset({1, 2})


def test_id_set_empty_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_CHAT_IDS", raising=False)
    monkeypatch.delenv("WATCHDOG_NOTIFY_CHAT", raising=False)
    assert config._get_id_set("ADMIN_CHAT_IDS", "WATCHDOG_NOTIFY_CHAT") == frozenset()


def test_is_admin_gate():
    if "manim" not in sys.modules:
        import importlib.util
        if importlib.util.find_spec("aiogram") is None:
            pytest.skip("aiogram not importable")
    import bot
    # _is_admin reflects the configured set; check the logic against a known set.
    bot_admins = bot.ADMIN_CHAT_IDS
    assert bot._is_admin(None) is False
    if bot_admins:
        member = next(iter(bot_admins))
        assert bot._is_admin(member) is True
    assert bot._is_admin(-99999) is False  # an id that won't be configured
