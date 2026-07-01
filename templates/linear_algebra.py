"""Linear algebra templates: eigenvalues, SVD, matrix transforms."""

from __future__ import annotations

from templates.base import SceneTemplate, TemplateConfig, _common_manim_header, _indent


class EigenvaluesTemplate(SceneTemplate):
    """Eigenvalues transforming the unit circle."""
    name = "eigenvalues"
    keywords = ["eigenvalue", "eigenvector", "matrix", "transform", "circle", "stretch", "linear", "vector"]
    category = "linear_algebra"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        a11 = config.extra_params.get('a11', 2)
        a12 = config.extra_params.get('a12', 1)
        a21 = config.extra_params.get('a21', 1)
        a22 = config.extra_params.get('a22', 3)
        return _common_manim_header() + _indent(f"""
title = Text("Eigenvalues & Eigenvectors", font_size=36, color="{color}")
title.to_edge(UP)
matrix_tex = MathTex(r"A = \\begin{{pmatrix}} {a11} & {a12} \\\\ {a21} & {a22} \\end{{pmatrix}}", font_size=32, color=WHITE)
matrix_tex.to_edge(UP, buff=1)
self.play(Write(title, run_time=1.5), Write(matrix_tex, run_time=1.5))

# Unit circle
circle = Circle(radius=1.5, color="{color}", stroke_width=2)
circle_glow = circle.copy().set_stroke(width=8, opacity=0.2).set_fill(opacity=0)
self.add(circle_glow)
self.play(Create(circle, run_time=1.5))

# Eigenvectors (pre-computed for the default matrix)
eigen_pairs = [
    (0.382, np.array([0.851, -0.526, 0])),
    (3.618, np.array([0.526, 0.851, 0])),
]

# Show eigenvectors before transform (batched)
eigen_arrows = VGroup()
eigen_labels = VGroup()
for eigenval, eigenvec in eigen_pairs:
    vec_line = Arrow(ORIGIN, 2.5 * eigenvec, buff=0, color="#10B981", stroke_width=3)
    val_label = MathTex(rf"\\lambda = {{eigenval:.2f}}", font_size=24, color="#10B981")
    val_label.next_to(vec_line.get_end(), RIGHT + UP)
    eigen_arrows.add(vec_line)
    eigen_labels.add(val_label)
self.play(Create(eigen_arrows), Write(eigen_labels), run_time=1.5)

# Apply transformation
def transform_point(p):
    x, y = p[0], p[1]
    return np.array([{a11}*x + {a12}*y, {a21}*x + {a22}*y, 0])

# Animate the transform
transformed_circle = circle.copy()
self.play(
    transformed_circle.animate.apply_function(transform_point),
    run_time=3,
)

# Eigenvectors after transform (still aligned!)
new_vecs = VGroup()
for eigenval, eigenvec in eigen_pairs:
    new_end = transform_point(2.5 * eigenvec)
    new_vec = Arrow(ORIGIN, new_end, buff=0, color="#F59E0B", stroke_width=3)
    new_vecs.add(new_vec)
self.play(Create(new_vecs), run_time=1)

self.wait(2)
""")


class SVDTemplate(SceneTemplate):
    """SVD decomposition visualization."""
    name = "svd"
    keywords = ["svd", "singular", "decomposition", "decompose", "factorization", "rank"]
    category = "linear_algebra"

    def generate_code(self, config: TemplateConfig) -> str:
        color = config.colors[0]
        return _common_manim_header() + _indent(f"""
title = Text("Singular Value Decomposition", font_size=36, color="{color}")
title.to_edge(UP)
self.play(Write(title, run_time=1.5))

# A = U S V^T
eq = MathTex(r"A = U \\Sigma V^T", font_size=40, color=WHITE)
eq.to_edge(UP, buff=1.2)
self.play(Write(eq, run_time=1.5))

# Show decomposition steps
steps = [
    (r"\\text{{Rotation }} V^T", "{color}", "Rotate"),
    (r"\\text{{Scaling }} \\Sigma", "#10B981", "Scale"),
    (r"\\text{{Rotation }} U", "#F59E0B", "Rotate"),
]

grid = NumberPlane(x_range=[-3, 3], y_range=[-2, 2], faded_line_ratio=2)
self.play(Create(grid, run_time=1))

for label, col, action in steps:
    tex = MathTex(label, font_size=28, color=col)
    tex.to_edge(DOWN)
    self.play(Write(tex), run_time=1)
    self.wait(0.5)

self.wait(2)
""")
