# DevStack Setup for OpenStack/Keystone

This repository contains the DevStack installation and configuration for OpenStack Keystone environment.

## System Requirements

- **OS**: Ubuntu 22.04 LTS (recommended)
- **RAM**: Minimum 8GB (16GB recommended)
- **Disk**: 20GB free space
- **CPU**: 2+ cores
- **Network**: Internet connection

## Quick Start
```bash
git clone https://github.com/username/01-devstack-setup.git
cd 01-devstack-setup
chmod +x scripts/install.sh
./scripts/install.sh
```

## Detailed Documentation

- [Prerequisites](docs/prerequisites.md)
- [Installation Steps](docs/installation-steps.md)
- [Troubleshooting](docs/troubleshooting.md)

## Project Context

This is the first phase of the thesis: "Machine Learning-Based Anomaly Detection of API Calls in Private Cloud Environment (OpenStack/Keystone)"

**Next Step**: [02-log-collection](../02-log-collection)

## Architecture Overview
```
┌─────────────────────────────────────────┐
│         DevStack Environment            │
│  ┌─────────────────────────────────┐   │
│  │        Keystone Service         │   │
│  │  (Identity & Authentication)    │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │       API Endpoints             │   │
│  │  - /v3/auth/tokens              │   │
│  │  - /v3/users                    │   │
│  │  - /v3/projects                 │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │      Logging System             │   │
│  │  /var/log/keystone/             │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Features

- ✅ Minimal DevStack configuration focused on Keystone
- ✅ Enhanced logging for API call monitoring
- ✅ Debug mode enabled for detailed traces
- ✅ Automated installation scripts
- ✅ Verification and testing tools

## Contributing

This is a thesis project. For questions or suggestions, please open an issue.

## License

MIT License

## Author

Nargiz - MSc Cybersecurity Student, ELTE University
