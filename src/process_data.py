"""Validate raw logs and calculate reproducible, query-clustered summaries."""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = ("rule_based", "llm")
BOOTSTRAPS = 2000
SEED = 42


def load_evaluation(path):
    raw = pd.read_json(path, lines=True)
    allowed_phases = {"warmup", "evaluation"}
    if not set(raw["phase"]).issubset(allowed_phases):
        raise ValueError("Unknown benchmark phase")
    data = raw.loc[raw["phase"].eq("evaluation")].copy()
    keys = ["concurrency", "query_id", "repetition"]
    if data.empty or data.duplicated([*keys, "system"]).any():
        raise ValueError("Expected unique evaluation rows for each system and request")
    if set(data["system"]) != set(SYSTEMS) or not data.groupby(keys).size().eq(2).all():
        raise ValueError("Each evaluation request must have both systems")
    if not data.groupby(keys)[["expected_intent", "expected_case_ref"]].nunique(
        dropna=False
    ).eq(1).all().all():
        raise ValueError("Ground truth differs across paired requests")
    if not set(data["status"]).issubset({"ok", "error"}):
        raise ValueError("Unknown request status")
    if data["latency_ms"].isna().any() or (data["latency_ms"] <= 0).any():
        raise ValueError("Expected positive measured durations")
    data["success"] = data["status"].eq("ok")
    data["correct"] = data["success"] & data["predicted_intent"].eq(data["expected_intent"])
    data["has_reference"] = data["expected_case_ref"].fillna("").ne("")
    data["crm_correct"] = (
        data["success"] & data["has_reference"]
        & data["predicted_case_ref"].eq(data["expected_case_ref"])
    )
    return raw, data


def interval(samples):
    finite = np.asarray(samples)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return np.nan, np.nan
    return tuple(np.percentile(finite, [2.5, 97.5]))


def bootstrap_indices(size):
    return np.random.default_rng(SEED).integers(0, size, (BOOTSTRAPS, size))


def latency_summary(group):
    successful = group.loc[group["success"], "latency_ms"]
    durations = group.assign(timed_ms=group["latency_ms"].where(group["success"])).pivot(
        index="query_id", columns="repetition", values="timed_ms"
    ).to_numpy()
    sampled = durations[bootstrap_indices(len(durations))]
    median_samples = np.array([
        np.median(row[np.isfinite(row)]) if np.isfinite(row).any() else np.nan
        for row in sampled
    ])
    low, high = interval(median_samples)
    return {
        "mean_ms": successful.mean(),
        "median_ms": successful.median(),
        "median_ci_low_ms": low,
        "median_ci_high_ms": high,
        "p95_ms": successful.quantile(0.95),
    }


def summarize(evaluation):
    rows = []
    load_ids = evaluation.loc[evaluation["concurrency"].eq(2), "query_id"].unique()
    scopes = {
        "primary": evaluation.loc[evaluation["concurrency"].eq(1)],
        "matched_load": evaluation.loc[evaluation["query_id"].isin(load_ids)],
    }
    for scope, data in scopes.items():
        for (level, system), group in data.groupby(["concurrency", "system"]):
            accuracy_per_query = group.groupby("query_id")["correct"].mean().to_numpy()
            low, high = interval(100 * accuracy_per_query[
                bootstrap_indices(len(accuracy_per_query))
            ].mean(axis=1))
            eligible = group.loc[group["has_reference"]]
            no_ref = group.loc[~group["has_reference"] & group["success"]]
            rows.append({
                "scope": scope,
                "concurrency": level,
                "system": system,
                "queries": group["query_id"].nunique(),
                "requests": len(group),
                "errors": int((~group["success"]).sum()),
                "error_rate_pct": 100 * (~group["success"]).mean(),
                "accuracy_pct": 100 * group["correct"].mean(),
                "accuracy_ci_low_pct": low,
                "accuracy_ci_high_pct": high,
                "crm_required": len(eligible),
                "crm_correct": int(eligible["crm_correct"].sum()),
                "crm_completeness_pct": 100 * eligible["crm_correct"].mean(),
                "crm_false_positives": int(no_ref["predicted_case_ref"].fillna("").ne("").sum()),
                **latency_summary(group),
            })
    return pd.DataFrame(rows)


def paired_accuracy(evaluation):
    primary = evaluation.loc[evaluation["concurrency"].eq(1)]
    per_query = primary.groupby(["query_id", "system"])["correct"].mean().unstack()
    delta = 100 * (per_query["llm"] - per_query["rule_based"]).to_numpy()
    low, high = interval(delta[bootstrap_indices(len(delta))].mean(axis=1))
    first = primary.loc[primary["repetition"].eq(1)].pivot(
        index="query_id", columns="system", values="correct"
    ).astype(bool)
    llm_only = int((first["llm"] & ~first["rule_based"]).sum())
    baseline_only = int((first["rule_based"] & ~first["llm"]).sum())
    discordant = llm_only + baseline_only
    p_value = binomtest(llm_only, discordant, 0.5, alternative="greater").pvalue if discordant else 1.0
    return {
        "paired_queries": len(delta),
        "delta_pp": delta.mean(),
        "ci_low_pp": low,
        "ci_high_pp": high,
        "first_repeat_llm_only": llm_only,
        "first_repeat_baseline_only": baseline_only,
        "mcnemar_one_sided_p": p_value,
    }


if __name__ == "__main__":
    _, evaluation = load_evaluation(ROOT / "data/raw/test_run.jsonl")
    output = ROOT / "data/processed/metrics_summary.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    summarize(evaluation).to_csv(output, index=False)
    print(pd.Series(paired_accuracy(evaluation)).to_string())
