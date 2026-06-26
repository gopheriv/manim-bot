#!/bin/bash
# setup_server.sh — Full server setup for Manim Bot on Oracle Cloud Free Tier
# Ubuntu 24.04 ARM (Ampere)
# Run as: sudo bash setup_server.sh

set -euo pipefail

echo "========================================"
echo "  Manim Bot — Server Setup"
echo "  Oracle Cloud Free Tier (ARM Ampere)"
echo "========================================"

# ── 1. System packages ──────────────────────────────────────────────────────
echo ""
echo "[1/7] Installing system packages..."
apt-get update
apt-get install -y \
    python3.14 python3.14-venv python3-pip \
    ffmpeg \
    libpango1.0-dev pkg-config libcairo2-dev \
    libglew-dev libegl1 libgl1 \
    git curl tmux \
    build-essential

# ── 2. Create application directory ─────────────────────────────────────────
echo ""
echo "[2/7] Setting up /opt/manim-bot..."
mkdir -p /opt/manim-bot
chown ubuntu:ubuntu /opt/manim-bot

# ── 3. Clone or copy bot code ───────────────────────────────────────────────
echo ""
echo "[3/7] Deploying bot code..."

if [ -d "/opt/manim-bot/.git" ]; then
    echo "  Git repo found, pulling latest..."
    cd /opt/manim-bot
    git pull || true
else
    echo "  No git repo — expecting code to be copied via scp/rsync"
    echo "  Run: scp -i ~/.ssh/oracle.pem -r ~/manim-bot/* ubuntu@<server-ip>:/opt/manim-bot/"
fi

# ── 4. Python virtual environment ──────────────────────────────────────────
echo ""
echo "[4/7] Creating Python virtual environment..."
cd /opt/manim-bot

if [ -d "venv" ]; then
    echo "  venv exists, upgrading..."
    python3.14 -m venv venv --upgrade
else
    python3.14 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Install psutil for memory guard
pip install psutil

echo "  Installed packages:"
pip list --format=columns | head -20

# ── 5. Create required directories ─────────────────────────────────────────
echo ""
echo "[5/7] Creating directories..."
mkdir -p /opt/manim-bot/logs
mkdir -p /opt/manim-bot/data
mkdir -p /opt/manim-bot/tmp
mkdir -p /tmp/manim_render
chown -R ubuntu:ubuntu /opt/manim-bot /tmp/manim_render

# ── 6. Setup systemd service ───────────────────────────────────────────────
echo ""
echo "[6/7] Installing systemd service..."

SERVICE_FILE="/etc/systemd/system/manim-bot.service"

if [ -f "/opt/manim-bot/deploy/manim-bot.service" ]; then
    cp /opt/manim-bot/deploy/manim-bot.service "$SERVICE_FILE"
    echo "  Service file installed from deploy/"
elif [ -f "manim-bot.service" ]; then
    cp manim-bot.service "$SERVICE_FILE"
    echo "  Service file installed from current dir"
else
    echo "  WARNING: No service file found!"
    echo "  Copy manim-bot.service to /etc/systemd/system/ manually"
fi

systemctl daemon-reload
systemctl enable manim-bot

echo "  Service configured. Start with: sudo systemctl start manim-bot"

# ── 7. Setup log rotation ──────────────────────────────────────────────────
echo ""
echo "[7/7] Setting up log rotation..."

cat > /etc/logrotate.d/manim-bot << 'EOF'
/opt/manim-bot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    size 10M
}
EOF

echo "  Log rotation configured (daily, 7 days, 10MB max)"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Copy .env file:"
echo "     scp -i ~/.ssh/oracle.pem .env ubuntu@<server-ip>:/opt/manim-bot/.env"
echo ""
echo "  2. Copy user data (optional):"
echo "     scp -i ~/.ssh/oracle.pem user_settings.json ubuntu@<server-ip>:/opt/manim-bot/"
echo "     scp -i ~/.ssh/oracle.pem data/analytics.json ubuntu@<server-ip>:/opt/manim-bot/data/"
echo ""
echo "  3. Start the bot:"
echo "     sudo systemctl start manim-bot"
echo ""
echo "  4. Check logs:"
echo "     sudo journalctl -u manim-bot -f"
echo ""
echo "  5. Check status:"
echo "     sudo systemctl status manim-bot"
echo ""
