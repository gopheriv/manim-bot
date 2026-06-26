"""Scene awareness helper — runtime layout tools for generated Manim scenes.

Generated Manim code can optionally import and use this helper to manage
spatial layout and avoid overlap. The helper provides placement methods
that check for conflicts with existing objects.

Usage in generated code:
    from scene_awareness import SceneLayout
    layout = SceneLayout(self)
    title = layout.add(Text("Title", font_size=36), "title", position=UP*3, priority=1)
    formula = layout.add(MathTex("x^2", font_size=32), "formula", position=ORIGIN, priority=1)
    layout.place_below(formula, title, buff=0.4)
"""

from __future__ import annotations

import numpy as np

# These are imported at runtime by the generated Manim scene
# We define them here so the generated code can do:
#   from scene_awareness import SceneLayout


class SceneLayout:
    """Tracks object positions and provides overlap-aware placement helpers."""

    def __init__(self, scene):
        self.scene = scene
        self._registry: list[dict] = []

    def add(self, mob, name: str, position=None, priority: int = 2, avoid: bool = True):
        """Register a mobject and optionally place it at a position.

        Args:
            mob: The Manim mobject.
            name: Unique identifier for this object.
            position: Where to place it (Manim direction/coordinate).
            priority: 1=essential, 2=important, 3=decoration.
            avoid: If True, check for overlaps before placing.
        """
        entry = {
            "name": name,
            "mob": mob,
            "priority": priority,
            "position": position,
        }

        if position is not None:
            mob.move_to(position)

        if avoid and position is not None:
            self._resolve_overlap(mob, name, priority)

        self._registry.append(entry)
        return mob

    def place_below(self, mob, target, buff: float = 0.4):
        """Place mob below target with explicit spacing."""
        mob.next_to(target, np.array([0, -1, 0]), buff=buff)
        return mob

    def place_above(self, mob, target, buff: float = 0.4):
        """Place mob above target with explicit spacing."""
        mob.next_to(target, np.array([0, 1, 0]), buff=buff)
        return mob

    def place_right_of(self, mob, target, buff: float = 0.4):
        """Place mob to the right of target with explicit spacing."""
        mob.next_to(target, np.array([1, 0, 0]), buff=buff)
        return mob

    def place_left_of(self, mob, target, buff: float = 0.4):
        """Place mob to the left of target with explicit spacing."""
        mob.next_to(target, np.array([-1, 0, 0]), buff=buff)
        return mob

    def place_safe(self, mob, position=None, buff: float = 0.5):
        """Place mob at position, shifting if it overlaps with existing objects."""
        if position is not None:
            mob.move_to(position)
        self._resolve_overlap(mob, "safe_placement", priority=2)
        return mob

    def fade_if_crowded(self, name: str, fade_time: float = 0.5):
        """Fade out a previously registered object to make room."""
        for entry in self._registry:
            if entry["name"] == name:
                from manim import FadeOut
                self.scene.play(FadeOut(entry["mob"]), run_time=fade_time)
                return True
        return False

    def reserve_region(self, position, width: float = 4.0, height: float = 1.0, name: str = "reserved"):
        """Mark a screen region as occupied (for future overlap checks)."""
        self._registry.append({
            "name": name,
            "mob": None,
            "priority": 2,
            "position": position,
            "reserved_size": (width, height),
        })
        return name

    def _resolve_overlap(self, mob, name: str, priority: int):
        """Check if mob overlaps with registered high-priority objects and shift if needed."""
        try:
            mob_center = mob.get_center()
        except Exception:
            return

        for entry in self._registry:
            if entry["name"] == name:
                continue
            if entry["mob"] is None:
                continue
            if entry.get("priority", 3) > 2 and priority > 2:
                continue  # Don't bother resolving decoration-vs-decoration

            try:
                existing_center = entry["mob"].get_center()
                dist = np.linalg.norm(mob_center[:2] - existing_center[:2])
                if dist < 0.5:  # Too close — shift down
                    mob.shift(np.array([0, -0.8, 0]))
                    break
            except Exception:
                continue
