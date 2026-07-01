"""Visual baseline tests — correctness of the perceptual-hash functions.

These tests create tiny PIL images and verify the ahash/hamming/is_degenerate
functions behave correctly. NO manim rendering in these tests.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image

from scripts.visual_baseline import ahash, hamming, is_degenerate


# ── ahash correctness ─────────────────────────────────────────────────────────

def test_ahash_solid_black_is_degenerate():
    """A solid-black 8×8 image should produce a degenerate hash.
    
    Note: With the >= comparison in ahash, both solid black and solid white
    produce all-1 bits (0xfff...) because every pixel >= the mean (which equals
    that same pixel value). This is correct — both are degenerate.
    """
    img = Image.new("L", (8, 8), 0)
    img.save("tmp_black.png")
    h = ahash("tmp_black.png")
    assert is_degenerate(h), f"Black image hash should be degenerate, got {h}"


def test_ahash_solid_white_is_degenerate():
    """A solid-white 8×8 image should produce an all-1 hash (degenerate)."""
    img = Image.new("L", (8, 8), 255)
    img.save("tmp_white.png")
    h = ahash("tmp_white.png")
    assert h == "f" * 16, f"White image hash should be all-1 (0xff...), got {h}"
    assert is_degenerate(h)


def test_ahash_deterministic():
    """Same image should produce the same hash every time."""
    img = Image.new("RGB", (8, 8), (100, 150, 200))
    img.save("tmp_test.png")
    h1 = ahash("tmp_test.png")
    h2 = ahash("tmp_test.png")
    assert h1 == h2


def test_ahash_not_degenerate_for_mixed():
    """A mixed image (half black, half white) should NOT be degenerate."""
    img = Image.new("L", (8, 8))
    for y in range(8):
        for x in range(8):
            img.putpixel((x, y), 0 if x < 4 else 255)
    img.save("tmp_mixed.png")
    h = ahash("tmp_mixed.png")
    assert not is_degenerate(h), f"Mixed image hash should not be degenerate: {h}"


# ── hamming distance correctness ──────────────────────────────────────────────

def test_hamming_identical_is_zero():
    """Two identical hashes should have hamming distance 0."""
    assert hamming("1234abcd5678ef01", "1234abcd5678ef01") == 0


def test_hamming_opposite_is_64():
    """All-0 vs all-1 should differ in all 64 bits."""
    assert hamming("0" * 16, "f" * 16) == 64


def test_hamming_symmetric():
    """hamming(a, b) == hamming(b, a)."""
    a = "1234abcd5678ef01"
    b = "fedcba9876543210"
    assert hamming(a, b) == hamming(b, a)


def test_hamming_single_bit():
    """Two hashes differing in exactly 1 bit should have distance 1."""
    h1 = "0" * 16
    h2 = "0" * 15 + "1"  # last bit flipped
    assert hamming(h1, h2) == 1


# ── is_degenerate correctness ─────────────────────────────────────────────────

def test_is_degenerate_all_zeros():
    assert is_degenerate("0" * 16) is True


def test_is_degenerate_all_ones():
    assert is_degenerate("f" * 16) is True


def test_is_degenerate_mixed():
    assert is_degenerate("1234abcd5678ef01") is False


def test_is_degenerate_almost_all_zeros():
    """63 zeros and 1 one is NOT degenerate."""
    assert is_degenerate("0" * 15 + "1") is False


# ── Cleanup temp files ────────────────────────────────────────────────────────

def test_cleanup():
    """Remove temporary test images."""
    import os
    for f in ["tmp_black.png", "tmp_white.png", "tmp_test.png", "tmp_mixed.png"]:
        if os.path.exists(f):
            os.unlink(f)
