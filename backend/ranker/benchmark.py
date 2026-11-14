import json
from ranker import rank_psi_runs
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]  # C:\Users\Ariele\Desktop\NASA
DATA_DIR = ROOT_DIR / "data"

DATASET_PATH = DATA_DIR / "psi_solid_flammability.json"
PRESETS_PATH = DATA_DIR / "mission_presets.json"

with open(DATASET_PATH, encoding="utf-8") as f:
    DATA = list({r["test_id"]: r for r in json.load(f)}.values())

with open(PRESETS_PATH, encoding="utf-8") as f:
    PRESETS = json.load(f)


def legacy_rank(records, o2_t, p_t, v_t, mat=None, k=5):
    out = []
    for r in records:
        dist = (
            0.50 * abs(r["o2_percent"] - o2_t) / 30.0
            + 0.25 * abs(r["pressure_psi"] - p_t) / 10.4
            + 0.25 * abs(r["airflow_cm_s"] - v_t) / 30.0
        )
        score = 100.0 - dist * 100.0 + (10.0 if mat and r["material"] == mat else 0.0)
        out.append({**r, "relevance_score": round(score, 1)})
    out.sort(key=lambda x: x["relevance_score"], reverse=True)
    return out[:k]


def run_preset_benchmark():
    print("=== 1. PRESET PRECISION@3 & SCORE BOUNDS ===")
    materials = ["Cotton/Fiberglass Blend", "PMMA (Cast Acrylic)", "Nomex", "Silicone"]
    for preset in PRESETS:
        o2, p, v = preset["o2_percent"], preset["pressure_psi"], preset["airflow_cm_s"]
        for mat in materials:
            old_top = legacy_rank(DATA, o2, p, v, mat, k=3)
            new_res = rank_psi_runs(DATA, o2, p, v, mat, top_k=3)
            new_top = new_res["top_runs"]

            old_p3 = sum(r["material"] == mat for r in old_top) / 3.0
            new_p3 = sum(r["material"] == mat for r in new_top) / 3.0
            old_range = (min(r["relevance_score"] for r in old_top), max(r["relevance_score"] for r in old_top))
            new_range = (min(r["relevance_score"] for r in new_top), max(r["relevance_score"] for r in new_top))

            print(
                f"{preset['id']:18s} | {mat:23s} | "
                f"P@3: {old_p3:.2f}->{new_p3:.2f} | "
                f"Scores: {old_range}->{new_range}"
            )


def run_loo_benchmark():
    print("\n=== 2. LEAVE-ONE-OUT (LOO) OUTCOME CONCORDANCE (k=3) ===")
    for name, fn in [
        (
            "Legacy L1",
            lambda pool, q: legacy_rank(
                pool, q["o2_percent"], q["pressure_psi"], q["airflow_cm_s"], q["material"], k=3
            ),
        ),
        (
            "RQ + PO2",
            lambda pool, q: rank_psi_runs(
                pool,
                q["o2_percent"],
                q["pressure_psi"],
                q["airflow_cm_s"],
                q["material"],
                q.get("flow_direction"),
                q.get("thickness_mm"),
                top_k=3,
            )["top_runs"],
        ),
    ]:
        tp = fp = fn_cnt = 0
        for i, q in enumerate(DATA):
            pool = DATA[:i] + DATA[i + 1 :]
            neighbors = fn(pool, q)
            pos_w = sum(
                max(n["relevance_score"], 0.0)
                for n in neighbors
                if n["outcome"] == "Ignited - Sustained Spread"
            )
            tot_w = sum(max(n["relevance_score"], 0.0) for n in neighbors) or 1.0
            pred = (pos_w / tot_w) >= 0.5
            actual = q["outcome"] == "Ignited - Sustained Spread"

            tp += int(pred and actual)
            fp += int(pred and not actual)
            fn_cnt += int(not pred and actual)

        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn_cnt) if (tp + fn_cnt) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"{name:10s} | Precision: {prec:.3f} | Recall: {rec:.3f} | Sustained-Spread F1: {f1:.3f}")


if __name__ == "__main__":
    run_preset_benchmark()
    run_loo_benchmark()