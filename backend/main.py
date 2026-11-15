import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.ranker.ranker import rank_psi_runs
from backend.schemas import HabitatTarget, InterpretRequest
from backend.interpreter import generate_si_brief

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

with open(DATA_DIR / "psi_solid_flammability.json", encoding="utf-8") as f:
    DATASET = list({r["test_id"]: r for r in json.load(f)}.values())

with open(DATA_DIR / "mission_presets.json", encoding="utf-8") as f:
    PRESETS = json.load(f)

app = FastAPI(title="NASA PSI Flammability & Operating-Envelope API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/presets")
def get_presets():
    return PRESETS


@app.get("/api/dataset")
def get_dataset():
    """Serves all 55 normalized records for the Operating-Envelope Scatter Matrix."""
    return DATASET


@app.post("/api/rank")
def rank_habitat(target: HabitatTarget):
    return rank_psi_runs(
        records=DATASET,
        target_o2=target.o2_percent,
        target_p=target.pressure_psi,
        target_v=target.airflow_cm_s,
        target_material=target.material,
        target_flow=target.flow_direction,
        top_k=5,
    )


@app.post("/api/interpret")
def interpret_habitat(req: InterpretRequest):
    try:
        return generate_si_brief(req)
    except KeyError:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SI synthesis error: {exc}")