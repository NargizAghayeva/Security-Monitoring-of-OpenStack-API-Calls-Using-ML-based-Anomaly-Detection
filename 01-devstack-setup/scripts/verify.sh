#!/bin/bash

echo "======================================"
echo "DevStack Installation Verification"
echo "======================================"

SUCCESS=0
WARNINGS=0
ERRORS=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check if OpenStack client is available
echo -n "Checking OpenStack client... "
if command -v openstack &> /dev/null; then
    echo -e "${GREEN}✓ Found${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}✗ Not found${NC}"
    ((ERRORS++))
    exit 1
fi

# Source credentials
if [ -f "/opt/stack/devstack/openrc" ]; then
    source /opt/stack/devstack/openrc admin admin
else
    echo -e "${RED}✗ Credentials file not found${NC}"
    exit 1
fi

# Test Keystone service
echo -n "Testing Keystone service... "
if openstack token issue > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Working${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}✗ Not responding${NC}"
    ((ERRORS++))
fi

# Check Keystone endpoints
echo -n "Checking Keystone endpoints... "
ENDPOINTS=$(openstack endpoint list --service keystone -f value 2>/dev/null | wc -l)
if [ "$ENDPOINTS" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $ENDPOINTS endpoints${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}✗ No endpoints found${NC}"
    ((ERRORS++))
fi

# List users
echo -n "Checking users... "
USERS=$(openstack user list -f value 2>/dev/null | wc -l)
if [ "$USERS" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $USERS users${NC}"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠ No users found${NC}"
    ((WARNINGS++))
fi

# List projects
echo -n "Checking projects... "
PROJECTS=$(openstack project list -f value 2>/dev/null | wc -l)
if [ "$PROJECTS" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $PROJECTS projects${NC}"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠ No projects found${NC}"
    ((WARNINGS++))
fi

# Check Keystone log file
echo -n "Checking Keystone log file... "
if [ -f "/var/log/keystone/keystone.log" ]; then
    LOG_SIZE=$(stat -f%z "/var/log/keystone/keystone.log" 2>/dev/null || stat -c%s "/var/log/keystone/keystone.log" 2>/dev/null)
    echo -e "${GREEN}✓ Exists (${LOG_SIZE} bytes)${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}✗ Not found${NC}"
    ((ERRORS++))
fi

# Check log directory permissions
echo -n "Checking log directory permissions... "
if [ -w "/var/log/keystone" ]; then
    echo -e "${GREEN}✓ Writable${NC}"
    ((SUCCESS++))
else
    echo -e "${YELLOW}⚠ Not writable${NC}"
    ((WARNINGS++))
fi

# Test API endpoint accessibility
echo -n "Testing API endpoint... "
if curl -s http://localhost:5000/v3 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Accessible${NC}"
    ((SUCCESS++))
else
    echo -e "${RED}✗ Not accessible${NC}"
    ((ERRORS++))
fi

echo ""
echo "======================================"
echo "Verification Summary"
echo "======================================"
echo -e "${GREEN}Successful checks: $SUCCESS${NC}"
if [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
fi
if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}Errors: $ERRORS${NC}"
fi

if [ $ERRORS -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ Installation verified successfully!${NC}"
    echo ""
    echo "Sample log entries:"
    echo "==================="
    sudo tail -n 5 /var/log/keystone/keystone.log
    echo ""
    echo "Useful commands:"
    echo "  - Source credentials: source /opt/stack/devstack/openrc admin admin"
    echo "  - View services: systemctl status devstack@*"
    echo "  - View logs: sudo tail -f /var/log/keystone/keystone.log"
    echo "  - Test token: openstack token issue"
    exit 0
else
    echo ""
    echo -e "${RED}✗ Installation verification failed${NC}"
    echo "Please check the errors above and review logs at:"
    echo "  /opt/stack/logs/stack.sh.log"
    exit 1
fi
