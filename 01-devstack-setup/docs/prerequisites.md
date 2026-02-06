# Prerequisites

## Hardware Requirements

### Minimum Specifications
- **CPU**: 2 cores (64-bit processor)
- **RAM**: 8GB
- **Disk**: 20GB free space
- **Network**: Stable internet connection (minimum 5 Mbps)

### Recommended Specifications
- **CPU**: 4+ cores
- **RAM**: 16GB
- **Disk**: 40GB+ free space (SSD preferred for better performance)
- **Network**: 10+ Mbps internet connection

## Software Requirements

### Operating System

**Supported (Tested):**
- Ubuntu 22.04 LTS (Jammy Jellyfish) - **Recommended**
- Ubuntu 20.04 LTS (Focal Fossa)

**May Work (Untested):**
- Debian 11 (Bullseye)
- Debian 12 (Bookworm)

**Not Supported:**
- CentOS/RHEL (DevStack has limited support)
- Fedora (may work but not recommended)
- Windows (use WSL2 or VM)
- macOS (use VM)

### Required Packages

The installation script will install these, but you can pre-install them:
```bash
sudo apt-get update
sudo apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    libssl-dev \
    libffi-dev
```

### Network Configuration

**Firewall Ports** (if applicable):
- 5000: Keystone public API
- 35357: Keystone admin API (deprecated but may be used)
- 80: HTTP (if Horizon enabled)
- 443: HTTPS (if configured)
- 3306: MySQL
- 5672: RabbitMQ

**Network Setup:**
- Static IP recommended (or reliable DHCP with reservation)
- No proxy required, but if present, ensure it allows access to:
  - opendev.org
  - github.com
  - Ubuntu package repositories

## System Checks

### Pre-installation Verification

Run these commands to verify your system meets requirements:
```bash
# 1. Check OS version
lsb_release -a
# Expected: Ubuntu 22.04 or 20.04

# 2. Check available RAM (should show 8GB+)
free -h

# 3. Check disk space (should show 20GB+ available)
df -h /

# 4. Check CPU cores (should show 2+)
nproc

# 5. Check internet connectivity
ping -c 3 opendev.org

# 6. Check if running on physical/VM (VM is fine)
sudo dmidecode -s system-manufacturer

# 7. Verify sudo access
sudo -v
```

### Expected Output Examples

**RAM Check:**
```
              total        used        free      shared  buff/cache   available
Mem:           15Gi       2.0Gi        10Gi       100Mi       3.0Gi        13Gi
```

**Disk Check:**
```
Filesystem      Size  Used Avail Use% Mounted on
/dev/sda1        50G   10G   40G  20% /
```

**CPU Check:**
```
4
```

## User Requirements

### Account Permissions

- Must have a non-root user account
- User must have sudo privileges
- Do NOT run installation as root

### Verify Sudo Access
```bash
# Test sudo access
sudo -v

# Check if user is in sudo group
groups $USER | grep sudo
```

If you don't have sudo access:
```bash
# Add user to sudo group (run as root or existing sudo user)
sudo usermod -aG sudo $USER

# Log out and log back in for changes to take effect
```

## Virtual Machine Recommendations

If running in a VM:

### VMware / VirtualBox
- Enable VT-x/AMD-V (hardware virtualization)
- Allocate at least 2 CPU cores
- Enable "Nested Virtualization" if available
- Use bridged networking or NAT with port forwarding

### Cloud Providers (AWS, Azure, GCP)
- Instance type: t3.large or equivalent (2 vCPU, 8GB RAM)
- Open security group ports as needed
- Attach additional EBS volume if needed

### Docker/Containers
- NOT recommended for DevStack
- DevStack requires systemd and full OS environment

## Common Issues to Avoid

❌ **Don't:**
- Run as root user
- Install on a system with existing OpenStack
- Use Windows native (use WSL2 or VM instead)
- Install with less than 8GB RAM
- Use slow internet connection

✅ **Do:**
- Use a clean Ubuntu installation
- Ensure stable internet connection
- Have at least 20GB free disk space
- Run as regular user with sudo
- Keep system updated before installation

## Next Steps

Once prerequisites are met, proceed to [Installation Steps](installation-steps.md).
