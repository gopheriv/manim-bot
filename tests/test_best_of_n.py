"""Best-of-N tournament — orchestrator tested with mocked I/O seams."""

import asyncio
from pathlib import Path

import pytest

import best_of_n


def run(coro):
    return asyncio.run(coro)


# ── _is_valid_code ───────────────────────────────────────────────────────────

def test_is_valid_code_accepts_good():
    code = "from manim import *\nclass GenScene(Scene):\n    def construct(self):\n        pass\n"
    assert best_of_n._is_valid_code(code)


def test_is_valid_code_rejects_no_class():
    assert not best_of_n._is_valid_code("def construct(self): pass")


def test_is_valid_code_rejects_no_construct():
    assert not best_of_n._is_valid_code("class GenScene(Scene): pass")


def test_is_valid_code_rejects_non_string():
    assert not best_of_n._is_valid_code(None)
    assert not best_of_n._is_valid_code(42)
    assert not best_of_n._is_valid_code(Exception("oops"))


# ── select_best_code — full tournament ───────────────────────────────────────

def _good_code(idx):
    return f"from manim import *\nclass GenScene(Scene):\n    def construct(self):\n        # candidate {idx}\n"


def test_tournament_picks_highest_score(monkeypatch):
    """Three candidates render, vision picks the one with the highest score."""
    codes = [_good_code(i) for i in range(3)]
    scores = [5.0, 8.5, 6.0]  # candidate 1 wins

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        return codes.pop(0) if codes else ""

    async def fake_render(code, chat_id, idx, quality, fps):
        return Path(f"tmp/draft_{idx}.mp4")

    async def fake_score(video, prompt, code):
        name = video.name
        i = int(name.split("_")[1].split(".")[0])
        return scores[i]

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)
    monkeypatch.setattr(best_of_n, "_score", fake_score)

    result = run(best_of_n.select_best_code("test prompt", "theme", n=3, chat_id=1))
    # The winner should be candidate 1 (score 8.5)
    assert "# candidate 1" in result


def test_tournament_returns_none_when_all_gen_fail(monkeypatch):
    """If every candidate fails to generate, returns None."""

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)

    result = run(best_of_n.select_best_code("prompt", "theme", n=3, chat_id=1))
    assert result is None


def test_tournament_returns_unranked_when_all_renders_fail(monkeypatch):
    """If all drafts fail to render, returns the first valid candidate unranked."""
    codes = [_good_code(0), _good_code(1)]

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        return codes.pop(0) if codes else ""

    async def fake_render(code, chat_id, idx, quality, fps):
        return None  # cloud is down

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)

    result = run(best_of_n.select_best_code("prompt", "theme", n=2, chat_id=1))
    assert result is not None
    assert "# candidate 0" in result


def test_tournament_handles_partial_gen_failure(monkeypatch):
    """Some candidates fail to generate; remaining are still rendered and judged."""
    call_count = 0

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("gen failed for candidate 2")
        return _good_code(call_count)

    async def fake_render(code, chat_id, idx, quality, fps):
        return Path(f"tmp/draft_{idx}.mp4")

    async def fake_score(video, prompt, code):
        return 7.0

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)
    monkeypatch.setattr(best_of_n, "_score", fake_score)

    result = run(best_of_n.select_best_code("prompt", "theme", n=3, chat_id=1))
    assert result is not None
    assert "GenScene" in result


def test_tournament_handles_scoring_failure(monkeypatch):
    """If vision scoring fails for a candidate, it gets score=0 and doesn't crash."""
    codes = [_good_code(0), _good_code(1)]
    scores = [8.0, None]  # second score raises

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        return codes.pop(0) if codes else ""

    async def fake_render(code, chat_id, idx, quality, fps):
        return Path(f"tmp/draft_{idx}.mp4")

    async def fake_score(video, prompt, code):
        name = video.name
        i = int(name.split("_")[1].split(".")[0])
        if scores[i] is None:
            raise RuntimeError("vision API down")
        return scores[i]

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)
    monkeypatch.setattr(best_of_n, "_score", fake_score)

    result = run(best_of_n.select_best_code("prompt", "theme", n=2, chat_id=1))
    # Candidate 0 scored 8.0, candidate 1 got score=0 → 0 wins
    assert "# candidate 0" in result


def test_n_clamped_to_minimum_2(monkeypatch):
    """n=1 is clamped to 2 (a tournament needs at least 2 candidates)."""
    gen_calls = 0

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        nonlocal gen_calls
        gen_calls += 1
        return _good_code(gen_calls)

    async def fake_render(code, chat_id, idx, quality, fps):
        return Path(f"tmp/draft_{idx}.mp4")

    async def fake_score(video, prompt, code):
        return 5.0

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)
    monkeypatch.setattr(best_of_n, "_score", fake_score)

    result = run(best_of_n.select_best_code("prompt", "theme", n=1, chat_id=1))
    assert result is not None
    assert gen_calls == 2  # clamped from 1 to 2


def test_gen_candidate_forwards_metaphors(monkeypatch):
    """_gen_candidate routes the menu to the director and the recipes to code-gen."""
    captured = {}

    async def fake_storyboard(prompt, metaphor_menu="", **kw):
        captured["menu"] = metaphor_menu
        return "{}"

    async def fake_codegen(prompt, theme_instructions="", storyboard="", metaphor_recipes="", **kw):
        captured["recipes"] = metaphor_recipes
        return _good_code(0)

    monkeypatch.setattr(best_of_n, "generate_storyboard", fake_storyboard)
    monkeypatch.setattr(best_of_n, "generate_manim_code", fake_codegen)
    monkeypatch.setattr(best_of_n, "parse_storyboard", lambda raw: {"beats": [{}]})
    monkeypatch.setattr(best_of_n, "format_storyboard_for_codegen", lambda sb: "SB")
    monkeypatch.setattr(best_of_n, "strip_code_fences", lambda c: c)

    code = run(best_of_n._gen_candidate("p", "theme", metaphor_menu="MENU", metaphor_recipes="RECIPES"))
    assert captured["menu"] == "MENU"
    assert captured["recipes"] == "RECIPES"
    assert "GenScene" in code


def test_select_best_code_forwards_metaphors_to_every_candidate(monkeypatch):
    """The tournament shares one menu/recipe set across all N candidates."""
    seen = []

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        seen.append((metaphor_menu, metaphor_recipes))
        return _good_code(len(seen))

    async def fake_render(code, chat_id, idx, quality, fps):
        return Path(f"tmp/draft_{idx}.mp4")

    async def fake_score(video, prompt, code):
        return 5.0

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)
    monkeypatch.setattr(best_of_n, "_score", fake_score)

    run(best_of_n.select_best_code("p", "theme", n=3, chat_id=1, metaphor_menu="M", metaphor_recipes="R"))
    assert len(seen) == 3
    assert all(mm == "M" and mr == "R" for mm, mr in seen)


def test_invalid_code_filtered_from_candidates(monkeypatch):
    """Candidates that don't have GenScene/construct are filtered out before rendering."""
    responses = [_good_code(0), "print('hello')", _good_code(2)]

    async def fake_gen(prompt, theme, metaphor_menu="", metaphor_recipes=""):
        return responses.pop(0) if responses else ""

    render_calls = []

    async def fake_render(code, chat_id, idx, quality, fps):
        render_calls.append(code)
        return Path(f"tmp/draft_{idx}.mp4")

    async def fake_score(video, prompt, code):
        return 7.0

    monkeypatch.setattr(best_of_n, "_gen_candidate", fake_gen)
    monkeypatch.setattr(best_of_n, "_render_draft", fake_render)
    monkeypatch.setattr(best_of_n, "_score", fake_score)

    result = run(best_of_n.select_best_code("prompt", "theme", n=3, chat_id=1))
    assert result is not None
    # The invalid candidate should NOT have been rendered
    assert len(render_calls) == 2
    assert all("GenScene" in c for c in render_calls)
