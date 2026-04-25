"""
config.py
=========
Shared configuration for all data collection scripts.
Edit DEVSTACK_HOST and ADMIN_PASSWORD before running any script.
"""

# ── DevStack connection ────────────────────────────────────────────────────────
DEVSTACK_HOST   = "http://192.168.200.152"          # your DevStack IP
KEYSTONE_URL    = f"{DEVSTACK_HOST}/identity"       # Keystone v3 base URL

# ── Admin credentials ──────────────────────────────────────────────────────────
ADMIN_USER      = "admin"
ADMIN_PASSWORD  = "secret"                          # from local.conf / localrc
ADMIN_PROJECT   = "admin"
ADMIN_DOMAIN    = "Default"

# ── Test users (created with setup_users.sh) ──────────────────────────────────
TEST_USERS = [
    {"name": "user1", "password": "test123", "project": "demo"},
    {"name": "user2", "password": "test123", "project": "demo"},
    {"name": "user3", "password": "test123", "project": "demo"},
    {"name": "user4", "password": "test123", "project": "demo"},
    {"name": "user5", "password": "test123", "project": "demo"},
]

# ── Output directory ───────────────────────────────────────────────────────────
OUTPUT_DIR      = "./collected_data"

# ── Default target request count ──────────────────────────────────────────────
NORMAL_TARGET   = 8000
ATTACK_TARGET   = 2000

# ── CSV column schema (shared across all scripts) ─────────────────────────────
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
    "source_ip", "label", "attack_type",
]
