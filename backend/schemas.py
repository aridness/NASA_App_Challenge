from pydantic import BaseModel, Field
from typing import Any


class HabitatTarget(BaseModel):
    o2_percent: float = Field(..., ge=15.0, le=100.0)
    pressure_psi: float = Field(..., ge=4.0, le=16.0)
    airflow_cm_s: float = Field(..., ge=0.0, le=50.0)
    material: str | None = None
    flow_direction: str | None = None


class InterpretRequest(BaseModel):
    target: HabitatTarget
    top_runs: list[dict[str, Any]] = Field(..., min_length=1, max_length=5)
    bounding_envelope: dict[str, Any]
    habitat_risk_index: float


class ModelingParameters(BaseModel):
    estimated_loi_percent: str = Field(
        ..., description="Recommended Limiting Oxygen Index threshold grounded in cited runs."
    )
    zero_g_spread_bounds_mm_s: str = Field(
        ..., description="Lower/upper 0g flame spread bounds from PSI data (or proxy note if null)."
    )
    partial_g_bracket_mm_s: str = Field(
        ..., description="1/6g Lunar or 3/8g Mars bracket bounded between 0g PSI and 1g Earth baseline."
    )


class InterpretResponse(BaseModel):
    engineering_summary: list[str] = Field(
        ..., min_length=3, max_length=3,
        description="Exactly 3 concise bullets assessing ignition and spread risk in the target habitat."
    )
    modeling_parameters: ModelingParameters
    earth_dual_use: str = Field(
        ..., description="Application of this exact O2/material threshold to hyperbaric chambers, submarines, or firefighter PPE."
    )
    cited_test_ids: list[str] = Field(
        ..., description="Exact test_id strings referenced in the analysis."
    )