# mARB 2.0 Documentation

This directory contains all project documentation organized by category.

## 🚀 Quick Start

**New to the project?** Start here:
1. **[Quick Reference](../DOCUMENTATION_QUICK_REFERENCE.md)** - Find docs by task, module, or topic
2. **[Contributing Guide](../CONTRIBUTING.md)** - How to contribute and update documentation
3. **[Main README](../README.md)** - Project overview and setup

## 📚 Documentation Index

### Getting Started
- **[Setup Guide](../SETUP.md)** - Initial setup and configuration
- **[Dependencies](../DEPENDENCIES.md)** - Complete list of prerequisites
- **[Troubleshooting](../TROUBLESHOOTING.md)** - Common issues and solutions

### API & Development
- **[API Documentation](../API_DOCUMENTATION.md)** - Complete API reference with examples
- **[EDI Format Guide](../EDI_FORMAT_GUIDE.md)** - EDI file format specifications
- **[Development Roadmap](./ROADMAP.md)** - Development priorities and roadmap

### Deployment & Operations
- **[Deployment Guide](../deployment/DEPLOYMENT.md)** - Production deployment instructions
- **[Deployment Runbook](../deployment/DEPLOYMENT_RUNBOOK.md)** - Step-by-step operational procedures
- **[Backup/Restore Guide](../deployment/BACKUP_RESTORE.md)** - Database backup and restore procedures
- **[Production Security Checklist](../deployment/PRODUCTION_SECURITY_CHECKLIST.md)** - Security checklist for production
- **[HTTPS Setup](../deployment/SETUP_HTTPS.md)** - HTTPS/TLS configuration guide

### Monitoring & Tools
- **[Sentry Setup](./guides/SENTRY_SETUP.md)** - Error tracking and monitoring configuration
- **[Memory Monitoring](../MEMORY_MONITORING.md)** - Memory tracking and threshold configuration
- **[Load Testing](../LOAD_TEST_SUITE_COMPLETE.md)** - Load testing for large files

### Security
- **[Security Guide](../SECURITY.md)** - Security and HIPAA compliance information

### Guides
- **[Sentry Setup](./guides/SENTRY_SETUP.md)** - Complete Sentry error tracking guide

## 📁 Directory Structure

```
docs/
├── README.md              # This file - documentation index
├── ROADMAP.md            # Development roadmap
├── archive/              # Archived/obsolete documentation
├── guides/               # Detailed guides
│   └── SENTRY_SETUP.md  # Sentry error tracking guide
└── deployment/          # Deployment-specific docs (symlinked from ../deployment)
```

## 🔍 Finding Documentation

### Quick Reference

**Use the [Documentation Quick Reference](../DOCUMENTATION_QUICK_REFERENCE.md)** to find documentation by:
- **Task** (e.g., "I'm adding a new API endpoint")
- **Module/Component** (e.g., `app/api/routes/`)
- **Topic** (e.g., "Authentication & Security")

### By Topic

**Setup & Installation**
- Setup Guide
- Dependencies
- Troubleshooting

**API Development**
- API Documentation
- EDI Format Guide

**Deployment**
- Deployment Guide
- Deployment Runbook
- Backup/Restore Guide
- Production Security Checklist
- HTTPS Setup

**Monitoring & Operations**
- Sentry Setup
- Memory Monitoring
- Load Testing

**Security**
- Security Guide

**Planning**
- Development Roadmap

## 📝 Documentation Maintenance

To prevent documentation bloat:

1. **Archive obsolete docs** - Move status/completion docs to `docs/archive/`
2. **Consolidate redundant docs** - Merge overlapping content into single guides
3. **Update README** - Keep documentation index current
4. **Remove outdated content** - Delete truly obsolete documentation

## 🗄️ Archived Documentation

Historical and status documentation has been moved to `docs/archive/` for reference. These files are kept for historical context but are not actively maintained.

