# OpenStack Keystone API Attack Dataset — Data Collection Framework

This repository contains the data collection and attack simulation scripts used in the MSc thesis:

> **ML-Based Anomaly Detection of API Calls in a Private Cloud Environment**  
> Nargiz Aghayeva, Eötvös Loránd University, Budapest, 2026

The scripts generate a labeled Keystone API request dataset from a live DevStack environment, covering four attack categories alongside realistic normal traffic.

---

## Dataset Summary

| Type       | Requests | Sessions (60s) | Key Detection Signal         |
|------------|----------|----------------|------------------------------|
| Normal     | 6,349    | 857            | Baseline                     |
| Brute Force| 2,000    | 765            | High `fail_rate_per_ip_60s`  |
| Port Scan  | 2,500    | 118            | High `unique_endpoints/60s`  |
| Web Attack | 2,000    | 1,695          | Large `request_bytes`        |
| DoS        | 20,000   | 43             | Extreme `req_rate_per_ip_60s`|
| **Total**  | **32,849**| **3,478**     |                              |

After session aggregation (60-second window per source IP), the dataset yields **3,478 sessions**: 857 normal and 2,621 attack sessions.

---

## Prerequisites

- Ubuntu 22.04 with DevStack installed and running
- Python 3.8+
- OpenStack Keystone accessible at your DevStack IP

```bash
pip install requests
```

---

## Setup

### Step 1 — Configure DevStack connection

Edit `config.py`:

```python
DEVSTACK_HOST  = "http://192.168.200.152"   # your DevStack IP
ADMIN_PASSWORD = "secret"                    # from local.conf / localrc
```

### Step 2 — Create test users (one-time setup)

```bash
source /opt/stack/openrc admin admin

for i in 1 2 3 4 5; do
  openstack user create --password test123 --project demo user$i
  openstack role add --user user$i --project demo member
done
```

---

## Data Collection

Run scripts in the following order. Attack scripts can be run in parallel terminals once normal traffic collection is under way.

### Normal traffic (~45–90 minutes)

```bash
python3 1_normal_traffic.py --target 8000
```

Simulates realistic multi-user Keystone API interactions: authentication, user/project queries, role lookups, catalog queries. Inter-request delay: 0.3–2.5 seconds.

### Brute Force (~20 minutes)

```bash
python3 2_attack_brute.py --target 2000 --mode mixed
```

Repeated POST requests to `/v3/auth/tokens` with incorrect credentials. Mixed mode alternates between random passwords and a common wordlist.

### Port Scan (~90 minutes)

```bash
python3 3_attack_portscan.py --target 2000
```

GET requests across 35 real and non-existent Keystone endpoints. Inter-request delay: **1.5–4.0 seconds** — this is intentionally slow to distribute requests across multiple 60-second session windows.

### Web Attack (~30 minutes)

```bash
python3 4_attack_webattack.py --target 2000
```

POST requests to `/v3/auth/tokens` with SQL injection, XSS, and path traversal payloads embedded in auth request bodies. Key signal: elevated `request_bytes` (~2,000 bytes vs normal ~400 bytes).

### DoS (~60 minutes)

```bash
python3 5_attack_dos.py --target 20000
```

High-volume POST flooding from a small pool of source IPs. Inter-request delay: **0.15–0.25 seconds** to maintain realistic flood rate (300–600 req/60s).

---

## Verification and Merging

After all collection scripts complete:

```bash
python3 6_verify_dataset.py
```

This script:
- Checks volume and feature separation for each attack type
- Reports session counts per attack type (target: portscan ≥ 100, dos ≥ 40)
- Saves merged output files to `collected_data/`

### Output files

```
collected_data/
├── raw_normal.csv          (label=0, attack_type=normal)
├── raw_brute_mixed.csv     (label=1, attack_type=brute)
├── raw_portscan.csv        (label=1, attack_type=portscan)
├── raw_webattack.csv       (label=1, attack_type=webattack)
├── raw_dos.csv             (label=1, attack_type=dos)
├── final_normal.csv        (merged normal rows)
├── final_attack.csv        (merged attack rows)
└── final_dataset.csv       (all rows, shuffled — use this for training)
```

---

## CSV Schema

All output files share the following columns:

| Column                    | Description                                      |
|---------------------------|--------------------------------------------------|
| `timestamp`               | ISO 8601 request timestamp                       |
| `hour_of_day`             | Hour (0–23)                                      |
| `minute_of_hour`          | Minute (0–59)                                    |
| `day_of_week`             | Weekday (0=Monday)                               |
| `is_business_hours`       | 1 if 09:00–18:00                                 |
| `http_method`             | 1=GET, 2=POST                                    |
| `endpoint_name`           | Full API path                                    |
| `endpoint_category`       | Path depth (proxy for endpoint type)             |
| `path_depth`              | Number of `/` separators                         |
| `request_bytes`           | Request body + header size in bytes              |
| `response_bytes`          | Response body size in bytes                      |
| `status_code`             | HTTP response status code                        |
| `status_class`            | Status class (2=2xx, 4=4xx, 5=5xx)              |
| `response_time_ms`        | Round-trip time in milliseconds                  |
| `is_slow_request`         | 1 if response_time_ms > 500                      |
| `is_auth_endpoint`        | 1 if path contains "auth"                        |
| `is_admin_endpoint`       | 1 if path contains "admin"                       |
| `user_id_hash`            | Hashed user identifier                           |
| `has_user_context`        | 1 if request includes user credentials           |
| `req_rate_per_ip_60s`     | Request count from this IP in last 60 seconds    |
| `fail_rate_per_ip_60s`    | Failure rate from this IP in last 60 seconds     |
| `user_req_count_60s`      | Same as req_rate (per-user view)                 |
| `avg_response_time_recent`| Mean of last 20 response times                   |
| `has_error_log`           | 1 if status_code >= 500                          |
| `is_burst`                | 1 if traffic pattern is bursty                   |
| `is_repeated_fail`        | 1 if fail_rate > 0.5                             |
| `source_ip`               | Source IP address (simulated)                    |
| `label`                   | 0=normal, 1=attack                               |
| `attack_type`             | normal / brute / portscan / webattack / dos      |

---

## Notes

- **Port scan timing:** The 1.5–4.0 second inter-request delay is critical. Faster scans collapse into 1–2 sessions after aggregation, making detection unreliable. See thesis Section 5.2 for a detailed analysis.
- **DoS sessions:** DoS produces few sessions (43 in the final dataset) because its high request rate compresses many requests into each 60-second window. This is expected behavior.
- **Reproducibility:** All scripts use `random.seed` is not set — re-runs will produce slightly different datasets. The overall statistical properties remain consistent.

---

## Citation

If you use this dataset or scripts in your research, please cite:

```
Aghayeva, N. (2026). ML-Based Anomaly Detection of API Calls in a Private 
Cloud Environment. MSc Thesis, Eötvös Loránd University, Budapest.
```
