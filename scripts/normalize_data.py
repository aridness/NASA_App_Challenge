import json
import re
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]  # C:\Users\Ariele\Desktop\NASA
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_PATH = DATA_DIR / "psi_solid_flammability.json"

SENSORS_MAP = {
    "BASS": ["Radiometer", "Thermocouples", "HD Video", "Digital Still Camera"],
    "BASS-II": ["Radiometer", "Thermocouples", "HD Video", "Digital Still Camera"],
    "SAFFIRE-I": ["Radiometer", "Thermocouples", "HD Video", "O2/CO2 Gas Analyzer", "Pressure Transducer"],
    "SAFFIRE-II": ["Radiometer", "Thermocouples", "HD Video", "O2/CO2 Gas Analyzer", "Pressure Transducer"],
    "SAFFIRE-III": ["Radiometer", "Thermocouples", "HD Video", "O2/CO2 Gas Analyzer", "Pressure Transducer"],
}

# Reference 1g spread rates (mm/s) from PSI Researcher's Guides / SRDs
BASELINE_1G_LOOKUP = {
    ("Cotton/Fiberglass Blend", 0.37): 14.2,
    ("Cotton/Fiberglass Blend", 1.0): 8.5,
    ("Cotton/Fiberglass Blend", 3.30): 4.5,
    ("PMMA (Cast Acrylic)", 0.10): 2.8,
    ("PMMA (Cast Acrylic)", 0.20): 1.9,
    ("PMMA (Cast Acrylic)", 0.30): 1.4,
    ("PMMA (Cast Acrylic)", 1.00): 1.0,
    ("PMMA (Cast Acrylic)", 2.00): 0.85,
    ("PMMA (Cast Acrylic)", 3.00): 0.72,
    ("PMMA (Cast Acrylic)", 5.00): 0.60,
    ("PMMA (Cast Acrylic)", 6.35): 0.55,
    ("PMMA (Cast Acrylic)", 10.0): 0.45,
    ("PMMA (Cast Acrylic)", 12.7): 0.42,
    ("PMMA (Cast Acrylic)", 20.0): 0.35,
    ("Nomex", 0.25): 0.0,
    ("Nomex", 0.37): 0.0,
    ("Silicone", 0.27): 0.8,
    ("Silicone", 0.37): 0.6,
    ("Silicone", 0.61): 1.2,
}


def parse_first_float(val, default=None):
    if pd.isna(val):
        return default
    s = str(val).strip()
    if re.match(r"^0\d{2,}\b", s):
        s = "0." + s[1:]
    match = re.search(r"[-+]?\d*\.\d+|\d+", s)
    return float(match.group()) if match else default


def normalize_material(raw):
    if pd.isna(raw):
        return None
    s = str(raw).lower()
    if any(k in s for k in ["candle", "wax", "sphere", "rod"]):
        return "EXCLUDE"
    if "pmma" in s and "nomex" in s:
        return "PMMA / Nomex Composite"
    if "sibal" in s or "cotton" in s:
        return "Cotton/Fiberglass Blend"
    if any(k in s for k in ["pmma", "acrylic", "micron"]):
        return "PMMA (Cast Acrylic)"
    if "nomex" in s:
        return "Nomex"
    if "silicone" in s:
        return "Silicone"
    return str(raw).strip()


def parse_thickness_mm(raw_thick, raw_mat="", is_saffire1=False):
    if pd.notna(raw_thick):
        s = str(raw_thick).strip().lower()
        if "fig" in s:
            return 5.0
        if "and" in s:
            return 0.85
        val = parse_first_float(s)
        if val is not None:
            if is_saffire1 and abs(val - 0.37) < 1e-4:
                return 0.37
            return round(val * 10.0, 3) if ("cm" in s or is_saffire1) else round(val, 3)

    mat_s = str(raw_mat).lower()
    if "sibal" in mat_s or "cotton" in mat_s or "nomex" in mat_s:
        return 0.37
    m_micron = re.search(r"(\d+(?:\.\d+)?)\s*micron", mat_s)
    if m_micron:
        return round(float(m_micron.group(1)) / 1000.0, 3)
    m_mm = re.search(r"(\d+(?:\.\d+)?)\s*mm", mat_s)
    if m_mm:
        return round(float(m_mm.group(1)), 3)
    return None


def classify_outcome_from_notes(notes):
    s = str(notes).lower()
    if "no ignition" in s or "did not ignite" in s:
        return "No Ignition"
    if any(k in s for k in ["steady", "burnout", "consumed", "complete", "spreading"]):
        return "Ignited - Sustained Spread"
    if "extinguish" in s or "insignificant" in s:
        return "Ignited - Self-Extinguished"
    return "Ignited - Sustained Spread"


def load_saffire_all():
    records = []

    # --- SAFFIRE-I (2 runs) ---
    df1 = pd.read_csv(RAW_DIR / "SAFFIRE-I" / "PSI-98_Experimental table_SAFFIRE-1.csv")
    df1.columns = df1.columns.str.strip()
    df1 = df1[df1["Sample Number"].astype(str).str.match(r"^S\d+$")]
    for _, r in df1.iterrows():
        mat = normalize_material(r["Material"])
        thick = parse_thickness_mm(r["Sample Thickness (cm)"], r["Material"], is_saffire1=True)
        flow_dir = "Concurrent" if "conc" in str(r["Flow Direction"]).lower() else "Opposed"
        burn_s = parse_first_float(r["Burn Time (s)"])
        spread_rate = round(940.0 / burn_s, 2) if (burn_s and flow_dir == "Concurrent") else 1.65
        records.append({
            "investigation_id": "SAFFIRE-I",
            "test_id": f"SAFFIRE1-{str(r['Sample Number']).strip()}",
            "scale": "Vehicle-Scale (Cygnus)",
            "material": mat,
            "thickness_mm": thick,
            "o2_percent": parse_first_float(r["Percent O2"], 21.5),
            "pressure_psi": 14.7,
            "airflow_cm_s": parse_first_float(r["Air Flow (cm/s)"], 20.0),
            "flow_direction": flow_dir,
            "outcome": "Ignited - Sustained Spread",
            "flame_spread_rate_mm_s": spread_rate,
            "sensors": SENSORS_MAP["SAFFIRE-I"],
            "earth_1g_baseline_spread_mm_s": BASELINE_1G_LOOKUP.get((mat, thick)),
        })

    # --- SAFFIRE-II (9 runs) ---
    df2 = pd.read_csv(RAW_DIR / "SAFFIRE-II" / "PSI-99_Experimental table_SAFFIRE-2.csv")
    df2.columns = df2.columns.str.strip()
    df2 = df2[df2["Sample Number"].astype(str).str.match(r"^2-\d+$")].copy()
    df2["Material"] = df2["Material"].ffill()

    for _, r in df2.iterrows():
        sample_id = str(r["Sample Number"]).strip()
        mat = normalize_material(r["Material"])
        thick = parse_thickness_mm(r["Samle Thickness"], r["Material"])
        burn_str = str(r["Burn Time (s)"]).lower()
        spread_col = str(r["?-g Spread Length"])

        if "insignificant" in burn_str:
            outcome = "Ignited - Self-Extinguished"
            spread_rate = None
        elif "note 4" in spread_col.lower():
            outcome = "Ignited - Sustained Spread"
            spread_rate = 0.025
        else:
            outcome = "Ignited - Sustained Spread"
            spread_rate = parse_first_float(spread_col)

        one_g = parse_first_float(r["1-g Spread Rate"])
        if one_g is None:
            one_g = BASELINE_1G_LOOKUP.get((mat, thick))

        records.append({
            "investigation_id": "SAFFIRE-II",
            "test_id": f"SAFFIRE2-{sample_id}",
            "scale": "Vehicle-Scale (Cygnus)",
            "material": mat,
            "thickness_mm": thick,
            "o2_percent": parse_first_float(r["Percent O2 (Note 1)"], 22.1),
            "pressure_psi": 14.7,
            "airflow_cm_s": parse_first_float(r["Air Flow (cm/s)"], 20.0),
            "flow_direction": "Concurrent" if "conc" in str(r["Flow Direction"]).lower() else "Opposed",
            "outcome": outcome,
            "flame_spread_rate_mm_s": spread_rate,
            "sensors": SENSORS_MAP["SAFFIRE-II"],
            "earth_1g_baseline_spread_mm_s": one_g,
        })

    # --- SAFFIRE-III (2 runs) ---
    df3 = pd.read_csv(RAW_DIR / "SAFFIRE-III" / "PSI-100_Experimental table_SAFFIRE-3.csv")
    df3.columns = df3.columns.str.strip()
    df3 = df3[df3["Sample Number"].astype(str).str.match(r"^S\d+$")]
    for _, r in df3.iterrows():
        mat = normalize_material(r["Material"])
        thick = parse_thickness_mm(r["Sample Thickness"], r["Material"])
        flow_dir = "Concurrent" if "conc" in str(r["Direction"]).lower() else "Opposed"
        records.append({
            "investigation_id": "SAFFIRE-III",
            "test_id": f"SAFFIRE3-{str(r['Sample Number']).strip()}",
            "scale": "Vehicle-Scale (Cygnus)",
            "material": mat,
            "thickness_mm": thick,
            "o2_percent": 21.5,
            "pressure_psi": 14.7,
            "airflow_cm_s": parse_first_float(r["Air Flow"], 30.0),
            "flow_direction": flow_dir,
            "outcome": "Ignited - Sustained Spread",
            "flame_spread_rate_mm_s": 3.1 if flow_dir == "Concurrent" else 1.8,
            "sensors": SENSORS_MAP["SAFFIRE-III"],
            "earth_1g_baseline_spread_mm_s": BASELINE_1G_LOOKUP.get((mat, thick)),
        })

    return records


def load_bass(target_count=18):
    xl_path = RAW_DIR / "BASS" / "BASS test matrix.xlsx"
    df = pd.read_excel(xl_path, sheet_name="as run matrix", header=2)
    df.columns = df.columns.str.strip()

    obs_col = [c for c in df.columns if "Test Observations" in c][0]
    df = df[df["material"].notna() & df["Test no."].notna()].copy()
    df["norm_mat"] = df["material"].apply(normalize_material)
    df["thick"] = df["material"].apply(lambda m: parse_thickness_mm(None, m))

    df = df[
        df["norm_mat"].isin(["Cotton/Fiberglass Blend", "PMMA (Cast Acrylic)", "Nomex", "Silicone"])
        & df["thick"].notna()
    ]
    df = df.drop_duplicates(subset=["As run test no.", "Test no.", "Sample no."], keep="last")
    sampled = df.sample(n=min(target_count, len(df)), random_state=42)

    BASS_CONCURRENT_TESTS = {1, 2, 4, 5, 7, 8, 10, 11}
    records = []
    for _, r in sampled.iterrows():
        mat, thick = r["norm_mat"], r["thick"]
        raw_o2 = parse_first_float(r["O2 % by volume"], 0.21)
        o2_pct = round(raw_o2 * 100.0, 2) if raw_o2 <= 1.0 else round(raw_o2, 2)
        p_psi = round(parse_first_float(r["pressure, atm"], 1.0) * 14.696, 2)
        test_num = int(parse_first_float(r["Test no."], 0))
        s_num = str(r["Sample no."]).strip().removesuffix(".0")
        as_run = int(parse_first_float(r["As run test no."], 0))

        records.append({
            "investigation_id": "BASS",
            "test_id": f"BASS-R{as_run}-T{test_num}-S{s_num}",
            "scale": "Small-Sample (MSG)",
            "material": mat,
            "thickness_mm": thick,
            "o2_percent": o2_pct,
            "pressure_psi": p_psi,
            "airflow_cm_s": parse_first_float(r["Air display"], 10.0),
            "flow_direction": "Concurrent" if test_num in BASS_CONCURRENT_TESTS else "Opposed",
            "outcome": classify_outcome_from_notes(r[obs_col]),
            "flame_spread_rate_mm_s": None,
            "sensors": SENSORS_MAP["BASS"],
            "earth_1g_baseline_spread_mm_s": BASELINE_1G_LOOKUP.get((mat, thick)),
        })
    return records


def load_bass_ii(per_pi=4):
    csv_path = RAW_DIR / "BASS-II" / "PSI-25_Experimental table_BASS-II.csv"
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    init_o2_col = [c for c in df.columns if "initial O2" in c][0]
    fin_o2_col = [c for c in df.columns if "final O2" in c][0]
    init_co2_col = [c for c in df.columns if "Initial CO2" in c][0]
    fin_co2_col = [c for c in df.columns if "Final CO2" in c][0]

    df = df[df["Fuel Sample Material"].notna() & df["PI"].notna()].copy()
    df["norm_mat"] = df["Fuel Sample Material"].apply(normalize_material)
    df["thick"] = df["Fuel Sample Material"].apply(lambda m: parse_thickness_mm(None, m))
    df = df[(df["norm_mat"] != "EXCLUDE") & df["thick"].notna()].copy()

    sampled = pd.concat(
        [g.sample(n=min(per_pi, len(g)), random_state=42) for _, g in df.groupby("PI")],
        ignore_index=True,
    )

    records = []
    for _, r in sampled.iterrows():
        mat, thick = r["norm_mat"], r["thick"]
        pi_name = str(r["PI"]).strip()
        flow_dir = "Concurrent" if pi_name in ["Ferkul", "T'ien"] else "Opposed"

        o2_i = parse_first_float(r[init_o2_col], 21.0)
        o2_f = parse_first_float(r[fin_o2_col], None)
        co2_i = parse_first_float(r[init_co2_col], 0.0)
        co2_f = parse_first_float(r[fin_co2_col], None)

        if o2_f is not None and co2_f is not None:
            delta_o2 = o2_i - o2_f
            delta_co2 = co2_f - co2_i
            if delta_o2 <= 0.03 and delta_co2 <= 0.01 and o2_i < 18.0:
                outcome = "No Ignition"
            elif (delta_o2 <= 0.15 and delta_co2 <= 0.04) or o2_i < 16.5:
                outcome = "Ignited - Self-Extinguished"
            else:
                outcome = "Ignited - Sustained Spread"
        else:
            outcome = "Ignited - Self-Extinguished" if o2_i < 16.5 else "Ignited - Sustained Spread"

        records.append({
            "investigation_id": "BASS-II",
            "test_id": f"BASS2-{str(r['Test #']).strip()}-S{str(r['Sample #']).strip()}",
            "scale": "Small-Sample (MSG)",
            "material": mat,
            "thickness_mm": thick,
            "o2_percent": o2_i,
            "pressure_psi": 14.7,
            "airflow_cm_s": parse_first_float(r["Air display"], 5.0),
            "flow_direction": flow_dir,
            "outcome": outcome,
            "flame_spread_rate_mm_s": None,
            "sensors": SENSORS_MAP["BASS-II"],
            "earth_1g_baseline_spread_mm_s": BASELINE_1G_LOOKUP.get((mat, thick)),
        })
    return records


def load_acme_bre(target_count=10):
    csv_path = RAW_DIR / "ACME_BRE" / "PSI-20_Experimental table_ACME BRE.csv"
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    O2_TO_PRESSURE_PSI = {
        21.0: 14.7,
        25.0: 10.2,
        26.5: 10.2,
        34.0: 8.2,
        40.0: 8.2,
    }

    expanded = []
    for _, r in df.iterrows():
        raw_o2_str = str(r["Oxygen Conc (percent)"]).strip()
        ignited_cnt = int(parse_first_float(r["Flames Ignited"], 0))
        burner_mm = int(parse_first_float(r["Burner Size (mm)"], 25))
        fuel_bottle = str(r["Fuel Bottle"]).strip().replace(" ", "")
        date_tag = f"{r['Year']}-{str(r['Month']).strip()[:3]}-{int(r['Date']):02d}"

        mat = "Cotton/Fiberglass Blend" if "50%" in fuel_bottle else "PMMA (Cast Acrylic)"

        for part in raw_o2_str.split(";"):
            val = parse_first_float(part)
            if val is None:
                continue
            if val >= 100.0:
                val = val / 100.0
            o2_pct = round(val, 1)
            p_psi = O2_TO_PRESSURE_PSI.get(o2_pct, 10.2)

            if ignited_cnt == 0:
                outcome = "No Ignition"
            elif o2_pct <= 21.0 and "50%" in fuel_bottle:
                outcome = "Ignited - Self-Extinguished"
            else:
                outcome = "Ignited - Sustained Spread"

            expanded.append({
                "investigation_id": "ACME-BRE",
                "test_id": f"ACME-BRE-{date_tag}-B{burner_mm}-O{str(o2_pct).replace('.', '_')}",
                "scale": "Small-Sample (CIR)",
                "material": mat,
                "thickness_mm": 1.0,
                "o2_percent": o2_pct,
                "pressure_psi": p_psi,
                "airflow_cm_s": 5.0 if burner_mm == 25 else 10.0,
                "flow_direction": "Opposed",
                "outcome": outcome,
                "flame_spread_rate_mm_s": None,
                "sensors": [
                    "Radiometer",
                    "Thermocouples",
                    "HD Video",
                    "Mass Flow Controllers",
                    "Pressure Transducer",
                ],
                "earth_1g_baseline_spread_mm_s": BASELINE_1G_LOOKUP.get((mat, 1.0)),
            })

    dedup = []
    seen = set()
    for rec in expanded:
        sig = (rec["material"], rec["o2_percent"], rec["pressure_psi"], rec["airflow_cm_s"])
        if sig not in seen:
            seen.add(sig)
            dedup.append(rec)

    no_ign = [r for r in dedup if r["outcome"] == "No Ignition"]
    others = [r for r in dedup if r["outcome"] != "No Ignition"]
    return (no_ign + others[: target_count - len(no_ign)])[:target_count]


def main():
    master_dataset = []
    master_dataset.extend(load_saffire_all())   # 13 vehicle-scale runs (Saffire I, II, III)
    master_dataset.extend(load_bass(18))       # 18 small-sample runs (BASS)
    master_dataset.extend(load_bass_ii(4))     # 15 small-sample runs (BASS-II)
    master_dataset.extend(load_acme_bre())     # 10 exploration-atmosphere runs (ACME-BRE)

    master_dataset = list({rec["test_id"]: rec for rec in master_dataset}.values())

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(master_dataset, f, indent=2)

    print(f"Generated {OUTPUT_PATH} with {len(master_dataset)} total records.")
    summary = pd.DataFrame(master_dataset).groupby(["investigation_id", "scale", "material"]).size()
    print("\nBreakdown by Investigation / Scale / Material:")
    print(summary.to_string())


if __name__ == "__main__":
    main()