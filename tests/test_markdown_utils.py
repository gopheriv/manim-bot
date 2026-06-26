"""Tests for markdown_utils — MarkdownV2 safety."""

import sys
from pathlib import Path

# Add parent dir to path so imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from markdown_utils import strip_markdown, safe_markdown


def test_strip_markdown_removes_bold():
    assert strip_markdown("**hello**") == "hello"


def test_strip_markdown_removes_italic():
    assert strip_markdown("_hello_") == "hello"
    assert strip_markdown("*hello*") == "hello"


def test_strip_markdown_removes_code_fences():
    assert strip_markdown("`code`") == "code"


def test_strip_markdown_removes_links():
    assert strip_markdown("[text](https://example.com)") == "text"


def test_strip_markdown_strikethrough():
    assert strip_markdown("~~deleted~~") == "deleted"


def test_strip_markdown_complex():
    text = "**Hello** _world_ `code` [link](url) ~~strike~~"
    result = strip_markdown(text)
    assert "Hello" in result
    assert "world" in result
    assert "code" in result
    assert "link" in result
    assert "strike" in result
    assert "**" not in result
    assert "`" not in result


def test_safe_markdown_escapes_special_chars():
    text = "Hello * world _ test"
    result = safe_markdown(text)
    # Special chars outside formatting should be escaped
    assert r"\*" in result or r"\_" in result


def test_safe_markdown_preserves_code_blocks():
    text = "```\nprint('hello')\n```"
    result = safe_markdown(text)
    # Code blocks should not be modified
    assert "print('hello')" in result


def test_safe_markdown_preserves_inline_code():
    text = "Use `print()` function"
    result = safe_markdown(text)
    assert "`print()`" in result


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
