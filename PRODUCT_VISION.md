# Manim Bot → Visual Learning Platform: Next-Generation Blueprint

*Staff-level product & architecture review — June 2026*

---

# Part 1 — Brutal Assessment

## What's Impressive

1. **End-to-end pipeline works.** Prompt → video in ~2-5 minutes is genuinely useful.
2. **Self-healing loop** (3 retries + fallback) means users almost never get "error" — they get *something*.
3. **Scene awareness layer** (plan → validate → repair) is a novel approach to spatial layout.
4. **14 domain templates** with fuzzy matching = 60%+ of common requests can bypass full LLM gen.
5. **Hardware-aware prompt engineering** (40-point weight budget) is clever constraint programming.
6. **Dual-LLM architecture** (specialized code model + chat model) is the right pattern.
7. **Voiceover integration** turns it from "cool demo" into "actually useful explainer."
8. **Memory guards** (85% block, 92% kill) keep the laptop alive under load.

## Top 20 Weaknesses

| # | Weakness | Severity |
|---|----------|----------|
| 1 | **No iteration** — user can't say "make it slower" or "change the color" after seeing a render | Critical |
| 2 | **No conversation memory** — every request is independent, no "build on the last one" | Critical |
| 3 | **Render time is 2-5 min** — too slow for "wow" moment, too fast for async workflow | High |
| 4 | **No preview before commit** — user waits 5 min then sees they don't like it | High |
| 5 | **Template matching is keyword-only** — "show me how e^(iπ) = -1" won't match anything | High |
| 6 | **No error feedback to user** — render fails silently to fallback, user doesn't know why | Medium |
| 7 | **Single concurrent render** — one user blocks everyone | High |
| 8 | **No share/export mechanism** — video trapped in Telegram chat | High |
| 9 | **No quality scoring** — bot doesn't know if output is good or bad | Medium |
| 10 | **Voiceover timing is naive** — no sync between narration beats and visual events | Medium |
| 11 | **No LaTeX parsing** — user can't paste equations to animate | High |
| 12 | **No educational context** — doesn't know *why* Euler's identity matters, just draws it | High |
| 13 | **Themes are cosmetic** — don't affect animation structure or pacing | Low |
| 14 | **No analytics on what users actually request** — can't improve what you don't measure | Medium |
| 15 | **Fallback scene is generic** — always the same sin curve + NumberPlane | Medium |
| 16 | **No rate limit visibility** — user doesn't know they have 3/10 renders left | Low |
| 17 | **D1 cache disabled** — identical prompts re-render every time | Medium |
| 18 | **No batch mode** — can't say "animate all steps of the quadratic formula" | Medium |
| 19 | **No 3D support in practice** — prompt allows it but RAM kills everything 3D | Medium |
| 20 | **No A/B testing of prompts** — can't measure if new prompts produce better output | Low |

## Top 20 Opportunities

| # | Opportunity | Potential |
|---|------------|-----------|
| 1 | **Iteration loop** — "make the curve red", "slow down the transform" | 10x retention |
| 2 | **Inline mode** — generate animations in any chat with `@bot fourier series` | 5x discovery |
| 3 | **Photo → animation** — textbook photo → animated proof | Viral |
| 4 | **LaTeX → animation** — paste `\int_0^1 x^2 dx` → animated Riemann sum | 10x utility for students |
| 5 | **Animation threads** — reply to animation with modifications, build a sequence | Product depth |
| 6 | **Educational narration** — not just "here's a curve" but "notice how the slope..." | Educational impact |
| 7 | **Quality scoring agent** — rate output 1-5, auto-regenerate if < 3 | Quality floor |
| 8 | **Scene graph DSL** — intermediate representation between plan and code | Repairability |
| 9 | **Community gallery** — public channel of best animations + remix | Growth loop |
| 10 | **TikTok-native export** — 9:16, hooks, CTA, ready to post | Viral growth |
| 11 | **Voice input** — explain what you want via voice message → animation | Accessibility |
| 12 | **Batch sequences** — "animate all 5 steps of Gaussian elimination" | Course creation |
| 13 | **Concept maps** — "what should I learn before Fourier transforms?" → path | Learning platform |
| 14 | **Teacher mode** — generate quiz + animation + worksheet from one topic | B2B/B2E |
| 15 | **Embeddable player** — share animation as iframe on any website | Distribution |
| 16 | **Real-time preview** — stream low-res frames while rendering full quality | Perceived speed |
| 17 | **Prompt templates library** — curated prompts for specific curricula (STEP, A-Level, IB) | Niche dominance |
| 18 | **Multi-language** — narration in 10 languages via edge-tts | Global reach |
| 19 | **Collaborative editing** — two users modify same scene in group chat | Social feature |
| 20 | **API access** — let other apps/bots call your render pipeline | Platform play |

## What Competitors Could Easily Copy

- Basic prompt → Manim code → render (anyone with OpenAI + Manim can do this in a weekend)
- Template matching with keywords
- Voiceover with edge-tts
- Theme switching

## What Creates a Moat

- **Iteration memory** — "remember what we built last time and modify it"
- **Scene graph DSL** — structured intermediate representation that enables editing, remixing, caching
- **Educational intelligence** — understanding *what* to animate and *why*, not just *how*
- **Template quality** — 100+ battle-tested templates covering entire curricula
- **Quality scoring** — automated aesthetic + correctness evaluation
- **Community library** — network effects from shared animations

---

# Part 2 — 50+ Feature Proposals

## User Experience (12 features)

| # | Feature | Impact | Difficulty | Priority |
|---|---------|--------|-----------|----------|
| 1 | **Iterative editing** — reply to animation with "make it red" / "slower" / "add labels" | 10/10 | 6/10 | P0 |
| 2 | **Preview frames** — send 3 static frames (first/middle/last) before committing to full render | 8/10 | 3/10 | P0 |
| 3 | **Prompt enhancement** — user types "eigenvalues", bot expands to rich description | 7/10 | 2/10 | P0 |
| 4 | **Render progress with frame preview** — every 25% send a low-res screenshot | 6/10 | 4/10 | P1 |
| 5 | **Undo/version history** — "go back to version 2" | 7/10 | 5/10 | P1 |
| 6 | **Quality selector inline** — buttons: Fast (480p) / Standard (720p) / HD (1080p) | 5/10 | 1/10 | P0 |
| 7 | **Rate limit visibility** — "3/10 renders remaining this hour" in status | 4/10 | 1/10 | P1 |
| 8 | **Smart defaults** — detect "this is a physics question" → physics theme + physics templates | 6/10 | 3/10 | P1 |
| 9 | **Keyboard shortcuts** — reply with emoji: 🔴=redo, ⚡=faster, 🎨=theme, 🔊=voice | 5/10 | 2/10 | P1 |
| 10 | **Animation cards** — rich preview with thumbnail + title + duration in history | 5/10 | 3/10 | P2 |
| 11 | **Bookmark/favorite** — save animations to personal collection | 4/10 | 2/10 | P2 |
| 12 | **Export options** — GIF, MP4, WebM, with/without audio | 6/10 | 3/10 | P1 |

## AI Agent Features (10 features)

| # | Feature | Impact | Difficulty | Priority |
|---|---------|--------|-----------|----------|
| 13 | **Planner Agent** — decomposes "show me Fourier series" into 4-phase storyboard | 9/10 | 5/10 | P0 |
| 14 | **Critic Agent** — scores output on: clarity, beauty, accuracy, pacing (1-5 each) | 8/10 | 4/10 | P0 |
| 15 | **Education Agent** — ensures mathematical correctness of equations and visuals | 8/10 | 6/10 | P1 |
| 16 | **Narration Agent** — generates narration synchronized to visual beats | 7/10 | 5/10 | P1 |
| 17 | **Repair Agent** — specialized in fixing specific error categories (API, layout, perf) | 7/10 | 4/10 | P1 |
| 18 | **Enhancement Agent** — rewrites user's vague prompt into rich visual description | 7/10 | 2/10 | P0 |
| 19 | **Curriculum Agent** — knows STEP/A-Level/IB syllabi, suggests relevant animations | 8/10 | 5/10 | P2 |
| 20 | **Comparison Agent** — "show me Riemann vs Lebesgue integration side-by-side" | 6/10 | 7/10 | P2 |
| 21 | **Debug Agent** — when render fails, explains *why* in plain English to the user | 5/10 | 3/10 | P1 |
| 22 | **Style Transfer Agent** — "make it look like 3Blue1Brown" / "make it minimalist" | 6/10 | 5/10 | P2 |

## Education (10 features)

| # | Feature | Impact | Difficulty | Priority |
|---|---------|--------|-----------|----------|
| 23 | **Concept → animation chain** — "quadratic formula" → 5 connected animations | 9/10 | 7/10 | P1 |
| 24 | **Quiz mode** — generate animation + multiple choice question + reveal answer | 8/10 | 5/10 | P1 |
| 25 | **Step-by-step solver** — "show me how to solve x²+5x+6=0" with animated steps | 9/10 | 6/10 | P1 |
| 26 | **LaTeX → animation** — paste equation, get visualization | 8/10 | 4/10 | P0 |
| 27 | **Photo → proof animation** — textbook photo → animated proof walkthrough | 9/10 | 8/10 | P1 |
| 28 | **Learning path** — "I'm studying for STEP" → personalized animation sequence | 7/10 | 8/10 | P2 |
| 29 | **Spaced repetition** — re-show animations at intervals, ask "do you remember?" | 6/10 | 6/10 | P3 |
| 30 | **Interactive parameter exploration** — inline buttons: "ζ=0.1 / ζ=0.5 / ζ=1.0" | 8/10 | 5/10 | P1 |
| 31 | **Exam paper animator** — upload STEP/A-Level paper → animate specific questions | 9/10 | 7/10 | P2 |
| 32 | **Proof verifier** — animate a proof AND verify each step is logically correct | 7/10 | 9/10 | P3 |

## Collaboration & Growth (8 features)

| # | Feature | Impact | Difficulty | Priority |
|---|---------|--------|-----------|----------|
| 33 | **Inline mode** — `@manimbot fourier series` in any chat | 9/10 | 3/10 | P0 |
| 34 | **Share link** — each animation gets a `manim.bot/v/abc123` link | 8/10 | 4/10 | P1 |
| 35 | **Public gallery channel** — best community animations, curated | 7/10 | 3/10 | P1 |
| 36 | **Remix** — reply to shared animation with modifications | 8/10 | 6/10 | P2 |
| 37 | **Group classroom mode** — teacher sends topic, all students see animation simultaneously | 7/10 | 5/10 | P2 |
| 38 | **Collaborative scene** — user A creates, user B modifies in group chat | 6/10 | 7/10 | P3 |
| 39 | **TikTok/Reels export** — 9:16 + hooks + CTA + watermark | 8/10 | 4/10 | P1 |
| 40 | **Referral rewards** — invite 3 friends → unlock HD renders | 6/10 | 3/10 | P2 |

## Monetization (5 features)

| # | Feature | Impact | Difficulty | Priority |
|---|---------|--------|-----------|----------|
| 41 | **Stars payment** — freemium: 3 free/day, unlimited for 500 Stars/mo | 8/10 | 4/10 | P1 |
| 42 | **API access** — developers pay to use your render pipeline | 7/10 | 6/10 | P2 |
| 43 | **Teacher packs** — bundled animation sets for specific courses, sold as Paid Media | 7/10 | 5/10 | P2 |
| 44 | **White-label** — universities embed your renderer in their LMS | 6/10 | 8/10 | P3 |
| 45 | **Enterprise** — bulk licenses, SSO, admin dashboard | 5/10 | 9/10 | P3 |

## Platform & Infrastructure (7 features)

| # | Feature | Impact | Difficulty | Priority |
|---|---------|--------|-----------|----------|
| 46 | **Scene graph cache** — hash(prompt+params) → reuse render without re-calling LLM | 7/10 | 3/10 | P0 |
| 47 | **Background HD render** — send 480p preview instantly, upgrade to HD when ready | 8/10 | 5/10 | P1 |
| 48 | **Render farm** — dispatch to GPU cloud workers for parallel rendering | 8/10 | 8/10 | P2 |
| 49 | **Webhook mode** — replace polling with webhooks for lower latency | 5/10 | 3/10 | P1 |
| 50 | **Scene DSL** — JSON-based scene description language (renders without LLM) | 7/10 | 7/10 | P2 |
| 51 | **Metrics pipeline** — track: prompt, template hit, render time, success rate, user score | 6/10 | 3/10 | P1 |
| 52 | **A/B prompt testing** — randomly assign users to prompt variants, measure outcomes | 5/10 | 4/10 | P2 |

---

# Part 3 — Architecture Evolution

## Current Architecture (as-is)

```
User Prompt
  → Regex/LLM intent classification
  → [if ANIMATE]:
    → Scene plan (LLM call #1, 20-30s)
    → Code generation (LLM call #2, 60-120s)
    → Layout validation (regex, instant)
    → Layout repair (LLM call #3, 20-30s, if issues)
    → Manim render (subprocess, 30-300s)
    → Self-heal retry (up to 1x)
    → Deterministic fallback (if all fail)
    → Voiceover merge (parallel with render)
    → Send to Telegram
```

**Problems:** 3 sequential LLM calls (slow), no intermediate representation (can't edit), no quality gate (can't reject bad output), no state (can't iterate).

## Proposed Architecture (to-be)

```
User Input (text/photo/LaTeX/voice)
  │
  ▼
┌─────────────────────────────────────────────┐
│  INPUT UNDERSTANDING LAYER                   │
│  ├─ Intent Router (regex + small classifier)│
│  ├─ Prompt Enhancer (vague → rich)         │
│  ├─ LaTeX Parser (equation → structured)    │
│  ├─ Vision Analyzer (photo → description)   │
│  └─ Voice Transcriber (audio → text)        │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│  EDUCATIONAL DECOMPOSITION                   │
│  ├─ Concept Identifier (what math topic?)   │
│  ├─ Prerequisites Resolver (what comes before?)│
│  ├─ Decomposition (multi-step → sub-scenes) │
│  └─ Curriculum Mapper (STEP/A-Level/IB tag) │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│  SCENE GRAPH GENERATION                      │
│  ├─ Storyboard Agent (phases, timing, beats)│
│  ├─ Visual Planner (layout, colors, layers) │
│  ├─ Asset Planner (which Manim objects)     │
│  ├─ Narration Planner (script + sync points)│
│  └─ Performance Estimator (weight budget)   │
│                                              │
│  OUTPUT: SceneGraph JSON (edit-able!)        │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│  CODE GENERATION                             │
│  ├─ Template Matcher (fast path, no LLM)    │
│  ├─ Code Generator (LLM, cached prompt)     │
│  ├─ Code Validator (syntax + API check)     │
│  └─ Code Optimizer (weight reduction)       │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│  QUALITY GATE                                │
│  ├─ Layout Validator (overlap, crowding)    │
│  ├─ Educational Correctness Check           │
│  ├─ Visual Aesthetic Scorer (1-5)           │
│  ├─ Performance Budget Check (< 40 pts)     │
│  └─ Critic Agent (overall quality: pass/fail)│
│                                              │
│  FAIL → Repair Agent (targeted fixes)       │
│  FAIL 2x → Simplify Agent (reduce scope)    │
│  FAIL 3x → Fallback (deterministic)         │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│  RENDER ENGINE                               │
│  ├─ Preview Renderer (-ql, 3 frames)        │
│  ├─ Full Renderer (-qm/-qh)                 │
│  ├─ Narration Synthesizer (edge-tts)        │
│  ├─ Audio-Video Merger (ffmpeg)             │
│  └─ Export Formatter (MP4/GIF/WebM/TikTok)  │
└──────────────┬──────────────────────────────┘
               ▼
┌─────────────────────────────────────────────┐
│  DELIVERY & MEMORY                           │
│  ├─ Send to Telegram (with inline buttons)  │
│  ├─ Store SceneGraph (for iteration)        │
│  ├─ Cache render (content hash → file_id)   │
│  ├─ Update user session (conversation state)│
│  └─ Log analytics (prompt, quality, timing) │
└─────────────────────────────────────────────┘
```

## Key Design Decisions

### Scene Graph DSL

The most important architectural change. Instead of going directly from plan → Manim code, introduce a structured intermediate representation:

```json
{
  "version": "1.0",
  "metadata": {
    "title": "Euler's Identity",
    "topic": "complex_analysis",
    "duration": 18,
    "theme": "visual_math"
  },
  "canvas": {
    "background": "#0B1026",
    "x_range": [-7, 7],
    "y_range": [-4, 4]
  },
  "objects": [
    {
      "id": "unit_circle",
      "type": "Circle",
      "params": {"radius": 2, "color": "#58C4DD", "stroke_width": 3},
      "position": "center",
      "enter": {"animation": "Create", "beat": 2, "duration": 2},
      "exit": {"animation": "FadeOut", "beat": 5}
    },
    {
      "id": "euler_point",
      "type": "Dot",
      "params": {"color": "#F5D547", "radius": 0.12},
      "position": "on:unit_circle:angle=PI",
      "enter": {"animation": "FadeIn", "beat": 4}
    }
  ],
  "beats": [
    {"id": 1, "time": [0, 3], "action": "atmosphere", "objects": ["stars", "title"]},
    {"id": 2, "time": [3, 7], "action": "construct", "objects": ["unit_circle", "axes"]},
    {"id": 3, "time": [7, 12], "action": "animate", "objects": ["euler_point", "trail"]},
    {"id": 4, "time": [12, 16], "action": "reveal", "objects": ["euler_equation"]},
    {"id": 5, "time": [16, 18], "action": "ambient", "objects": ["pulse_glow"]}
  ],
  "narration": {
    "script": "Euler's identity connects five fundamental constants...",
    "sync_points": [
      {"time": 3, "event": "circle appears"},
      {"time": 12, "event": "equation revealed"}
    ]
  },
  "performance": {
    "estimated_weight": 28,
    "updaters": 1,
    "max_objects_visible": 4
  }
}
```

**Why this matters:**
- **Editable** — user says "make it red" → modify `objects[id].params.color`, re-render only that object
- **Cacheable** — hash(scene_graph) → rendered video. Same concept, different theme → only swap colors
- **Template-friendly** — templates produce SceneGraphs, not raw code
- **Validatable** — check overlap, budget, correctness on the graph, not on generated code
- **Portable** — could render with Manim, Motion Canvas, or a web-based renderer

### State Management

```python
@dataclass
class RenderSession:
    session_id: str
    chat_id: int
    scene_graph: SceneGraph        # Current scene state
    render_history: list[RenderResult]  # All versions
    conversation: list[Message]    # Full context
    created_at: datetime
    last_modified: datetime

class SessionStore:
    """Redis-backed session storage with TTL."""
    def get(self, session_id: str) -> RenderSession
    def save(self, session: RenderSession) -> None
    def get_latest_for_user(self, chat_id: int) -> RenderSession | None
    def fork(self, session_id: str) -> RenderSession  # For iteration
```

### Failure Recovery (escalation ladder)

```
Level 1: Template match → deterministic code → render (fastest, most reliable)
Level 2: Cached SceneGraph → regenerate code → render (skip planning)
Level 3: Full pipeline → code gen → validate → render (normal path)
Level 4: Critic rejects → Repair Agent → re-render (targeted fix)
Level 5: Repair fails → Simplify Agent → reduced scene → render (graceful degradation)
Level 6: Simplify fails → Smart Fallback (topic-aware, not generic sin curve)
Level 7: Fallback fails → Error with debug info + suggested rephrasing
```

### Cost Optimization

| Strategy | Savings | Implementation |
|----------|---------|---------------|
| Prompt caching (system prompt) | 50% TTFT, 90% cost on prefix | Structure: static prompt first, user prompt last |
| Template fast path | 100% LLM cost for matched queries | Expand to 50+ templates |
| SceneGraph cache | 100% for identical requests | Content-hash lookup before any LLM call |
| Iteration reuse | 80% — only re-gen modified objects | Diff SceneGraph, regenerate delta |
| `enable_thinking: False` for simple tasks | 30% latency on classification/config | Already partially done |
| Batch LLM calls | 50% cost on OpenAI batch API | Queue non-urgent renders for batch processing |

---

# Part 4 — AI Improvements

## Specialized Agent Definitions

### 1. Planner Agent
**Input:** Enhanced prompt + user context + conversation history
**Output:** SceneGraph JSON
**Model:** GPT-5.5, reasoning_effort=high
**Responsibilities:**
- Decompose concept into 3-5 visual beats
- Assign objects to spatial positions (respecting hardware budget)
- Plan timing and transitions
- Select animation types appropriate to content
- Flag educational prerequisites

### 2. Code Generator Agent
**Input:** SceneGraph JSON + theme config
**Output:** Valid Manim Python code
**Model:** GPT-5.5 or Qwen 3.7 Max, reasoning_effort=high
**Responsibilities:**
- Translate SceneGraph into executable Manim code
- Apply theme colors and styling
- Stay within performance budget
- Use correct Manim CE APIs

### 3. Critic Agent
**Input:** SceneGraph + generated code + (optionally) rendered frames
**Output:** Quality scores + pass/fail + improvement suggestions
**Model:** GPT-5.5, reasoning_effort=medium
**Scoring dimensions:**
- **Clarity** (1-5): Is the math concept clearly visible?
- **Aesthetics** (1-5): Colors, spacing, motion quality
- **Accuracy** (1-5): Are equations correct? Is the visualization faithful?
- **Pacing** (1-5): Does timing match content complexity?
- **Completeness** (1-5): Does it tell a complete visual story?

**Pass threshold:** Average ≥ 3.5, no dimension < 2

### 4. Education Agent
**Input:** SceneGraph + original prompt
**Output:** Correctness verification + educational suggestions
**Responsibilities:**
- Verify mathematical equations are correct
- Check that visual representation matches mathematical truth
- Suggest prerequisite concepts if topic is advanced
- Generate narration that explains *why*, not just *what*

### 5. Repair Agent
**Input:** Failed code + error message + SceneGraph
**Output:** Fixed code
**Specializations:**
- **API errors:** wrong Manim method names, deprecated kwargs
- **Layout errors:** overlap, off-screen objects, font too small
- **Performance errors:** too many updaters, heavy surfaces
- **Logic errors:** wrong equation, incorrect parameterization

### 6. Enhancement Agent
**Input:** User's raw prompt
**Output:** Enhanced prompt with visual details
**Example:**
```
Input:  "eigenvalues"
Output: "Animate a 2D linear transformation showing how eigenvectors remain
         on their span while other vectors rotate. Display the characteristic
         polynomial det(A - λI) = 0, show eigenvalues λ₁, λ₂ as colored dots
         on the number line, and trace how the unit circle deforms into an
         ellipse aligned with the eigenvectors."
```

## Agent Handoff Protocol

```
User Prompt
  │
  ├─ Enhancement Agent ──→ Enhanced Prompt
  │                            │
  ├─ Planner Agent ──────→ SceneGraph JSON
  │                            │
  │   ┌───── Education Agent validates SceneGraph ─────┐
  │   │  PASS: continue                                 │
  │   │  FAIL: Planner Agent revises with feedback      │
  │   └─────────────────────────────────────────────────┘
  │                            │
  ├─ Code Generator ─────→ Manim Code
  │                            │
  │   ┌───── Critic Agent scores code ─────────────────┐
  │   │  PASS (≥3.5): send to renderer                  │
  │   │  FAIL (<3.5): Repair Agent fixes, retry 2x      │
  │   │  FAIL 3x: Simplify Agent reduces scope           │
  │   └─────────────────────────────────────────────────┘
  │                            │
  ├─ Renderer ──────────→ Video
  │                            │
  │   ┌───── Post-render Critic (optional) ────────────┐
  │   │  Analyze 3 extracted frames                     │
  │   │  If quality < threshold: flag for user review   │
  │   └─────────────────────────────────────────────────┘
  │                            │
  └─ Delivery ──────────→ Telegram + Session Store
```

## Improved Planning

1. **Conversation-aware planning** — if user previously animated "matrices", the planner knows to reference that visual style
2. **Curriculum-aware decomposition** — "Fourier series" → planner knows this needs: periodic function, harmonics building up, frequency spectrum
3. **Hardware-first planning** — planner estimates weight BEFORE code gen, adjusts complexity to budget
4. **Beat timing optimization** — each beat gets duration proportional to its cognitive load (simple = 2s, complex = 5s)

## Quality Scoring Algorithm

```python
def score_scene(scene_graph: SceneGraph, code: str, frames: list[Image]) -> QualityScore:
    scores = {}

    # 1. Static analysis (fast, no LLM)
    scores["performance"] = 1.0 if estimate_weight(code) < 40 else 0.5
    scores["layout"] = 1.0 - len(validate_layout(code)) * 0.2
    scores["api_correctness"] = check_manim_api_usage(code)

    # 2. LLM-based scoring (1 call, structured output)
    llm_scores = critic_agent.evaluate(scene_graph, code)
    scores["clarity"] = llm_scores.clarity / 5.0
    scores["aesthetics"] = llm_scores.aesthetics / 5.0
    scores["accuracy"] = llm_scores.accuracy / 5.0
    scores["pacing"] = llm_scores.pacing / 5.0

    # 3. Visual analysis (if frames available)
    if frames:
        scores["visual_clutter"] = detect_clutter(frames)
        scores["color_harmony"] = analyze_palette(frames)

    # Weighted average
    weights = {"clarity": 0.25, "aesthetics": 0.2, "accuracy": 0.25,
               "pacing": 0.1, "performance": 0.1, "layout": 0.1}
    total = sum(scores[k] * weights[k] for k in weights)

    return QualityScore(scores=scores, total=total, pass_=total >= 0.7)
```

---

# Part 5 — Product Strategy

## Positioning

**"The fastest way to see any mathematical idea."**

Not "a Manim code generator." Not "an AI animation tool." A **visual intuition engine** — type any concept, see it animated in under 2 minutes.

## Target Customer

**Primary:** STEM students (16-25) studying pure math, physics, engineering.
- STEP/A-Level/IB students who need visual intuition for abstract concepts
- University students struggling with proofs and theorems
- Self-learners following 3Blue1Brown-style content

**Secondary:** Educators and content creators
- Teachers who want quick visual aids for lectures
- TikTok/YouTube math creators who need animation assets
- Tutors who want to show students visual explanations

**Tertiary:** Developers and platforms
- EdTech companies that want animation APIs
- Textbook publishers who want interactive supplements
- Online course platforms (Coursera, Khan Academy)

## Why Not Write Manim Manually?

| Factor | Manual Manim | Bot |
|--------|-------------|-----|
| Time to first animation | 2-4 hours (learning curve) | 2 minutes |
| Iteration speed | Edit → render → wait 2 min | Reply "make it red" → 30s |
| Error debugging | Read tracebacks, Google API docs | Auto-repair |
| Quality floor | Depends on skill | Minimum 3.5/5 quality gate |
| Templates | Build from scratch | 50+ battle-tested |

## Why Not Generic AI Video?

| Factor | Sora/Runway | Manim Bot |
|--------|------------|-----------|
| Mathematical accuracy | Hallucinated visuals | Verified equations |
| Precision | "Looks like math" | Actually IS math |
| Editability | Re-generate from scratch | Modify specific elements |
| Educational value | Entertainment | Genuine learning |
| LaTeX input | Not supported | Native |

## Moat

1. **Template library** — 500+ templates covering entire STEM curricula (years to replicate)
2. **SceneGraph DSL** — enables editing, caching, remixing that competitors can't easily replicate
3. **Educational intelligence** — curriculum-aware planning that understands *what* to teach
4. **Community flywheel** — shared animations → more users → more templates → better quality
5. **Data advantage** — millions of prompt→quality→satisfaction data points → fine-tuned models

## Roadmaps

### 1-Year Roadmap
- Q1: Iteration loop, inline mode, LaTeX input, 50 templates, quality gate
- Q2: Scene graph DSL, educational agent, gallery, TikTok export
- Q3: Stars monetization, API access, curriculum mapping (STEP/A-Level/IB)
- Q4: Teacher mode, batch sequences, multi-language narration, 200 templates

### 3-Year Roadmap
- Year 2: Web app (beyond Telegram), render farm, collaborative editing, embeddable player
- Year 3: AI tutor (full courses with spaced repetition), B2B enterprise, university partnerships

## Most Likely Failure Modes

1. **LLM cost explosion** — at scale, 5 LLM calls per render at $0.01-0.05 each = $0.05-0.25 per render. At 100K users × 3 renders/day = $15K-75K/day. **Mitigation:** template fast path (0 LLM calls), SceneGraph caching, batch API.

2. **Quality inconsistency** — LLMs are stochastic; 20% of outputs may be bad. **Mitigation:** quality gate with auto-retry, expand template library to cover 80% of queries.

3. **Telegram platform risk** — Telegram changes bot API, rate limits, or monetization rules. **Mitigation:** build web app as backup, keep Telegram as distribution channel not platform dependency.

4. **Competition from OpenAI/Google** — they add "math animation" to ChatGPT/Gemini. **Mitigation:** moat is in educational intelligence + templates + community, not raw rendering.

5. **Render infrastructure** — scaling from 1 laptop to 100K users requires cloud GPU infrastructure. **Mitigation:** template rendering is CPU-cheap; only full-gen needs GPU workers.

---

# Part 6 — 20+ Telegram Superpowers

| # | Feature | Description | Impact |
|---|---------|-------------|--------|
| 1 | **Inline mode** | `@manimbot fourier series` → generates preview in any chat | Discovery |
| 2 | **Reply-to-modify** | Reply to any animation with "slower" / "red" / "add axis" | Core UX |
| 3 | **Voice → animation** | Send voice message describing concept → animation | Accessibility |
| 4 | **Photo → animation** | Send textbook photo → animated walkthrough | Viral |
| 5 | **Group live mode** | In group: teacher sends `/live eigenvalues` → all see animation sync'd | Classroom |
| 6 | **Pin-to-learn** | Pin an animation → bot quizzes you on it after 1 day, 3 days, 7 days | Retention |
| 7 | **Animation threads** | Reply to animation → creates a branch (v2, v3...) | Iteration |
| 8 | **Poll-driven animation** | Group poll: "what should we animate?" → winner auto-renders | Engagement |
| 9 | **Daily theorem** | Scheduled push at 9 AM: animated theorem of the day | Habit |
| 10 | **Sticker pack** | Export key frames as Telegram sticker pack | Sharing |
| 11 | **Quiz mode** | Bot sends animation → hides result → multiple choice → reveal | Education |
| 12 | **Reaction analytics** | Track which animations get ❤️ vs 👎 → improve quality | Quality |
| 13 | **Video note mode** | Send circular video note → bot animates what you describe | Novelty |
| 14 | **Scheduled animations** | "Animate this every Monday at 8am for my study group" | Utility |
| 15 | **Channel integration** | Auto-post animations to a channel with LaTeX description | Content |
| 16 | **Mini App settings** | Telegram Mini App for rich settings UI (color picker, timeline) | UX |
| 17 | **Paid media** | Sell premium animation packs via Telegram Stars | Revenue |
| 18 | **Game mode** | "Guess the function" — animate a curve, user guesses the equation | Fun |
| 19 | **Collaborative canvas** | Group members each add one element to a shared scene | Social |
| 20 | **Bot-to-bot protocol** | Let math solver bots request animations from your bot | Platform |
| 21 | **Animated profile** | Generate a looping animation for user's profile video | Personalization |
| 22 | **Webhook events** | Notify user via bot when their HD render finishes | Async UX |
| 23 | **Topic threads** | Bot organizes animations by topic in forum-enabled groups | Organization |
| 24 | **Gift animations** | "Send this animation to @friend as a birthday gift" | Social |

---

# Part 7 — 30 "Wow" Features

Features that would make users screenshot and share:

| # | Feature | The "Wow" |
|---|---------|-----------|
| 1 | **Textbook → animated lesson** | Photo a page → get a 30-second animated explanation |
| 2 | **Handwriting → animation** | Photo your handwritten notes → animated, cleaned-up version |
| 3 | **Full lecture from one topic** | "Teach me Fourier series" → 5 connected animations + narration + quiz |
| 4 | **Research paper animator** | Paste arXiv link → animated summary of key results |
| 5 | **Interactive parameter playground** | Inline buttons change parameters in real-time, re-render 3s preview |
| 6 | **"Explain like I'm 5" mode** | Same concept, simplified visual metaphor |
| 7 | **Side-by-side comparison** | "Riemann vs Lebesgue integration" — split screen, synchronized |
| 8 | **Math fight mode** | Two users submit approaches, bot animates both, group votes |
| 9 | **Proof cinema** | Animated proof where each step appears with narration + highlight |
| 10 | **Dimensional explorer** | "Show me this in 2D, 3D, and 4D projection" |
| 11 | **Historical context** | "Euler's identity" → animated history: Euler's life, the discovery, the impact |
| 12 | **Sound-reactive math** | Upload music → FFT → animated frequency decomposition |
| 13 | **Physics simulator** | "Drop a ball from 10m" → real physics simulation, not just illustration |
| 14 | **Code → animation** | Paste Python/numpy code → animated visualization of what it computes |
| 15 | **LaTeX document → video series** | Upload a .tex file → generate animation for each section |
| 16 | **Mistake finder** | "Show me WHERE students typically make errors in integration by parts" |
| 17 | **Concept constellation** | Visual map of how concepts relate, animated connections |
| 18 | **Time travel** | "Show me how Newton would have visualized this vs how we do today" |
| 19 | **Zoom infinity** | Mandelbrot-style infinite zoom into any mathematical structure |
| 20 | **Dual narration** | "Explain this both intuitively AND rigorously" — two audio tracks |
| 21 | **Live coding** | Show the Manim code being written in real-time alongside the render |
| 22 | **A/B visualization** | "Show me two different ways to visualize eigenvalues" — side by side |
| 23 | **Animated flashcards** | Generate a deck of animated flashcards from any chapter |
| 24 | **Problem → solution movie** | Photo a homework problem → step-by-step animated solution |
| 25 | **Emoji math** | "🔵 + 📐 = ?" → animate the geometric meaning of circle + triangle |
| 26 | **Music video mode** | Full-screen animation synced to a song, with math overlays |
| 27 | **Collaborative proof** | Group chat: each person adds one step, bot animates the full chain |
| 28 | **Real-world overlay** | "Show me the parabola in this photo of a fountain" |
| 29 | **AI debate** | "Is the Axiom of Choice necessary?" — two AI agents debate with animations |
| 30 | **Personal math documentary** | "Tell me the story of calculus" → 3-minute narrated animation documentary |

---

# Part 8 — Prioritized Execution Plan

## Phase 1: Foundation (2 weeks) — "Fix the Core"

| Task | Impact | Effort | Risk | Value |
|------|--------|--------|------|-------|
| **Iteration loop** — reply to animation with modifications | 10/10 | 5 days | Low | Retention — users come back to refine |
| **Prompt enhancement** — expand vague prompts before generation | 7/10 | 1 day | None | Quality — better input = better output |
| **Inline mode** — `@manimbot query` in any chat | 9/10 | 2 days | Low | Discovery — 5x new users |
| **Quality buttons** — Fast/Standard/HD inline keyboard | 5/10 | 0.5 days | None | UX — user control |
| **Preview frames** — send 3 static frames before full render | 8/10 | 2 days | Low | Perceived speed |
| **Render caching** — hash(prompt) → cached file_id | 7/10 | 1 day | Low | Speed + cost |

**Total: ~12 days. Transformative.**

## Phase 2: Differentiation (1 month) — "Build the Moat"

| Task | Impact | Effort | Risk | Value |
|------|--------|--------|------|-------|
| **SceneGraph DSL** — intermediate representation | 9/10 | 2 weeks | Medium | Foundation for everything above |
| **LaTeX → animation** — parse equations to visual | 8/10 | 3 days | Low | Student utility |
| **Critic Agent** — auto-score quality, reject bad output | 8/10 | 3 days | Low | Quality floor |
| **50 templates** — expand from 14 to 50 | 7/10 | 1 week | Low | 80% template hit rate |
| **Gallery channel** — public showcase of best animations | 7/10 | 2 days | Low | Growth loop |
| **TikTok export** — 9:16, hooks, CTA, watermark | 8/10 | 3 days | Low | Viral growth |
| **Voice input** — voice message → animation | 6/10 | 2 days | Low | Accessibility |

**Total: ~5 weeks. Category-leading.**

## Phase 3: Platform (3 months) — "Become Infrastructure"

| Task | Impact | Effort | Risk | Value |
|------|--------|--------|------|-------|
| **Education Agent** — curriculum-aware decomposition | 8/10 | 2 weeks | Medium | Educational impact |
| **Photo → animation** — textbook to walkthrough | 9/10 | 2 weeks | Medium | Viral + utility |
| **Interactive parameters** — inline buttons change values | 8/10 | 1 week | Low | Engagement |
| **Stars monetization** — freemium tiers | 8/10 | 1 week | Low | Revenue |
| **API access** — render pipeline as a service | 7/10 | 2 weeks | Medium | Platform play |
| **Multi-language narration** — 10 languages | 6/10 | 3 days | Low | Global reach |
| **Quiz mode** — animation + question + reveal | 8/10 | 1 week | Low | Education + retention |
| **Share links** — `manim.bot/v/abc123` | 8/10 | 1 week | Low | Distribution |

**Total: ~3 months. Defensible business.**

## Phase 4: Vision (6+ months) — "Category-Defining"

| Task | Impact | Effort | Risk | Value |
|------|--------|--------|------|-------|
| **Web app** — beyond Telegram | 9/10 | 2 months | Medium | Platform independence |
| **Render farm** — GPU cloud workers | 8/10 | 1 month | Medium | Scale to 100K users |
| **AI tutor** — full courses with spaced repetition | 9/10 | 3 months | High | EdTech disruption |
| **Collaborative editing** — real-time multi-user scenes | 7/10 | 2 months | High | Social platform |
| **Research paper animator** — arXiv → visual summary | 8/10 | 1 month | Medium | Academic market |
| **Enterprise/white-label** — universities, publishers | 6/10 | 2 months | Medium | B2B revenue |
| **Physics simulator** — real physics, not just illustrations | 8/10 | 2 months | High | Scientific tool |
| **Personal math documentary** — AI-generated educational films | 9/10 | 3 months | High | Cultural impact |

**Total: ~12 months. New category.**

---

# Appendix: Implementation Priorities

## If You Can Only Do 5 Things This Week

1. **Iteration loop** — `reply with "change X"` → modify scene → re-render. This single feature doubles retention.
2. **Inline mode** — 1 day of work, 5x discovery. No-brainer.
3. **Prompt enhancement** — 50 lines of code, immediate quality improvement.
4. **Render caching** — content-hash lookup, eliminates redundant renders.
5. **Quality buttons** — let users choose speed vs quality. Reduces frustration.

## If You Can Only Do 1 Thing This Month

**Build the SceneGraph DSL.** Everything else — iteration, caching, editing, remixing, templates, quality gates — becomes 10x easier with a structured intermediate representation. It's the foundation of the next-generation architecture.

---

*End of blueprint. The bot is good. The platform it could become is extraordinary.*
