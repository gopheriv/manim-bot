#!/bin/bash
# migrate_to_cloud.sh — Migrate Manim Bot data from laptop to cloud server
# Run on the SERVER after setup_server.sh is complete
# Usage: bash migrate_to_cloud.sh <laptop-ssh-user>@<laptop-public-ip>

set -euo pipefail

LAPTOP="${1:-}"
if [ -z "$LAPTOP" ]; then
    echo "Usage: bash migrate_to_cloud.sh <user>@<laptop-ip>"
    echo ""
    echo "Example:"
    echo "  bash migrate_to_cloud.sh sunak@100.93.247.16"
    echo ""
    echo "Note: Laptop must be reachable (same Tailscale network or public IP)"
    exit 1
fi

echo "========================================"
echo "  Manim Bot — Data Migration"
echo "  Source: $LAPTOP"
echo "========================================"

# SSH options
SSH_KEY="${HOME}/.ssh/id_rsa"
if [ ! -f "$SSH_KEY" ]; then
    echo ""
    echo "WARNING: No SSH key found at $SSH_KEY"
    echo "You'll need to specify the key manually:"
    echo "  SSH_KEY=/path/to/key bash migrate_to_cloud.sh user@ip"
    echo ""
    read -p "Press Enter to continue (will use default key)..."
fi

SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
if [ -f "$SSH_KEY" ]; then
    SSH_OPTS="$SSH_OPTS -i $SSH_KEY"
fi

# Detect laptop OS and paths
echo ""
echo "[1/5] Detecting laptop OS..."

LAPTOP_OS=$(ssh $SSH_OPTS "$LAPTOP" 'uname -s' 2>/dev/null || echo "unknown")
echo "  Laptop OS: $LAPTOP_OS"

if [[ "$LAPTOP_OS" == *"MINGW"* ]] || [[ "$LAPTOP_OS" == *"MSYS"* ]] || [[ "$LAPTOP_OS" == *"CYGWIN"* ]]; then
    # Windows laptop via Git Bash/WSL
    MANIM_DIR="/c/Users/sunak/manim-bot"
elif [[ "$LAPTOP_OS" == *"Linux"* ]]; then
    MANIM_DIR="/home/$(ssh $SSH_OPTS "$LAPTOP" 'whoami')/manim-bot"
elif [[ "$LAPTOP_OS" == *"Darwin"* ]]; then
    MANIM_DIR="/Users/$(ssh $SSH_OPTS "$LAPTOP" 'whoami')/manim-bot"
else
    echo "  WARNING: Unknown OS, trying default Windows path"
    MANIM_DIR="/c/Users/sunak/manim-bot"
fi

echo "  Manim dir: $MANIM_DIR"

# Check connectivity
echo ""
echo "[2/5] Testing connectivity..."
if ssh $SSH_OPTS "$LAPTOP" "test -d '$MANIM_DIR'" 2>/dev/null; then
    echo "  ✅ Manim bot directory found"
else
    echo "  ❌ Cannot access $MANIM_DIR on laptop"
    echo "  Make sure:"
    echo "    - Laptop is running and reachable"
    echo "    - SSH server is running on laptop"
    echo "    - Path is correct (edit script if needed)"
    exit 1
fi

# Migrate files
echo ""
echo "[3/5] Migrating configuration..."

# .env (critical — contains secrets)
echo "  .env..."
scp $SSH_OPTS "$LAPTOP:$MANIM_DIR/.env" /opt/manim-bot/.env 2>/dev/null && \
    echo "    ✅ .env migrated" || echo "    ⚠️ .env not found (create manually from deploy/.env.production)"

# user_settings.json
echo "  user_settings.json..."
scp $SSH_OPTS "$LAPTOP:$MANIM_DIR/user_settings.json" /opt/manim-bot/user_settings.json 2>/dev/null && \
    echo "    ✅ user_settings.json migrated" || echo "    ⚠️ user_settings.json not found (no user data yet)"

echo ""
echo "[4/5] Migrating data..."

# analytics.json
mkdir -p /opt/manim-bot/data
scp $SSH_OPTS "$LAPTOP:$MANIM_DIR/data/analytics.json" /opt/manim-bot/data/analytics.json 2>/dev/null && \
    echo "  ✅ analytics.json migrated" || echo "  ⚠️ analytics.json not found"

# .local_cache.db
scp $SSH_OPTS "$LAPTOP:$MANIM_DIR/.local_cache.db" /opt/manim-bot/.local_cache.db 2>/dev/null && \
    echo "  ✅ .local_cache.db migrated" || echo "  ⚠️ .local_cache.db not found"

# Fix permissions
sudo chown -R ubuntu:ubuntu /opt/manim-bot

echo ""
echo "[5/5] Migration complete!"
echo ""
echo "========================================"
echo "  Summary"
echo "========================================"
echo ""
echo "Files migrated to /opt/manim-bot/"
echo ""
echo "Next steps:"
echo "  1. Verify .env has correct TELEGRAM_BOT_TOKEN:"
echo "     grep TELEGRAM_BOT_TOKEN /opt/manim-bot/.env"
echo ""
echo "  2. Restart the bot:"
echo "     sudo systemctl restart manim-bot"
echo ""
echo "  3. Check logs:"
echo "     sudo journalctl -u manim-bot -f"
echo ""
echo "  4. Test: send /start to @Manim_is_so_useful_bot"
echo ""
