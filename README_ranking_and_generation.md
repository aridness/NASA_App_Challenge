# Deterministic Physics-Informed Ranking & Constrained SI Synthesis Engine

A transparent retrieval, hazard-quantification, and citation-constrained synthesis backend built on top of the normalized NASA Physical Sciences Informatics (PSI) solid-flammability dataset (`psi_solid_flammability.json`). Replacing black-box semantic embeddings with a physics-informed Rational Quadratic similarity kernel and schema-enforced LLM synthesis, this layer ranks empirical microgravity ($0g$) analogs, brackets partial-gravity ($1/6g$ Lunar, $3/8g$ Mars) flame-spread rates against $1g$ Earth baselines, and generates strictly cited engineering risk briefs.

---

## Current Project Scope (Phase 2 Completed)

Work completed in Phase 2 covers **deterministic proximity scoring, offline retrieval benchmarking, schema-enforced LLM synthesis, and REST API exposure**:

1. **Physics-Informed Proximity & Bounding Engine (`backend/ranker/ranker.py`):** Implemented a bounded `(0, 100]` heavy-tailed Rational Quadratic ranker incorporating oxygen partial pressure ($P_{\text{O}_2}$), stratified material matching, fidelity tie-breaking, similarity-weighted hazard scoring, and cohort-level partial-gravity envelope aggregation.
2. **Offline Information Retrieval & Concordance Benchmark (`backend/ranker/benchmark.py`):** Validated the ranking function against a baseline linear L1 formula across all 16 mission preset $\times$ material combinations (`Precision@3 = 1.00`) and Leave-One-Out (LOO) ignition outcome concordance (`Sustained-Spread F1 = 0.827`).
3. **Constrained "SI" Interpreter & Citation Auditor (`backend/interpreter.py`, `backend/schemas.py`):** Configured structured JSON synthesis via `gemini-3.8-flash` with Pydantic schema enforcement, deterministic `test_id` post-verification, and an offline deterministic fallback (`_build_mock_brief`) for key-free local testing.
4. **FastAPI Service Layer & Automated Smoke Tests (`backend/main.py`, `tests/test_api.py`):** Exposed four REST endpoints (`/api/presets`, `/api/dataset`, `/api/rank`, `/api/interpret`) and verified end-to-end schema and citation integrity across all 55 unique PSI records and 4 mission presets.

---

## Workspace Structure

```text
NASA/
├── backend/
│   ├── ranker/
│   │   ├── ranker.py                 # Physics-informed Rational Quadratic ranker & envelope builder
│   │   └── benchmark.py              # Preset P@3 & Leave-One-Out (LOO) concordance evaluation suite
│   ├── interpreter.py                # Constrained Gemini 2.5 Flash synthesis + citation audit
│   ├── main.py                       # FastAPI application entrypoint
│   └── schemas.py                    # Pydantic request/response contracts
├── data/
│   ├── raw/                          # Original PSI CSV/Excel matrices & metadata PDFs
│   ├── psi_solid_flammability.json   # Unified 55-record (56-row) normalized dataset
│   └── mission_presets.json          # Reference atmospheric benchmarks
├── frontend/                         # Phase 3 interactive dashboard workspace
├── scripts/
│   ├── src_eda/                      # Phase 1 inspection & PDF extraction utilities
│   └── normalize_data.py             # Master ETL normalization pipeline
└── tests/
    └── test_api.py                   # End-to-end FastAPI TestClient verification suite

```

---

## Physics-Informed Proximity & Risk Architecture (`ranker.py`)

### 1. Coupling Mole Fraction and Pressure via $P_{\text{O}_2}$

Because spacecraft exploration habitats alter both oxygen concentration and total cabin pressure simultaneously (e.g., `32.0% O2` at `10.2 psi` on Lunar habitats or `34.0% O2` at `8.2 psi` on Mars transit vehicles), evaluating $\text{O}_2\%$ and total pressure independently misrepresents gas-phase reaction kinetics. Prior to distance calculation, both the target query and every deduplicated PSI record compute oxygen partial pressure:

$$P_{\text{O}_2} = \frac{\text{O}_2\%}{100} \cdot P$$

### 2. Heavy-Tailed Rational Quadratic Similarity Kernel

Rather than unbounded linear subtraction—which overflows above `100` on exact material matches and underflows below `0` on extreme stress presets—proximity is computed via a weighted Rational Quadratic (Cauchy-type) kernel strictly bounded in `(0, 100]`:

$$d_w^2 = \sum_{i \in \{O_2, P_{O_2}, P, V\}} w_i \left(\frac{x_i - x_{i,\text{target}}}{\sigma_i}\right)^2 + \mathbb{I}(t_{\text{target}} \neq \text{None}) \cdot 0.15 \left(\frac{t - t_{\text{target}}}{2.0}\right)^2$$

$$\text{Score} = \min\left(100.0,\; \text{round}\left(\frac{100.0}{1.0 + d_w^2} \cdot M_{\text{mat}} \cdot M_{\text{flow}} \cdot M_{\text{fidelity}},\; 1\right)\right)$$

* **Why Rational Quadratic over Gaussian RBF:** A pure Gaussian kernel ($\exp(-d_w^2)$) underflows to `0.0` across all records on extreme out-of-distribution queries (such as `apollo1_mir_stress` at `50% O2 / 14.7 psi`), collapsing rank ordering into arbitrary tie-breaks. Polynomial tail decay preserves smooth, non-degenerate ranking across all atmospheric regimes.

| Feature ($i$) | Weight ($w_i$) | Bandwidth ($\sigma_i$) | Physical & Empirical Rationale |
| --- | --- | --- | --- |
| **$\text{O}_2\%$** | `0.25` | `10.0 %` | Captures direct oxygen mole-fraction proximity and nitrogen thermal-quenching dilution. |
| **$P_{\text{O}_2}$** | `0.25` | `1.5 psi` | Bridges hypobaric/hyperoxic exploration regimes (`ACME-BRE`) with $1\text{ atm}$ tests. |
| **Total Pressure ($P$)** | `0.10` | `4.0 psi` | Accounts for total-pressure diffusive and buoyant transport variations. |
| **Airflow Velocity ($V$)** | `0.40` | `5.0 cm/s` | Tight bandwidth (`5.0 cm/s`) discriminates low-flow quenching vs. convective spread inside the dense $1\text{ atm}$ (`21–22.7% O2`) `BASS`/`SAFFIRE` cluster. |
| **Thickness ($t$, optional)** | `0.15` | `2.0 mm` | Applied when target sample thickness is specified (e.g., Leave-One-Out validation). |

### 3. Multipliers, Stratified Sorting & Decoupled Envelopes

* **Domain Multipliers:** Non-matching materials incur $M_{\text{mat}} = 0.72$; mismatched `flow_direction` (`Concurrent` vs. `Opposed`) incurs $M_{\text{flow}} = 0.85$. A minor fidelity tie-breaker $M_{\text{fidelity}} \in [1.00, 1.04]$ adds `+0.02` for direct solid-fuel experiments (`SAFFIRE`, `BASS`, `BASS-II`) over gaseous ethylene burner proxies (`ACME-BRE`) and `+0.02` for records with measured non-null `flame_spread_rate_mm_s`.
* **Stratified Material Retrieval:** Candidate runs are sorted by `(material_match, relevance_score)` descending. Because elevated-$\text{O}_2$ / reduced-pressure runs exist only in `ACME-BRE` (`PMMA` and `Cotton/Fiberglass`), stratification prevents gaseous proxy records from crowding out exact material analogs (`Nomex`, `Silicone`) during elevated-$\text{O}_2$ queries.
* **Similarity-Weighted Hazard Index (`habitat_risk_index`):** Computed over the Top-$K$ (`k=5`) retrieved runs by weighting empirical outcome severity (`"Ignited - Sustained Spread": 1.0`, `"Ignited - Self-Extinguished": 0.4`, `"No Ignition": 0.0`) by each run's `relevance_score`.
* **Cohort-Level Partial-Gravity Bounding Envelope (`bounding_envelope`):** Because `43 / 55` unique records (`BASS`, `BASS-II`, `ACME-BRE`) retain `"flame_spread_rate_mm_s": null`, spread-rate bounds (`zero_g_min_mm_s`, `zero_g_max_mm_s`, `earth_1g_min_mm_s`, `earth_1g_max_mm_s`, `sample_count_0g`) are aggregated across the full material-matched cohort rather than only the Top-5 slice, ensuring $1/6g$ Lunar and $3/8g$ Mars visual bounds remain populated even when top matches come from extinction-only investigations.

---

## Offline Retrieval & Concordance Validation (`benchmark.py`)

To verify ranking behavior without subjective labels, `benchmark.py` evaluates `RQ + PO2` against the initial linear L1 formula (`Legacy L1`) across two quantitative tests:

### 1. Preset Material `Precision@3` & Score Calibration

Evaluates Top-3 retrieval across all 4 presets $\times$ 4 primary material classes (`16` queries total):

| Mission Preset | Target Material | `Legacy L1` `P@3` $\rightarrow$ `RQ + PO2` `P@3` | `Legacy L1` Scores $\rightarrow$ `RQ + PO2` Scores |
| --- | --- | --- | --- |
| `iss_standard` (`21% O2, 14.7 psi`) | All 4 Materials | `1.00` $\rightarrow$ **`1.00`** | `(99.8, 108.7)` $\rightarrow$ **`(39.1, 100.0)`** |
| `lunar_habitat` (`32% O2, 10.2 psi`) | `Cotton/Fiberglass Blend` | `0.67` $\rightarrow$ **`1.00`** | `(87.7, 93.5)` $\rightarrow$ **`(58.7, 62.2)`** |
| `lunar_habitat` (`32% O2, 10.2 psi`) | `Nomex` / `Silicone` | `0.00` $\rightarrow$ **`1.00`** | `(83.5, 87.7)` $\rightarrow$ **`(57.6, 75.1)`** |
| `mars_habitat` (`34% O2, 8.2 psi`) | `Cotton/Fiberglass Blend` | `0.33` $\rightarrow$ **`1.00`** | `(94.2, 104.2)` $\rightarrow$ **`(61.0, 61.6)`** |
| `mars_habitat` (`34% O2, 8.2 psi`) | `Nomex` / `Silicone` | `0.00` $\rightarrow$ **`1.00`** | `(94.2, 98.3)` $\rightarrow$ **`(38.3, 59.6)`** |
| `apollo1_mir_stress` (`50% O2, 14.7 psi`) | All 4 Materials | `1.00` $\rightarrow$ **`1.00`** | `(53.8, 61.0)` $\rightarrow$ **`(15.5, 20.4)`** |

### 2. Leave-One-Out (LOO) Outcome Concordance ($k=3$)

Each of the 55 unique records is held out as a query against the remaining 54 records, predicting binary `"Ignited - Sustained Spread"` via similarity-weighted Top-3 neighbor voting:

| Ranker Model | Precision | Recall | Sustained-Spread F1 |
| --- | --- | --- | --- |
| `Legacy L1` | `0.816` | `0.838` | `0.827` |
| **`RQ + PO2` (Production)** | **`0.816`** | **`0.838`** | **`0.827`** |

---

## Constrained "SI" Synthesis & API Layer (`main.py`, `interpreter.py`, `schemas.py`)

### REST Endpoints (`backend/main.py`)

| Method | Endpoint | Request / Response Contract | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/presets` | `list[dict]` | Serves the 4 standardized mission benchmarks from `data/mission_presets.json`. |
| `GET` | `/api/dataset` | `list[dict]` | Serves all 55 deduplicated PSI records for the Phase 3 Operating-Envelope Scatter Matrix. |
| `POST` | `/api/rank` | `HabitatTarget` $\rightarrow$ `dict` | Executes `rank_psi_runs(..., top_k=5)` and returns `top_runs`, `habitat_risk_index`, and `bounding_envelope`. |
| `POST` | `/api/interpret` | `InterpretRequest` $\rightarrow$ `dict` | Synthesizes a citation-audited 3-part engineering brief from the Top-3 ranked runs and bounding envelope. |

### Grounding Guardrails & Offline Fallback (`backend/interpreter.py`)

* **Structured Output Enforcement:** Calls `gemini-3.8-flash` (`temperature=0.1`) with `response_mime_type="application/json"` and `response_schema=InterpretResponse` (`schemas.py`), guaranteeing exact field structure (`engineering_summary` with 3 bullets, `modeling_parameters`, `earth_dual_use`, and `cited_test_ids`).
* **Anti-Hallucination & Null-Rate Rules:** The system prompt requires `[investigation_id | test_id]` citations for every claim, prohibits fabricating linear spread rates when `flame_spread_rate_mm_s` is `null`, and forces explicit cross-match comparison across `thickness_mm`, `flow_direction`, `scale`, and `po2_psi`.
* **Deterministic Citation Post-Check:** Every returned string in `cited_test_ids` is intersected against the exact `test_id` set passed in `req.top_runs`, stripping ungrounded IDs and setting `"citation_audit_passed": true`.
* **Key-Free Offline Mode (`_build_mock_brief`):** When `GEMINI_API_KEY` is unset in the environment, `generate_si_brief()` automatically routes to a deterministic template builder returning schema-valid `InterpretResponse` JSON (`"is_mock": true`), allowing full frontend and API testing without external API credits.

---

## Local Execution & Verification

Run all commands from the repository root (`NASA/`):

```powershell
# 1. Run retrieval P@3 and Leave-One-Out concordance benchmark
python .\backend\ranker\benchmark.py

# 2. Run automated FastAPI end-to-end smoke tests (uses offline mock brief if GEMINI_API_KEY is unset)
python -m tests.test_api

# 3. Start the local FastAPI server (interactive Swagger UI available at http://localhost:8000/docs)
uvicorn backend.main:app --reload --port 8000

```

```

```