import math
from typing import Any

OUTCOME_RISK = {
    "Ignited - Sustained Spread": 1.0,
    "Ignited - Self-Extinguished": 0.4,
    "No Ignition": 0.0,
}


def rank_psi_runs(
    records: list[dict[str, Any]],
    target_o2: float,
    target_p: float,
    target_v: float,
    target_material: str | None = None,
    target_flow: str | None = None,
    target_thickness: float | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    # Deduplicate on test_id (guards against duplicate BASS-R24-T12-S27 row)
    unique_records = list({r["test_id"]: r for r in records}.values())
    target_po2 = (target_o2 / 100.0) * target_p

    # Rebalanced weights & bandwidths:
    # Tighter sigma_v (5.0 cm/s) and higher w_v (0.40) improve outcome discrimination
    # inside the dense 1 atm (21-22.7% O2) BASS/SAFFIRE cluster.
    specs = [
        ("o2", 0.25, 10.0),
        ("po2", 0.25, 1.5),
        ("p", 0.10, 4.0),
        ("v", 0.40, 5.0),
    ]

    scored = []
    for r in unique_records:
        r_po2 = (r["o2_percent"] / 100.0) * r["pressure_psi"]
        diffs = {
            "o2": (r["o2_percent"] - target_o2) / 10.0,
            "po2": (r_po2 - target_po2) / 1.5,
            "p": (r["pressure_psi"] - target_p) / 4.0,
            "v": (r["airflow_cm_s"] - target_v) / 5.0,
        }

        weighted_sq_dist = sum(w * (diffs[k] ** 2) for k, w, _ in specs)

        # Optional thickness term (used when comparing samples of known thickness, e.g., LOO eval)
        if target_thickness is not None and r.get("thickness_mm") is not None:
            thick_diff = (r["thickness_mm"] - target_thickness) / 2.0
            weighted_sq_dist += 0.15 * (thick_diff ** 2)

        # Heavy-tailed Rational Quadratic kernel avoids 0.0 underflow on extreme presets
        sim_score = 100.0 / (1.0 + weighted_sq_dist)

        mat_match = (
            not target_material
            or target_material == "All"
            or r["material"] == target_material
        )
        if not mat_match:
            sim_score *= 0.72

        if target_flow and r.get("flow_direction") != target_flow:
            sim_score *= 0.85

        # Minor fidelity tie-breaker: prefer direct solid tests & non-null 0g spread telemetry
        fidelity_mult = 1.0
        if r["investigation_id"] != "ACME-BRE":
            fidelity_mult += 0.02
        if r["flame_spread_rate_mm_s"] is not None:
            fidelity_mult += 0.02

        final_score = min(100.0, round(sim_score * fidelity_mult, 1))

        scored.append({
            **r,
            "relevance_score": final_score,
            "material_match": mat_match,
            "is_gaseous_proxy": r["investigation_id"] == "ACME-BRE",
            "po2_psi": round(r_po2, 2),
        })

    # Stratified sort: exact material matches always rank ahead of cross-material backfills
    scored.sort(
        key=lambda x: (x["material_match"], x["relevance_score"]),
        reverse=True,
    )
    top_runs = scored[:top_k]

    # Partial-Gravity Bounding Envelope across material-matched cohort
    cohort = [
        r for r in unique_records
        if (not target_material or target_material == "All" or r["material"] == target_material)
    ] or unique_records

    og_rates = [r["flame_spread_rate_mm_s"] for r in cohort if r["flame_spread_rate_mm_s"] is not None]
    eg_rates = [r["earth_1g_baseline_spread_mm_s"] for r in cohort if r["earth_1g_baseline_spread_mm_s"] is not None]

    # Similarity-weighted hazard index across Top-K
    weight_sum = sum(r["relevance_score"] for r in top_runs) or 1.0
    weighted_risk = sum(
        r["relevance_score"] * OUTCOME_RISK.get(r["outcome"], 0.5) for r in top_runs
    ) / weight_sum

    return {
        "top_runs": top_runs,
        "habitat_risk_index": round(weighted_risk * 100, 1),
        "bounding_envelope": {
            "zero_g_min_mm_s": min(og_rates) if og_rates else None,
            "zero_g_max_mm_s": max(og_rates) if og_rates else None,
            "earth_1g_min_mm_s": min(eg_rates) if eg_rates else None,
            "earth_1g_max_mm_s": max(eg_rates) if eg_rates else None,
            "sample_count_0g": len(og_rates),
        },
    }