# Manim Animation Bot

A Telegram bot that turns text descriptions into cinematic Manim animations. Send any message — the bot generates code, renders a video, adds voiceover narration, and sends it back.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Manim-Community-orange.svg" alt="Manim Community">
  <img src="https://img.shields.io/badge/Telegram-aiogram-2CA5E0.svg" alt="aiogram">
</p>

## Features

- **LLM-powered code generation** — Qwen 3.7 Max generates cinematic Manim animations from natural language
- **Scene planner** — LLM produces a JSON composition plan before code generation
- **Self-healing render** — if code fails to render, the bot fixes the code automatically (up to 2 retries with escalating simplification)
- **Heavy scene protection** — auto-detects heavy scenes, downgrades quality, disables caching, sets low CPU priority
- **Real-time progress** — live Telegram progress bar showing Manim's actual render % and current animation name
- **Voiceover narration** — Azure TTS generates narration synced to the animation
- **Smart caching** — SQLite cache stores solver results, RAG references, and rendered scenes
- **RAG textbook memory** — auto-ingests local math/physics PDFs for reference
- **Multi-provider LLM** — switch between Qwen and Claude for chat
- **Theme system** — Nord, Solarized, Dark, Light, Dracula, Monokai visual themes
- **Quality control** — `/quality` command: `-ql` (480p), `-qm` (720p), `-qh` (1080p)
- **Queue management** — semaphore-limited rendering, one job at a time

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
manim --version  # Verify Manim is installed
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `GPT_API_KEY` + `GPT_BASE_URL` — Qwen 3.7 Max for code generation
- `OPENAI_API_KEY` + `LLM_BASE_URL` — Qwen 3.6 Plus for chat
- `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` — (optional) voiceover narration

### 3. Run

```bash
python bot.py
```

The bot starts polling immediately. Send it a message like:
> `animate a damped harmonic oscillator`

## Architecture

```
User message
    │
    ▼
┌─ Intent Classifier ─────────────┐
│  ANIMATE / EXPLAIN / CHAT       │
└────────────────┬────────────────┘
                 │
          ANIMATE?
                 │
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌──────────┐
│ Scene  │  │  RAG   │  │ Parallel │
│ Planner│  │Search  │  │ Render + │
└───┬────┘  └───┬────┘  │  TTS     │
    │           │       └────┬─────┘
    ▼           ▼            │
┌──────────────────────┐     │
│  Code Generation     │◄────┘
│  (Qwen 3.7 Max)      │
└──────────┬───────────┘
           │
    ▼      ▼
┌──────────────┐     ┌──────────┐
│ Manim Render │────►│  Merge   │
│  (480p/720p) │     │ + Voice  │
└──────┬───────┘     └────┬─────┘
       │                  │
       ▼                  ▼
   [Video.mp4] ─────►  Telegram
```

### Key files

| File | Purpose |
|---|---|
| `bot.py` | Telegram handlers, pipeline orchestration |
| `llm.py` | LLM clients, code generation, chat responses |
| `prompt_builder.py` | Compressed system prompts for Manim code generation |
| `renderer.py` | Manim subprocess, progress streaming, heavy scene detection |
| `scene_planner.py` | JSON scene composition planner |
| `scene_validator.py` | Layout overlap/crowding validator |
| `voiceover.py` | Azure TTS + ffmpeg video/audio merge |
| `fallback_scene.py` | Deterministic fallback animation |
| `queue_manager.py` | Job queue with semaphore + status tracking |
| `config.py` | Environment variable loader |
| `themes.py` | Visual theme definitions |
| `rate_limiter.py` | Per-user rate limiting |
| `database.py` | SQLite cache for solver/RAG/scene results |

## Requirements

- Python 3.12+
- Manim Community Edition (`pip install manim`)
- FFmpeg (`choco install ffmpeg` on Windows)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- API keys for LLM providers (Qwen, optionally Claude)
- (Optional) Azure Speech API key for voiceover

## Hardware

Tested on **Intel i5-1155G7, 8GB RAM, Intel Iris Xe**.
The heavy scene protection system auto-mitigates for constrained hardware:
- Score > 60 → force 480p, disable caching, BELOW_NORMAL priority
- RAM > 92% during render → kill + fallback animation
- RAM > 85% before render → block entirely

## Commands

| Command | Description |
|---|---|
| `/start` | Bot info + settings |
| `/help` | Usage guide |
| `/settings` | Open settings page |
| `/quality` | Set render quality |
| `/theme` | Set visual theme |
| `/voiceover` | Toggle voice narration |
| `/voice` | Set voice type |
| `/rate` | Set narration speed |
| `/cancel` | Cancel running render |
| `/status` | Check render status |
| `/provider` | Switch LLM provider |
| `/clear` | Clear render cache |
| `/render <file>` | Render a local .py file |

## License

Private — all rights reserved. Not for redistribution.
