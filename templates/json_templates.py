"""JSON-based template system — scalable way to add 50+ templates without new Python files.

Each template is a JSON spec with:
- name, category, keywords
- Manim code template with {placeholder} slots
- default_config with parameter values

Templates are loaded from templates/data/templates.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from templates.base import SceneTemplate, TemplateConfig

logger = logging.getLogger(__name__)

JSON_TEMPLATES_PATH = Path(__file__).parent / "data" / "templates.json"
JSON_TEMPLATES_PATH.parent.mkdir(parents=True, exist_ok=True)


class JsonSceneTemplate(SceneTemplate):
    """A template loaded from JSON spec."""

    def __init__(self, spec: dict):
        self._name = spec["name"]
        self._keywords = spec.get("keywords", [self._name.lower()])
        self._category = spec.get("category", "General")
        self._code_template = spec["code_template"]
        self._default_config = spec.get("default_config", {})
        self._description = spec.get("description", "")

    @property
    def name(self) -> str:
        return self._name

    @property
    def keywords(self) -> list[str]:
        return self._keywords

    @property
    def category(self) -> str:
        return self._category

    def default_config(self) -> TemplateConfig:
        cfg = self._default_config.copy()
        # Ensure required fields exist
        cfg.setdefault("title", self._name)
        cfg.setdefault("equation", "")
        cfg.setdefault("description", self._description)
        cfg.setdefault("duration", 15)
        cfg.setdefault("colors", ["#58C4DD", "#FFFFFF", "#FF8080"])
        return TemplateConfig(**{k: v for k, v in cfg.items() if k in TemplateConfig.__dataclass_fields__})

    # NOTE: match_score is intentionally NOT overridden — JSON templates use the
    # shared strength-based SceneTemplate.match_score so all templates score
    # consistently against the registry threshold. (The old override used loose
    # substring matching — "parts" matched "particle" — and a normalization that
    # scored an exact phrase like "cross product" at 0.47, below threshold.)

    def generate_code(self, config: TemplateConfig) -> str:
        """Generate Manim code from template + config."""
        code = self._code_template

        # Colors MUST become quoted Python string literals. Templates write them
        # as `color={color1}` (no quotes), and substituting a bare hex produced
        # `color=#58C4DD` — the `#` starts a comment and breaks the line (this is
        # why most JSON templates failed to compile). Strip any quotes already
        # around the placeholder, then substitute a single quoted value so both
        # `{color1}` and `"{color1}"` forms come out correct exactly once.
        colors = config.colors or []
        color_values = (
            colors[0] if len(colors) > 0 else "#58C4DD",
            colors[1] if len(colors) > 1 else "#FFFFFF",
            colors[2] if len(colors) > 2 else "#FF8080",
        )
        for ph, val in zip(("{color1}", "{color2}", "{color3}"), color_values):
            code = code.replace(f'"{ph}"', ph).replace(f"'{ph}'", ph)
            code = code.replace(ph, f'"{val}"')

        # Text/number placeholders sit inside existing quotes (or numeric context).
        replacements = {
            "{title}": config.title,
            "{equation}": config.equation,
            "{description}": config.description,
            "{duration}": str(config.duration),
        }
        if hasattr(config, "extra_params"):
            for key, val in config.extra_params.items():
                replacements[f"{{{key}}}"] = str(val)

        for placeholder, value in replacements.items():
            code = code.replace(placeholder, value)

        return code


def load_json_templates() -> list[JsonSceneTemplate]:
    """Load all JSON templates from disk."""
    if not JSON_TEMPLATES_PATH.exists():
        logger.warning("No JSON templates file found at %s", JSON_TEMPLATES_PATH)
        return []

    try:
        specs = json.loads(JSON_TEMPLATES_PATH.read_text(encoding="utf-8"))
        templates = []
        for spec in specs:
            try:
                templates.append(JsonSceneTemplate(spec))
            except Exception as e:
                logger.warning("Failed to load template spec: %s — %s", spec.get("name", "?"), e)
        logger.info("Loaded %d JSON templates", len(templates))
        return templates
    except Exception as e:
        logger.error("Failed to load JSON templates: %s", e)
        return []
