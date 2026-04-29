#!/usr/bin/env python3
"""
3_attack_portscan.py
====================
Simulates port scan / endpoint enumeration against Keystone.

Attack pattern:
- GET requests across many different API endpoints (real + non-existent)
- High unique_endpoints count per 60-second window
- 100% failure rate (scanning non-existent paths returns 404/403)
- Controlled inter-request sleep (1.5-4s) to spread across multiple sessions

Key signal for detection:
- unique_endpoints_per_60s >> normal baseline
- High fail_rate combined with endpoint diversity

Usage:
    python3 3_attack_portscan.py --target 2000
"""

import requests
import time
import random
import csv
import os
import argparse
from datetime import datetime
from config import KEYSTONE_URL, OUTPUT_DIR, LOG_FIELDS, ATTACK_TARGET

os.makedirs(OUTPUT_DIR, exist_ok=True)

SCAN_ENDPOINTS = [
    # Real Keystone v3 endpoints
    "/v3/auth/tokens", "/v3/auth/catalog", "/v3/auth/projects",
    "/v3/projects", "/v3/users", "/v3/groups", "/v3/roles",
    "/v3/domains", "/v3/services", "/v3/endpoints", "/v3/regions",
    "/v3/credentials", "/v3/policies", "/v3/limits",
    "/v3/registered_limits", "/v3/application_credentials",
    # Non-existent paths (return 404 — typical scan behavior)
    "/v3/admin", "/v3/secret", "/v3/internal", "/v2.0/tokens",
    "/v2/tokens", "/v1/auth", "/api/v1/users", "/admin/users",
    "/v3/os-quota-sets", "/v3/os-simple-tenant-usage",
    "/v3/os-services", "/v3/os-hosts", "/v3/os-aggregates",
    "/v3/os-availability-zone", "/v3/os-cells",
    "/v3/os-cloudpipe", "/v3/os-floating-ips",
    "/v3/os-networks", "/v3/os-security-groups",
]


class RateTracker:
    def __init__(self):
        self.requests  = []
        self.fails     = []
        self.times     = []
        self.endpoints = []

    def add(self, ts, success, resp_ms, ep):
        cutoff = ts - 60
        self.requests  = [t for t in self.requests  if t > cutoff]
        self.fails     = [t for t in self.fails     if t > cutoff]
        self.times     = [(t, r) for t, r in self.times     if t > cutoff]
        self.endpoints = [(t, e) for t, e in self.endpoints if t > cutoff]
        self.requests.append(ts)
        self.times.append((ts, resp_ms))
        self.endpoints.append((ts, ep))
        if not success:
            self.fails.append(ts)

    def req_rate(self):   return len(self.requests)
    def unique_eps(self): return len(set(e for _, e in self.endpoints))
    def fail_rate(self):
        return len(self.fails) / len(self.requests) if self.requests else 0.0


def simulate_portscan(target=ATTACK_TARGET, output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_portscan.csv")

    print(f"Port Scan simulation")
    print(f"Target: {target} requests → {output_file}\n")

    source_ip    = f"10.0.{random.randint(1, 5)}.{random.randint(1, 20)}"
    tracker      = RateTracker()
    rows         = []
    total        = 0
    recent_times = []

    while total < target:
        ep_path = random.choice(SCAN_ENDPOINTS)
        url     = f"{KEYSTONE_URL}{ep_path}"
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": source_ip,
        }
        req_bytes = len(str(headers))
        ts_start  = time.time()
        try:
            resp       = requests.get(url, headers=headers, timeout=5)
            resp_ms    = (time.time() - ts_start) * 1000
            status     = resp.status_code
            resp_bytes = len(resp.content)
        except Exception:
            resp_ms    = 500
            status     = 0
            resp_bytes = 0

        success = 200 <= status < 400
        now     = time.time()
        tracker.add(now, success, resp_ms, ep_path)
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
            "http_method":              1,   # GET
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
            "user_id_hash":             0,
            "has_user_context":         0,
            "req_rate_per_ip_60s":      tracker.req_rate(),
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 1,
            "is_repeated_fail":         1 if tracker.fail_rate() > 0.5 else 0,
            "source_ip":                source_ip,
            "label":                    1,
            "attack_type":              "portscan",
        }
        rows.append(row)
        total += 1

        if total % 200 == 0:
            print(f"  [{total}/{target}] "
                  f"unique_eps={tracker.unique_eps()} "
                  f"req_rate={tracker.req_rate()}/60s "
                  f"fail={tracker.fail_rate():.1%}")

        # Slow inter-request delay to spread across multiple 60s sessions
        time.sleep(random.uniform(1.5, 4.0))

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Max req_rate: {max(r['req_rate_per_ip_60s'] for r in rows)}/60s")
    fail_count = sum(1 for r in rows if r["status_code"] not in range(200, 400))
    print(f"  Fail rate:    {fail_count/total:.1%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Port scan / endpoint enumeration simulator")
    parser.add_argument("--target", type=int, default=ATTACK_TARGET)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_portscan(target=args.target, output_file=args.output)
