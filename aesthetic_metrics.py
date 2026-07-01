"""Pure precision/recall accounting for visual-defect judges.

Deterministic and dependency-free so the metric logic is unit-tested with mocked
verdicts (no vision API). A judge ``flagged=None`` means the vision call could not be
measured (flaky endpoint) — those rows are counted as ``errors`` and EXCLUDED from
precision/recall rather than guessed, so a metric is never fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalRow:
    scene: str
    label: str               # "defect" | "clean" (ground truth)
    flagged: bool | None     # judge said "defective"? None = unmeasured (vision error)
    detail: str = ""


def compute_metrics(rows: list[EvalRow]) -> dict:
    """Confusion matrix + precision/recall over the MEASURED rows.

    Positive class = "defect". precision/recall are None when their denominator is 0
    (e.g. nothing flagged → precision undefined) so callers report honestly.
    """
    tp = fp = tn = fn = errors = 0
    for r in rows:
        if r.flagged is None:
            errors += 1
            continue
        positive = (r.label == "defect")
        if r.flagged and positive:
            tp += 1
        elif r.flagged and not positive:
            fp += 1
        elif (not r.flagged) and positive:
            fn += 1
        else:
            tn += 1
    measured = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision and recall and (precision + recall) else None)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn, "errors": errors,
        "measured": measured, "precision": precision, "recall": recall, "f1": f1,
    }


def missed_defects(rows: list[EvalRow]) -> list[str]:
    """Defect scenes the judge did NOT flag (recall failures — the worst kind here)."""
    return [r.scene for r in rows if r.label == "defect" and r.flagged is False]


def false_alarms(rows: list[EvalRow]) -> list[str]:
    """Clean scenes the judge wrongly flagged (precision failures)."""
    return [r.scene for r in rows if r.label == "clean" and r.flagged is True]


def format_report(title: str, rows: list[EvalRow]) -> str:
    """Human-readable per-scene table + summary line."""
    m = compute_metrics(rows)
    lines = [f"=== {title} ===",
             f"{'scene':<28} {'truth':<8} {'flagged':<9} detail"]
    for r in rows:
        fl = "ERROR" if r.flagged is None else ("FLAG" if r.flagged else "pass")
        lines.append(f"{r.scene:<28} {r.label:<8} {fl:<9} {r.detail[:60]}")
    p = "n/a" if m["precision"] is None else f"{m['precision']*100:.0f}%"
    rc = "n/a" if m["recall"] is None else f"{m['recall']*100:.0f}%"
    lines.append(
        f"TP={m['tp']} FP={m['fp']} TN={m['tn']} FN={m['fn']} "
        f"errors={m['errors']} | precision={p} recall={rc}"
    )
    miss = missed_defects(rows)
    if miss:
        lines.append("MISSED DEFECTS (recall failures): " + ", ".join(miss))
    fa = false_alarms(rows)
    if fa:
        lines.append("FALSE ALARMS (precision failures): " + ", ".join(fa))
    return "\n".join(lines)
