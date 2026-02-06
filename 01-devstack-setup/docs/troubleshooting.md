# Troubleshooting Guide

Common issues and solutions for DevStack installation and Keystone configuration.

---

## Installation Issues

### Issue: Script fails with "Permission denied"

**Symptoms:**
```
bash: ./install.sh: Permission denied
```

**Solution:**
```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

---

### Issue: "Please do not run as root"

**Symptoms:**
```
ERROR: Please do not run as root
```

**Solution:**
Run the script as a regular user with sudo privileges, not as root:
```bash
# If logged in as root, create a regular user:
adduser devuser
usermod -aG sudo devuser
su - devuser

# Then run installation
cd /path/to/01-devstack-setup
./scripts/install.sh
```

---

### Issue: Installation hangs or takes too long

**Symptoms:**
- Installation stuck at "Downloading packages..."
- No progress for 30+ minutes

**Diagnosis:**
```bash
# In another terminal, check what's happening
tail -f /opt/stack/logs/stack.sh.log

# Check network activity
sudo iftop

# Check disk I/O
iostat -x 2
```

**Solutions:**

1. **Slow Internet:**
```bash
# Check download speed
speedtest-cli

# If slow, wait or use better connection
```

2. **Repository Issues:**
```bash
# Use different mirror
# Edit /opt/stack/devstack/local.conf
GIT_BASE=https://github.com
```

3. **Disk I/O bottleneck:**
```bash
# Check disk space
df -h

# Check if disk is slow
sudo hdparm -tT /dev/sda
```

---

### Issue: "Stack user already exists"

**Symptoms:**
```
useradd: user 'stack' already exists
```

**Solution:**
This is usually fine. The script will continue. If you need a clean installation:
```bash
# Remove existing stack user (CAUTION: deletes data)
sudo userdel -r stack

# Re-run installation
./scripts/install.sh
```

---

## Service Issues

### Issue: Keystone service not starting

**Symptoms:**
```
Job for devstack@keystone.service failed
```

**Diagnosis:**
```bash
# Check service status
sudo systemctl status devstack@keystone

# Check logs
sudo journalctl -u devstack@keystone -n 100 --no-pager

# Check Keystone logs
sudo tail -n 50 /var/log/keystone/keystone.log
```

**Common Causes & Solutions:**

1. **Port 5000 already in use:**
```bash
# Find what's using port 5000
sudo lsof -i :5000

# Kill the process if safe
sudo kill -9 <PID>

# Restart Keystone
sudo systemctl restart devstack@keystone
```

2. **Database connection issues:**
```bash
# Check MySQL is running
sudo systemctl status mysql

# Restart MySQL
sudo systemctl restart mysql

# Restart Keystone
sudo systemctl restart devstack@keystone
```

3. **Configuration errors:**
```bash
# Verify configuration syntax
sudo keystone-manage config-validate

# Check for typos in config
sudo cat /etc/keystone/keystone.conf | grep -i error
```

---

### Issue: "Unable to establish connection to database"

**Symptoms:**
```
OperationalError: (pymysql.err.OperationalError) (2003, "Can't connect to MySQL server...")
```

**Solution:**
```bash
# Check MySQL status
sudo systemctl status mysql

# If not running, start it
sudo systemctl start mysql

# Verify database exists
sudo mysql -e "SHOW DATABASES;" | grep keystone

# If missing, recreate
sudo mysql -e "CREATE DATABASE keystone;"

# Re-run db_sync
sudo -u stack keystone-manage db_sync

# Restart Keystone
sudo systemctl restart devstack@keystone
```

---

## API / Authentication Issues

### Issue: "openstack command not found"

**Symptoms:**
```bash
openstack token issue
-bash: openstack: command not found
```

**Solution:**
```bash
# Source the credentials file
source /opt/stack/devstack/openrc admin admin

# Verify
which openstack
# Should show: /usr/local/bin/openstack

# If still not found, install client
pip3 install python-openstackclient
```

---

### Issue: "Missing value auth-url required"

**Symptoms:**
```
Missing value auth-url required for auth plugin password
```

**Solution:**
```bash
# Make sure you've sourced credentials
source /opt/stack/devstack/openrc admin admin

# Verify environment variables
env | grep OS_

# Should see:
# OS_AUTH_URL=http://x.x.x.x:5000/v3
# OS_PROJECT_NAME=admin
# OS_USERNAME=admin
# OS_PASSWORD=secret
# etc.
```

---

### Issue: "The request you have made requires authentication"

**Symptoms:**
```
The request you have made requires authentication. (HTTP 401)
```

**Solutions:**

1. **Token expired:**
```bash
# Get new token
source /opt/stack/devstack/openrc admin admin
openstack token issue
```

2. **Wrong credentials:**
```bash
# Check credentials in local.conf
cat /opt/stack/devstack/local.conf | grep PASSWORD

# Try with explicit credentials
openstack --os-auth-url http://localhost:5000/v3 \
  --os-project-name admin \
  --os-username admin \
  --os-password secret \
  token issue
```

---

## Logging Issues

### Issue: Log file not found

**Symptoms:**
```
/var/log/keystone/keystone.log: No such file or directory
```

**Solution:**
```bash
# Create log directory
sudo mkdir -p /var/log/keystone

# Set ownership
sudo chown stack:stack /var/log/keystone

# Set permissions
sudo chmod 755 /var/log/keystone

# Restart Keystone
sudo systemctl restart devstack@keystone

# Verify log is being created
sudo ls -lh /var/log/keystone/
```

---

### Issue: No logs being written

**Symptoms:**
Log file exists but is empty or not updating

**Diagnosis:**
```bash
# Check file permissions
ls -lh /var/log/keystone/keystone.log

# Check Keystone process
ps aux | grep keystone

# Check configuration
sudo grep -i "log_file" /etc/keystone/keystone.conf
```

**Solution:**
```bash
# Fix permissions
sudo chown stack:stack /var/log/keystone/keystone.log
sudo chmod 644 /var/log/keystone/keystone.log

# Verify logging is enabled in config
sudo nano /etc/keystone/keystone.conf
# Ensure these lines exist under [DEFAULT]:
# log_file = /var/log/keystone/keystone.log
# debug = True

# Restart service
sudo systemctl restart devstack@keystone

# Test by making API call
openstack token issue

# Check logs
sudo tail /var/log/keystone/keystone.log
```

---

## Network Issues

### Issue: "Connection refused" when accessing API

**Symptoms:**
```
Connection refused when connecting to localhost:5000
```

**Diagnosis:**
```bash
# Check if Keystone is listening
sudo netstat -tlnp | grep 5000

# Check firewall
sudo ufw status

# Test localhost connection
curl http://localhost:5000/v3
```

**Solutions:**

1. **Service not running:**
```bash
sudo systemctl start devstack@keystone
```

2. **Firewall blocking:**
```bash
sudo ufw allow 5000/tcp
sudo ufw reload
```

3. **Binding to wrong interface:**
```bash
# Check Keystone configuration
sudo grep -i "bind" /etc/keystone/keystone.conf

# Should bind to 0.0.0.0 or correct IP
```

---

## Resource Issues

### Issue: "Cannot allocate memory"

**Symptoms:**
```
Cannot allocate memory
OSError: [Errno 12] Cannot allocate memory
```

**Solution:**
```bash
# Check memory usage
free -h

# If low on RAM, add swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Restart installation
cd /opt/stack/devstack
./unstack.sh
./stack.sh
```

---

### Issue: "No space left on device"

**Symptoms:**
```
OSError: [Errno 28] No space left on device
```

**Solution:**
```bash
# Check disk usage
df -h

# Find large files
sudo du -sh /* | sort -h

# Clean up if needed
sudo apt-get clean
sudo apt-get autoremove

# Clear old logs
sudo journalctl --vacuum-time=3d

# Remove old DevStack logs
rm -rf /opt/stack/logs/*.old
```

---

## Recovery Procedures

### Complete Restart

If all else fails, completely uninstall and reinstall:
```bash
# 1. Stop all services
cd /opt/stack/devstack
./unstack.sh

# 2. Clean up
./clean.sh

# 3. Remove databases
sudo mysql -e "DROP DATABASE IF EXISTS keystone;"

# 4. Remove logs
sudo rm -rf /var/log/keystone/*
sudo rm -rf /opt/stack/logs/*

# 5. Re-run installation
./stack.sh
```

---

### Backup Important Data

Before major troubleshooting:
```bash
# Backup configuration
cp /opt/stack/devstack/local.conf ~/local.conf.backup

# Backup database (if needed)
sudo mysqldump keystone > ~/keystone_backup.sql

# Backup logs
sudo tar -czf ~/keystone_logs_backup.tar.gz /var/log/keystone/
```

---

## Getting Help

If issues persist:

1. **Check logs thoroughly:**
```bash
sudo tail -n 200 /opt/stack/logs/stack.sh.log
sudo tail -n 200 /var/log/keystone/keystone.log
sudo journalctl -u devstack@keystone -n 200
```

2. **Search DevStack/OpenStack documentation:**
   - https://docs.openstack.org/devstack/latest/
   - https://docs.openstack.org/keystone/latest/

3. **Community resources:**
   - OpenStack mailing lists
   - #openstack on OFTC IRC
   - Ask OpenStack: https://ask.openstack.org/

4. **Include this information when asking for help:**
   - Ubuntu version: `lsb_release -a`
   - DevStack version/branch
   - Relevant log excerpts
   - Steps to reproduce
   - Error messages

---

## Prevention Tips

- Always check prerequisites before installation
- Monitor resources during installation
- Keep backups of working configurations
- Document any custom changes
- Test in VM before production
- Keep system updated but stable
