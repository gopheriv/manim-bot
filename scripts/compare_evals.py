"""Print the Phase-3 comparison: baseline critic vs Aesthetic Director panel.

Reads tests/gauntlet/eval_baseline.json and eval_panel.json (written by eval_critic.py)
and prints precision/recall side by side, plus the per-scene disagreements.

    PYTHONIOENCODING=utf-8 python scripts/compare_evals.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aesthetic_metrics import EvalRow, compute_metrics, missed_defects, false_alarms  # noqa: E402

GDIR = ROOT / "tests" / "gauntlet"


def _load(which: str) -> list[EvalRow]:
    path = GDIR / f"eval_{which}.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [EvalRow(d["scene"], d["label"], d["flagged"], d.get("detail", "")) for d in data]


def _fmt(m: dict, key: str) -> str:
    v = m[key]
    return "n/a" if v is None else f"{v*100:.0f}%"


def main() -> None:
    base = _load("baseline")
    panel = _load("panel")
    if not base or not panel:
        print(f"Need both eval files. baseline={len(base)} rows, panel={len(panel)} rows.")
        print("Run: python scripts/eval_critic.py baseline   AND   python scripts/eval_critic.py panel")
        return
    mb, mp = compute_metrics(base), compute_metrics(panel)

    print("=== PRECISION / RECALL — baseline critic vs Aesthetic Director ===\n")
    print(f"{'metric':<14}{'baseline':>12}{'panel':>12}")
    for label, key in [("precision", "precision"), ("recall", "recall"), ("f1", "f1")]:
        print(f"{label:<14}{_fmt(mb, key):>12}{_fmt(mp, key):>12}")
    print(f"{'TP':<14}{mb['tp']:>12}{mp['tp']:>12}")
    print(f"{'FP (false alarm)':<14}{mb['fp']:>12}{mp['fp']:>12}")
    print(f"{'FN (missed)':<14}{mb['fn']:>12}{mp['fn']:>12}")
    print(f"{'TN':<14}{mb['tn']:>12}{mp['tn']:>12}")
    print(f"{'errors':<14}{mb['errors']:>12}{mp['errors']:>12}")

    print("\n-- baseline missed defects:", missed_defects(base) or "none")
    print("-- baseline false alarms :", false_alarms(base) or "none")
    print("-- panel    missed defects:", missed_defects(panel) or "none")
    print("-- panel    false alarms :", false_alarms(panel) or "none")

    bmap = {r.scene: r for r in base}
    print("\n-- per-scene (truth | baseline | panel) --")
    for r in panel:
        b = bmap.get(r.scene)
        bf = "?" if b is None or b.flagged is None else ("FLAG" if b.flagged else "pass")
        pf = "ERR" if r.flagged is None else ("FLAG" if r.flagged else "pass")
        print(f"  {r.scene:<28} {r.label:<7} base={bf:<5} panel={pf}")


if __name__ == "__main__":
    main()
