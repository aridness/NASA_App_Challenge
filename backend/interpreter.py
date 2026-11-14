import json
import os
from google import genai
from google.genai import types
from backend.schemas import InterpretRequest, InterpretResponse

SYSTEM_PROMPT = """You are a NASA spacecraft fire-safety combustion engineer.
Analyze the user's target habitat atmosphere against the provided top-ranked NASA PSI experimental records and partial-gravity bounding envelope.

STRICT GROUNDING RULES:
1. Every quantitative claim, ignition outcome, or spread rate MUST cite the exact `investigation_id` and `test_id` (e.g., `[SAFFIRE-II | SAFFIRE2-2-5]`).
2. Never invent spread rates. If `flame_spread_rate_mm_s` is null (as in BASS, BASS-II, or ACME-BRE gaseous proxy runs), explicitly state that linear spread rate was not tabulated and rely on qualitative `outcome` and `earth_1g_baseline_spread_mm_s`.
3. Explicitly compare how governing variables differed across the top matches: sample `thickness_mm`, `flow_direction` (Opposed vs. Concurrent), `scale` (Small-Sample MSG/CIR vs. Vehicle-Scale Cygnus), and `po2_psi`.
4. Populate `engineering_summary` with exactly 3 technical bullets.
5. In `earth_dual_use`, map the exact O2%/pressure/material threshold to terrestrial equivalents (clinical hyperbaric oxygen chambers, submarine atmospheres, or firefighter/industrial PPE)."""


def generate_si_brief(req: InterpretRequest) -> dict:
    # Requires GEMINI_API_KEY (or Vertex AI env vars)
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    allowed_ids = {r["test_id"] for r in req.top_runs}
    payload = {
        "target_habitat": req.target.model_dump(),
        "habitat_risk_index_percent": req.habitat_risk_index,
        "partial_gravity_bounding_envelope": req.bounding_envelope,
        "top_ranked_psi_runs": req.top_runs,
    }

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"Analyze this retrieval bundle and return structured JSON:\n{json.dumps(payload, indent=2)}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=InterpretResponse,
            temperature=0.1,  # Low temperature for deterministic citation fidelity
        ),
    )

    parsed = InterpretResponse.model_validate_json(response.text)

    # Deterministic post-check: strip any hallucinated test_ids not present in top_runs
    verified_citations = [tid for tid in parsed.cited_test_ids if tid in allowed_ids]
    result = parsed.model_dump()
    result["cited_test_ids"] = verified_citations
    result["citation_audit_passed"] = len(verified_citations) > 0
    return result