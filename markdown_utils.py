"""Telegram Markdown safety utilities — prevents unescaped token crashes."""

import logging
import re

logger = logging.getLogger(__name__)

# Characters that need escaping in MarkdownV2
_MARKDOWN_SPECIAL = r"*_`[]()~>#+=|{}.!-\\"

# Strips all Markdown formatting for plain-text fallback
_MD_STRIP_RE = re.compile(
    r"[*_~`]|"
    r"\[([^\]]+)\]\([^)]+\)|"  # [text](url) -> text
    r"\[([^\]]+)\]\([^)]+\)"   # duplicate safety
)


def strip_markdown(text: str) -> str:
    """Remove all Markdown formatting, leaving clean plain text."""
    # Replace links with just their text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove inline code backticks
    text = text.replace("`", "")
    # Remove bold/italic/strikethrough markers
    text = re.sub(r"[*_~]", "", text)
    return text.strip()


def safe_markdown(text: str) -> str:
    """Attempt to make text safe for Markdown parse mode.
    Escapes special characters outside of code blocks."""
    # Don't touch code blocks
    parts = re.split(r"(```[\s\S]*?```|`[^`]+`)", text)
    result = []
    for i, part in enumerate(parts):
        if part.startswith("```") or (part.startswith("`") and part.endswith("`")):
            result.append(part)
        else:
            # Escape special chars that aren't part of formatting
            escaped = ""
            j = 0
            while j < len(part):
                ch = part[j]
                if ch in "*_~" and j + 1 < len(part) and part[j + 1] == ch:
                    # Likely intentional formatting, keep it
                    escaped += ch
                elif ch in ("*", "_", "~", "`", "[", "]", "(", ")", ">", "#", "+", "=", "|", "{", "}", ".", "!", "-", "\\"):
                    escaped += "\\" + ch
                else:
                    escaped += ch
                j += 1
            result.append(escaped)
    return "".join(result)
