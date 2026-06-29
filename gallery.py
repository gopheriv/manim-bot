"""Gallery Mode — public library of curated animations.

Users can browse and render from a curated catalog of the best
animations, organized by category and difficulty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

GALLERY_PATH = Path(__file__).parent / "data" / "gallery.json"
GALLERY_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class GalleryItem:
    """A single gallery animation entry."""
    id: int
    category: str
    title: str
    prompt: str
    difficulty: int      # 1-10
    tags: list[str] = field(default_factory=list)
    is_3d: bool = False
    is_featured: bool = False
    view_count: int = 0
    render_count: int = 0


# ── Curated gallery catalog ─────────────────────────────────────────────────

GALLERY_CATALOG: list[GalleryItem] = [
    # Calculus
    GalleryItem(id=1, category="Calculus", title="Taylor Series Approximation",
                prompt="Animate the Taylor series approximation of sin(x) showing each term building up",
                difficulty=6, tags=["taylor", "series", "sin", "polynomial"], is_featured=True),
    GalleryItem(id=2, category="Calculus", title="Fourier Transform Decomposition",
                prompt="Show how a Fourier transform decomposes a signal into sine waves",
                difficulty=7, tags=["fourier", "signal", "decomposition"], is_featured=True),
    GalleryItem(id=3, category="Calculus", title="Riemann Sum Convergence",
                prompt="Show the Riemann sum approximation of an integral with rectangles converging",
                difficulty=5, tags=["riemann", "integral", "rectangles"]),
    GalleryItem(id=4, category="Calculus", title="Gradient Descent Optimization",
                prompt="Visualize how gradient descent finds the minimum of a loss function",
                difficulty=5, tags=["gradient", "descent", "optimization", "ML"]),
    GalleryItem(id=5, category="Calculus", title="Newton's Method Convergence",
                prompt="Show the convergence of Newton's method for finding roots",
                difficulty=6, tags=["newton", "roots", "iteration"]),
    GalleryItem(id=6, category="Calculus", title="Fundamental Theorem of Calculus",
                prompt="Animate the connection between differentiation and integration: show area under curve building up as antiderivative",
                difficulty=7, tags=["fundamental theorem", "integration", "differentiation"], is_featured=True),

    # Linear Algebra
    GalleryItem(id=7, category="Linear Algebra", title="Eigenvalues and Eigenvectors",
                prompt="Visualize the eigenvalues of a 2x2 matrix as it transforms the unit circle",
                difficulty=6, tags=["eigenvalues", "eigenvectors", "matrix"], is_featured=True),
    GalleryItem(id=8, category="Linear Algebra", title="SVD Decomposition",
                prompt="Animate singular value decomposition: show a matrix being decomposed into U, Sigma, V^T",
                difficulty=7, tags=["SVD", "decomposition", "matrix"]),
    GalleryItem(id=9, category="Linear Algebra", title="Cross Product Visualization",
                prompt="Visualize the cross product of two vectors as a changing parallelogram area",
                difficulty=4, tags=["cross product", "vectors", "area"]),
    GalleryItem(id=10, category="Linear Algebra", title="Matrix Multiplication as Composition",
                prompt="Animate why matrix multiplication is function composition: show how applying two transformations in sequence equals their product",
                difficulty=7, tags=["matrix", "composition", "transformation"], is_featured=True),

    # Probability
    GalleryItem(id=11, category="Probability", title="Central Limit Theorem",
                prompt="Animate the central limit theorem with random distributions converging to a bell curve",
                difficulty=5, tags=["CLT", "normal distribution", "convergence"], is_featured=True),
    GalleryItem(id=12, category="Probability", title="Bayes' Theorem Visualized",
                prompt="Animate Bayes' theorem: show how prior probability updates to posterior with new evidence",
                difficulty=5, tags=["Bayes", "probability", "conditional"]),
    GalleryItem(id=13, category="Probability", title="Law of Large Numbers",
                prompt="Animate the law of large numbers: show sample mean converging to expected value as samples increase",
                difficulty=4, tags=["LLN", "convergence", "expected value"]),

    # Physics
    GalleryItem(id=14, category="Physics", title="Damped Harmonic Oscillator",
                prompt="Animate a damped harmonic oscillator with phase space diagram",
                difficulty=5, tags=["oscillator", "damping", "phase space"], is_featured=True),
    GalleryItem(id=15, category="Physics", title="Schrodinger Equation",
                prompt="Animate the time evolution of a quantum wave function solving the Schrodinger equation",
                difficulty=9, tags=["quantum", "schrodinger", "wave function"]),
    GalleryItem(id=16, category="Physics", title="Thermodynamics Cycle",
                prompt="Animate a Carnot cycle on a PV diagram showing isothermal and adiabatic processes",
                difficulty=7, tags=["thermodynamics", "Carnot", "PV diagram"]),

    # Geometry
    GalleryItem(id=17, category="Geometry", title="Voronoi Diagram Construction",
                prompt="Animate the construction of a Voronoi diagram from random seed points",
                difficulty=4, tags=["voronoi", "tessellation", "distance"]),
    GalleryItem(id=18, category="Geometry", title="Pythagorean Theorem Proof",
                prompt="Prove the Pythagorean theorem visually: show how a^2 + b^2 = c^2 by rearranging squares",
                difficulty=3, tags=["Pythagoras", "proof", "geometry"], is_featured=True),
    GalleryItem(id=19, category="Geometry", title="Parametric Curve Tracing",
                prompt="Animate a particle moving along a parametric curve with a glowing trail",
                difficulty=3, tags=["parametric", "curve", "particle"]),

    # Complex Analysis
    GalleryItem(id=20, category="Complex Analysis", title="Mandelbrot Set Zoom",
                prompt="Animate the Mandelbrot set zoom-in revealing self-similarity",
                difficulty=8, tags=["Mandelbrot", "fractal", "self-similarity"], is_featured=True),
    GalleryItem(id=21, category="Complex Analysis", title="Contour Integration",
                prompt="Animate contour integration in the complex plane showing path deformation",
                difficulty=8, tags=["contour", "complex", "residue"]),
]


def get_categories() -> list[str]:
    """Get all gallery categories."""
    return sorted(set(item.category for item in GALLERY_CATALOG))


def get_featured() -> list[GalleryItem]:
    """Get featured items."""
    return [item for item in GALLERY_CATALOG if item.is_featured]


def get_by_category(category: str) -> list[GalleryItem]:
    """Get items in a category (case-insensitive)."""
    return [item for item in GALLERY_CATALOG if item.category.lower() == category.lower()]


def get_by_id(item_id: int) -> GalleryItem | None:
    """Get a specific item by ID."""
    for item in GALLERY_CATALOG:
        if item.id == item_id:
            return item
    return None


def search(query: str) -> list[GalleryItem]:
    """Search gallery by title, prompt, or tags."""
    query_lower = query.lower()
    results = []
    for item in GALLERY_CATALOG:
        if (query_lower in item.title.lower() or
            query_lower in item.prompt.lower() or
            any(query_lower in tag.lower() for tag in item.tags)):
            results.append(item)
    return results


def increment_view(item_id: int) -> None:
    """Increment view count for a gallery item."""
    for item in GALLERY_CATALOG:
        if item.id == item_id:
            item.view_count += 1
            break


def increment_render(item_id: int) -> None:
    """Increment render count for a gallery item."""
    for item in GALLERY_CATALOG:
        if item.id == item_id:
            item.render_count += 1
            break
