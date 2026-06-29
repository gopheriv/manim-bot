"""Referral Program — track referrals and reward users.

Each user gets a unique referral code. When someone starts the bot with
/start <referral_code>, both the referrer and referee get bonus renders.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

REFERRAL_PATH = Path(__file__).parent / "data" / "referrals.json"
REFERRAL_PATH.parent.mkdir(parents=True, exist_ok=True)

BONUS_RENDERS = 5  # free renders for successful referral


def _load() -> dict:
    if not REFERRAL_PATH.exists():
        return {"users": {}, "referrals": []}
    try:
        return json.loads(REFERRAL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"users": {}, "referrals": []}


def _save(data: dict) -> None:
    # Atomic write: a crash mid-write would otherwise corrupt the ledger, and
    # _load() returns an empty default on corruption — silently wiping every
    # user's bonus renders. Write to a temp file then atomically replace.
    tmp = REFERRAL_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(REFERRAL_PATH)


def generate_referral_code(chat_id: int) -> str:
    """Generate a unique referral code for a user."""
    raw = f"{chat_id}:{datetime.now().isoformat()}"
    return hashlib.md5(raw.encode()).hexdigest()[:8].upper()


def register_user(chat_id: int, referred_by: int | None = None) -> dict:
    """Register a new user and process referral if applicable.

    Returns:
        dict with 'bonus' (renders added) and 'referred_by' (referrer chat_id or None)
    """
    data = _load()
    chat_id_str = str(chat_id)

    # Already registered
    if chat_id_str in data["users"]:
        return {"bonus": 0, "referred_by": None, "already_registered": True}

    # Generate referral code
    code = generate_referral_code(chat_id)
    data["users"][chat_id_str] = {
        "chat_id": chat_id,
        "referral_code": code,
        "referred_by": referred_by,
        "bonus_renders": 0,
        "total_renders": 0,
        "referrals_made": 0,
        "registered_at": datetime.now().isoformat(),
    }

    # Process referral
    bonus = 0
    if referred_by:
        referrer_str = str(referred_by)
        if referrer_str in data["users"]:
            # Award bonus to referrer
            data["users"][referrer_str]["bonus_renders"] += BONUS_RENDERS
            data["users"][referrer_str]["referrals_made"] += 1
            # Also give bonus to referee
            data["users"][chat_id_str]["bonus_renders"] = BONUS_RENDERS
            bonus = BONUS_RENDERS

            # Log referral
            data["referrals"].append({
                "referrer": referred_by,
                "referee": chat_id,
                "timestamp": datetime.now().isoformat(),
            })

            logger.info(f"Referral processed: {referred_by} → {chat_id}, +{BONUS_RENDERS} bonus renders each")
        else:
            logger.warning(f"Invalid referral: referrer {referred_by} not found")

    _save(data)
    return {"bonus": bonus, "referred_by": referred_by}


def use_bonus_render(chat_id: int) -> bool:
    """Use one bonus render. Returns True if bonus was used."""
    data = _load()
    chat_id_str = str(chat_id)

    if chat_id_str not in data["users"]:
        return False

    user = data["users"][chat_id_str]
    if user["bonus_renders"] > 0:
        user["bonus_renders"] -= 1
        user["total_renders"] += 1
        _save(data)
        return True
    return False


def track_render(chat_id: int) -> None:
    """Track a render (uses bonus if available, otherwise increments total)."""
    data = _load()
    chat_id_str = str(chat_id)

    if chat_id_str not in data["users"]:
        return

    user = data["users"][chat_id_str]
    if user["bonus_renders"] > 0:
        user["bonus_renders"] -= 1
    user["total_renders"] += 1
    _save(data)


def get_user_referral_info(chat_id: int) -> dict:
    """Get referral info for a user."""
    data = _load()
    chat_id_str = str(chat_id)

    if chat_id_str not in data["users"]:
        return {
            "code": generate_referral_code(chat_id),
            "bonus_renders": 0,
            "referrals_made": 0,
            "total_renders": 0,
        }

    user = data["users"][chat_id_str]
    return {
        "code": user["referral_code"],
        "bonus_renders": user["bonus_renders"],
        "referrals_made": user["referrals_made"],
        "total_renders": user["total_renders"],
    }


def get_referral_stats() -> dict:
    """Get global referral statistics."""
    data = _load()
    total_users = len(data["users"])
    total_referrals = len(data["referrals"])
    total_bonus_renderers = sum(
        1 for u in data["users"].values() if u["bonus_renders"] > 0
    )

    return {
        "total_users": total_users,
        "total_referrals": total_referrals,
        "users_with_bonus": total_bonus_renderers,
        "top_referrers": sorted(
            [
                (u["chat_id"], u["referrals_made"])
                for u in data["users"].values()
                if u["referrals_made"] > 0
            ],
            key=lambda x: -x[1],
        )[:5],
    }
