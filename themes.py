"""
Visual themes for Manim animations.

Each theme defines:
  - name: display name
  - bg_color: Manim background color (hex)
  - palette: color palette description for the LLM
  - extra_instructions: additional Manim-specific instructions
  - post_effects: optional post-render effects (e.g., shake for chalkboard)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Theme:
    name: str
    bg_color: str          # hex color for Manim config_background_color
    palette_desc: str      # natural language color palette description
    extra_instructions: str = ""
    post_effects: str = ""  # reserved for future ffmpeg filters
    # Structured palette (primary, accent/insight, transform, contrast, text).
    # Used to make deterministic templates follow the active theme.
    colors: list[str] = field(default_factory=list)


# ── Theme Definitions ────────────────────────────────────────────────────────

NORD = Theme(
    name="Nord",
    bg_color="#2E3440",
    palette_desc=(
        "Use a Nord color palette: background #2E3440 (dark slate), "
        "primary accents in pastel blues (#88C0D0, #81A1C1), "
        "soft greens (#A3BE8C), and warm whites (#ECEFF4) for text and lines. "
        "Keep the overall feel calm, minimal, and clean."
    ),
    extra_instructions=(
        "Prefer simple geometric shapes. Use thin lines (stroke_width=2). "
        "Text should use the Frost palette (#E5E9F0)."
    ),
    colors=["#88C0D0", "#EBCB8B", "#81A1C1", "#BF616A", "#ECEFF4"],
)

CYBERPUNK = Theme(
    name="Cyberpunk",
    bg_color="#000000",
    palette_desc=(
        "Use a Cyberpunk color palette: background pure black (#000000), "
        "neon pink (#FF007F) and neon cyan (#00FFFF) as primary accent colors, "
        "electric purple (#BF00FF) for secondary elements, "
        "bright yellow (#FFFF00) for highlights. "
        "Make everything look glowing and high-contrast."
    ),
    extra_instructions=(
        "Use thick glowing lines (stroke_width=4-6). "
        "Add a subtle glow effect by layering a blurred duplicate behind elements "
        "using .set_stroke(opacity=0.3, width=10) on a copy. "
        "Text should be bold and bright."
    ),
    colors=["#FF007F", "#00FFFF", "#BF00FF", "#FFFF00", "#FFFFFF"],
)

CHALKBOARD = Theme(
    name="Chalkboard",
    bg_color="#2D4A2D",
    palette_desc=(
        "Use a Chalkboard color palette: background dark green (#2D4A2D), "
        "all lines and text in chalk white (#F5F5DC) with slight opacity variation "
        "(opacity 0.8-1.0 to simulate chalk dust). "
        "Accent colors: dusty yellow (#D4C89A) and faded red (#C17C74)."
    ),
    extra_instructions=(
        "Make lines slightly rough-looking by using stroke_width=3 with "
        "set_stroke(opacity=0.9). Add small random dots near text to simulate "
        "chalk dust. Use a handwritten-style feel — avoid perfectly straight lines "
        "where possible."
    ),
    post_effects="shake",  # will apply ffmpeg shake filter
    colors=["#F5F5DC", "#D4C89A", "#C17C74", "#A3BE8C", "#F5F5DC"],
)

VISUAL_MATH = Theme(
    name="Visual Math",
    bg_color="#0B1026",
    palette_desc=(
        "Use a premium visual mathematics palette: deep navy background (#0B1026), "
        "mathematical blue (#58C4DD) for primary objects, warm yellow (#F5D547) "
        "for the active insight, teal (#2DD4BF) for transformations, coral (#FF6B6B) "
        "only for contrast or warnings, and soft white (#F8FAFC) for text. "
        "Keep the look refined, minimal, and concept-driven."
    ),
    extra_instructions=(
        "Use color semantically and consistently: each mathematical object keeps its "
        "color across equations, labels, vectors, and graphs. Prefer smooth geometric "
        "transforms, elegant spacing, thin guide lines, and clean final compositions. "
        "The style should evoke high-end mathematical explainers without copying any "
        "specific creator's branding, logo, assets, or exact scenes."
    ),
    colors=["#58C4DD", "#F5D547", "#2DD4BF", "#FF6B6B", "#F8FAFC"],
)

DEFAULT = Theme(
    name="Default",
    bg_color="#1C1C1C",
    palette_desc=(
        "Use Manim's default dark background (#1C1C1C) with standard colors: "
        "white for text, blue (#58C4DD) and yellow (#FFFF00) for accents, "
        "green (#83C167) and red (#FC6255) for highlights."
    ),
    colors=["#58C4DD", "#FFFF00", "#83C167", "#FC6255", "#FFFFFF"],
)


# ── Theme Registry ───────────────────────────────────────────────────────────

ALL_THEMES: dict[str, Theme] = {
    "visual_math": VISUAL_MATH,
    "default": DEFAULT,
    "nord": NORD,
    "cyberpunk": CYBERPUNK,
    "chalkboard": CHALKBOARD,
}

THEME_ORDER = ["visual_math", "default", "nord", "cyberpunk", "chalkboard"]


def get_theme(name: str) -> Theme:
    """Get a theme by name, case-insensitive. Falls back to default."""
    return ALL_THEMES.get(name.lower(), DEFAULT)


def next_theme(current: str) -> str:
    """Cycle to the next theme in order."""
    try:
        idx = THEME_ORDER.index(current.lower())
    except ValueError:
        idx = 0
    return THEME_ORDER[(idx + 1) % len(THEME_ORDER)]


def build_theme_prompt(theme: Theme) -> str:
    """Build the full themeing instruction block for the system prompt."""
    parts = [
        f"VISUAL THEME: {theme.name}",
        f"Background color MUST be set to {theme.bg_color}.",
        theme.palette_desc,
    ]
    if theme.post_effects:
        parts.append(f"Apply post-processing effects: {theme.post_effects}")
    if theme.extra_instructions:
        parts.append(theme.extra_instructions)
    return "\n".join(parts)
