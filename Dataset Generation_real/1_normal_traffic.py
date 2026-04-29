#!/usr/bin/env python3
"""
1_normal_traffic.py
===================
Simulates realistic normal Keystone API traffic.

Behavior:
- Authenticates as multiple legitimate users
- Performs a variety of API operations (token requests, user/project queries,
  role lookups, catalog queries, credential checks)
- Randomizes timing, user agents, and operation sequences to reflect
  realistic usage patterns
- Generates labeled output with label=0 (normal) and attack_type='normal'

Usage:
    python3 1_normal_traffic.py --target 8000
"""

import requests
import time
import random
import csv
import os
import argparse
import hashlib
from datetime import datetime
from config import KEYSTONE_URL, OUTPUT_DIR, LOG_FIELDS, NORMAL_TARGET, \
    ADMIN_USER, ADMIN_PASSWORD, ADMIN_PROJECT, ADMIN_DOMAIN, TEST_USERS

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Realistic endpoint mix for normal traffic
NORMAL_ENDPOINTS = [
    ("/v3/auth/tokens",    "POST", "auth"),
    ("/v3/auth/catalog",   "GET",  "auth"),
    ("/v3/auth/projects",  "GET",  "auth"),
    ("/v3/projects",       "GET",  "list"),
    ("/v3/users",          "GET",  "list"),
    ("/v3/roles",          "GET",  "list"),
    ("/v3/domains",        "GET",  "list"),
    ("/v3/services",       "GET",  "list"),
    ("/v3/endpoints",      "GET",  "list"),
    ("/v3/regions",        "GET",  "list"),
    ("/v3/credentials",    "GET",  "list"),
    ("/v3/policies",       "GET",  "list"),
]


class RateTracker:
    """Tracks per-IP request rate and failure rate over a 60-second window."""
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

    def req_rate(self):
        return len(self.requests)

    def fail_rate(self):
        return len(self.fails) / len(self.requests) if self.requests else 0.0

    def avg_resp(self):
        return (sum(r for _, r in self.times) / len(self.times)
                if self.times else 0.0)


def get_admin_token():
    """Obtain an admin token for authenticated requests."""
    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": ADMIN_USER,
                        "domain": {"name": ADMIN_DOMAIN},
                        "password": ADMIN_PASSWORD,
                    }
                },
            },
            "scope": {
                "project": {
                    "name": ADMIN_PROJECT,
                    "domain": {"name": ADMIN_DOMAIN},
                }
            },
        }
    }
    try:
        r = requests.post(
            f"{KEYSTONE_URL}/v3/auth/tokens",
            json=payload,
            timeout=10,
        )
        return r.headers.get("X-Subject-Token", "")
    except Exception:
        return ""


def simulate_normal(target=NORMAL_TARGET, output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_normal.csv")

    print(f"Normal traffic simulation")
    print(f"Target: {target} requests → {output_file}\n")

    token    = get_admin_token()
    trackers = {}   # per source_ip rate trackers
    rows     = []
    total    = 0
    recent_times = []

    while total < target:
        # Randomly pick a user and assign a source IP
        user      = random.choice(TEST_USERS + [
            {"name": ADMIN_USER, "password": ADMIN_PASSWORD,
             "project": ADMIN_PROJECT}
        ])
        source_ip = f"10.0.{random.randint(1, 5)}.{random.randint(1, 20)}"
        if source_ip not in trackers:
            trackers[source_ip] = RateTracker()
        tracker = trackers[source_ip]

        # Pick an endpoint
        ep_path, method, ep_type = random.choice(NORMAL_ENDPOINTS)
        url     = f"{KEYSTONE_URL}{ep_path}"
        headers = {
            "Content-Type": "application/json",
            "X-Auth-Token": token,
            "X-Forwarded-For": source_ip,
        }

        # Build request body for POST /auth/tokens
        body = None
        if method == "POST" and "tokens" in ep_path:
            body = {
                "auth": {
                    "identity": {
                        "methods": ["password"],
                        "password": {
                            "user": {
                                "name": user["name"],
                                "domain": {"name": ADMIN_DOMAIN},
                                "password": user["password"],
                            }
                        },
                    }
                }
            }

        req_bytes = len(str(body or "")) + len(str(headers))
        ts_start  = time.time()

        try:
            if method == "POST":
                resp = requests.post(url, json=body, headers=headers, timeout=5)
            else:
                resp = requests.get(url, headers=headers, timeout=5)
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
            "http_method":              2 if method == "POST" else 1,
            "endpoint_name":            ep_path,
            "endpoint_category":        len(ep_path.split("/")) - 1,
            "path_depth":               ep_path.count("/"),
            "request_bytes":            req_bytes,
            "response_bytes":           resp_bytes,
            "status_code":              status,
            "status_class":             status // 100 if status > 0 else 0,
            "response_time_ms":         round(resp_ms, 2),
            "is_slow_request":          1 if resp_ms > 500 else 0,
            "is_auth_endpoint":         1 if "auth" in ep_path else 0,
            "is_admin_endpoint":        1 if "admin" in ep_path else 0,
            "user_id_hash":             int(hashlib.md5(
                                            user["name"].encode()).hexdigest(), 16) % 10000,
            "has_user_context":         1,
            "req_rate_per_ip_60s":      tracker.req_rate(),
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 0,
            "is_repeated_fail":         0,
            "source_ip":                source_ip,
            "label":                    0,
            "attack_type":              "normal",
        }
        rows.append(row)
        total += 1

        if total % 500 == 0:
            print(f"  [{total}/{target}] "
                  f"req_rate={tracker.req_rate()}/60s "
                  f"fail={tracker.fail_rate():.1%}")

        # Realistic inter-request delay
        time.sleep(random.uniform(0.3, 2.5))

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Avg req_rate: "
          f"{sum(r['req_rate_per_ip_60s'] for r in rows) / len(rows):.1f}/60s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normal Keystone traffic simulator")
    parser.add_argument("--target", type=int, default=NORMAL_TARGET)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_normal(target=args.target, output_file=args.output)
