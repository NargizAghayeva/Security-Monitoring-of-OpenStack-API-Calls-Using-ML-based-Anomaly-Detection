# Installation Steps

This guide provides both automated and manual installation methods.

## Method 1: Automated Installation (Recommended)

### Quick Install
```bash
# Clone the repository
git clone https://github.com/yourusername/01-devstack-setup.git
cd 01-devstack-setup

# Make scripts executable
chmod +x scripts/*.sh

# Run installation
./scripts/install.sh
```

### Installation Process

The script will:
1. Update system packages (~5 minutes)
2. Install dependencies (~5 minutes)
3. Create stack user (~1 minute)
4. Clone DevStack repository (~2 minutes)
5. Set up log directories (~1 minute)
6. Copy configuration files (~1 minute)
7. Run DevStack installation (~30-45 minutes)
8. Verify installation (~2 minutes)

**Total time: ~45-60 minutes**

### Monitoring Installation

In a separate terminal, monitor the installation progress:
```bash
# Watch installation logs
tail -f /opt/stack/logs/stack.sh.log

# Check system resources
htop

# Monitor network activity
nethogs
```

### Post-Installation

After successful installation:
```bash
# Source credentials
source /opt/stack/devstack/openrc admin admin

# Verify Keystone is working
openstack token issue

# List services
openstack service list

# Check endpoint list
openstack endpoint list
```

---

## Method 2: Manual Installation

### Step 1: System Preparation
```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install essential packages
sudo apt-get install -y \
    git \
    python3-pip \
    python3-dev \
    libssl-dev \
    libffi-dev \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libmysqlclient-dev \
    pkg-config
```

### Step 2: Create Stack User
```bash
# Create user
sudo useradd -s /bin/bash -d /opt/stack -m stack

# Grant sudo privileges
echo "stack ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/stack
sudo chmod 0440 /etc/sudoers.d/stack

# Verify
sudo -u stack sudo -v
```

### Step 3: Clone DevStack
```bash
# Switch to stack user
sudo su - stack

# Clone repository
cd /opt/stack
git clone https://opendev.org/openstack/devstack
cd devstack

# Checkout stable branch
git checkout stable/2024.1
```

### Step 4: Configure DevStack
```bash
# Create local.conf (copy from configs/local.conf in this repo)
# Or create minimal configuration:

cat > /opt/stack/devstack/local.conf << 'EOF'
[[local|localrc]]
ADMIN_PASSWORD=secret
DATABASE_PASSWORD=$ADMIN_PASSWORD
RABBIT_PASSWORD=$ADMIN_PASSWORD
SERVICE_PASSWORD=$ADMIN_PASSWORD

HOST_IP=$(ip addr | grep 'state UP' -A2 | tail -n1 | awk '{print $2}' | cut -f1 -d'/')

LOGFILE=/opt/stack/logs/stack.sh.log
VERBOSE=True
LOG_COLOR=True

enable_service rabbit mysql key keystone

disable_service n-net n-cpu n-api n-crt n-obj n-novnc n-xvnc n-cauth
disable_service horizon tempest

enable_service g-api g-reg c-api c-sch c-vol

KEYSTONE_TOKEN_FORMAT=fernet
API_RATE_LIMIT=False

[[post-config|$KEYSTONE_CONF]]
[DEFAULT]
debug = True
log_file = /var/log/keystone/keystone.log
log_dir = /var/log/keystone

[oslo_log]
logging_default_format_string = %(asctime)s.%(msecs)03d %(process)d %(levelname)s %(name)s [-] %(message)s
EOF
```

### Step 5: Create Log Directory
```bash
# Exit stack user if you're in it
exit

# Create and set permissions
sudo mkdir -p /var/log/keystone
sudo chown stack:stack /var/log/keystone
sudo chmod 755 /var/log/keystone

sudo mkdir -p /opt/stack/logs
sudo chown stack:stack /opt/stack/logs
```

### Step 6: Run Installation
```bash
# Switch to stack user
sudo su - stack

# Navigate to devstack directory
cd /opt/stack/devstack

# Run installation (this takes 30-60 minutes)
./stack.sh
```

### Step 7: Verify Installation
```bash
# Source credentials
source /opt/stack/devstack/openrc admin admin

# Test Keystone
openstack token issue

# Should see output like:
# +------------+----------------------------------+
# | Field      | Value                            |
# +------------+----------------------------------+
# | expires    | 2024-02-06T14:30:00+0000        |
# | id         | gAAAAABl...                      |
# | project_id | abc123...                        |
# | user_id    | def456...                        |
# +------------+----------------------------------+
```

---

## Verification Steps

### 1. Check Services
```bash
# List all services
systemctl list-units "devstack@*"

# Check Keystone specifically
systemctl status devstack@keystone
```

### 2. Test API Endpoints
```bash
# Public endpoint
curl http://localhost:5000/v3

# Should return JSON with version info
```

### 3. Verify Logs
```bash
# Check if logs are being written
sudo ls -lh /var/log/keystone/

# View recent log entries
sudo tail -n 20 /var/log/keystone/keystone.log
```

### 4. Run Verification Script
```bash
cd /path/to/01-devstack-setup
./scripts/verify.sh
```

---

## Common Installation Issues

### Issue 1: Installation Fails
```bash
# Check logs
tail -n 100 /opt/stack/logs/stack.sh.log

# Common causes:
# - Insufficient RAM
# - Disk space full
# - Network connectivity issues
# - Previous failed installation artifacts
```

**Solution:**
```bash
# Clean previous installation
sudo su - stack
cd /opt/stack/devstack
./unstack.sh
./clean.sh

# Re-run installation
./stack.sh
```

### Issue 2: Services Not Starting
```bash
# Check service status
systemctl status devstack@keystone

# Restart service
sudo systemctl restart devstack@keystone

# Check logs for errors
sudo journalctl -u devstack@keystone -n 50
```

### Issue 3: Port Conflicts
```bash
# Check if port 5000 is in use
sudo lsof -i :5000

# Kill conflicting process if safe
sudo kill -9 <PID>
```

### Issue 4: Permission Errors
```bash
# Fix log directory permissions
sudo chown -R stack:stack /var/log/keystone
sudo chmod -R 755 /var/log/keystone
```

---

## Post-Installation Configuration

### Enable Additional Logging
```bash
# Edit Keystone configuration
sudo nano /etc/keystone/keystone.conf

# Add under [DEFAULT]:
debug = True
verbose = True
```

### Restart Services
```bash
sudo systemctl restart devstack@keystone
```

### Create Test Users/Projects
```bash
# Source credentials
source /opt/stack/devstack/openrc admin admin

# Create test project
openstack project create --description "Test Project" test_project

# Create test user
openstack user create --project test_project --password testpass testuser

# Grant role
openstack role add --project test_project --user testuser member
```

---

## Next Steps

Once installation is verified:

1. **Explore Keystone API**: Test different API endpoints
2. **Generate traffic**: Create users, projects, tokens
3. **Monitor logs**: Watch `/var/log/keystone/keystone.log`
4. **Proceed to next phase**: [02-log-collection](../../02-log-collection)

---

## Useful Commands Reference
```bash
# Source credentials
source /opt/stack/devstack/openrc admin admin

# Token operations
openstack token issue
openstack token revoke <token_id>

# User management
openstack user list
openstack user create --password <pass> <username>
openstack user delete <username>

# Project management
openstack project list
openstack project create <name>

# Service management
sudo systemctl status devstack@keystone
sudo systemctl restart devstack@keystone
sudo systemctl stop devstack@keystone

# Log viewing
sudo tail -f /var/log/keystone/keystone.log
sudo journalctl -u devstack@keystone -f

# Uninstall DevStack
cd /opt/stack/devstack
./unstack.sh  # Stop services
./clean.sh    # Clean up
```
