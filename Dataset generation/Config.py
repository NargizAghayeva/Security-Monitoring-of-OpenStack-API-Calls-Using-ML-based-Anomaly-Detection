# ============================================================
# config.py — DevStack connection parameters
# ============================================================
# Update this file according to your DevStack environment

DEVSTACK_HOST = "http://192.168.1.x"   # your DevStack IP
KEYSTONE_URL  = f"{DEVSTACK_HOST}:5000"

# Admin credentials
ADMIN_USER     = "admin"
ADMIN_PASSWORD = "your_admin_password"   # password from devstack localrc
ADMIN_PROJECT  = "admin"
ADMIN_DOMAIN   = "Default"

# Test users — create these in DevStack beforehand
# Using python-openstackclient: openstack user create --password test123 user1
USERS = [
    {"username": "user1", "password": "test123", "project": "demo"},
    {"username": "user2", "password": "test123", "project": "demo"},
    {"username": "user3", "password": "test123", "project": "demo"},
    {"username": "user4", "password": "test123", "project": "demo"},
    {"username": "user5", "password": "test123", "project": "demo"},
]

# Log file paths
KEYSTONE_LOG = "/var/log/keystone/keystone.log"   # standard path in DevStack
OUTPUT_DIR   = "./collected_data"

# Collection parameters
NORMAL_TARGET   = 8000   # number of normal requests to collect
ATTACK_TARGET   = 2000   # number of requests per attack type
REQUEST_TIMEOUT = 10     # seconds
