# IGNIS-PSI Engineering CSV Export — Utility & Content Specification

## 1. Engineering Utility
The exported CSV packages the Top 5 physics-ranked NASA Physical Sciences Informatics (PSI) combustion runs alongside the target spacecraft atmosphere into a flat, analysis-ready table. Engineers can import it directly into Excel, MATLAB, Python/Pandas, or fire-modeling preprocessors (NIST FDS, ANSYS Fluent, Gpyro) without manual unit conversion or JSON parsing to:

* **Set Solver Boundary Conditions:** Supplies ambient cabin conditions in both NASA engineering units (`psi`, `cm/s`) and SI solver units (`Pa`, `m/s`).
* **Bracket Partial-Gravity Fire Spread:** Bounds unmeasured $1/6g$ (Lunar) and $3/8g$ (Mars) flame spread using empirical $0g$ microgravity and $1g$ Earth baseline rates.
* **Screen Spacecraft Materials:** Evaluates cabin fabrics, polymers, and wire insulations against elevated-$\text{O}_2$ / reduced-pressure ignition outcomes (`No Ignition`, `Self-Extinguished`, `Sustained Spread`).
* **Locate Model Validation Data:** Pinpoints exact `investigation_id` / `test_id` records and instrument channels (radiometers, thermocouples, gas analyzers) for CFD calibration.

---

## 2. File Contents (33 Columns per Ranked Row)

* **Traceability & Fidelity:** `rank`, `relevance_score_pct`, `investigation_id`, `test_id`, `scale`, `is_gaseous_proxy`
* **Target Habitat Conditions (NASA + SI):** `scenario_name`, `habitat_ignition_risk_pct`, `risk_severity_tier`, `target_o2_pct`, `target_pressure_psi`, `target_pressure_pa`, `target_po2_psi`, `target_po2_pa`, `target_airflow_cm_s`, `target_airflow_m_s`
* **Material & Experimental Conditions (NASA + SI):** `material`, `thickness_mm`, `exp_o2_pct`, `exp_pressure_psi`, `exp_pressure_pa`, `exp_po2_psi`, `exp_airflow_cm_s`, `exp_airflow_m_s`, `flow_direction`
* **Flammability & Partial-$g$ Spread Envelope:** `outcome`, `exp_0g_spread_rate_mm_s`, `earth_1g_baseline_spread_mm_s`, `cohort_0g_max_mm_s`, `cohort_lunar_1_6g_est_mm_s`, `cohort_mars_3_8g_est_mm_s`, `cohort_1g_max_mm_s`
* **Validation Telemetry:** `available_sensors` *(semicolon-delimited list of PSI measurement instruments)*

---

How MATLAB uses it: When loaded via T = readtable('ignis_psi_....csv'), an engineer immediately has a clean table where T.target_pressure_pa(1) and T.target_airflow_m_s(1) set the simulation's ambient boundary conditions, while T.cohort_0g_max_mm_s(1) and T.cohort_1g_max_mm_s(1) (alongside the 5 empirical test rows) define the lower and upper flame-spread bounds to validate their partial-gravity simulation against.

---

Epistemic certainty is a property of the NASA PSI experimental dataset, not the user's cursor. Instead of measuring distance to the target, each pixel $(x, y)$ should compute its maximum kernel proximity to the actual NASA PSI experiments in the active material/flow cohort:$$\text{Certainty}(x, y) = \max_{i \in \text{PSI Cohort}} \frac{100}{1 + d^2\big((x, y, z_{\text{target}}),\ \text{run}_i\big)}$$