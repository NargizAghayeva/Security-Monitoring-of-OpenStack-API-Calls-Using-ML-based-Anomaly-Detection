#!/usr/bin/env python3
"""
6_verify_dataset.py
===================
Verifies dataset quality, merges all CSV files, and saves final outputs.

Checks:
1. Volume per attack type
2. Feature separation between normal and attack traffic
3. Per-attack feature statistics
4. Problematic columns (near-zero variance, NaN)
5. Session count per attack type (60s window)

Outputs:
    collected_data/final_normal.csv   — normal rows only
    collected_data/final_attack.csv   — attack rows only
    collected_data/final_dataset.csv  — all rows, shuffled

Usage:
    python3 6_verify_dataset.py
"""

import os
import pandas as pd
import numpy as np
from config import OUTPUT_DIR

# ── File map ───────────────────────────────────────────────────────────────────
FILE_MAP = {
    "normal":    os.path.join(OUTPUT_DIR, "raw_normal.csv"),
    "brute":     os.path.join(OUTPUT_DIR, "raw_brute_mixed.csv"),
    "portscan":  os.path.join(OUTPUT_DIR, "raw_portscan.csv"),
    "webattack": os.path.join(OUTPUT_DIR, "raw_webattack.csv"),
    "dos":       os.path.join(OUTPUT_DIR, "raw_dos.csv"),
}

KEY_FEATURES = [
    "req_rate_per_ip_60s", "fail_rate_per_ip_60s",
    "request_bytes", "response_bytes",
    "response_time_ms", "endpoint_category",
    "is_auth_endpoint", "is_burst",
]


def load_all():
    dfs = {}
    print("Loading CSV files...")
    for name, path in FILE_MAP.items():
        if os.path.exists(path):
            df = pd.read_csv(path)
            dfs[name] = df
            print(f"  [OK]      {name:<12}: {len(df):>7,} rows")
        else:
            print(f"  [MISSING] {name:<12}: {path}")
    return dfs


def check_quality(dfs):
    all_df = pd.concat(dfs.values(), ignore_index=True)
    normal = all_df[all_df["label"] == 0]
    attack = all_df[all_df["label"] == 1]

    print(f"\n{'='*65}")
    print("DATASET QUALITY CHECK")
    print(f"{'='*65}")

    # 1. Volume
    print(f"\n1. Volume summary:")
    for name, df in dfs.items():
        label = df["label"].iloc[0] if len(df) > 0 else "?"
        print(f"   {name:<12}: {len(df):>7,} rows  (label={label})")
    print(f"   {'TOTAL':<12}: {len(all_df):>7,} rows")
    print(f"   Attack ratio: {len(attack)/len(all_df):.1%}")

    # 2. Feature separation
    print(f"\n2. Feature separation (Normal vs All Attacks):")
    print(f"   {'Feature':<35} {'Normal mean':>12} {'Attack mean':>12} {'Ratio':>8}")
    print(f"   {'-'*68}")
    for feat in KEY_FEATURES:
        if feat not in all_df.columns:
            continue
        nm = normal[feat].mean()
        am = attack[feat].mean()
        ratio = am / nm if nm != 0 else float("inf")
        flag = " <-- GOOD SIGNAL" if abs(ratio - 1) > 0.5 else ""
        print(f"   {feat:<35} {nm:>12.3f} {am:>12.3f} {ratio:>7.2f}x{flag}")

    # 3. Per-attack stats
    print(f"\n3. Per-attack feature statistics:")
    stat_features = [
        "req_rate_per_ip_60s", "fail_rate_per_ip_60s",
        "request_bytes", "is_burst",
    ]
    for atype in [k for k in dfs if k != "normal"]:
        df_a = dfs[atype]
        print(f"\n   [{atype.upper()}]")
        for feat in stat_features:
            if feat in df_a.columns:
                print(f"     {feat:<32}: "
                      f"mean={df_a[feat].mean():.3f}  "
                      f"std={df_a[feat].std():.3f}  "
                      f"max={df_a[feat].max():.3f}")

    # 4. Problematic columns
    print(f"\n4. Problematic columns:")
    problems_found = False
    for col in all_df.select_dtypes(include=np.number).columns:
        if all_df[col].std() < 0.001:
            print(f"   [WARN] '{col}' has near-zero variance — poor feature for ML")
            problems_found = True
        if all_df[col].isna().sum() > 0:
            print(f"   [WARN] '{col}' has {all_df[col].isna().sum()} NaN values")
            problems_found = True
    if not problems_found:
        print("   No issues found.")

    # 5. Session count check
    print(f"\n5. Session count check (60s window per IP):")
    try:
        all_df["timestamp"] = pd.to_datetime(all_df["timestamp"])
        all_df["time_bucket"] = all_df["timestamp"].dt.floor("60s")
        sessions = all_df.groupby(
            ["source_ip", "time_bucket", "attack_type"]
        ).size().reset_index(name="req_count")
        print(f"   {'Attack Type':<12} {'Sessions':>10} {'Avg req/session':>16}")
        print(f"   {'-'*40}")
        for atype in all_df["attack_type"].unique():
            s   = sessions[sessions["attack_type"] == atype]
            avg = s["req_count"].mean()
            print(f"   {atype:<12} {len(s):>10,} {avg:>16.1f}")
        total_sessions = len(sessions)
        print(f"\n   TOTAL sessions: {total_sessions:,}")
        ps = sessions[sessions["attack_type"] == "portscan"]
        ds = sessions[sessions["attack_type"] == "dos"]
        if len(ps) >= 100:
            print(f"   [OK] portscan: {len(ps)} sessions (>= 100)")
        else:
            print(f"   [WARN] portscan: only {len(ps)} sessions — re-run with slower sleep")
        if len(ds) >= 40:
            print(f"   [OK] dos: {len(ds)} sessions (>= 40)")
        else:
            print(f"   [WARN] dos: only {len(ds)} sessions — re-run with slower sleep")
    except Exception as e:
        print(f"   [ERROR] Could not compute sessions: {e}")

    return all_df


def merge_and_save(dfs):
    all_df = pd.concat(dfs.values(), ignore_index=True)
    all_df = all_df.sample(frac=1, random_state=42).reset_index(drop=True)

    normal_out = os.path.join(OUTPUT_DIR, "final_normal.csv")
    attack_out = os.path.join(OUTPUT_DIR, "final_attack.csv")
    full_out   = os.path.join(OUTPUT_DIR, "final_dataset.csv")

    all_df[all_df["label"] == 0].to_csv(normal_out, index=False)
    all_df[all_df["label"] == 1].to_csv(attack_out, index=False)
    all_df.to_csv(full_out, index=False)

    print(f"\n6. Saved output files:")
    print(f"   {normal_out}")
    print(f"   {attack_out}")
    print(f"   {full_out}")
    print(f"\n[DONE] Dataset is ready for training.")


if __name__ == "__main__":
    dfs = load_all()
    if not dfs:
        print("\n[ERROR] No CSV files found. Run the collection scripts first.")
        exit(1)
    all_df = check_quality(dfs)
    merge_and_save(dfs)
