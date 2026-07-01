# Learning Loop — How the Bot Gets Smarter

The manim-bot has two self-improving feedback loops that persist lessons from failures and inject them into future generation prompts. Both loops are now fully closed (write → store → read).

## Loop 1: Judge Rejection Memory

When the Judge of AI Court reviews generated code and issues a REPAIR or REJECT verdict, the rejection reasons are persisted as "lessons" so the same defect never happens twice.

### Flow

```
Judge verdict (REPAIR/REJECT)
  ↓
bot.py:918 → log_judge_rejection(reasons, code, verdict)
  ↓
data/judge_rejections.json  (30-day TTL, deduped by line-number-agnostic signature)
  ↓
bot.py:573 → get_top_judge_lessons(limit=3)      → storyboard prompt (planning stage)
bot.py:574 → get_recurring_lesson_constraints()  → storyboard hard constraints (≥3 recurrences)
bot.py:684 → get_judge_avoidance_modifiers()     → code-gen footer (fallback if no storyboard)
```

### What triggers a lesson
- Judge verdict is REPAIR or REJECT
- Each distinct reason becomes a lesson (line numbers stripped for dedup)
- Repeated same defect bumps count (not a new entry)

### Caps and bounds
- **TTL**: 30 days (lessons expire if not seen again)
- **Dedup**: by normalized reason text (line numbers stripped)
- **Top lessons**: 3 most recurring → storyboard planning
- **Hard constraints**: lessons seen ≥3 times → MUST-NOT rules for storyboard regeneration
- **Avoidance modifiers**: up to 10 most recent → code-gen footer (when no storyboard)

## Loop 2: Render Error Patterns

When a render fails (after self-heal is exhausted), the error is categorized and persisted so future prompts avoid the same failure mode.

### Flow

```
Render failure (after self-heal exhausted)
  ↓
bot.py:1198,1291 → log_error(prompt, error_message, code)
  ↓
data/error_patterns.json  (7-day TTL, deduped by normalized error signature)
  ↓
bot.py:563 → get_adaptive_prompt_modifiers(constrained=tier) → theme_prompt
```

### What triggers a lesson
- Render fails after all self-heal attempts are exhausted
- Error is categorized into one of: `numpy_compat`, `missing_import`, `syntax_error`, `attribute_error`, `type_error`, `manim_api`, `render_timeout`, `memory_error`, `name_error`, `value_error`, `unknown`

### Caps and bounds
- **TTL**: 7 days (more aggressive than Judge lessons — render errors are transient)
- **Dedup**: by normalized error signature (numbers → `#`, first 200 chars)
- **Threshold**: modifiers fire only when a category has count ≥ 2 (except `memory_error` which fires at ≥ 1 on constrained tier)
- **Constrained-only**: the memory-pressure modifier ("keep scene lightweight") only applies on the constrained (8GB laptop) tier

### Migration (one-time)
Legacy entries logged before the dedup system was added (no `signature` field) are automatically migrated on first load: signatures are backfilled, categories are recomputed with current logic, and duplicate entries are merged. This runs once and is a no-op after migration.

## What's NOT in the loop (intentionally)

- **Simple/medium topics**: Don't get pedagogical storyboards (no extra cost for "draw a red circle")
- **Best-of-N fallback**: When `storyboard_text` is empty, per-candidate storyboards don't get `top_lessons` — but `theme_prompt` still carries error modifiers
- **One-off errors**: A single render failure doesn't trigger modifiers (except memory errors on constrained hardware) — the threshold prevents noise from cluttering prompts
- **Resource errors**: RAM kills and timeouts are system conditions, not code bugs — they trigger the lightweight-scene modifier but don't feed into the Judge repair path
