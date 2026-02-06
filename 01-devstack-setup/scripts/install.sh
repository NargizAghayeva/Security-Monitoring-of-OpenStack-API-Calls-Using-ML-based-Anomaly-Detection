#!/bin/bash

set -e

echo "======================================"
echo "DevStack Installation Script"
echo "======================================"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo -e "${RED}ERROR: Please do not run as root${NC}"
    echo "Run as regular user with sudo privileges"
    exit 1
fi

# Check Ubuntu version
echo -e "${YELLOW}Checking system requirements...${NC}"
if ! grep -q "Ubuntu" /etc/os-release; then
    echo -e "${RED}WARNING: This script is tested on Ubuntu. Proceed at your own risk.${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 1: System Update
echo -e "${GREEN}[1/8] Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# Step 2: Install Dependencies
echo -e "${GREEN}[2/8] Installing dependencies...${NC}"
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

# Step 3: Create stack user
echo -e "${GREEN}[3/8] Creating stack user...${NC}"
if ! id "stack" &>/dev/null; then
    sudo useradd -s /bin/bash -d /opt/stack -m stack
    echo "stack ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/stack
    sudo chmod 0440 /etc/sudoers.d/stack
    echo -e "${GREEN}Stack user created successfully${NC}"
else
    echo -e "${YELLOW}Stack user already exists${NC}"
fi

# Step 4: Clone DevStack
echo -e "${GREEN}[4/8] Cloning DevStack repository...${NC}"
sudo -u stack bash <<'EOF'
cd /opt/stack
if [ ! -d "devstack" ]; then
    git clone https://opendev.org/openstack/devstack
    cd devstack
    git checkout stable/2024.1
else
    echo "DevStack already cloned"
    cd devstack
    git pull
fi
EOF

# Step 5: Create log directory
echo -e "${GREEN}[5/8] Setting up log directories...${NC}"
sudo mkdir -p /var/log/keystone
sudo chown stack:stack /var/log/keystone
sudo mkdir -p /opt/stack/logs
sudo chown stack:stack /opt/stack/logs

# Step 6: Copy configuration
echo -e "${GREEN}[6/8] Copying configuration files...${NC}"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
sudo cp "$SCRIPT_DIR/../configs/local.conf" /opt/stack/devstack/
sudo chown stack:stack /opt/stack/devstack/local.conf

# Step 7: Run stack.sh
echo -e "${GREEN}[7/8] Running DevStack installation...${NC}"
echo -e "${YELLOW}This may take 30-60 minutes depending on your internet connection${NC}"
echo -e "${YELLOW}You can monitor progress in another terminal with:${NC}"
echo -e "${YELLOW}tail -f /opt/stack/logs/stack.sh.log${NC}"
echo ""

sudo -u stack bash <<'EOF'
cd /opt/stack/devstack
./stack.sh
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: DevStack installation failed${NC}"
    echo "Check logs at: /opt/stack/logs/stack.sh.log"
    exit 1
fi

# Step 8: Verification
echo -e "${GREEN}[8/8] Verifying installation...${NC}"
bash "$SCRIPT_DIR/verify.sh"

echo -e "${GREEN}======================================"
echo "Installation completed successfully!"
echo "======================================${NC}"
echo ""
echo -e "${YELLOW}Important Information:${NC}"
echo "  - Horizon Dashboard: http://$(hostname -I | awk '{print $1}')/dashboard"
echo "  - Username: admin"
echo "  - Password: secret"
echo "  - Keystone logs: /var/log/keystone/keystone.log"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Source credentials: source /opt/stack/devstack/openrc admin admin"
echo "  2. Test Keystone: openstack token issue"
echo "  3. Proceed to: 02-log-collection"
