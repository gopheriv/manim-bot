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

THREE_BLUE_ONE_BROWN = Theme(
    name="3Blue1Brown",
    bg_color="#000000",
    palette_desc=(
        "Use a 3Blue1Brown-style palette on a pure black background (#000000): a restrained "
        "range of blues — deep blue (#1C758A) for primary objects and bright blue (#29ABCA) "
        "for objects undergoing a transformation — with a single warm accent, yellow "
        "(#FFFF00), for the current focus, green (#83C167) for results and conclusions, and "
        "red (#FC6255) reserved for contrast or warnings. Text and structure in near-white "
        "(#ECECEC). The feel is calm, precise, and concept-driven."
    ),
    extra_instructions=(
        "Computer-Modern / serif feel: use Tex/MathTex for ALL mathematics (LaTeX's Computer "
        "Modern font is what gives this look its character). Thin near-white axes and guide "
        "lines (stroke_width=2). Keep to restrained blues with a single warm accent; pure "
        "black background. Use color semantically — a symbol keeps its color across every "
        "equation, graph, vector, and label. Evoke the high-end mathematical-explainer style "
        "without copying any specific creator's logo, assets, watermark, or exact scenes."
    ),
    colors=["#1C758A", "#FFFF00", "#29ABCA", "#FC6255", "#ECECEC"],
)

BLUEPRINT = Theme(
    name="Blueprint",
    bg_color="#1A2744",
    palette_desc=(
        "Use a blueprint-style palette on a deep navy background (#1A2744): cyan-blue "
        "(#64B5F6) for primary objects and grid lines, bright white (#FFFFFF) for text and "
        "labels, warm amber (#FFB74D) for the active insight, soft steel blue (#4FC3F7) for "
        "transformations, and muted red (#EF5350) for contrast or warnings. The feel is "
        "technical, precise, and engineering-like — like reading a well-drawn blueprint."
    ),
    extra_instructions=(
        "Use thin, precise lines (stroke_width=2) with a technical-drawing feel. "
        "Add faint guide lines or grid hints where helpful (opacity 0.3). "
        "Keep spacing clean and avoid overlapping objects — everything should feel "
        "measured and intentional, like an engineering schematic."
    ),
    colors=["#64B5F6", "#FFB74D", "#4FC3F7", "#EF5350", "#FFFFFF"],
)

COLORSAFE = Theme(
    name="ColorSafe",
    bg_color="#101418",
    palette_desc=(
        "Use a color-blind-safe palette (Okabe-Ito) on a near-black background (#101418): "
        "sky-blue (#56B4E9) for primary objects, orange (#E69F00) for the active insight, "
        "bluish-green (#009E73) for transformations, and vermillion (#D55E00) for contrast "
        "or warnings. Text in bright white (#FFFFFF). These colors remain distinguishable "
        "under red-green color blindness (deuteranopia), making the animation accessible to "
        "the ~8% of men who cannot distinguish red from green. NEVER use red+green together "
        "to carry meaning."
    ),
    extra_instructions=(
        "Use color semantically and consistently. Avoid red/green pairs for contrasting "
        "objects — use the sky-blue, orange, bluish-green, and vermillion from the palette "
        "instead. These are proven distinguishable under deuteranopia simulation."
    ),
    colors=["#56B4E9", "#E69F00", "#009E73", "#D55E00", "#FFFFFF"],
)


# ── Theme Registry ───────────────────────────────────────────────────────────

ALL_THEMES: dict[str, Theme] = {
    "visual_math": VISUAL_MATH,
    "threeblue1brown": THREE_BLUE_ONE_BROWN,
    "default": DEFAULT,
    "nord": NORD,
    "cyberpunk": CYBERPUNK,
    "chalkboard": CHALKBOARD,
    "blueprint": BLUEPRINT,
    "colorsafe": COLORSAFE,
}

THEME_ORDER = [
    "visual_math", "threeblue1brown", "default", "nord",
    "cyberpunk", "chalkboard", "blueprint", "colorsafe",
]


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


# ── WCAG Contrast Ratio ──────────────────────────────────────────────────────

def _srgb_to_linear(hex_color: str) -> tuple[float, float, float]:
    """Convert a '#rrggbb' hex color to linearized sRGB components (0.0–1.0)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return r, g, b


def _linearize(c: float) -> float:
    """Linearize a single sRGB channel per WCAG 2.x spec."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """Compute WCAG relative luminance from a '#rrggbb' hex color."""
    r, g, b = _srgb_to_linear(hex_color)
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(hex1: str, hex2: str) -> float:
    """Compute the WCAG contrast ratio between two '#rrggbb' colors.

    Returns a value >= 1.0 (higher = more readable).
    Formula: (L_lighter + 0.05) / (L_darker + 0.05)
    """
    l1 = _relative_luminance(hex1)
    l2 = _relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ── Color-Blindness Simulation ───────────────────────────────────────────────

def _hex_to_rgb255(hex_color: str) -> tuple[int, int, int]:
    """Convert '#rrggbb' to (R, G, B) in 0..255."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _rgb255_to_hex(r: int, g: int, b: int) -> str:
    """Convert (R, G, B) in 0..255 to '#rrggbb'."""
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def simulate_deuteranopia(hex_color: str) -> str:
    """Simulate red-green color blindness (deuteranopia) for a '#rrggbb' color.

    Uses the standard Brettel / Viénot-inspired sRGB matrix:
        R' = 0.625*R + 0.375*G + 0.000*B
        G' = 0.700*R + 0.300*G + 0.000*B
        B' = 0.000*R + 0.300*G + 0.700*B
    Values are rounded and clamped to 0..255.
    """
    r, g, b = _hex_to_rgb255(hex_color)
    r2 = round(0.625 * r + 0.375 * g + 0.000 * b)
    g2 = round(0.700 * r + 0.300 * g + 0.000 * b)
    b2 = round(0.000 * r + 0.300 * g + 0.700 * b)
    return _rgb255_to_hex(r2, g2, b2)


def color_distance(hex1: str, hex2: str) -> float:
    """Euclidean distance between two '#rrggbb' colors in RGB (0..255) space.

    Returns sqrt(dR² + dG² + dB²). Max possible is ~441.67 (black to white).
    """
    r1, g1, b1 = _hex_to_rgb255(hex1)
    r2, g2, b2 = _hex_to_rgb255(hex2)
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5
