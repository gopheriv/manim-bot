# Manim Bot — Quality-First Architecture Review

*Brutally honest, evidence-based teardown — 2026-06-27*

**Premise of this review:** You stated the only thing you care about is **output quality** —
visually polished, professionally directed, creatively composed, narration-synced, style-consistent
Manim videos with no AI slop and no timing/transition bugs. You explicitly do **not** care about
tokens, latency, cost, or simplicity, and you assume **unlimited compute / render time**.

Read against that goal, the single most important finding is this:

> **Almost every load-bearing design decision in this codebase optimizes for the exact opposite of
> what you want.** The system is architected end-to-end to *survive an 8 GB laptop* and *never show
> the user an error* — at the direct expense of resolution, ambition, cinematography, and polish.
> It is a reliability/cost-minimizing system wearing a quality-maximizing product description.

The rest of this document is the evidence.

---

## 0. How to read the severity tags

- 🔴 **Fatal to the goal** — actively caps quality; no amount of compute helps until it's redesigned.
- 🟠 **Major** — significantly limits ceiling or introduces slop/desync.
- 🟡 **Bug / incoherence** — concrete defect or self-contradiction that degrades output.

---

## 1. 🔴 The whole pipeline is a hardware-survival system, not a quality system

This is not a vibe; it is written into the prompts, the renderer, and the config.

**The code generator's own system prompt is explicitly anti-ambition.** From
[prompt_builder.py:1-6](prompt_builder.py):

> *"Philosophy: elegant minimalism over cinematic excess. A beautiful 3-layer scene that renders in
> 10s beats a 7-layer scene that OOMs on 8GB RAM."*

It then hard-codes that aesthetic into the model:

- `STYLE_DIRECTIVES`: *"Every scene has exactly 3 layers"* ([prompt_builder.py:35-55](prompt_builder.py)).
- `HARDWARE_BUDGET`: *"max 40 points total"*, `Surface`/`ParametricSurface` = **FORBIDDEN**,
  `always_redraw` **max 2 total**, *"When in doubt: simpler wins … leave it out"*
  ([prompt_builder.py:59-89](prompt_builder.py)).
- `ANTI_LAZY` sets the *quality floor* at *"At least 3 animated objects"* — i.e. the bar for
  "not lazy" is three objects ([prompt_builder.py:104-110](prompt_builder.py)).
- Total duration is clamped to **12–25 seconds** ([prompt_builder.py:24](prompt_builder.py)),
  and *"Max 150 total animation frames"* / *"stay under 200 frames"*.

**The renderer enforces the same ceiling at runtime.** [renderer.py:38-92](renderer.py) computes a
"scene weight" and if a scene scores ≥ 40 it is declared *heavy* and **silently downgraded to 480p,
15 fps, caching disabled, below-normal CPU priority** ([renderer.py:153-187](renderer.py)). A
`Surface` alone is +30, two updaters +16 — so any genuinely cinematic scene trips the heavy path
and gets **force-rendered at `-ql` 480p15**, the *lowest* quality Manim offers.

**The config defaults reinforce it.** `MANIM_QUALITY = -qm` → 720p ([config.py:59](config.py));
`MAX_CONCURRENT_RENDERS = 1` *"on i5/8GB RAM"* ([config.py:64](config.py)); the render dir and memory
guards (`> 85%` block, `> 92%` kill) are all tuned to one specific laptop
([renderer.py:135-141, 224-239](renderer.py)).

**Why this is fatal to your goal:** you said you have unlimited compute, but the system has no
concept of "more compute = better video." There is no 1080p/4K path, no 60 fps path, no high-sample
anti-aliasing, no `Surface`/3D path that actually survives. The quality ceiling is *welded shut* at
720p/30fps for "simple" scenes and 480p/15fps for anything ambitious. **Every knob points down.**
Even if you swapped in a render farm, the prompts would still instruct the model to make a 3-layer,
sub-25-second, Surface-free animation. The constraint lives in the *prompt*, not just the hardware.

> **Verdict:** This is the #1 thing preventing world-class output. The "hardware budget" needs to
> become a *tier* that scales with available compute, not a global law baked into every prompt.

---

## 2. 🔴 Wrong model doing the most important job, with reasoning disabled

The most creatively demanding task in the system — turning a concept into a directed animation — is
handed to a model with its reasoning turned **off**.

- Code generation runs on `GPT_MODEL`, which despite the "GPT-5.5" comments everywhere is actually
  **`qwen3.7-max`** ([config.py:38](config.py) — `MANIM_MODEL` default `qwen3.7-max`; the
  module docstring at [llm.py:1](llm.py) confirms "Qwen 3.7 Max code gen").
- Every code-gen call passes `extra_body={"enable_thinking": False}`
  ([llm.py:77-79](llm.py), applied in `generate_manim_code`, `fix_manim_code`, `repair_layout`,
  `generate_scene_plan`). For the one task where chain-of-thought matters most — spatial reasoning,
  timing, composition — **thinking is explicitly disabled**.
- `max_tokens=8192` ([llm.py:93](llm.py)) hard-caps the program at ~500–600 lines. A multi-scene,
  professionally directed Manim file routinely exceeds that; the cap guarantees truncation →
  syntax error → fallback for the most ambitious requests.
- The strongest models present in the codebase — **Claude Opus 4.8** and the Anthropic client —
  are wired **only into chat/vision/intent** ([llm.py:276-296, 334-355](llm.py)), never into code
  generation. The frontier model never touches the artifact you care about.

**Why this is fatal:** "world-class" creative direction from a non-frontier model with reasoning
disabled and a 8k output ceiling is not achievable. With unlimited budget you would do the opposite
of all three choices: best available model, **maximum** reasoning effort, large/uncapped output, and
likely *best-of-N* sampling (see §15).

---

## 3. 🔴 There is no intermediate representation — so there is no cinematography

The product vision document in this very repo ([PRODUCT_VISION.md:269-333](PRODUCT_VISION.md))
correctly identifies the fix — a **SceneGraph DSL** — and then it was never built. What exists:

- One LLM call emits **one flat `GenScene.construct()`** as raw Python
  ([prompt_builder.py:13-31](prompt_builder.py): *"`class GenScene(Scene):` with `def construct`"*).
- There is no storyboard object, no beat list with timing, no shot/scene sequence, no camera plan,
  no transition graph — nothing the system can *reason over, edit, or validate as a composition*.
- "Cinematography" in Manim means scene-to-scene cuts, camera moves, `MovingCameraScene` framing,
  match-cuts between related objects, pacing curves. None of that is represented or planned. The
  generator is asked for one continuous single-screen scene under 25 seconds.

**Consequence for every creative goal you listed:**
- *Strong animation direction & cinematography* — impossible to plan or check; it's whatever one
  token stream happened to produce.
- *Creative scene composition* — capped at "exactly 3 layers" on one screen (§1).
- *No broken transitions* — there is no transition model to validate; transitions are implicit in
  text.
- *Consistent visual style* — nothing carries style state across shots because there are no shots.

Without a structured intermediate representation, the system cannot *direct* anything. It can only
*ask and hope*. This is the deepest architectural limitation in the codebase.

---

## 4. 🔴 The narration↔visual synchronization you want is architecturally impossible here

You asked specifically for *"accurate synchronization between narration, visuals, and animations."*
The current design makes that unreachable, by construction:

- Narration is generated **from the prompt, not from the code or the rendered animation**
  ([bot.py:806-826](bot.py) `_generate_narration` feeds only the text prompt to the LLM), and it is
  generated **in parallel with the render** ([bot.py:591-606](bot.py)) so it *cannot* know what the
  animation actually does or when events happen.
- The narrator prompt's idea of "sync" is *"write a tight 12-18 second narration … Match a 12-20
  second video so the last frame is not frozen"* ([bot.py:811-817](bot.py)) — i.e. match a *duration
  guess*, not events.
- The merge step is pure duration arithmetic: if audio is longer, **freeze the last video frame** to
  pad; if shorter, **append silence** ([voiceover.py:88-141](voiceover.py)). There is no alignment of
  spoken phrases to visual beats.
- The padding behavior directly *reintroduces* the dead/frozen final frame that the generation prompt
  works hard to forbid (`ANTI_LAZY`: *"Final 2s: ambient motion … NOT a freeze frame"*,
  [prompt_builder.py:108](prompt_builder.py)). The narration system undoes the animation system.

The vision doc again describes the right thing (`narration.sync_points` keyed to beats,
[PRODUCT_VISION.md:313-319](PRODUCT_VISION.md)) and it does not exist. Real sync requires the
animation to expose timestamped beats (which requires §3's scene graph) and the narration/TTS to be
time-stretched or scheduled against them. None of that machinery is present.

---

## 5. 🔴 No visual feedback loop — a visual medium judged only as text

Every "quality" check in the system reads **source code as a string**. Nothing ever looks at a
rendered frame. You cannot evaluate visual polish, composition, color harmony, real overlap,
readability, or motion quality without *seeing the pixels* — and the pipeline never does.

- `critique_code` scores "aesthetic", "visual_clarity", etc. from the **code text only**
  ([critic_agent.py:79-129](critic_agent.py)).
- The `Judge` reviews **code text only** ([judge_ai.py:121-213](judge_ai.py)).
- `review_education` reviews **code text only** ([edu_reviewer.py:98-153](edu_reviewer.py)).
- `validate_layout` is **regex over code** with no geometry ([scene_validator.py](scene_validator.py)).

Tellingly, the repo contains `temp_frames/` with `extract_keyframes.py`, `analyze_frames.py`, and
`code_review.py` — someone clearly did frame extraction + vision analysis **by hand, once**, and it
was never wired into the pipeline. The capability exists (the vision clients in
[llm.py:301-355](llm.py)); it is simply not in the loop.

**Why this is fatal:** "no AI slop", "visually polished", "no overlap in practice" are *visual*
properties. A pipeline that never renders-then-looks cannot enforce them. With unlimited compute the
obvious move is: render a draft → extract keyframes → have a vision model critique the *actual image*
→ regenerate. That loop is absent.

---

## 6. 🟠 The "quality gates" are theater — they score, then discard

The system has an impressive-looking lineup of review agents. In the main pipeline, most of them
**produce a score and then do nothing with it.** Walk the actual control flow in
[bot.py:435-562](bot.py):

- **Critic Agent** ([critic_agent.py](critic_agent.py)): result is logged
  (`logger.info(f"Critic score: …")`, [bot.py:438](bot.py)) and passed to the Judge as *context*.
  Its own `needs_repair`/`passes` thresholds are never used to trigger a repair. A 2/10 critic score
  changes nothing.
- **Education Reviewer** ([edu_reviewer.py](edu_reviewer.py)): on `is_correct == False` it logs a
  warning ([bot.py:448-449](bot.py)) and **proceeds to render the mathematically wrong animation
  anyway.** There is no branch that blocks or repairs on educational failure. So "verified equations"
  is not actually verified — it's *logged*.
- **Judge** is the *only* gate with teeth — and it's capped at **2 iterations**, on a separate model
  (`MiniMax-M3`), and on failure it defaults to **ACCEPT** ([judge_ai.py:215-225](judge_ai.py)). Any
  Judge error → code ships unreviewed.

So the architecture *looks* like a multi-stage quality funnel, but in practice it is: generate →
(log some scores) → Judge maybe-fixes bugs twice → render. The scoring agents add latency and the
appearance of rigor without affecting the output. For a quality-first system this is the worst of
both worlds: cost of review, none of the benefit.

---

## 7. 🟡 The scene planner is silently dead — schema mismatch guarantees it fails

The "Scene Awareness: plan → generate → validate → repair" pillar advertised at
[bot.py:365-403](bot.py) is, for the LLM path, **effectively off** because of a contract mismatch:

- `parse_scene_plan` **requires** every object to contain the field `role`:
  `required_fields = {"id", "type", "role", "position", "priority", "visible_from", "visible_to"}`
  ([scene_planner.py:62](scene_planner.py)). If any object lacks `role`, it returns `None`.
- But the prompt that asks the model for the plan **never mentions `role`**. Its schema is
  `{"id", "type", "position", "priority", "visible_from", "visible_to"}`
  ([prompt_builder.py:168-184](prompt_builder.py); confirmed: `grep role prompt_builder.py` →
  no matches).

So the model is asked for a schema that **cannot pass validation**. Every plan is rejected with
*"Scene plan object missing fields: {'role'}"*, the exception path logs *"Scene plan parsing failed,
proceeding without plan"* ([bot.py:374-378](bot.py)), and code is generated **with no layout plan**.
The headline "scene awareness" feature is dark in normal operation, and nobody would notice because
its failure is deliberately non-fatal.

Relatedly, `scene_awareness.py`'s `SceneLayout` helper — an overlap-resolving placement system — is
**dead code**: `grep` finds it referenced only inside its own file. The generated code is never told
to import or use it, so its overlap avoidance never runs.

---

## 8. 🟠 Layout "validation" and "repair" are shallow regex with no geometry

What *does* run for layout is [scene_validator.py](scene_validator.py): a bag of regexes that count
`.move_to(ORIGIN)`, look for `next_to(` without `buff`, `VGroup(` without `.arrange()`, etc. It has
no model of the screen, no bounding boxes, no actual overlap detection, no off-screen detection, no
z-order, no contrast checking. It will:

- **Miss** real overlap that uses coordinates instead of `ORIGIN` (the common case).
- **False-positive** on legitimate code (e.g. a `VGroup` built then arranged 200 chars later than the
  window it scans, [scene_validator.py:148-150](scene_validator.py)).

When it fires, "repair" is **another full LLM rewrite** ([llm.py:155-181](llm.py),
`repair_layout`) that can change the whole scene while claiming to only fix spacing — there is no
diff, no guarantee it preserved anything. So the layout subsystem both under-detects the bugs you
care about and can introduce new ones while "fixing" phantom ones.

---

## 9. 🟠 Two contradictory, partly-applied style systems → inconsistent look

You asked for *consistent visual style*. The codebase has **at least three** style regimes that
disagree, and which one you get depends on an invisible routing decision:

1. **Theme path (LLM):** `build_theme_prompt(theme)` injects a palette, e.g. Visual Math's navy
   `#0B1026` + `#58C4DD`/`#F5D547` ([themes.py:79-96](themes.py)).
2. **Template path:** deterministic templates **hard-code a different background** `#0A0A0F` and a
   **different palette** `["#06B6D4", "#10B981", "#8B5CF6"]` ([templates/base.py:80-90, 25](templates/base.py)).
   The user's chosen theme is **never applied** to template output. Same bot, same theme setting, two
   visibly different looks depending on whether a keyword happened to match a template.
3. **TikTok path:** `get_tiktok_prompt` ([prompt_builder_tiktok.py:206-227](prompt_builder_tiktok.py))
   builds the prompt from `BASE_MANIM_RULES + TIKTOK_FORMAT_RULES + SCENE_AWARENESS` **and drops the
   theme, the `STYLE_DIRECTIVES`, the `HARDWARE_BUDGET`, and `ANTI_LAZY` entirely.** It also uses a
   *different* duration contract (25–30 s vs 12–25 s) and *different* font-size rules. So TikTok
   renders are stylistically unrelated to everything else and unconstrained by the hardware budget the
   rest of the system treats as sacred.

On top of that, when the Judge issues a **REJECT**, the regeneration call
([bot.py:531-534](bot.py)) is `generate_manim_code(prompt + "AVOID: …")` **with no
`theme_instructions` and no `scene_plan`** — so a rejected-then-regenerated animation loses the
palette and reverts to default colors. Style consistency is not a property the system maintains;
it's an accident of which branch ran.

---

## 10. 🟠 The failure ladder degrades *quality* silently, and the floor is near-zero

The self-healing story sounds good ("users almost never get an error") but every rung trades quality
down, and the bottom rung is essentially nothing:

1. On render failure, the repair prompt tells the model to **strip the animation down**:
   *"SIMPLIFY the scene: reduce object count, remove heavy updaters, fewer self.play() calls, shorter
   duration"* ([bot.py:652-655](bot.py)).
2. If repair fails, the **deterministic fallback** is — after a recent commit that "simplified" it —
   literally a title `Text` that fades in and out over ~3.5 seconds and nothing else
   ([fallback_scene.py:20-39](fallback_scene.py)). That is shipped to the user as their "animation",
   captioned only as a *"safe fallback animation"* ([bot.py:685](bot.py)).

So the realized distribution of outputs is bimodal: a decent 3-layer clip, or a blank title card —
with a silent slide between them on any hard prompt. For a quality-first product the fallback should
be the *last* thing you ever show; here it is a first-class, frequently-reachable outcome, and the
"healing" actively removes ambition rather than fixing the root cause.

---

## 11. 🟠 Templates are frozen, off-theme, and demonstrably buggy — not "battle-tested"

Templates are presented as the reliable fast path ("proven, pre-tested",
[templates/base.py:1-6](templates/base.py)). Inspecting them:

- **Off-theme** (see §9): hard-coded `#0A0A0F` background and a cyan/green/purple palette regardless
  of the user's theme.
- **Mathematically/visually sloppy.** In `RiemannSumTemplate`
  ([templates/calculus.py:43-67](templates/calculus.py)) the rectangle height is built in
  **screen space** (`axes.y_axis.unit_size * h`) but the rectangle is centered in **data space**
  (`axes.c2p(x_i + dx/2, h/2)`) — these don't compose correctly, so the bars generally won't sit
  flush on the axis. It silently uses a **left-endpoint** Riemann sum without labeling it as such,
  and renders the final answer with `Text("∫_0^4 …")` so the integral shows literal `_0^4`
  underscores instead of proper limits.
- **Violate the system's own rules.** The shared `_star_field` helper
  ([templates/base.py:99-119](templates/base.py)) creates **25 per-dot `add_updater` calls** — the
  `HARDWARE_BUDGET` allows *2 total* — passes `Dot(..., opacity=0.3)` (not a valid Dot constructor
  kwarg in Manim CE), and drives drift with `math.sin(dt * 0.5)` where `dt` is the per-frame delta,
  not elapsed time, so the motion is a near-constant micro-nudge rather than a drift.

Because templates are deterministic, these defects are *frozen in* and shipped verbatim whenever the
keyword matcher fires. And the matcher fires easily: threshold is **0.2**
([templates/registry.py:23](templates/registry.py)) with crude substring scoring
([templates/base.py:54-73](templates/base.py)), so prompts get captured by a template whose visual
language doesn't match the request or the theme.

---

## 12. 🟠 "Iteration" throws the previous render away and regenerates from a string

You listed *no desync / no broken transitions / consistent style*, all of which benefit from being
able to *edit* a known-good animation. The system can't. The follow-up/edit path
([bot.py:1688-1700](bot.py)) does:

```python
combined_prompt = f"{original_prompt}. EDIT: {text}"   # "make it slower"
await _send_animation(message, combined_prompt, …)      # full regeneration from scratch
```

It **does not pass the previous code** to the model (the prior code *is* in the DB —
[bot.py:1692-1694](bot.py) reads it — and then ignores it). "Make it slower" therefore produces a
*completely different* animation, not a slowed version of the one the user liked. Every iteration is a
fresh dice roll; visual continuity across a "thread" is impossible. True iteration requires editing a
structured representation (§3) or at least re-feeding and diffing the prior code.

The D1 cache makes this worse: `check_cache(chat_id, prompt)` returns the **previous video for an
identical prompt** ([bot.py:292-299](bot.py)) regardless of a changed theme/quality setting — so
"render it again, but nicer" can silently return the old file.

---

## 13. 🟠 Single-sample generation; no best-of-N where it would matter most

With unlimited compute, the highest-leverage quality move for a stochastic generator is **sample many,
keep the best**. The system almost never does this:

- The main path generates **one** candidate ([bot.py:381-393](bot.py)).
- The one place that samples two — `/debate` — picks the winner with the **text-only critic**
  ([multi_agent_debate.py:82-100](multi_agent_debate.py)), i.e. it never renders either candidate and
  never looks at a frame, so it selects on a proxy that can't see the actual video. And `/debate` is a
  separate manual command, not the default path.
- `MAX_CONCURRENT_RENDERS = 1` ([config.py:64](config.py)) means even if you generated N candidates you
  couldn't render them in parallel to compare.

A quality-first design would generate K candidates (different seeds/temperatures/plans), render all K
at draft quality, score the **rendered frames** with a vision critic, then re-render the winner at full
quality. The architecture supports none of this.

---

## 14. 🟠 Output format itself is sub-professional: resolution, frame rate, audio

Concrete ceilings on the finished file:

- **Resolution:** default `-qm` = 720p; "heavy" (i.e. ambitious) scenes forced to **480p**
  ([renderer.py:153-156](renderer.py)). No 1080p/4K path exists in code.
- **Frame rate:** heavy scenes forced to **15 fps** ([renderer.py:185-187](renderer.py)); the on-disk
  artifacts confirm `…/480p15/` and the TikTok `…/1920p15/` outputs — **TikTok, a fast-scroll format,
  is being produced at 15 fps**, which is visibly choppy. Professional motion wants 30/60 fps.
- **Audio:** a single edge-tts voice, no music bed, no sound design, no ducking, no beat-synced SFX. The
  pad-to-length re-encode uses `-preset ultrafast -crf 28` ([voiceover.py:107-124](voiceover.py)),
  which is a visible quality drop applied to the *whole* video whenever narration runs long.

None of these are compute-bound; they're choices. They each cap "professionally designed" before the
content is even considered.

---

## 15. 🟡 Concrete bugs found while reading (each degrades real renders)

- **Un-awaited cancellation coroutines.** `_cancel_task` is `async def`
  ([bot.py:110-116](bot.py)) but is called **without `await`** at
  [bot.py:602, 603, 607, 618](bot.py). These coroutines are never scheduled → `RuntimeWarning:
  coroutine never awaited`, and the progress/narration tasks are **not actually cancelled**, so a
  cancelled render can leak the progress-loop and narration tasks.
- **Two writers racing one status message.** `_progress_loop` edits `status_msg` every 15 s
  ([bot.py:191-201](bot.py)) while `_on_manim_progress` edits the *same* message on every Manim
  progress tick ([bot.py:573-582](bot.py)), and the Judge edits it too ([bot.py:467-494](bot.py)).
  They clobber each other; the displayed progress is whichever fired last.
- **`pathlib` used but imported as `from pathlib import Path`.** `/export` calls
  `pathlib.Path(video_path)` ([bot.py:871](bot.py)) but the module only imports `Path`
  ([bot.py:9](bot.py)) — `pathlib` is not in scope, so `/export` of an existing file raises
  `NameError`.
- **Education failures are computed and ignored** (§6) — `edu_review.is_correct == False` never blocks
  ([bot.py:446-454](bot.py)). A sign error in a formula renders happily.
- **TikTok prompt re-imports `SCENE_AWARENESS`** but not the budget/style modules
  ([prompt_builder_tiktok.py:208](prompt_builder_tiktok.py)) — so TikTok scenes have *no* performance
  ceiling while the rest of the system treats the ceiling as inviolable; an unlucky TikTok prompt can
  OOM the very laptop the whole architecture exists to protect.

---

## 16. 🟡 Sprawl without a quality core (accretion smell)

The repo is ~11.7k lines across ~40 modules, but the surface area is dominated by *breadth* features
that don't touch render quality: referral program, teacher dashboard, exam-prep banks, course
generator, gallery, analytics, watermarking, multiple deploy variants. Meanwhile the identity of the
core is confused — the code generator is called "GPT-5.5" in comments, "Qwen 3.7 Max" in docstrings,
and `qwen3.7-max` in config; `bot.py`'s own header says *"Qwen 3.7 Max code gen, Qwen 3.6 chat"*.
This inconsistency is a symptom: the system grew by bolting on features, and the *one thing you
actually care about* — the generation→render→evaluate quality loop — was never given a coherent,
owned core. The `PRODUCT_VISION.md` in the repo is 748 lines of roadmap for growth/monetization
features and explicitly defers the SceneGraph (the actual quality foundation) as a "Phase 2" item
that was never started.

---

## 17. What a quality-first architecture would actually require

You don't need cost/latency fixes; you need a different spine. In rough priority:

1. **Introduce a Scene Graph / storyboard IR (§3).** A structured, validatable, editable description
   of shots → beats → objects → timing → camera → narration sync-points. Generate *this* first
   (with the best model, max reasoning), validate it as a composition, and only then compile to Manim.
   Everything else below depends on it.
2. **Close the visual loop (§5).** Draft-render → extract keyframes → vision-model critique of the
   *actual image* (overlap, contrast, balance, slop) → targeted regeneration. This is the only way to
   enforce "polished" and "no slop."
3. **Make the hardware budget a *tier*, not a law (§1).** Decouple "what to create" from "where it
   runs." Allow a `cinematic` tier: 1080p/4K, 60 fps, Surfaces/3D, many updaters — and route renders
   to adequate compute instead of forbidding the content.
4. **Best-of-N with rendered-frame selection (§13).** Generate K storyboards/codes, render all at
   draft, pick the winner on *visual* score, re-render at full quality. This is where "unlimited
   compute" buys the most quality.
5. **Real narration sync (§4).** Derive narration from the storyboard's beats, attach sync-points,
   and schedule/time-stretch TTS against them (or render visuals to match a recorded VO). Stop padding
   with frozen frames.
6. **Edit by diffing the IR, not concatenating strings (§12).** "Slower"/"make it red" should mutate
   the stored scene graph and recompile, preserving everything the user already liked.
7. **Upgrade the generator (§2):** frontier model, reasoning **on**, large/uncapped output, code-gen
   temperature tuned, prompt rewritten from "minimalism over cinematic excess" to its opposite.
8. **Make the quality gates *gate* (§6), unify the style system (§9), fix the planner schema (§7),
   and either make templates theme-aware and correct or drop them (§11).**

---

## 18. Bottom line

The system is a competently engineered **reliability-and-cost** machine: queue, rate-limit,
memory-guard, self-heal, fallback, cache. Judged as "never crash the laptop, never show the user an
error, keep costs near zero," it largely succeeds.

Judged against **your** stated goal — world-class, high-resolution, well-directed, narration-synced,
style-consistent, slop-free Manim films — it is fighting itself at every layer:

- It is **prompted** to avoid cinematic ambition (§1).
- It uses the **wrong model with reasoning off and an 8k cap** for the creative core (§2).
- It has **no representation to direct or edit** (§3, §12).
- It **cannot sync narration** to events (§4).
- It **never looks at a frame** (§5), so its quality gates are text-only theater (§6) and its
  signature "scene awareness" feature is silently disabled by a schema bug (§7).
- It **caps the output format** at 720p/30 (480p/15 for anything bold) and 15 fps for short-form (§14).
- Its **safety nets degrade quality** down to a blank title card (§10), and its style is **inconsistent
  by construction** across three disagreeing regimes (§9, §11).

None of these are compute problems, so your "unlimited compute" doesn't move them. They are
*architecture* problems. The good news embedded in that: the existing reliability scaffolding is
reusable. But the quality spine — IR → best-of-N generation → render → *see the pixels* → critique →
edit-by-diff, on a tier that scales with compute — has to be built. Today it does not exist.
