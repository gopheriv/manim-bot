"""Template registry — fuzzy matching of user prompts to pre-built scene templates.

When a user sends a prompt, the registry scores it against all registered
templates. If the best match exceeds a confidence threshold, the LLM only
needs to fill a small JSON config instead of generating 200+ lines of code.
"""

from __future__ import annotations

import logging

from templates.base import SceneTemplate, TemplateMatch

logger = logging.getLogger(__name__)


class TemplateRegistry:
    """Global registry of all scene templates."""

    def __init__(self) -> None:
        self._templates: list[SceneTemplate] = []
        self._confidence_threshold = 0.2  # minimum score to consider a match

    def register(self, template: SceneTemplate) -> None:
        """Add a template to the registry."""
        self._templates.append(template)

    def match(self, prompt: str) -> TemplateMatch | None:
        """Find the best matching template for a user prompt.

        Returns TemplateMatch if confidence >= threshold, else None (fallback to full code gen).
        """
        best: TemplateMatch | None = None

        for tmpl in self._templates:
            score = tmpl.match_score(prompt)
            if score >= self._confidence_threshold:
                candidate = TemplateMatch(template=tmpl, confidence=score, config=tmpl.default_config())
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

        if best:
            logger.info(
                "Template matched: %s (confidence %.2f, category=%s)",
                best.template.name,
                best.confidence,
                best.template.category,
            )
        else:
            logger.info("No template matched (threshold=%.2f), falling back to full code gen", self._confidence_threshold)

        return best

    @property
    def template_count(self) -> int:
        return len(self._templates)


# ── Global singleton ──────────────────────────────────────────────────────

_registry: TemplateRegistry | None = None


def get_registry() -> TemplateRegistry:
    """Get (or create) the global template registry with all templates loaded."""
    global _registry
    if _registry is not None:
        return _registry

    _registry = TemplateRegistry()

    # Register all category templates
    from templates.oscillator import DampedOscillatorTemplate, DrivenOscillatorTemplate
    from templates.fourier import FourierSeriesTemplate, LaplaceTransformTemplate
    from templates.calculus import RiemannSumTemplate, GradientDescentTemplate
    from templates.linear_algebra import EigenvaluesTemplate, SVDTemplate
    from templates.probability import CLTTemplate, BayesTheoremTemplate
    from templates.physics import SchrodingerTemplate, ThermodynamicsTemplate
    from templates.complex import MandelbrotTemplate, ContourIntegralTemplate

    for tmpl_cls in [
        DampedOscillatorTemplate,
        DrivenOscillatorTemplate,
        FourierSeriesTemplate,
        LaplaceTransformTemplate,
        RiemannSumTemplate,
        GradientDescentTemplate,
        EigenvaluesTemplate,
        SVDTemplate,
        CLTTemplate,
        BayesTheoremTemplate,
        SchrodingerTemplate,
        ThermodynamicsTemplate,
        MandelbrotTemplate,
        ContourIntegralTemplate,
    ]:
        _registry.register(tmpl_cls())

    logger.info("Template registry initialized with %d templates", _registry.template_count)

    # Load JSON-based templates (50+ additional templates)
    from templates.json_templates import load_json_templates
    json_templates = load_json_templates()
    for tmpl in json_templates:
        _registry.register(tmpl)

    logger.info("Template registry now has %d templates (class + JSON)", _registry.template_count)
    return _registry


def reset_registry() -> None:
    """Reset the registry (useful for testing or reloading)."""
    global _registry
    _registry = None
