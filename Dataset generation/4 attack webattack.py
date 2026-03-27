#!/usr/bin/env python3
"""
4_attack_webattack.py
======================
Simulates Web Attacks against Keystone — SQLi, XSS, path traversal.

Attack pattern:
- Abnormally large request_bytes (malicious payload in body)
- Anomalous request_bytes vs response_bytes ratio
- High fail rate (400/422 from input validation)
- Occasional success if validation is bypassed
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
from config import KEYSTONE_URL, OUTPUT_DIR, ATTACK_TARGET

os.makedirs(OUTPUT_DIR, exist_ok=True)

AUTH_URL = f"{KEYSTONE_URL}/v3/auth/tokens"

# Attack payloads
SQLI_PAYLOADS = [
    "' OR '1'='1", "' OR 1=1--", "admin'--",
    "' UNION SELECT * FROM users--",
    "'; DROP TABLE users;--",
    "' OR 'x'='x",
    "1' AND 1=1--",
    "' OR ''='",
]

XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert('XSS')",
    "<svg onload=alert(1)>",
    "\"><script>alert(document.cookie)</script>",
]

PATH_TRAVERSAL_PAYLOADS = [
    "../../../../etc/passwd",
    "../../../etc/shadow",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
]

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


def build_attack_body(attack_type):
    """Build a malicious request body based on attack type."""
    if attack_type == "sqli":
        payload = random.choice(SQLI_PAYLOADS)
    elif attack_type == "xss":
        payload = random.choice(XSS_PAYLOADS)
    else:  # traversal
        payload = random.choice(PATH_TRAVERSAL_PAYLOADS)

    # Large filler to simulate oversized payload — key signal for web attacks
    filler = "A" * random.randint(500, 3000)

    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": payload + filler[:50],
                        "password": payload,
                        "domain": {"name": "Default"},
                        "extra_data": filler   # abnormally large field
                    }
                }
            }
        }
    }
    return body, payload


def simulate_webattack(target=ATTACK_TARGET, output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_webattack.csv")

    print(f"Web Attack simulation (SQLi + XSS + Path Traversal)")
    print(f"Target: {target} requests → {output_file}\n")

    tracker      = RateTracker()
    rows         = []
    total        = 0
    recent_times = []
    attack_types = ["sqli", "xss", "traversal"]

    while total < target:
        attack_type = random.choice(attack_types)
        source_ip   = f"10.0.{random.randint(1, 3)}.{random.randint(1, 50)}"
        body, payload = build_attack_body(attack_type)

        headers   = {"Content-Type": "application/json",
                     "X-Forwarded-For": source_ip}
        body_str  = json.dumps(body)
        req_bytes = len(body_str) + len(str(headers))

        ts_start = time.time()
        try:
            resp       = requests.post(AUTH_URL, data=body_str,
                                       headers=headers, timeout=10)
            resp_ms    = (time.time() - ts_start) * 1000
            status     = resp.status_code
            resp_bytes = len(resp.content)
        except Exception:
            resp_ms    = 500
            status     = 0
            resp_bytes = 0

        success = 200 <= status < 400
        now     = time.time()
        tracker.add(now, success, resp_ms)
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
            "user_id_hash":             random.randint(1000, 9999),
            "has_user_context":         1,
            "req_rate_per_ip_60s":      tracker.req_rate(),
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 0,
            "is_repeated_fail":         1 if tracker.fail_rate() > 0.7 else 0,
            "source_ip":                source_ip,
            "label":                    1,
        }

        rows.append(row)
        total += 1

        if total % 200 == 0:
            avg_req = sum(r["request_bytes"] for r in rows[-200:]) / 200
            print(f"  [{total}/{target}] "
                  f"avg_request_bytes={avg_req:.0f} "
                  f"fail_rate={tracker.fail_rate():.1%}")

        time.sleep(random.uniform(0.3, 2.0))

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    avg_req = sum(r["request_bytes"] for r in rows) / len(rows)
    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Avg request_bytes: {avg_req:.0f} (normal ~500 — key signal)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web attack simulator (SQLi, XSS, traversal)")
    parser.add_argument("--target", type=int, default=ATTACK_TARGET)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_webattack(target=args.target, output_file=args.output)
