from manim import *
import numpy as np

class TaylorSinConvergence(Scene):
    def construct(self):
        # Colors
        self.camera.background_color = "#0B1026"
        WHITE = "#F8FAFC"
        BLUE = "#58C4DD"
        YELLOW = "#F5D547"
        TEAL = "#2DD4BF"
        CORAL = "#FF6B6B"
        PURPLE = "#A78BFA"
        
        # Title
        title = Text("Taylor Series Convergence: sin(x)", font_size=36, color=WHITE)
        title.to_edge(UP, buff=0.4)
        
        # Axes
        axes = Axes(
            x_range=[-8, 8, 2],
            y_range=[-2, 2, 1],
            x_length=11,
            y_length=5,
            axis_config={"color": WHITE, "stroke_width": 2},
            tips=False
        ).shift(DOWN * 0.3)
        
        # Actual sin(x) function
        sin_graph = axes.plot(lambda x: np.sin(x), x_range=[-7.5, 7.5], color=WHITE, stroke_width=3)
        sin_label = MathTex(r"\sin(x)", color=WHITE, font_size=32).next_to(axes.c2p(6, np.sin(6)), RIGHT, buff=0.2)
        
        # Taylor approximations (optimized - fewer points)
        # T1: x
        # T3: x - x^3/6
        # T5: x - x^3/6 + x^5/120
        # T7: x - x^3/6 + x^5/120 - x^7/5040
        
        def taylor_sin(x, terms):
            """Calculate Taylor series for sin(x) with 'terms' terms"""
            from math import factorial
            result = 0
            for n in range(terms):
                sign = (-1) ** n
                result += sign * (x ** (2*n + 1)) / factorial(2*n + 1)
            return result
        
        colors = [YELLOW, CORAL, TEAL, BLUE, PURPLE]
        taylor_graphs = []
        taylor_labels = []
        
        # Generate approximations (1, 2, 3, 4, 5 terms)
        for i, num_terms in enumerate([1, 2, 3, 4, 5]):
            color = colors[i]
            # Limit x_range to avoid numerical overflow
            if num_terms == 1:
                x_max = 3
            elif num_terms == 2:
                x_max = 4.5
            else:
                x_max = 7.5
                
            graph = axes.plot(
                lambda x, n=num_terms: taylor_sin(x, n),
                x_range=[-x_max, x_max],
                color=color,
                stroke_width=3,
                use_smoothing=False  # Faster rendering
            )
            taylor_graphs.append(graph)
            
            # Label showing degree
            degree = 2 * num_terms - 1
            label = MathTex(f"T_{{{degree}}}", color=color, font_size=28)
            taylor_labels.append(label)
        
        # Arrange labels
        labels_group = VGroup(*taylor_labels).arrange(RIGHT, buff=0.4).to_edge(DOWN, buff=0.5)
        
        # Animation sequence
        self.play(Write(title), Create(axes), run_time=1.5)
        self.play(Create(sin_graph), Write(sin_label), run_time=2)
        self.wait(0.5)
        
        # Show Taylor approximations one by one
        for i, (graph, label) in enumerate(zip(taylor_graphs, taylor_labels)):
            self.play(
                Create(graph),
                FadeIn(label, shift=UP*0.2),
                run_time=1.8
            )
            self.wait(0.3)
        
        # Final zoom effect - show convergence near 0
        zoom_rect = Rectangle(width=4, height=2.5, color=TEAL, stroke_width=3)
        zoom_rect.move_to(axes.c2p(0, 0))
        
        self.play(Create(zoom_rect), run_time=1)
        self.wait(0.5)
        
        # Fade out zoom and show divergence at edges
        edge_text = Text("Perfect near 0, diverges at edges", font_size=28, color=YELLOW)
        edge_text.next_to(zoom_rect, DOWN, buff=0.3)
        
        self.play(
            Write(edge_text),
            zoom_rect.animate.set_stroke(opacity=0.3),
            run_time=1.5
        )
        
        # Ambient ending - pulsing labels
        pulse_t = ValueTracker(0)
        
        def pulse_updater(mob, dt):
            pulse_t.increment_value(dt)
            for i, label in enumerate(mob):
                phase = i * 0.4
                opacity = 0.6 + 0.4 * np.sin(pulse_t.get_value() * 2 + phase)
                label.set_opacity(opacity)
        
        labels_group.add_updater(pulse_updater)
        
        self.wait(3)
