#!/usr/bin/env python3
"""
7_verify_dataset.py
====================
Merges all collected CSVs and verifies dataset quality.

Checks:
- Sufficient volume per attack type
- Statistical separation between normal and attack features
- Class imbalance ratio
- Which features discriminate best per attack type
- Any problematic columns (zero variance, NaN values)
"""

import pandas as pd
import numpy as np
import os
from config import OUTPUT_DIR


def load_all(output_dir=OUTPUT_DIR):
    files = {
        "normal":    os.path.join(output_dir, "raw_normal.csv"),
        "brute":     os.path.join(output_dir, "raw_brute_mixed.csv"),
        "portscan":  os.path.join(output_dir, "raw_portscan.csv"),
        "webattack": os.path.join(output_dir, "raw_webattack.csv"),
        "dos":       os.path.join(output_dir, "raw_dos.csv"),
    }
    dfs = {}
    print("Loading CSV files...\n")
    for name, path in files.items():
        if os.path.exists(path):
            df = pd.read_csv(path)
            df["attack_type"] = name
            dfs[name] = df
            print(f"  [OK]      {name:<12}: {len(df):>6,} rows")
        else:
            print(f"  [MISSING] {name:<12}: {path}")
    return dfs


def check_quality(dfs):
    print("\n" + "=" * 65)
    print("DATASET QUALITY CHECK")
    print("=" * 65)

    all_df = pd.concat(dfs.values(), ignore_index=True)

    # ── 1. Volume summary ────────────────────────────────────
    print("\n1. Volume summary:")
    for name, df in dfs.items():
        label = "Normal" if name == "normal" else "Attack"
        print(f"   {name:<12}: {len(df):>6,} rows  (label={df['label'].iloc[0]})")
    print(f"   {'TOTAL':<12}: {len(all_df):>6,} rows")
    print(f"   Attack ratio: {(all_df['label'] == 1).mean():.1%}")

    # ── 2. Feature separation: normal vs attack ───────────────
    numeric_features = [
        "req_rate_per_ip_60s", "fail_rate_per_ip_60s",
        "request_bytes", "response_bytes",
        "response_time_ms", "endpoint_category",
        "is_auth_endpoint", "is_burst",
    ]

    normal_df = all_df[all_df["label"] == 0]
    attack_df = all_df[all_df["label"] == 1]

    print(f"\n2. Feature separation (Normal vs All Attacks):")
    print(f"   {'Feature':<30} {'Normal mean':>12} {'Attack mean':>12} {'Ratio':>8}")
    print(f"   {'-' * 66}")

    for feat in numeric_features:
        if feat not in all_df.columns:
            continue
        n_mean = normal_df[feat].mean()
        a_mean = attack_df[feat].mean()
        ratio  = a_mean / n_mean if n_mean > 0 else float("inf")
        flag   = " <-- GOOD SIGNAL" if (ratio > 2.0 or ratio < 0.5) else ""
        print(f"   {feat:<30} {n_mean:>12.3f} {a_mean:>12.3f} {ratio:>8.2f}x{flag}")

    # ── 3. Per-attack type breakdown ─────────────────────────
    print(f"\n3. Per-attack feature statistics:")
    key_features = [
        "req_rate_per_ip_60s", "fail_rate_per_ip_60s",
        "request_bytes", "is_burst"
    ]
    for atype in [k for k in dfs if k != "normal"]:
        df_a = dfs[atype]
        print(f"\n   [{atype.upper()}]")
        for feat in key_features:
            if feat in df_a.columns:
                print(f"     {feat:<32}: "
                      f"mean={df_a[feat].mean():.3f}  "
                      f"std={df_a[feat].std():.3f}  "
                      f"max={df_a[feat].max():.3f}")

    # ── 4. Problematic columns ────────────────────────────────
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

    return all_df


def merge_and_save(dfs, output_dir=OUTPUT_DIR):
    all_df = pd.concat(dfs.values(), ignore_index=True)

    # Shuffle rows
    all_df = all_df.sample(frac=1, random_state=42).reset_index(drop=True)

    # Save separate and combined files
    normal_out = os.path.join(output_dir, "final_normal.csv")
    attack_out = os.path.join(output_dir, "final_attack.csv")
    full_out   = os.path.join(output_dir, "final_dataset.csv")

    all_df[all_df["label"] == 0].to_csv(normal_out, index=False)
    all_df[all_df["label"] == 1].to_csv(attack_out, index=False)
    all_df.to_csv(full_out, index=False)

    print(f"\n5. Saved output files:")
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
