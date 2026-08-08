"""
analysis.py — FlowLens bottleneck engine.

Deliberately simple, explainable statistics — no machine learning.

Input: list of records: {item_id, stage, entry_time, exit_time, duration_seconds}

Steps:
 1. Group durations by stage.
 2. Compute per-stage summary stats (mean, median, stddev, IQR).
 3. Compute a z-score for each stage's mean duration relative to the
    distribution of *stage means* ("is this stage slower than a typical
    stage in this pipeline?").
 4. Flag stages as bottlenecks where zScore >= threshold (default 1.0).
 5. Within every stage, flag individual items whose duration exceeds
    Q3 + 1.5*IQR (classic box-plot outlier rule) as "stuck items".
 6. Classify *why* each bottleneck stage is slow and attach a plain-English
    recommendation.
"""

from datetime import datetime, timezone


def mean(values):
    return sum(values) / len(values) if values else 0.0


def stddev(values, avg=None):
    if len(values) < 2:
        return 0.0
    avg = mean(values) if avg is None else avg
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    return variance ** 0.5


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    idx = (p / 100) * (len(sorted_vals) - 1)
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_vals) - 1)
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def summarize(values):
    s = sorted(values)
    avg = mean(values)
    sd = stddev(values, avg)
    q1 = percentile(s, 25)
    q3 = percentile(s, 75)
    iqr = q3 - q1
    return {
        "count": len(values),
        "mean": avg,
        "median": percentile(s, 50),
        "stddev": sd,
        "min": min(values) if values else 0,
        "max": max(values) if values else 0,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "outlierCeiling": q3 + 1.5 * iqr,
        "outlierCount": 0,  # filled in later
    }


def classify_cause(stage_summary, overall_mean):
    cv = (stage_summary["stddev"] / stage_summary["mean"]) if stage_summary["mean"] > 0 else 0
    high_mean = stage_summary["mean"] > overall_mean
    high_variance = cv > 0.6
    outlier_share = stage_summary["outlierCount"] / max(stage_summary["count"], 1)

    if high_mean and high_variance:
        return {
            "cause": "Inconsistent process",
            "explanation": (
                "Most items move through reasonably fast, but a meaningful share get stuck much "
                "longer than others. This points to an inconsistent process rather than a hard "
                "capacity limit — think manual approvals, missing information, exception handling, "
                "or a step that only some cases need."
            ),
            "recommendation": (
                'Investigate the outlier items specifically (see "Stuck Items" below) — look for a '
                "common cause (same approver, same customer type, same missing field) and standardize "
                "or automate that path."
            ),
        }

    if high_mean and not high_variance:
        return {
            "cause": "Capacity constraint",
            "explanation": (
                "This stage is consistently slow for almost everyone who passes through it, with low "
                "variability. That pattern usually means the stage itself is under-resourced or "
                "rate-limited, not that specific cases are going wrong."
            ),
            "recommendation": (
                "Consider adding capacity at this stage — more staff/machines, running it in parallel, "
                "or pre-allocating time/resources here, since every item pays the same cost."
            ),
        }

    if outlier_share > 0.15:
        return {
            "cause": "Exception handling problem",
            "explanation": (
                "The average time here is close to normal, but a notable fraction of items are taking "
                'far longer than the rest (see "Stuck Items"). The everyday case is fine — it is edge '
                "cases that are costly."
            ),
            "recommendation": (
                "Build a fast-track or escalation path for the recurring edge case instead of "
                "optimizing the whole stage."
            ),
        }

    return {
        "cause": "Not a significant bottleneck",
        "explanation": "This stage performs close to or better than the rest of the pipeline on average.",
        "recommendation": "No action needed here right now — focus effort on the flagged stages above.",
    }


def build_summary_text(primary, bottlenecks, stuck_count, total_stages):
    if not primary:
        return "Not enough data to summarize."
    parts = []
    parts.append(
        f'Out of {total_stages} stage(s) analyzed, "{primary["stage"]}" is the primary bottleneck, '
        f'averaging {round(primary["mean"])}s per item, {primary["zScore"]:.2f} standard deviations '
        f"above the average stage duration in this pipeline."
    )
    parts.append(f'Root cause: {primary["cause"]}. {primary["explanation"]}')
    parts.append(f'Recommendation: {primary["recommendation"]}')
    if len(bottlenecks) > 1:
        names = ", ".join(b["stage"] for b in bottlenecks)
        parts.append(f"{len(bottlenecks)} stage(s) in total were flagged as bottlenecks: {names}.")
    if stuck_count > 0:
        parts.append(f"{stuck_count} individual item(s) across all stages were flagged as unusually stuck.")
    return " ".join(parts)


def run_analysis(records, z_threshold: float = 1.0):
    if not records:
        return {"error": "No records to analyze."}

    by_stage = {}
    for r in records:
        by_stage.setdefault(r["stage"], []).append(r)

    stage_names = list(by_stage.keys())

    stage_summaries = {}
    for stage in stage_names:
        durations = [r["duration_seconds"] for r in by_stage[stage]]
        stage_summaries[stage] = summarize(durations)

    stage_means = [stage_summaries[s]["mean"] for s in stage_names]
    overall_mean = mean(stage_means)
    overall_std = stddev(stage_means, overall_mean) or 1e-9

    for stage in stage_names:
        z = (stage_summaries[stage]["mean"] - overall_mean) / overall_std
        stage_summaries[stage]["zScore"] = z if z == z else 0.0  # NaN guard
        stage_summaries[stage]["isBottleneck"] = stage_summaries[stage]["zScore"] >= z_threshold

    stuck_items = []
    for stage in stage_names:
        ceiling = stage_summaries[stage]["outlierCeiling"]
        count = 0
        for r in by_stage[stage]:
            if r["duration_seconds"] > ceiling:
                count += 1
                stuck_items.append({
                    "item_id": r["item_id"],
                    "stage": stage,
                    "duration_seconds": r["duration_seconds"],
                    "expected_ceiling_seconds": ceiling,
                    "exceeded_by_seconds": r["duration_seconds"] - ceiling,
                })
        stage_summaries[stage]["outlierCount"] = count
    stuck_items.sort(key=lambda x: x["exceeded_by_seconds"], reverse=True)

    stage_reports = []
    for stage in stage_names:
        s = stage_summaries[stage]
        cause_info = classify_cause(s, overall_mean)
        stage_reports.append({"stage": stage, **s, **cause_info})
    stage_reports.sort(key=lambda x: x["mean"], reverse=True)

    bottleneck_stages = [s for s in stage_reports if s["isBottleneck"]]
    primary_bottleneck = bottleneck_stages[0] if bottleneck_stages else (stage_reports[0] if stage_reports else None)

    item_totals = {}
    for r in records:
        item_totals[r["item_id"]] = item_totals.get(r["item_id"], 0) + r["duration_seconds"]
    overall_process_summary = summarize(list(item_totals.values()))

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "zThreshold": z_threshold,
        "totalItems": len(item_totals),
        "totalStages": len(stage_names),
        "totalRecords": len(records),
        "overallMeanStageDuration": overall_mean,
        "overallStdStageDuration": overall_std,
        "overallProcessSummary": overall_process_summary,
        "stageReports": stage_reports,
        "bottleneckStages": bottleneck_stages,
        "primaryBottleneck": primary_bottleneck,
        "stuckItems": stuck_items[:50],
        "stuckItemCount": len(stuck_items),
        "summaryText": build_summary_text(primary_bottleneck, bottleneck_stages, len(stuck_items), len(stage_names)),
    }
