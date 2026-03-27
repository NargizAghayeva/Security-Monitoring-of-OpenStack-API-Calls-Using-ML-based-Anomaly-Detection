#!/usr/bin/env python3
"""
1_normal_traffic.py
====================
Simulates normal Keystone API traffic.

Strategy:
- 5 different virtual users
- Various endpoints with realistic distribution
- Real user behavior patterns (burst, idle, active, slow)
- Target: 8000-10000 requests
"""

import requests
import time
import random
import json
import csv
import os
import hashlib
import argparse
from datetime import datetime
from config import KEYSTONE_URL, USERS, OUTPUT_DIR, NORMAL_TARGET

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Keystone endpoints with usage probabilities ─────────────
ENDPOINTS = {
    "auth_tokens":     (f"{KEYSTONE_URL}/v3/auth/tokens",  "POST", 0.35),
    "auth_catalog":    (f"{KEYSTONE_URL}/v3/auth/catalog", "GET",  0.10),
    "projects":        (f"{KEYSTONE_URL}/v3/projects",     "GET",  0.15),
    "users_self":      (f"{KEYSTONE_URL}/v3/users",        "GET",  0.10),
    "roles":           (f"{KEYSTONE_URL}/v3/roles",        "GET",  0.08),
    "auth_tokens_get": (f"{KEYSTONE_URL}/v3/auth/tokens",  "GET",  0.07),
    "services":        (f"{KEYSTONE_URL}/v3/services",     "GET",  0.05),
    "endpoints_list":  (f"{KEYSTONE_URL}/v3/endpoints",    "GET",  0.05),
    "domains":         (f"{KEYSTONE_URL}/v3/domains",      "GET",  0.05),
}

ENDPOINT_NAMES   = list(ENDPOINTS.keys())
ENDPOINT_WEIGHTS = [ENDPOINTS[e][2] for e in ENDPOINT_NAMES]


# ── Token acquisition ───────────────────────────────────────
def get_token(username, password, project, domain="Default"):
    url  = f"{KEYSTONE_URL}/v3/auth/tokens"
    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": username,
                        "password": password,
                        "domain": {"name": domain}
                    }
                }
            },
            "scope": {
                "project": {
                    "name": project,
                    "domain": {"name": domain}
                }
            }
        }
    }
    try:
        resp = requests.post(url, json=body, timeout=10)
        if resp.status_code == 201:
            return resp.headers.get("X-Subject-Token"), resp
        return None, resp
    except Exception as e:
        print(f"  [Token Error] {e}")
        return None, None


# ── Behavior patterns ───────────────────────────────────────
def get_sleep_time(behavior):
    """Return sleep interval based on user behavior type."""
    if behavior == "active":   # actively working user
        return random.uniform(0.5, 3.0)
    elif behavior == "burst":  # rapid successive requests
        return random.uniform(0.1, 0.5)
    elif behavior == "idle":   # occasional requests
        return random.uniform(5.0, 20.0)
    elif behavior == "slow":   # very infrequent requests
        return random.uniform(15.0, 45.0)
    return random.uniform(1.0, 5.0)


def get_behavior_sequence():
    """Simulate a realistic user session with mixed behaviors."""
    patterns = [
        ["active"] * 10 + ["idle"] * 3,
        ["burst"] * 5 + ["active"] * 8 + ["idle"] * 2,
        ["active"] * 5 + ["slow"] * 3 + ["active"] * 5,
        ["burst"] * 8 + ["idle"] * 5,
        ["slow"] * 5 + ["active"] * 10,
    ]
    seq = random.choice(patterns)
    random.shuffle(seq)
    return seq


# ── Helper encoders ─────────────────────────────────────────
def encode_method(method):
    return {"GET": 1, "POST": 2, "PUT": 3, "DELETE": 4, "PATCH": 5}.get(method, 0)


def encode_endpoint(name):
    mapping = {
        "auth_tokens": 1, "auth_catalog": 2, "projects": 3,
        "users_self": 4, "roles": 5, "auth_tokens_get": 6,
        "services": 7, "endpoints_list": 8, "domains": 9,
    }
    return mapping.get(name, 10)


def hash_user(username):
    return int(hashlib.md5(username.encode()).hexdigest()[:8], 16) % 10000


# ── Rate tracker ────────────────────────────────────────────
class RateTracker:
    """Tracks request and failure rates over a 60-second sliding window."""

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

    def avg_resp_time(self):
        return sum(r for _, r in self.times) / len(self.times) if self.times else 0.0


# ── CSV field definitions ───────────────────────────────────
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


# ── Main simulation ─────────────────────────────────────────
def simulate_normal_traffic(target=NORMAL_TARGET, output_file=None):
    if output_file is None:
        output_file = os.path.join(OUTPUT_DIR, "raw_normal.csv")

    print(f"Starting normal traffic simulation...")
    print(f"Target: {target} requests")
    print(f"Output: {output_file}\n")

    tracker      = RateTracker()
    rows         = []
    total        = 0
    fail_count   = 0
    source_ip    = "192.168.1.100"
    recent_times = []

    # Acquire tokens for all users
    tokens = {}
    for user in USERS:
        token, _ = get_token(user["username"], user["password"], user["project"])
        if token:
            tokens[user["username"]] = token
            print(f"  [OK] Token acquired: {user['username']}")
        else:
            print(f"  [WARN] Failed to get token: {user['username']}")

    if not tokens:
        print("[ERROR] No tokens acquired. Check config.py and DevStack status.")
        return

    while total < target:
        username = random.choice(list(tokens.keys()))
        token    = tokens[username]

        # Refresh token every 1000 requests
        if total % 1000 == 0 and total > 0:
            user_info = next(u for u in USERS if u["username"] == username)
            new_token, _ = get_token(username, user_info["password"],
                                     user_info["project"])
            if new_token:
                tokens[username] = new_token

        # Select endpoint and behavior
        ep_name       = random.choices(ENDPOINT_NAMES, weights=ENDPOINT_WEIGHTS, k=1)[0]
        url, method, _ = ENDPOINTS[ep_name]
        behavior_seq  = get_behavior_sequence()
        behavior      = behavior_seq[total % len(behavior_seq)]
        sleep_time    = get_sleep_time(behavior)

        headers = {
            "X-Auth-Token": token,
            "Content-Type": "application/json",
            "X-Forwarded-For": source_ip,
        }
        req_bytes = len(json.dumps(headers))

        # Build POST body for auth endpoint
        body = None
        if method == "POST" and ep_name == "auth_tokens":
            user_info = next((u for u in USERS if u["username"] == username), USERS[0])
            body = {
                "auth": {
                    "identity": {
                        "methods": ["password"],
                        "password": {"user": {
                            "name": username,
                            "password": user_info["password"],
                            "domain": {"name": "Default"}
                        }}
                    },
                    "scope": {
                        "project": {
                            "name": user_info["project"],
                            "domain": {"name": "Default"}
                        }
                    }
                }
            }
            req_bytes += len(json.dumps(body))

        # Send request
        ts_start = time.time()
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=10)
            else:
                resp = requests.post(url, headers=headers, json=body, timeout=10)
            resp_ms    = (time.time() - ts_start) * 1000
            status     = resp.status_code
            resp_bytes = len(resp.content)
            success    = 200 <= status < 400
        except Exception:
            resp_ms    = (time.time() - ts_start) * 1000
            status     = 0
            resp_bytes = 0
            success    = False

        now = time.time()
        tracker.add(now, success, resp_ms)
        recent_times.append(resp_ms)
        if len(recent_times) > 20:
            recent_times.pop(0)

        if not success:
            fail_count += 1

        dt     = datetime.now()
        hour   = dt.hour
        is_biz = 1 if 9 <= hour <= 18 else 0

        row = {
            "timestamp":                dt.isoformat(),
            "hour_of_day":              hour,
            "minute_of_hour":           dt.minute,
            "day_of_week":              dt.weekday(),
            "is_business_hours":        is_biz,
            "http_method":              encode_method(method),
            "endpoint_name":            ep_name,
            "endpoint_category":        encode_endpoint(ep_name),
            "path_depth":               url.count("/") - 2,
            "request_bytes":            req_bytes,
            "response_bytes":           resp_bytes,
            "status_code":              status,
            "status_class":             status // 100 if status > 0 else 0,
            "response_time_ms":         round(resp_ms, 2),
            "is_slow_request":          1 if resp_ms > 500 else 0,
            "is_auth_endpoint":         1 if "auth" in ep_name else 0,
            "is_admin_endpoint":        0,
            "user_id_hash":             hash_user(username),
            "has_user_context":         1,
            "req_rate_per_ip_60s":      tracker.req_rate(),
            "fail_rate_per_ip_60s":     round(tracker.fail_rate(), 4),
            "user_req_count_60s":       tracker.req_rate(),
            "avg_response_time_recent": round(
                sum(recent_times) / len(recent_times), 2),
            "has_error_log":            1 if status >= 500 else 0,
            "is_burst":                 1 if behavior == "burst" else 0,
            "is_repeated_fail":         1 if fail_count > 3 else 0,
            "source_ip":                source_ip,
            "label":                    0,
        }

        rows.append(row)
        total += 1

        if total % 500 == 0:
            print(f"  [{total}/{target}] "
                  f"fail_rate={tracker.fail_rate():.2%} "
                  f"avg_resp={tracker.avg_resp_time():.0f}ms")

        time.sleep(sleep_time)

    # Write CSV
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] {total} requests written → {output_file}")
    print(f"  Normal:     {total - fail_count}")
    print(f"  Failed:     {fail_count} ({fail_count / total:.1%})")


# ── Entry point ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Normal Keystone traffic simulator")
    parser.add_argument("--target", type=int, default=NORMAL_TARGET,
                        help="Number of requests to collect")
    parser.add_argument("--output", type=str, default=None,
                        help="Output CSV file path")
    args = parser.parse_args()
    simulate_normal_traffic(target=args.target, output_file=args.output)
