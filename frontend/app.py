import csv
import io
import json
import sys
from pathlib import Path
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# Point Python to the NASA/ root folder
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load environment variables from NASA/.env
load_dotenv(ROOT_DIR / ".env")

from backend.ranker.ranker import rank_psi_runs
from backend.interpreter import generate_si_brief
from backend.schemas import InterpretRequest

IMAGES_DIR = Path(__file__).resolve().parent / "images"

# -----------------------------------------------------------------------------
# Page Config & Clean Scientific Light-Mode Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="IGNIS-PSI | Spacecraft Fire Safety & Partial-g Risk Engine",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] {
        visibility: hidden;
        height: 0px;
    }
    #MainMenu, footer {
        visibility: hidden;
    }
    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 0.6rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
        max-width: 100%;
    }
    .badge {
        display: inline-block;
        padding: 2px 9px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-red { background: #fee2e2; color: #991b1b; border: 1px solid #f87171; }
    .badge-amber { background: #fef3c7; color: #92400e; border: 1px solid #fbbf24; }
    .badge-green { background: #d1fae5; color: #065f46; border: 1px solid #34d399; }
    .badge-blue { background: #e0f2fe; color: #075985; border: 1px solid #38bdf8; }
    .analog-banner {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        padding: 7px 12px;
        margin-top: 8px;
        font-size: 0.82rem;
        color: #0f172a;
    }
    div[data-testid="stImage"] img {
        border-radius: 6px;
        object-fit: cover;
        max-height: 165px;
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# Data Loading (from NASA/data/)
# -----------------------------------------------------------------------------
@st.cache_data
def load_data():
    data_dir = ROOT_DIR / "data"
    with open(data_dir / "psi_solid_flammability.json", "r", encoding="utf-8") as f:
        records = json.load(f)
    with open(data_dir / "mission_presets.json", "r", encoding="utf-8") as f:
        presets = json.load(f)
    return records, presets


records, presets = load_data()
unique_records = list({r["test_id"]: r for r in records}.values())
materials = ["All"] + sorted({r["material"] for r in unique_records if r.get("material")})


# -----------------------------------------------------------------------------
# Local Scenario Image Renderer (frontend/images/)
# -----------------------------------------------------------------------------
def render_scenario_asset(preset_id: str, o2: float, pressure: float, airflow: float):
    meta = {
        "iss_standard": (
            "ISS.jpg",
            "International Space Station (LEO)",
            "0g Microgravity · 1 atm Standard Cabin",
        ),
        "lunar_habitat": (
            "moon.jpg",
            "Artemis Lunar Surface Habitat",
            "1/6g Partial Gravity · Exploration Atmosphere",
        ),
        "mars_habitat": (
            "mars.jpg",
            "Mars Transit & Surface Base",
            "3/8g Partial Gravity · Hypobaric High-O₂",
        ),
        "apollo1_mir_stress": (
            "apollo11.jpg",
            "Hyperoxic Stress Benchmark",
            "High-O₂ / Forced-Flow Boundary Limit",
        ),
    }
    filename, title, regime = meta.get(
        preset_id,
        (None, "Custom Parametric Envelope", "User-Defined Habitat Boundary"),
    )

    image_path = (IMAGES_DIR / filename) if filename else None
    if image_path and image_path.exists():
        st.image(str(image_path), use_container_width=True)
    else:
        st.markdown(
            f"<div style='background:#f1f5f9;border:1px dashed #cbd5e1;border-radius:6px;"
            f"padding:22px 12px;text-align:center;color:#475569;font-size:0.78rem;'>"
            f"<b>Custom Parametric Regime</b><br>Adjust sliders above to probe arbitrary cabin atmospheres</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<div style='text-align:center;margin-top:6px;'>"
        f"<div style='font-size:0.84rem;font-weight:700;color:#0f172a;'>{title}</div>"
        f"<div style='font-size:0.74rem;color:#475569;margin-top:1px;'>{regime}</div>"
        f"<div style='margin-top:6px;'>"
        f"<span class='badge badge-blue'>{o2:.0f}% O₂</span>"
        f"<span class='badge badge-blue'>{pressure:.1f} psi</span>"
        f"<span class='badge badge-blue'>{airflow:.0f} cm/s</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Session State Initialization (Defaults to Lunar Habitat Preset)
# -----------------------------------------------------------------------------
lunar_default = next((p for p in presets if p["id"] == "lunar_habitat"), presets[0])

if "o2" not in st.session_state:
    st.session_state.o2 = float(lunar_default["o2_percent"])
    st.session_state.pressure = float(lunar_default["pressure_psi"])
    st.session_state.airflow = float(lunar_default["airflow_cm_s"])
    st.session_state.active_preset_id = lunar_default["id"]
    st.session_state.active_preset_name = lunar_default["name"]
    st.session_state.material = "All"
    st.session_state.flow_dir = "Any"
    st.session_state.last_brief = None


def apply_preset(preset: dict):
    st.session_state.o2 = float(preset["o2_percent"])
    st.session_state.pressure = float(preset["pressure_psi"])
    st.session_state.airflow = float(preset["airflow_cm_s"])
    st.session_state.active_preset_id = preset["id"]
    st.session_state.active_preset_name = preset["name"]


def mark_custom_profile():
    st.session_state.active_preset_id = "custom"
    st.session_state.active_preset_name = "Custom Habitat Envelope"


# -----------------------------------------------------------------------------
# Cached Wrapper Around backend.interpreter.generate_si_brief
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def get_cached_si_brief(payload_json: str) -> dict:
    req = InterpretRequest.model_validate_json(payload_json)
    return generate_si_brief(req)


# -----------------------------------------------------------------------------
# On-Demand Modal Dialogs (Progressive Disclosure)
# -----------------------------------------------------------------------------
@st.dialog("📄 Top Matched NASA PSI Experimental Sources", width="large")
def show_sources_dialog(matched_runs: list[dict]):
    st.caption(
        "Ranked via physics-informed Rational Quadratic proximity kernel incorporating "
        "oxygen partial pressure ($P_{O_2}$), total pressure, ventilation flow, and material fidelity."
    )
    for idx, run in enumerate(matched_runs, start=1):
        outcome_cls = (
            "badge-red" if "Sustained" in run["outcome"]
            else "badge-amber" if "Self-Extinguished" in run["outcome"]
            else "badge-green"
        )
        spread_0g = (
            f"{run['flame_spread_rate_mm_s']} mm/s"
            if run["flame_spread_rate_mm_s"] is not None
            else "N/A (Proxy/No-Spread)"
        )
        spread_1g = (
            f"{run['earth_1g_baseline_spread_mm_s']} mm/s"
            if run["earth_1g_baseline_spread_mm_s"] is not None
            else "N/A"
        )
        sensors_str = ", ".join(run.get("sensors", [])) or "Standard Telemetry"

        with st.container(border=True):
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"**#{idx} · {run['investigation_id']}** (`{run['test_id']}`) — *{run['scale']}*")
            c2.markdown(
                f"<div style='text-align:right;'><span class='badge badge-blue'>{run['relevance_score']}% Match</span></div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<span class='badge {outcome_cls}'>{run['outcome']}</span> "
                f"<b>{run['material']}</b> ({run['thickness_mm']} mm)",
                unsafe_allow_html=True,
            )
            st.caption(
                f"Atmosphere: **{run['o2_percent']}% O₂** · **{run['pressure_psi']} psi** "
                f"($P_{{O_2}}$ = **{run['po2_psi']} psi**) · Flow: **{run['airflow_cm_s']} cm/s** ({run['flow_direction']})\n\n"
                f"Spread Rates: **0g = {spread_0g}** vs. **1g Earth = {spread_1g}** · Sensors: *{sensors_str}*"
            )


@st.dialog("🧠 Constrained SI Engineering Brief", width="large")
def show_si_brief_dialog(interpret_payload: dict):
    with st.spinner("Synthesizing grounded PSI engineering brief..."):
        brief = get_cached_si_brief(json.dumps(interpret_payload, sort_keys=True))
    st.session_state.last_brief = brief

    h_left, h_right = st.columns([2.2, 1.3])
    with h_left:
        if brief.get("is_mock"):
            st.caption(f"⚙️ Deterministic Fallback Brief · `{brief.get('fallback_error', 'Offline mode')}`")
        else:
            audit_icon = "✅" if brief.get("citation_audit_passed") else "⚠️"
            st.caption(f"{audit_icon} Verified PSI Citations: `{', '.join(brief.get('cited_test_ids', []))}`")
    with h_right:
        focus_mode = st.segmented_control(
            "Brief Perspective",
            options=["Spacecraft", "Earth Dual-Use"],
            default="Spacecraft",
            label_visibility="collapsed",
        )

    if focus_mode == "Earth Dual-Use":
        with st.container(border=True):
            st.markdown("#### 🌍 Earth Dual-Use & Terrestrial Safety")
            st.info(brief["earth_dual_use"])

    with st.container(border=True):
        st.markdown("#### 🚀 Spacecraft Ignition & Spread Assessment")
        for bullet in brief["engineering_summary"]:
            st.markdown(f"- {bullet}")

    with st.container(border=True):
        st.markdown("#### 📐 Predictive Fire-Modeling Parameters")
        mp = brief["modeling_parameters"]
        st.markdown(
            f"- **Estimated LOI:** {mp['estimated_loi_percent']}\n"
            f"- **0g Spread Bounds:** {mp['zero_g_spread_bounds_mm_s']}\n"
            f"- **Partial-g Bracket:** {mp['partial_g_bracket_mm_s']}"
        )

    if focus_mode == "Spacecraft":
        with st.container(border=True):
            st.markdown("#### 🌍 Earth Dual-Use Crossover")
            st.caption(brief["earth_dual_use"])


# -----------------------------------------------------------------------------
# Execute Deterministic Ranker
# -----------------------------------------------------------------------------
flow_arg = None if st.session_state.flow_dir == "Any" else st.session_state.flow_dir
results = rank_psi_runs(
    records=records,
    target_o2=st.session_state.o2,
    target_p=st.session_state.pressure,
    target_v=st.session_state.airflow,
    target_material=st.session_state.material,
    target_flow=flow_arg,
    top_k=5,
)
top_runs = results["top_runs"]
env = results["bounding_envelope"]
risk_pct = results["habitat_risk_index"]
target_po2 = round((st.session_state.o2 / 100.0) * st.session_state.pressure, 2)

if risk_pct >= 70.0:
    risk_tier_label = "CRITICAL IGNITION RISK"
    risk_tier_cls = "badge-red"
elif risk_pct >= 40.0:
    risk_tier_label = "ELEVATED RISK"
    risk_tier_cls = "badge-amber"
else:
    risk_tier_label = "LOW / NOMINAL RISK"
    risk_tier_cls = "badge-green"

interpret_payload = {
    "target": {
        "o2_percent": st.session_state.o2,
        "pressure_psi": st.session_state.pressure,
        "airflow_cm_s": st.session_state.airflow,
        "material": None if st.session_state.material == "All" else st.session_state.material,
        "flow_direction": flow_arg,
    },
    "top_runs": top_runs[:3],
    "habitat_risk_index": risk_pct,
    "bounding_envelope": env,
}

# -----------------------------------------------------------------------------
# Build Engineering CSV Export (NASA + SI Units + Partial-g Bounds)
# -----------------------------------------------------------------------------
PSI_TO_PA = 6894.757

og_max = env["zero_g_max_mm_s"] or 0.0
eg_max = env["earth_1g_max_mm_s"] or 0.0
lunar_est = round(og_max + (1.0 / 6.0) * max(0.0, eg_max - og_max), 2)
mars_est = round(og_max + (3.0 / 8.0) * max(0.0, eg_max - og_max), 2)

csv_buffer = io.StringIO()
csv_fields = [
    "rank",
    "relevance_score_pct",
    "investigation_id",
    "test_id",
    "scale",
    "is_gaseous_proxy",
    "scenario_name",
    "habitat_ignition_risk_pct",
    "risk_severity_tier",
    "target_o2_pct",
    "target_pressure_psi",
    "target_pressure_pa",
    "target_po2_psi",
    "target_po2_pa",
    "target_airflow_cm_s",
    "target_airflow_m_s",
    "material",
    "thickness_mm",
    "exp_o2_pct",
    "exp_pressure_psi",
    "exp_pressure_pa",
    "exp_po2_psi",
    "exp_airflow_cm_s",
    "exp_airflow_m_s",
    "flow_direction",
    "outcome",
    "exp_0g_spread_rate_mm_s",
    "earth_1g_baseline_spread_mm_s",
    "cohort_0g_max_mm_s",
    "cohort_lunar_1_6g_est_mm_s",
    "cohort_mars_3_8g_est_mm_s",
    "cohort_1g_max_mm_s",
    "available_sensors",
]

writer = csv.DictWriter(csv_buffer, fieldnames=csv_fields)
writer.writeheader()

for idx, run in enumerate(top_runs, start=1):
    writer.writerow({
        "rank": idx,
        "relevance_score_pct": run["relevance_score"],
        "investigation_id": run["investigation_id"],
        "test_id": run["test_id"],
        "scale": run.get("scale", ""),
        "is_gaseous_proxy": run.get("is_gaseous_proxy", False),
        "scenario_name": st.session_state.active_preset_name,
        "habitat_ignition_risk_pct": risk_pct,
        "risk_severity_tier": risk_tier_label,
        "target_o2_pct": st.session_state.o2,
        "target_pressure_psi": st.session_state.pressure,
        "target_pressure_pa": round(st.session_state.pressure * PSI_TO_PA, 1),
        "target_po2_psi": target_po2,
        "target_po2_pa": round(target_po2 * PSI_TO_PA, 1),
        "target_airflow_cm_s": st.session_state.airflow,
        "target_airflow_m_s": round(st.session_state.airflow / 100.0, 4),
        "material": run.get("material", ""),
        "thickness_mm": run.get("thickness_mm", ""),
        "exp_o2_pct": run["o2_percent"],
        "exp_pressure_psi": run["pressure_psi"],
        "exp_pressure_pa": round(run["pressure_psi"] * PSI_TO_PA, 1),
        "exp_po2_psi": run.get("po2_psi", round((run["o2_percent"] / 100.0) * run["pressure_psi"], 2)),
        "exp_airflow_cm_s": run["airflow_cm_s"],
        "exp_airflow_m_s": round(run["airflow_cm_s"] / 100.0, 4),
        "flow_direction": run.get("flow_direction", ""),
        "outcome": run["outcome"],
        "exp_0g_spread_rate_mm_s": run["flame_spread_rate_mm_s"] if run["flame_spread_rate_mm_s"] is not None else "",
        "earth_1g_baseline_spread_mm_s": run["earth_1g_baseline_spread_mm_s"] if run["earth_1g_baseline_spread_mm_s"] is not None else "",
        "cohort_0g_max_mm_s": env["zero_g_max_mm_s"] if env["zero_g_max_mm_s"] is not None else "",
        "cohort_lunar_1_6g_est_mm_s": lunar_est if env["zero_g_max_mm_s"] is not None else "",
        "cohort_mars_3_8g_est_mm_s": mars_est if env["zero_g_max_mm_s"] is not None else "",
        "cohort_1g_max_mm_s": env["earth_1g_max_mm_s"] if env["earth_1g_max_mm_s"] is not None else "",
        "available_sensors": "; ".join(run.get("sensors", [])),
    })

csv_data = csv_buffer.getvalue()

# -----------------------------------------------------------------------------
# Top Header Action Bar
# -----------------------------------------------------------------------------
hdr_title, btn_sources, btn_brief, btn_export = st.columns([2.85, 1.05, 1.05, 0.85], gap="small")

with hdr_title:
    st.markdown(
        f"<div style='padding-top:2px;'>"
        f"<span style='font-size:1.35rem;font-weight:700;color:#0f172a;'>🔥 IGNIS-PSI</span>"
        f"<span style='color:#cbd5e1;margin:0 10px;'>|</span>"
        f"<span style='font-size:0.92rem;color:#475569;'>"
        f"Active Scenario: <b style='color:#0f172a;'>{st.session_state.active_preset_name}</b> "
        f"({st.session_state.o2:.1f}% O₂ · {st.session_state.pressure:.1f} psi · {st.session_state.airflow:.0f} cm/s)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

with btn_sources:
    if st.button(f"📄 PSI Sources ({len(top_runs)})", use_container_width=True):
        show_sources_dialog(top_runs)

with btn_brief:
    if st.button("🧠 Generate SI Brief", type="primary", use_container_width=True):
        show_si_brief_dialog(interpret_payload)

with btn_export:
    st.download_button(
        label="⬇️ Export CSV",
        data=csv_data,
        file_name=f"ignis_psi_{int(st.session_state.o2)}pctO2_{st.session_state.pressure}psi.csv",
        mime="text/csv",
        use_container_width=True,
        help="Download Fire-Modeling & Analog Matrix (CSV with SI & NASA Units)",
    )

st.markdown("<hr style='margin: 0.4rem 0 0.8rem 0; border-color: #e2e8f0;'>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2-Zone Asymmetric Cockpit (Left Scenario Rail | Center Hero Stage)
# -----------------------------------------------------------------------------
col_left, col_stage = st.columns([1.0, 2.85], gap="medium")

# =============================================================================
# ZONE 1: LEFT RAIL (Mission Presets + Swappable Image / Custom Controls)
# =============================================================================
with col_left:
    with st.container(border=True):
        st.markdown("**Mission Scenarios**")
        st.caption("Select a spacecraft benchmark to evaluate fire risk:")

        preset_icons = {
            "iss_standard": "🛰️",
            "lunar_habitat": "🌔",
            "mars_habitat": "🔴",
            "apollo1_mir_stress": "⚠️",
        }
        preset_short_names = {
            "iss_standard": "ISS Standard",
            "lunar_habitat": "Lunar Habitat",
            "mars_habitat": "Mars Transit",
            "apollo1_mir_stress": "Apollo 1 / Mir",
        }

        for preset in presets:
            pid = preset["id"]
            icon = preset_icons.get(pid, "🚀")
            title = preset_short_names.get(pid, preset["name"])
            is_active = st.session_state.active_preset_id == pid
            label = f"{icon} {title}  ·  {preset['o2_percent']:.0f}% O₂ | {preset['pressure_psi']} psi"

            st.button(
                label,
                key=f"preset_card_{pid}",
                type="primary" if is_active else "secondary",
                use_container_width=True,
                help=preset["description"],
                on_click=apply_preset,
                args=(preset,),
            )

    with st.container(border=True):
        custom_expanded = st.toggle("⚙️ Custom Habitat & Fuel Parameters", value=False)
        if custom_expanded:
            st.slider(
                "Oxygen Mole Fraction (O₂ %)",
                min_value=18.0,
                max_value=55.0,
                step=0.5,
                key="o2",
                on_change=mark_custom_profile,
            )
            st.slider(
                "Cabin Pressure (psi)",
                min_value=4.3,
                max_value=14.7,
                step=0.1,
                key="pressure",
                on_change=mark_custom_profile,
            )
            st.slider(
                "Ventilation Airflow (cm/s)",
                min_value=0.0,
                max_value=30.0,
                step=0.5,
                key="airflow",
                on_change=mark_custom_profile,
            )
            st.selectbox(
                "Material Category",
                options=materials,
                key="material",
            )
            st.radio(
                "Ventilation Flow Direction",
                options=["Any", "Opposed", "Concurrent"],
                horizontal=True,
                key="flow_dir",
            )
        else:
            render_scenario_asset(
                st.session_state.active_preset_id,
                st.session_state.o2,
                st.session_state.pressure,
                st.session_state.airflow,
            )

# =============================================================================
# ZONE 2: CENTER HERO STAGE (KPI Strip + Empirical Manifold + Partial-g Anchor)
# =============================================================================
with col_stage:
    # 1. Top KPI Strip
    m1, m2, m3 = st.columns(3)
    with m1:
        with st.container(border=True):
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<span style='font-size:0.74rem;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:0.04em;'>Habitat Ignition Risk</span>"
                f"<span class='badge {risk_tier_cls}' style='margin-right:0;'>{risk_tier_label}</span>"
                f"</div>"
                f"<div style='font-size:1.65rem;font-weight:700;color:#0f172a;margin-top:4px;'>{risk_pct}%</div>"
                f"<div style='font-size:0.78rem;color:#64748b;margin-top:2px;'>Similarity-weighted across Top {len(top_runs)} PSI tests</div>",
                unsafe_allow_html=True,
            )
    with m2:
        with st.container(border=True):
            po2_delta = round(target_po2 - 3.09, 2)
            po2_badge_cls = "badge-red" if po2_delta > 0.5 else ("badge-amber" if po2_delta > 0 else "badge-green")
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<span style='font-size:0.74rem;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:0.04em;'>O₂ Partial Pressure (PO₂)</span>"
                f"<span class='badge {po2_badge_cls}' style='margin-right:0;'>{po2_delta:+.2f} psi vs Earth</span>"
                f"</div>"
                f"<div style='font-size:1.65rem;font-weight:700;color:#0f172a;margin-top:4px;'>{target_po2} psi</div>"
                f"<div style='font-size:0.78rem;color:#64748b;margin-top:2px;'>Earth sea-level baseline: 3.09 psi</div>",
                unsafe_allow_html=True,
            )
    with m3:
        with st.container(border=True):
            og_range = (
                f"{env['zero_g_min_mm_s']}–{env['zero_g_max_mm_s']} mm/s"
                if env["zero_g_max_mm_s"] is not None
                else "N/A"
            )
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<span style='font-size:0.74rem;font-weight:600;color:#475569;text-transform:uppercase;letter-spacing:0.04em;'>0g Microgravity Spread</span>"
                f"<span class='badge badge-blue' style='margin-right:0;'>{env['sample_count_0g']} valid runs</span>"
                f"</div>"
                f"<div style='font-size:1.65rem;font-weight:700;color:#0f172a;margin-top:4px;'>{og_range}</div>"
                f"<div style='font-size:0.78rem;color:#64748b;margin-top:2px;'>Cohort: {st.session_state.material}</div>",
                unsafe_allow_html=True,
            )

    # 2. Hero Empirical Data Manifold + Top-5 Matched Analogs
    with st.container(border=True):
        hdr_plot, hdr_axis = st.columns([3.0, 1.2])
        with hdr_plot:
            st.markdown("**PSI Empirical Support Manifold & Top-5 Matched Analogs**")
        with hdr_axis:
            y_axis_choice = st.selectbox(
                "Y-Axis",
                options=["Airflow Velocity (cm/s)", "Cabin Pressure (psi)"],
                label_visibility="collapsed",
            )

        y_field = "airflow_cm_s" if "Airflow" in y_axis_choice else "pressure_psi"
        target_y_val = st.session_state.airflow if y_field == "airflow_cm_s" else st.session_state.pressure

        # Filter PSI records to active material/flow cohort so the manifold reflects real data coverage
        cohort_records = [
            r for r in unique_records
            if (st.session_state.material == "All" or r.get("material") == st.session_state.material)
            and (flow_arg is None or r.get("flow_direction") == flow_arg)
        ] or unique_records

        # High-resolution 2D grid evaluating empirical proximity to NASA PSI experiments
        x_grid = [17.0 + i * (39.0 / 119.0) for i in range(120)]
        y_min_axis, y_max_axis = (-1.0, 32.0) if y_field == "airflow_cm_s" else (3.5, 16.0)
        y_grid = [y_min_axis + j * ((y_max_axis - y_min_axis) / 89.0) for j in range(90)]

        z_grid = []
        for y_val in y_grid:
            row_scores = []
            for o2_val in x_grid:
                p_val = st.session_state.pressure if y_field == "airflow_cm_s" else y_val
                v_val = y_val if y_field == "airflow_cm_s" else st.session_state.airflow
                po2_val = (o2_val / 100.0) * p_val

                max_support = 0.0
                for r in cohort_records:
                    r_po2 = r.get("po2_psi", (r["o2_percent"] / 100.0) * r["pressure_psi"])
                    dist_sq = (
                        0.25 * ((o2_val - r["o2_percent"]) / 10.0) ** 2
                        + 0.25 * ((po2_val - r_po2) / 1.5) ** 2
                        + 0.10 * ((p_val - r["pressure_psi"]) / 4.0) ** 2
                        + 0.40 * ((v_val - r["airflow_cm_s"]) / 5.0) ** 2
                    )
                    sim = 100.0 / (1.0 + dist_sq)
                    if sim > max_support:
                        max_support = sim
                row_scores.append(round(max_support, 2))
            z_grid.append(row_scores)

        fig = go.Figure()

        # Direct two-color smooth gradient (Warm Amber -> Sky Cyan, no white stop)
        fig.add_trace(
            go.Heatmap(
                x=x_grid,
                y=y_grid,
                z=z_grid,
                zsmooth="best",
                zmin=0,
                zmax=100,
                colorscale=[
                    [0.0, "#fde68a"],  # Warm amber: untested extrapolation regime
                    [1.0, "#38bdf8"],  # Sky cyan: high empirical NASA PSI support
                ],
                colorbar=dict(
                    title=dict(text="Empirical<br>Support %", font=dict(size=10, color="#334155")),
                    thickness=12,
                    len=0.82,
                    tickfont=dict(size=9, color="#334155"),
                ),
                hovertemplate=(
                    "O₂: %{x:.1f}%<br>"
                    + y_axis_choice.split(" (")[0]
                    + ": %{y:.1f}<br>PSI Data Support: %{z:.1f}%<extra></extra>"
                ),
                showscale=True,
            )
        )

        # Planned Lunar / Martian Habitat Zone (>= 30% O2)
        y_max_bound = 32.0 if y_field == "airflow_cm_s" else 10.2
        y_min_bound = 0.0 if y_field == "airflow_cm_s" else 4.0
        fig.add_shape(
            type="rect",
            x0=30.0,
            x1=56.0,
            y0=y_min_bound,
            y1=y_max_bound,
            fillcolor="rgba(255, 255, 255, 0.0)",
            line=dict(color="rgba(15, 23, 42, 0.55)", width=1.5, dash="dash"),
        )
        fig.add_annotation(
            x=43.0,
            y=y_max_bound * 0.94,
            text="Exploration Habitat Zone (≥30% O₂)",
            showarrow=False,
            font=dict(color="#0f172a", size=11),
        )

        # Plot ONLY the Top-5 Selected Best Datapoints
        outcome_colors = {
            "Ignited - Sustained Spread": "#dc2626",
            "Ignited - Self-Extinguished": "#d97706",
            "No Ignition": "#059669",
        }
        inv_symbols = {
            "BASS": "circle",
            "BASS-II": "circle",
            "SAFFIRE-I": "square",
            "SAFFIRE-II": "square",
            "SAFFIRE-III": "square",
            "ACME-BRE": "diamond",
        }

        ranked_runs = list(enumerate(top_runs, start=1))
        for outcome, color in outcome_colors.items():
            sub = [(idx, r) for idx, r in ranked_runs if r["outcome"] == outcome]
            if not sub:
                continue
            symbols = [inv_symbols.get(r["investigation_id"], "circle") for _, r in sub]
            hover_texts = [
                f"<b>Rank #{idx} · {r['investigation_id']} | {r['test_id']}</b><br>"
                f"Similarity Match: <b>{r['relevance_score']}%</b><br>"
                f"Material: {r['material']} ({r['thickness_mm']} mm)<br>"
                f"O₂: {r['o2_percent']}% | P: {r['pressure_psi']} psi | V: {r['airflow_cm_s']} cm/s<br>"
                f"Flow: {r['flow_direction']} | Outcome: {r['outcome']}<br>"
                f"0g Spread: {r['flame_spread_rate_mm_s']} mm/s | 1g Base: {r['earth_1g_baseline_spread_mm_s']} mm/s"
                for idx, r in sub
            ]
            fig.add_trace(
                go.Scatter(
                    x=[r["o2_percent"] for _, r in sub],
                    y=[r[y_field] for _, r in sub],
                    mode="markers+text",
                    name=outcome.replace("Ignited - ", ""),
                    text=[f"#{idx}" for idx, _ in sub],
                    textposition="bottom center",
                    textfont=dict(size=10, color="#0f172a", family="sans-serif"),
                    marker=dict(
                        size=14,
                        color=color,
                        symbol=symbols,
                        line=dict(width=2, color="#ffffff"),
                        opacity=0.98,
                    ),
                    hovertext=hover_texts,
                    hoverinfo="text",
                )
            )

        # Live Target Crosshair
        fig.add_trace(
            go.Scatter(
                x=[st.session_state.o2],
                y=[target_y_val],
                mode="markers+text",
                name="Target Habitat",
                text=["TARGET"],
                textposition="top center",
                textfont=dict(color="#0f172a", size=11, family="sans-serif"),
                marker=dict(
                    size=18,
                    color="#0f172a",
                    symbol="cross-thin",
                    line=dict(width=3, color="#0f172a"),
                ),
                hovertemplate=(
                    f"<b>Target Habitat</b><br>O₂: {st.session_state.o2}%<br>"
                    f"P: {st.session_state.pressure} psi | V: {st.session_state.airflow} cm/s<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            height=305,
            margin=dict(l=10, r=10, t=8, b=8),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#fde68a",
            font=dict(color="#0f172a", size=11),
            xaxis=dict(
                title="Oxygen Mole Fraction (%)",
                range=[17, 56],
                showgrid=False,
                linecolor="#cbd5e1",
                zeroline=False,
            ),
            yaxis=dict(
                title=y_axis_choice,
                range=[y_min_axis, y_max_axis],
                showgrid=False,
                linecolor="#cbd5e1",
                zeroline=False,
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                font=dict(size=10),
            ),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption(
            "Top-5 Matched Analogs (#1–#5) over Empirical PSI Data Manifold (Cyan = Tested Regime, Amber = Extrapolation) &nbsp;|&nbsp; "
            "Shapes: ● BASS / BASS-II &nbsp; ■ Saffire &nbsp; ◆ ACME-BRE"
        )

    # 3. Compact Partial-Gravity Bounding Envelope & #1 Analog Verdict
    with st.container(border=True):
        scale_max = max(eg_max, og_max, 1.0)
        og_pct = min(100.0, round((og_max / scale_max) * 100.0, 1))
        lunar_pct = min(100.0, round((lunar_est / scale_max) * 100.0, 1))
        mars_pct = min(100.0, round((mars_est / scale_max) * 100.0, 1))
        eg_pct = min(100.0, round((eg_max / scale_max) * 100.0, 1))

        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;'>"
            f"<span style='font-size:0.86rem;font-weight:700;color:#0f172a;'>Partial-Gravity Flame Spread Envelope ({st.session_state.material} Cohort)</span>"
            f"<span style='font-size:0.80rem;color:#334155;'>"
            f"<span style='color:#0284c7;font-weight:600;'>■ 0g PSI Max: {og_max} mm/s</span> &nbsp;→&nbsp; "
            f"<b>Lunar (1/6g): ~{lunar_est}</b> &nbsp;|&nbsp; "
            f"<b>Mars (3/8g): ~{mars_est}</b> &nbsp;→&nbsp; "
            f"<span style='color:#b45309;font-weight:600;'>■ 1g Earth Max: {eg_max} mm/s</span>"
            f"</span></div>"
            f"<div style='position:relative;height:14px;background:#e2e8f0;border-radius:999px;overflow:hidden;'>"
            f"<div style='position:absolute;left:0;top:0;height:100%;width:{eg_pct}%;background:#fde68a;'></div>"
            f"<div style='position:absolute;left:0;top:0;height:100%;width:{og_pct}%;background:#0284c7;'></div>"
            f"<div style='position:absolute;left:{lunar_pct}%;top:0;height:100%;width:3px;background:#0f172a;' title='Lunar 1/6g'></div>"
            f"<div style='position:absolute;left:{mars_pct}%;top:0;height:100%;width:3px;background:#dc2626;' title='Mars 3/8g'></div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if top_runs:
            best = top_runs[0]
            outcome_cls = (
                "badge-red" if "Sustained" in best["outcome"]
                else "badge-amber" if "Self-Extinguished" in best["outcome"]
                else "badge-green"
            )
            st.markdown(
                f"<div class='analog-banner'>"
                f"<span class='badge badge-blue'>#1 Closest Analog · {best['relevance_score']}% Match</span>"
                f"<b>{best['investigation_id']} · {best['test_id']}</b> &nbsp;|&nbsp; "
                f"{best['material']} ({best['thickness_mm']} mm) &nbsp;|&nbsp; "
                f"<span class='badge {outcome_cls}'>{best['outcome']}</span>"
                f"<span style='color:#64748b;font-size:0.78rem;'>({best['o2_percent']}% O₂, {best['pressure_psi']} psi, {best['airflow_cm_s']} cm/s)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )