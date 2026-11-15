import json
import os
from google import genai
from google.genai import types
from google.oauth2 import service_account
from backend.schemas import InterpretRequest, InterpretResponse, ModelingParameters

SYSTEM_PROMPT = """You are a NASA spacecraft fire-safety combustion engineer.
Analyze the user's target habitat atmosphere against the provided top-ranked NASA PSI experimental records and partial-gravity bounding envelope.

STRICT GROUNDING RULES:
1. Every quantitative claim, ignition outcome, or spread rate MUST cite the exact `investigation_id` and `test_id` (e.g., `[SAFFIRE-II | SAFFIRE2-2-5]`).
2. Never invent spread rates. If `flame_spread_rate_mm_s` is null (as in BASS, BASS-II, or ACME-BRE gaseous proxy runs), explicitly state that linear spread rate was not tabulated and rely on qualitative `outcome` and `earth_1g_baseline_spread_mm_s`.
3. Explicitly compare how governing variables differed across the top matches: sample `thickness_mm`, `flow_direction` (Opposed vs. Concurrent), `scale` (Small-Sample MSG/CIR vs. Vehicle-Scale Cygnus), and `po2_psi`.
4. Populate `engineering_summary` with exactly 3 technical bullets.
5. In `earth_dual_use`, map the exact O2%/pressure/material threshold to terrestrial equivalents (clinical hyperbaric oxygen chambers, submarine atmospheres, or firefighter/industrial PPE)."""

def _build_mock_brief(req: InterpretRequest) -> dict:
    """Deterministic schema-valid fallback when credentials/API key are unavailable."""
    r1 = req.top_runs[0]
    ids = [r["test_id"] for r in req.top_runs[:3]]
    env = req.bounding_envelope

    return InterpretResponse(
        engineering_summary=[
            f"Target {req.target.o2_percent}% O2 / {req.target.pressure_psi} psi aligns closest with [{r1['investigation_id']} | {r1['test_id']}] ({r1['outcome']}, PO2={r1.get('po2_psi', 'N/A')} psi).",
            f"Across top matches ({', '.join(ids)}), outcomes vary by airflow ({req.target.airflow_cm_s} cm/s target) and sample thickness ({r1['thickness_mm']} mm).",
            f"Composite Habitat Risk Index is {req.habitat_risk_index}%; vehicle-scale Cygnus data is absent above 22.1% O2, requiring conservative margins.",
        ],
        modeling_parameters=ModelingParameters(
            estimated_loi_percent=f"Evaluated against {r1['o2_percent']}% O2 empirical threshold [{r1['test_id']}].",
            zero_g_spread_bounds_mm_s=(
                f"{env['zero_g_min_mm_s']}–{env['zero_g_max_mm_s']} mm/s"
                if env.get("zero_g_min_mm_s") is not None
                else "Null in top matches (mass-burning/extinction regime only)."
            ),
            partial_g_bracket_mm_s=f"Bounded by 1g Earth baseline ({env.get('earth_1g_min_mm_s')}–{env.get('earth_1g_max_mm_s')} mm/s).",
        ),
        earth_dual_use=(
            f"At {req.target.o2_percent}% O2 and {req.target.pressure_psi} psi, ignition thresholds parallel clinical hyperbaric "
            f"oxygen chambers and submarine atmospheres, governing flame-resistant textile selection for {r1['material']}."
        ),
        cited_test_ids=ids,
    ).model_dump() | {"citation_audit_passed": True, "is_mock": True}


def generate_si_brief(req: InterpretRequest) -> dict:
    gcp_project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    gcp_location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
    api_key = os.environ.get("GEMINI_API_KEY")

    credentials = None
    try:
        import streamlit as st
        if not gcp_project and "GOOGLE_CLOUD_PROJECT" in st.secrets:
            gcp_project = st.secrets["GOOGLE_CLOUD_PROJECT"]
        if "GOOGLE_CLOUD_LOCATION" in st.secrets:
            gcp_location = st.secrets["GOOGLE_CLOUD_LOCATION"]
        if "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
    except Exception:
        pass

    if not gcp_project and not api_key and not credentials:
        return _build_mock_brief(req)

    compact_runs = [
        {
            "investigation_id": r.get("investigation_id"),
            "test_id": r.get("test_id"),
            "scale": r.get("scale"),
            "material": r.get("material"),
            "thickness_mm": r.get("thickness_mm"),
            "o2_percent": r.get("o2_percent"),
            "pressure_psi": r.get("pressure_psi"),
            "po2_psi": r.get("po2_psi"),
            "airflow_cm_s": r.get("airflow_cm_s"),
            "flow_direction": r.get("flow_direction"),
            "outcome": r.get("outcome"),
            "flame_spread_rate_mm_s": r.get("flame_spread_rate_mm_s"),
            "earth_1g_baseline_spread_mm_s": r.get("earth_1g_baseline_spread_mm_s"),
        }
        for r in req.top_runs
    ]

    payload = {
        "target_habitat": req.target.model_dump(),
        "habitat_risk_index_percent": req.habitat_risk_index,
        "partial_gravity_bounding_envelope": req.bounding_envelope,
        "top_ranked_psi_runs": compact_runs,
    }

    try:
        if gcp_project:
            client = genai.Client(
                vertexai=True,
                project=gcp_project,
                location=gcp_location,
                credentials=credentials,
                http_options=types.HttpOptions(timeout=30_000),
            )
        else:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=30_000),
            )
        
        model_name = "gemini-2.5-flash"

        response = client.models.generate_content(
            model=model_name,
            contents=f"Analyze this retrieval bundle and return structured JSON:\n{json.dumps(payload)}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=InterpretResponse,
                temperature=0.1,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if not response.text:
            return {**_build_mock_brief(req), "fallback_error": "Empty response.text"}

        allowed_ids = {r["test_id"] for r in req.top_runs}
        parsed = InterpretResponse.model_validate_json(response.text)
        verified_citations = [tid for tid in parsed.cited_test_ids if tid in allowed_ids]
        result = parsed.model_dump()
        result["cited_test_ids"] = verified_citations
        result["citation_audit_passed"] = len(verified_citations) > 0
        return result
    except Exception as exc:
        return {**_build_mock_brief(req), "fallback_error": repr(exc)}
