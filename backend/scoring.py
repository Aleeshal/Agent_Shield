"""Pass rate and before/after comparison. Pure functions, no model calls."""

OUTCOMES = ("pass", "confirmed_fail", "suspected_fail", "inconclusive")
FAILS = {"confirmed_fail", "suspected_fail"}


def _counts(results: list[dict]) -> dict:
    counts = {o: 0 for o in OUTCOMES}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    total = len(results)
    return {
        "total": total,
        "counts": counts,
        "failed": counts["confirmed_fail"] + counts["suspected_fail"],
        # Inconclusive tests count against the score: an unverified test is not a pass.
        "pass_rate": round(100 * counts["pass"] / total, 1) if total else 0.0,
    }


def summarize(results: list[dict]) -> dict:
    """Overall score, plus per-category and holdout breakdowns."""
    by_cat: dict[str, list[dict]] = {}
    for r in results:
        by_cat.setdefault(r["category"], []).append(r)
    return {
        **_counts(results),
        "by_category": {c: _counts(rs) for c, rs in sorted(by_cat.items())},
        "suite": _counts([r for r in results if not r.get("holdout")]),
        "holdout": _counts([r for r in results if r.get("holdout")]),
    }


def _change(before: str | None, after: str | None) -> str:
    if before is None or after is None:
        return "new" if before is None else "removed"
    if before in FAILS and after == "pass":
        return "fixed"
    if before == "pass" and after in FAILS:
        return "regressed"
    if before in FAILS and after in FAILS:
        return "still_failing"
    if before == after == "pass":
        return "still_passing"
    return "changed"  # anything involving inconclusive


def compare(before_run: dict, after_run: dict) -> dict:
    """Per-test outcome changes between two runs of the suite."""
    b = {r["test_id"]: r for r in before_run["results"]}
    a = {r["test_id"]: r for r in after_run["results"]}
    rows = []
    for tid in list(b) + [t for t in a if t not in b]:
        rb, ra = b.get(tid), a.get(tid)
        ref = ra or rb
        rows.append({
            "test_id": tid,
            "category": ref["category"],
            "holdout": ref.get("holdout", False),
            "before": rb["outcome"] if rb else None,
            "after": ra["outcome"] if ra else None,
            "change": _change(rb and rb["outcome"], ra and ra["outcome"]),
        })
    changes: dict[str, int] = {}
    for row in rows:
        changes[row["change"]] = changes.get(row["change"], 0) + 1
    sb, sa = summarize(before_run["results"]), summarize(after_run["results"])
    return {
        "before": {"run_id": before_run["id"], "label": before_run["label"], "summary": sb},
        "after": {"run_id": after_run["id"], "label": after_run["label"], "summary": sa},
        "pass_rate_delta": round(sa["pass_rate"] - sb["pass_rate"], 1),
        "holdout_pass_rate_delta": round(sa["holdout"]["pass_rate"] - sb["holdout"]["pass_rate"], 1),
        "changes": changes,
        "rows": rows,
    }
