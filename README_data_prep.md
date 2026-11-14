# Spacecraft Solid Flammability Dataset & Normalization Pipeline

A structured data acquisition and normalization pipeline that consolidates experimental microgravity ($0g$) combustion data from the **NASA Physical Sciences Informatics (PSI)** repository (`psi.nasa.gov`) with $1g$ Earth reference baselines. The resulting dataset provides a standardized, machine-readable foundation for evaluating solid-material ignition and flame-spread behavior across spacecraft and partial-gravity ($1/6g$ Lunar, $3/8g$ Martian) exploration atmospheres.

---

## Current Project Scope (Phase 1 Completed)

Work completed to date covers **data acquisition, schema inspection, multi-investigation normalization, and atmospheric preset definition**:

1. **PSI Data Acquisition:** Downloaded metadata documentation (`i_Investigation.txt`, Objectives/SRDs, Researcher Guides, and file descriptions) and experimental summary tables (CSV/Excel) across six PSI combustion investigations (`SAFFIRE-I`, `SAFFIRE-II`, `SAFFIRE-III`, `BASS`, `BASS-II`, and `ACME-BRE`), excluding raw `.avi`/`.mov` video and high-speed DSLR image archives.


2. **Schema & Regime Extraction (`src_eda/`):** Built inspection scripts to parse experimental table columns, Excel formatting artifacts, and PDF chamber-pressure documentation.


3. **Master Dataset Normalization (`normalize_data.py`):** Unified heterogeneous test matrices into a single flat 13-field JSON array (`psi_solid_flammability.json`) containing 56 planar test records (55 unique `test_id` entries after deduplicating multi-attempt ignition row `BASS-R24-T12-S27`).
4. **Reference Mission Benchmarks (`mission_presets.json`):** Defined four standardized spacecraft and historical failure atmospheric presets (`ISS Standard`, `Lunar Habitat / Pressurized Rover`, `Artemis EVA Spacesuit`, and `Apollo 1 / Mir 1997 Stress Benchmark`).

---

## Workspace Structure

```text
NASA/
├── data/
│   ├── ACME_BRE/
│   │   ├── PSI-20_Experimental table_ACME BRE.csv       # Summary test matrix[cite: 8]
│   │   ├── BRE_data_interpretation_20220804.pdf          # Operating pressure & O2 regime docs[cite: 8]
│   │   ├── ACME_non-imaging_data_file_description.pdf    # Sensor & telemetry specifications[cite: 8]
│   │   ├── ACME-BRE_Test_Summary.docx                    # Investigation summary[cite: 8]
│   │   └── i_Investigation.txt                           # ISA-Tab PSI metadata[cite: 8]
│   ├── BASS/                                             # MSG small-sample test matrix & docs
│   ├── BASS-II/                                          # MSG small-sample test matrix & docs
│   └── SAFFIRE/                                          # Cygnus vehicle-scale test matrices & docs
├── src_eda/
│   ├── normalize_data.py                                 # Master ETL & normalization script
│   ├── inspect_acme.py                                   # ACME-BRE CSV & DOCX column inspector
│   └── extract_pressure&fuels_acme.py                    # ACME-BRE PDF pressure/regime extractor
├── psi_solid_flammability.json                           # Unified master dataset
└── mission_presets.json                                  # Reference atmospheric benchmarks

```

---

## Dataset Coverage (`psi_solid_flammability.json`)

The dataset spans **6 PSI investigations**, **3 hardware scales**, **5 normalized material classes**, **$\text{O}_2$ concentrations from `15.0%` to `40.0%**`, **chamber pressures from `8.2` to `14.81 psi**`, and **forced airflow velocities from `2.0` to `30.0 cm/s**`:

| Investigation | Scale | Records | $\text{O}_2$ Range ($\%$) | Pressure ($\text{psi}$) | Airflow ($\text{cm/s}$) | Materials |
| --- | --- | --- | --- | --- | --- | --- |
| **`SAFFIRE-I`** | Vehicle-Scale (Cygnus) | 2 | `21.5` | `14.7` | `20.0` | Cotton/Fiberglass Blend |
| **`SAFFIRE-II`** | Vehicle-Scale (Cygnus) | 9 | `21.5–22.1` | `14.7` | `20.0` | Silicone, Cotton/Fiberglass, PMMA, PMMA/Nomex |
| **`SAFFIRE-III`** | Vehicle-Scale (Cygnus) | 2 | `21.5` | `14.7` | `30.0` | Cotton/Fiberglass Blend |
| **`BASS`** | Small-Sample (MSG) | 18 (17 unique) | `21.17–22.72` | `14.26–14.81` | `5.0–30.0` | Cotton/Fiberglass Blend, Nomex |
| **`BASS-II`** | Small-Sample (MSG) | 15 | `15.0–22.2` | `14.7` | `2.0–20.0` | PMMA (Cast Acrylic), Cotton/Fiberglass, Nomex |
| **`ACME-BRE`** | Small-Sample (CIR) | 10 | `21.0–40.0` | `8.2–14.7` | `5.0–10.0` | PMMA (Cast Acrylic), Cotton/Fiberglass (Emulated) |

* **Outcome Breakdown (56 rows):** 37 `"Ignited - Sustained Spread"`, 16 `"Ignited - Self-Extinguished"`, and 3 `"No Ignition"`.
* **Material Breakdown (56 rows):** 28 `"Cotton/Fiberglass Blend"`, 15 `"PMMA (Cast Acrylic)"`, 8 `"Nomex"`, 4 `"Silicone"`, and 1 `"PMMA / Nomex Composite"`.

---

## Unified Record Schema

Each entry in `psi_solid_flammability.json` follows a standardized 13-field structure:

```json
{
  "investigation_id": "SAFFIRE-I",
  "test_id": "SAFFIRE1-S1",
  "scale": "Vehicle-Scale (Cygnus)",
  "material": "Cotton/Fiberglass Blend",
  "thickness_mm": 0.37,
  "o2_percent": 21.5,
  "pressure_psi": 14.7,
  "airflow_cm_s": 20.0,
  "flow_direction": "Concurrent",
  "outcome": "Ignited - Sustained Spread",
  "flame_spread_rate_mm_s": 2.24,
  "sensors": [
    "Radiometer",
    "Thermocouples",
    "HD Video",
    "O2/CO2 Gas Analyzer",
    "Pressure Transducer"
  ],
  "earth_1g_baseline_spread_mm_s": 14.2
}

```

### Standardized Sensor Arrays by Scale

* **`Vehicle-Scale (Cygnus)` (`SAFFIRE-I/II/III`):** `["Radiometer", "Thermocouples", "HD Video", "O2/CO2 Gas Analyzer", "Pressure Transducer"]`
* **`Small-Sample (MSG)` (`BASS` / `BASS-II`):** `["Radiometer", "Thermocouples", "HD Video", "Digital Still Camera"]`
* **`Small-Sample (CIR)` (`ACME-BRE`):** `["Radiometer", "Thermocouples", "HD Video", "Mass Flow Controllers", "Pressure Transducer"]`

---

## Normalization Choices, Proxy Mappings & Assumptions

To preserve physical fidelity across experiments with differing instrumentation and reporting formats, the pipeline separates directly tabulated PSI measurements from documented normalization proxies:

### 1. Directly Grounded Telemetry

* **Test Conditions & Outcomes:** `o2_percent` (`15.0%–40.0%`), `BASS` chamber `pressure_psi` (`14.26–14.81 psi`), `SAFFIRE`/`BASS` `airflow_cm_s` (`2.0–30.0 cm/s`), and qualitative `outcome` classifications for `SAFFIRE-II` and `BASS` are extracted directly from the PSI CSV/Excel test matrices.
* **Measured $0g$ Spread Rates:** `flame_spread_rate_mm_s` is populated from reported values on `SAFFIRE1-S1` (`2.24 mm/s`), `SAFFIRE2-2-5` (`2.1 mm/s`), `SAFFIRE2-2-6` (`2.6 mm/s`), and `SAFFIRE2-2-8`/`2-9` (`0.025 mm/s`, midpoint of NASA's `0.01–0.04 mm/s` range for thick cast PMMA).
* **Direct $1g$ Baselines:** `SAFFIRE2-2-1` (`0.8 mm/s`), `SAFFIRE2-2-2` (`1.2 mm/s`), and `SAFFIRE2-2-4` (`0.6 mm/s`) are sourced directly from the `SAFFIRE-II` PSI table.

### 2. Engineering Rules & Proxy Mappings

* **Planar Geometry Restriction:** Only planar sheets and fabrics (`0.1–10.0 mm`) are retained; cylindrical rods and spheres in `BASS-II` are excluded so sample thickness remains comparable across records.
* **Composite `test_id` Construction:** Because `BASS` reuses `Test no.` and `Sample no.` across repeated runs, identifiers are formatted as `BASS-R{as_run}-T{test}-S{sample}` (with final deduplication on `test_id` to resolve multi-attempt ignition rows such as `BASS-R24-T12-S27`).
* **Standalone `Nomex` Thickness & $1g$ Baseline:** Raw `BASS` and `BASS-II` Nomex entries omit explicit thickness values; `normalize_data.py` assigns standard fabric thickness (`0.37 mm`) and an Earth $1g$ spread baseline of `0.0 mm/s` (reflecting self-extinction in normal $1g$ air).
* **`ACME-BRE` Gaseous-to-Solid Proxy Mapping:** `ACME-BRE` uses a porous burner (`25 mm` or `50 mm`) burning ethylene ($\text{C}_2\text{H}_4$) diluted with nitrogen to emulate solid-fuel burning limits in elevated-$\text{O}_2$ / reduced-pressure habitats (`PSI-20_Experimental table_ACME BRE.csv`):


* *Fuel Mapping:* `100% C2H4` and `50% C2H4` bottles are mapped to `"PMMA (Cast Acrylic)"` and `"Cotton/Fiberglass Blend"`, respectively, at a nominal `1.0 mm` reference thickness.
* *Multi-Condition Expansion & Formatting Repair:* Semicolon-delimited $\text{O}_2$ test days (`"21; 26.5; 40"`) are expanded into discrete atmospheric rows, correcting Excel percentage formatting artifacts (`"3400%"` $\rightarrow$ `34.0%`, `"2100%"` $\rightarrow$ `21.0%`).
* *Pressure Pairing:* Because chamber pressure is omitted from the summary CSV, $\text{O}_2$ concentrations are paired with the documented operating points in `BRE_data_interpretation_20220804.pdf` (p. 4): `21.0%` $\rightarrow$ `14.7 psi`, `25.0% / 26.5%` $\rightarrow$ `10.2 psi`, and `34.0% / 40.0%` $\rightarrow$ `8.2 psi`.
* *Flow & Outcome Mapping:* Burner diameters (`25 mm` vs. `50 mm`) map to `5.0 cm/s` and `10.0 cm/s` opposed flow; test dates with `Flames Ignited = 0` (`2019-Apr-01`, `21.0%` $\text{O}_2$) are mapped to `"No Ignition"`.


* **Nominal Cabin Defaults & Literature Lookups:**
* `14.7 psi` is applied as nominal cabin pressure for `SAFFIRE-I/II/III` and `BASS-II`; `21.5%` $\text{O}_2$ is applied to `SAFFIRE-III`.
* `SAFFIRE1-S2` (`1.65 mm/s`) and `SAFFIRE3-S1/S2` (`3.1`, `1.8 mm/s`) spread rates are sourced from published Saffire mission reports.
* `BASS-II` ignition outcomes are inferred from chamber $\Delta\text{O}_2 / \Delta\text{CO}_2$ gas concentration deltas.
* Remaining `earth_1g_baseline_spread_mm_s` values (`54/56` rows populated; `SAFFIRE2-2-3` and `SAFFIRE2-2-7` retained as `null`) are assigned via a standardized NASA literature lookup table keyed by `(material, thickness_mm)`.


* **Preservation of `null` Spread Rates:** All 43 `BASS`, `BASS-II`, and `ACME-BRE` records retain `"flame_spread_rate_mm_s": null` because NASA archived raw imagery or mass-burning extinction limits rather than tabulated linear flame-spread rates.

---

## Reference Atmospheric Presets (`mission_presets.json`)

Four standardized operating benchmarks are defined for downstream scenario evaluation:

| Preset ID | Scenario Name | Gravity Regime | $\text{O}_2\%$ | Pressure ($\text{psi}$) | Airflow ($\text{cm/s}$) |
| --- | --- | --- | --- | --- | --- |
| `iss_standard` | **ISS Standard** | $0g$ (Microgravity) | `21.0%` | `14.7` | `10.0` |
| `lunar_habitat` | **Lunar Habitat / Pressurized Rover** | $1/6g$ Bounded ($0g$–$1g$) | `32.0%` | `10.2` | `15.0` |
| `artemis_eva` | **Artemis EVA Spacesuit** | $1/6g$ Bounded ($0g$–$1g$) | `100.0%` | `4.3` | `5.0` |
| `apollo1_mir_stress` | **Historical Failure — Apollo 1 / Mir 1997** | $1g$ / $0g$ Stress Benchmark | `50.0%` | `14.7` | `25.0` |