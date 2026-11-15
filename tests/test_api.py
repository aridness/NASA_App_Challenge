import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "cached_briefs.json"

MATERIALS = [
    "Cotton/Fiberglass Blend",
    "PMMA (Cast Acrylic)",
    "Nomex",
    "Silicone",
]


def _make_cache_key(o2: float, p: float, v: float, material: str | None) -> str:
    return f"{o2:.1f}_{p:.1f}_{v:.1f}_{material or 'All'}"


def test_end_to_end():
    presets = client.get("/api/presets").json()
    dataset = client.get("/api/dataset").json()
    print(f"[OK] Loaded {len(dataset)} records and {len(presets)} presets.")

    saved_briefs = {}

    for p in presets:
        for mat in MATERIALS:
            target = {
                "o2_percent": p["o2_percent"],
                "pressure_psi": p["pressure_psi"],
                "airflow_cm_s": p["airflow_cm_s"],
                "material": mat,
            }
            rank_res = client.post("/api/rank", json=target)
            assert rank_res.status_code == 200, rank_res.text
            rank_data = rank_res.json()

            si_res = client.post(
                "/api/interpret",
                json={
                    "target": target,
                    "top_runs": rank_data["top_runs"][:3],
                    "bounding_envelope": rank_data["bounding_envelope"],
                    "habitat_risk_index": rank_data["habitat_risk_index"],
                },
            )
            assert si_res.status_code == 200, si_res.text
            si_data = si_res.json()

            assert len(si_data["engineering_summary"]) == 3
            assert si_data["citation_audit_passed"] is True
            assert not si_data.get("is_mock"), (
                f"Fallback mock on {p['id']} | {mat}: {si_data.get('fallback_error', 'No credentials loaded')}"
            )

            key = _make_cache_key(
                target["o2_percent"],
                target["pressure_psi"],
                target["airflow_cm_s"],
                target["material"],
            )
            saved_briefs[key] = si_data

            print(
                f"[OK] {p['id']:18s} | {mat:23s} | "
                f"Top: {rank_data['top_runs'][0]['relevance_score']:5.1f} | "
                f"Risk: {rank_data['habitat_risk_index']:5.1f}% | "
                f"Citations: {si_data['cited_test_ids']}"
            )

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(saved_briefs, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Saved {len(saved_briefs)} live Vertex AI briefs to {CACHE_PATH}")


if __name__ == "__main__":
    test_end_to_end()