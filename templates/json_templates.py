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
import re
from pathlib import Path
from typing import Any

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

    def match_score(self, prompt: str) -> float:
        """Fuzzy keyword matching."""
        prompt_lower = prompt.lower()
        matches = 0
        for kw in self._keywords:
            if kw.lower() in prompt_lower:
                matches += 1
        if matches == 0:
            return 0.0
        return min(1.0, matches / len(self._keywords) * 0.8 + 0.2 * (1 if self._keywords[0].lower() in prompt_lower else 0))

    def generate_code(self, config: TemplateConfig) -> str:
        """Generate Manim code from template + config."""
        code = self._code_template

        # Replace placeholders
        replacements = {
            "{title}": config.title,
            "{equation}": config.equation,
            "{description}": config.description,
            "{duration}": str(config.duration),
            "{color1}": config.colors[0] if config.colors else "#58C4DD",
            "{color2}": config.colors[1] if len(config.colors) > 1 else "#FFFFFF",
            "{color3}": config.colors[2] if len(config.colors) > 2 else "#FF8080",
        }

        # Add extra params
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
