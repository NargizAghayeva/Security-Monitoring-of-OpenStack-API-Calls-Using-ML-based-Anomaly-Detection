#!/bin/bash

# Additional configuration script for Keystone
# Run this after DevStack installation if you need custom settings

set -e

echo "Configuring Keystone for thesis requirements..."

# Ensure we're running as stack user
if [ "$USER" != "stack" ]; then
    echo "Please run as stack user"
    exit 1
fi

# Source OpenStack credentials
source /opt/stack/devstack/openrc admin admin

# Configure Keystone for enhanced logging
sudo tee -a /etc/keystone/keystone.conf > /dev/null <<EOF

# Custom configuration for thesis
[DEFAULT]
debug = True
verbose = True

# Increase token expiration for testing
[token]
expiration = 7200

# Enable additional event notifications
[oslo_messaging_notifications]
driver = messagingv2
topics = notifications

EOF

# Restart Keystone service
sudo systemctl restart devstack@keystone

echo "Configuration completed!"
echo "Keystone has been configured with:"
echo "  - Enhanced debug logging"
echo "  - Extended token expiration (2 hours)"
echo "  - Event notifications enabled"
