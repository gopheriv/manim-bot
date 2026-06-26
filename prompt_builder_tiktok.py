"""TikTok-specific prompt additions for vertical format (9:16, 1080x1920)"""

TIKTOK_FORMAT_RULES = """## TIKTOK FORMAT RULES (9:16 VERTICAL, MAX 30 SECONDS)

### Resolution & Aspect Ratio
- **Resolution**: 1080x1920 pixels (portrait)
- **Aspect ratio**: 9:16 (vertical phone screen)
- **Duration**: 25-30 seconds MAX (TikTok optimal)
- **Camera config**: Use default Manim camera, adjust content to fit vertical frame

### Content Structure (5-part story arc)
Every TikTok animation MUST follow this structure:

#### 1. HOOK (0-3s) — Grab attention IMMEDIATELY
- Bold, large text question or surprising statement
- Font size: 48-60 (LARGE for mobile)
- Use color gradient or pulse effect
- Examples:
  * "How does sin(x) become a polynomial?"
  * "This ONE trick makes calculus easy"
  * "Watch this curve morph into circles"

```python
hook = Text("Question goes here?", font_size=52, color=YELLOW, weight=BOLD, line_spacing=1.2)
hook.move_to(UP * 2.5)
self.play(Write(hook), hook.animate.scale(1.1).set_color_by_gradient(YELLOW, CORAL))
```

#### 2. CONTEXT (3-8s) — Show the problem
- Title card with concept name (font_size=44-48)
- Subtitle explaining what we'll see (font_size=26-32)
- Set up visual space: axes, diagrams, etc.

```python
title = Text("Taylor Series", font_size=48, weight=BOLD)
title.to_edge(UP, buff=0.4)
subtitle = Text("Breaking curves into polynomials", font_size=28, color=TEAL)
subtitle.next_to(title, DOWN, buff=0.3)
```

#### 3. EXPLANATION (8-20s) — Show the magic
- Step-by-step visualization with LARGE text labels
- Show 3-4 key steps MAX (TikTok attention span)
- Each step gets:
  * Formula (font_size=40-50, MathTex)
  * Plain English explanation (font_size=28-36, Text)
  * Visual demo (2-3 seconds)

```python
# Step 1
formula1 = MathTex(r"T_1 = x", font_size=50, color=YELLOW)
explanation1 = Text("Linear\\napproximation", font_size=32, color=YELLOW, line_spacing=1.1)
formula1.move_to(DOWN * 3.2)
explanation1.next_to(formula1, DOWN, buff=0.3)
self.play(Create(graph1), Write(formula1), FadeIn(explanation1), run_time=2.0)
```

#### 4. KEY INSIGHT (20-25s) — The takeaway
- ONE sentence summary (font_size=44-52, BOLD)
- Visual proof or final result
- Highlight the "aha!" moment

```python
insight = Text("More terms =\\nBetter fit!", font_size=48, color=YELLOW, weight=BOLD, line_spacing=1.2)
insight.move_to(DOWN * 3.5)
```

#### 5. CTA (25-30s) — Call to action
- "Follow for more" + emoji
- Tagline about channel (e.g., "Math explained visually")
- Pulsing animation to grab attention

```python
cta = VGroup(
    Text("Follow for more", font_size=40, weight=BOLD),
    Text("🔥 Math explained visually", font_size=32, color=YELLOW)
).arrange(DOWN, buff=0.4)
cta.move_to(DOWN * 3.5)
self.play(FadeIn(cta, scale=0.95), cta.animate.scale(1.05), rate_func=there_and_back)
```

### Layout Rules for Vertical Format

#### Safe Zones
```
┌─────────────────┐  ← Top 15%: Title/Hook zone
│     TITLE       │
├─────────────────┤  
│                 │  
│   MAIN VISUAL   │  ← Center 50%: Main content
│     (axes,      │     (graphs, diagrams, animations)
│    graphs...)   │  
│                 │  
├─────────────────┤  
│   EXPLANATION   │  ← Bottom 35%: Text/formulas/CTA
│   TEXT/FORMULA  │     (Large font, 2-3 lines max)
└─────────────────┘
```

#### Positioning Guidelines
```python
# Title zone (top 15%)
title.to_edge(UP, buff=0.3)

# Main visual zone (center 50%, vertically compact)
axes = Axes(
    x_range=[-6, 6, 2],
    y_range=[-1.5, 1.5, 1],
    x_length=9,      # Wider (phone is narrow)
    y_length=4,      # Shorter (vertical space is precious)
).shift(DOWN * 0.5)

# Explanation zone (bottom 35%)
formula.move_to(DOWN * 3.2)
explanation.next_to(formula, DOWN, buff=0.3)
```

### Font Sizes (Mobile-Optimized)
- **Hook/CTA**: 48-60 (HUGE)
- **Title**: 44-52 (LARGE)
- **Subtitle**: 28-36 (MEDIUM)
- **Formulas**: 40-50 (LARGE, legible on phone)
- **Explanations**: 28-36 (MEDIUM, 2-3 lines max)
- **Labels**: 32-38 (axis labels, annotations)

### Text Best Practices
- **Line spacing**: 1.1-1.3 (tighter for vertical space)
- **Weight**: Use BOLD for hooks, titles, CTAs
- **Colors**: High contrast (WHITE text on DARK bg, or bright YELLOW/TEAL/CORAL)
- **Max lines**: 2-3 per text block (mobile screens are small!)
- **Avoid**: Long paragraphs, tiny text, cluttered layouts

### Visual Best Practices
- **Axes**: Make them WIDER (x_length=9-10) and SHORTER (y_length=3.5-4.5)
- **Stroke width**: Increase by 25% vs desktop (3 → 4, 4 → 5)
- **Dots/points**: Larger radius (0.08 → 0.12)
- **Arrows**: Thicker, more visible (stroke_width=3-4)
- **Glow effects**: Reduce or remove (mobile performance)
- **Particle fields**: 15-20 elements MAX (not 30+)

### Timing Rules
- **Total**: 25-30 seconds (TikTok sweet spot)
- **Hook**: 1.5-2 seconds (fast!)
- **Each explanation step**: 2-3 seconds (not 4-5)
- **Transitions**: 0.6-1.0 seconds (snappy)
- **Final ambient**: 2-2.5 seconds (keep it short)

### Animation Principles
1. **Fast pacing**: TikTok users scroll fast — no slow burns
2. **Clear progression**: Viewer should see 3-4 distinct "beats"
3. **Text-heavy**: More explanatory text than desktop version
4. **Simplified**: Show 3 Taylor terms, not 5; one formula, not three
5. **High contrast**: Bright colors on dark background
6. **Minimal updaters**: Mobile performance is weak — avoid heavy `always_redraw()`

### Common Mistakes to AVOID
❌ Tiny text (font_size < 28)
❌ Too many steps (>4 explanation phases)
❌ Slow pacing (total duration > 30s)
❌ Horizontal-oriented axes (x_length < y_length)
❌ Cluttered bottom zone (overlap formula + CTA)
❌ Missing hook (jumping straight to math)
❌ No CTA (missing engagement opportunity)
❌ Complex gradients/glows (mobile lag)

### Example: Full TikTok Structure
```python
# 1. HOOK (0-2s)
hook = Text("Can you turn\\nsin(x) into a line?", font_size=50, weight=BOLD, line_spacing=1.2)
hook.move_to(UP * 2.5)
self.play(Write(hook), run_time=1.5)
self.play(FadeOut(hook), run_time=0.5)

# 2. CONTEXT (2-5s)
title = Text("Taylor Series", font_size=48, weight=BOLD).to_edge(UP, buff=0.4)
axes = Axes(x_range=[-6,6,2], y_range=[-1.5,1.5,1], x_length=9, y_length=4).shift(DOWN*0.5)
sin_graph = axes.plot(lambda x: np.sin(x), color=WHITE, stroke_width=5)
self.play(FadeIn(title), Create(axes), Create(sin_graph), run_time=2.0)

# 3. EXPLANATION (5-18s) - 3 steps
for i, (graph, formula_tex, explanation_text) in enumerate(steps):
    formula = MathTex(formula_tex, font_size=46).move_to(DOWN*3.2)
    explanation = Text(explanation_text, font_size=30).next_to(formula, DOWN, buff=0.3)
    self.play(Create(graph), Write(formula), FadeIn(explanation), run_time=2.5)
    self.wait(0.5)
    if i < len(steps)-1:
        self.play(FadeOut(formula), FadeOut(explanation), run_time=0.5)

# 4. INSIGHT (18-22s)
insight = Text("Perfect near x=0!", font_size=46, weight=BOLD, color=TEAL)
insight.move_to(DOWN * 3.5)
self.play(Write(insight), run_time=1.5)
self.wait(0.5)

# 5. CTA (22-27s)
self.play(FadeOut(insight), run_time=0.5)
cta = VGroup(
    Text("Follow for more 🔥", font_size=40, weight=BOLD),
    Text("Math made visual", font_size=32, color=YELLOW)
).arrange(DOWN, buff=0.4).move_to(DOWN*3.5)
self.play(FadeIn(cta), cta.animate.scale(1.05), run_time=1.5, rate_func=there_and_back)
self.wait(2.0)
```
"""

def get_tiktok_prompt(user_request: str) -> str:
    """Generate TikTok-optimized prompt from user request."""
    from prompt_builder import BASE_MANIM_RULES, SCENE_AWARENESS_CONTRACT

    return f"""{BASE_MANIM_RULES}

{TIKTOK_FORMAT_RULES}

{SCENE_AWARENESS_CONTRACT}

## User Request
{user_request}

## Additional Requirements for TikTok
- Camera resolution will be set to 1080x1920 via CLI (you don't need to configure it)
- Focus on MOBILE LEGIBILITY: larger text, simpler visuals, faster pacing
- Follow the 5-part structure: Hook → Context → Explanation → Insight → CTA
- Keep total duration 25-30 seconds
- Use vertical-optimized layout: title at top, visual in center, text at bottom

Generate the complete Manim scene code now.
"""
