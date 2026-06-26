# Manim Bot — Production Docker Image
# Build: docker build -t manim-bot:latest .
# Run:   docker run -d --name manim-bot --env-file .env -v manim-data:/opt/manim-bot/data manim-bot:latest

FROM python:3.14-slim

# Platform label (works on both amd64 and arm64)
ARG TARGETPLATFORM
LABEL org.opencontainers.image.description="Manim Animation Bot for Telegram"

# ── System dependencies ─────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libpango1.0-0 \
    libcairo2 \
    libglew2.2 \
    libegl1 \
    libgl1 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ───────────────────────────────────────────────────────
WORKDIR /opt/manim-bot

# ── Python dependencies ─────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir manim psutil

# ── Application code ────────────────────────────────────────────────────────
COPY bot.py .
COPY config.py .
COPY config_production.py config_prod.py
COPY llm.py .
COPY renderer_linux.py renderer_prod.py
COPY prompt_builder.py .
COPY voiceover.py .
COPY themes.py .
COPY settings.py .
COPY database.py .
COPY queue_manager.py .
COPY rate_limiter.py .
COPY analytics.py .
COPY markdown_utils.py .
COPY fallback_scene.py .
COPY d1.py .
COPY examples.py .

# ── Runtime configuration ───────────────────────────────────────────────────
# Create render and temp directories
RUN mkdir -p /tmp/manim_render/media /opt/manim-bot/logs /opt/manim-bot/data /opt/manim-bot/tmp

# Volume for persistent data (user settings, analytics, cache)
VOLUME ["/opt/manim-bot/data", "/opt/manim-bot/logs"]

# Environment
ENV PYTHONUNBUFFERED=1
ENV RENDER_DIR=/tmp/manim_render

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health') || exit 1"

# Expose (optional — for webhook mode)
EXPOSE 8080

# Run
CMD ["python3", "bot.py"]
