"""Narration rate parsing/formatting used by fit-to-video sync."""

from voiceover import _parse_rate, _format_rate


def test_parse_rate():
    assert _parse_rate("+10%") == 10
    assert _parse_rate("-20%") == -20
    assert _parse_rate("0%") == 0
    assert _parse_rate(None) == 0
    assert _parse_rate("garbage") == 0


def test_format_rate():
    assert _format_rate(35) == "+35%"
    assert _format_rate(0) == "+0%"
    assert _format_rate(-15) == "-15%"


def test_roundtrip():
    for pct in (-40, -1, 0, 10, 80):
        assert _parse_rate(_format_rate(pct)) == pct
