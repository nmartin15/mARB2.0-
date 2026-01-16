# Security and HIPAA Compliance for Sample Files

## ⚠️ CRITICAL SECURITY NOTICE

**These sample files contain synthetic PHI/PII data for testing purposes only. They are designed to mimic real-world EDI transactions and insurance plan designs while maintaining HIPAA compliance.**

## PHI/PII Data Handling

### Protected Health Information (PHI) in Sample Files

The sample files contain the following types of PHI/PII:

#### 835 Remittance File (`sample_835.txt`)
- **Patient Names**: Synthetic names (e.g., "PATIENT*JOHN*M")
- **Medical Record Numbers (MRN)**: Synthetic identifiers (e.g., "123456789")
- **Patient Control Numbers**: Synthetic identifiers (e.g., "PATIENT001")
- **Provider Names and NPIs**: Synthetic provider information
- **Service Dates**: Synthetic dates (2024-12-XX)
- **Diagnosis Codes**: Real ICD-10 codes (for realistic testing)
- **CPT Codes**: Real procedure codes (for realistic testing)
- **Claim Control Numbers**: Synthetic identifiers
- **Payment Information**: Synthetic amounts

#### Plan Design File (`sample_plan_design.json`)
- **Plan Information**: Generic plan names and structures
- **Benefit Rules**: Realistic but generic benefit structures
- **No Patient-Specific Data**: This file contains no PHI

## HIPAA Compliance Requirements

### 1. Access Controls

**All access to these files must be logged and audited:**

```python
# Example: All file access should go through audit middleware
from app.api.middleware.audit import AuditMiddleware

# All API endpoints accessing PHI must:
# - Require authentication
# - Log access with user_id, timestamp, IP address
# - Store audit logs in secure database
```

### 2. Encryption

**PHI must be encrypted at rest and in transit:**

- **At Rest**: Database columns containing PHI should use encryption
- **In Transit**: All API endpoints must use HTTPS/TLS
- **File Storage**: Sample files should be stored in encrypted directories
- **Backups**: All backups containing PHI must be encrypted

### 3. Data Minimization

**Only collect and store necessary PHI:**

- Store only PHI required for claim processing
- Anonymize or pseudonymize when possible
- Implement data retention policies
- Delete PHI when no longer needed

### 4. Audit Logging

**All PHI access must be logged:**

```python
# Required audit log fields:
{
    "user_id": "string",
    "timestamp": "ISO8601",
    "action": "read|write|delete|export",
    "resource_type": "claim|remittance|patient",
    "resource_id": "string",
    "ip_address": "string",
    "user_agent": "string",
    "success": "boolean"
}
```

### 5. Access Restrictions

**Implement role-based access control (RBAC):**

- **Administrators**: Full access with audit logging
- **Providers**: Access to their own patients only
- **Billing Staff**: Access to claims/remittances only
- **Analysts**: De-identified data only
- **External Systems**: API keys with limited scope

### 6. Data Transmission Security

**Secure file transfer protocols:**

- **SFTP/FTPS**: For EDI file transfers
- **HTTPS/TLS 1.2+**: For API communications
- **VPN**: For remote access
- **Encrypted Email**: If PHI must be emailed (avoid when possible)

### 7. Business Associate Agreements (BAAs)

**Required for all third-party services:**

- Cloud storage providers
- EDI clearinghouses
- Payment processors
- Analytics services
- Any service that processes PHI

## Security Best Practices for Sample Files

### 1. File Storage

```bash
# Store sample files in restricted directory
chmod 600 samples/sample_835.txt
chmod 600 samples/sample_plan_design.json

# Use encrypted filesystem if possible
# Never commit real PHI to version control
```

### 2. Database Security

```python
# Use parameterized queries (SQLAlchemy does this automatically)
# Never use string concatenation for SQL queries
# Encrypt sensitive columns
# Use connection pooling with SSL
```

### 3. API Security

```python
# Require authentication for all endpoints
# Use JWT tokens with expiration
# Implement rate limiting
# Validate and sanitize all inputs
# Use HTTPS only in production
```

### 4. Logging Security

```python
# Never log full PHI in log messages
# Use structured logging with redaction
# Example:
logger.info(
    "Claim processed",
    claim_id=claim_id,  # OK - identifier only
    # patient_name=patient_name,  # BAD - PHI in logs
    # ssn=ssn,  # BAD - PII in logs
)
```

### 5. Error Handling

```python
# Never expose PHI in error messages
# Use generic error messages for users
# Log detailed errors server-side only
# Sanitize error responses
```

## Testing with Sample Files

### Safe Testing Practices

1. **Use Synthetic Data Only**: These sample files contain synthetic data
2. **Isolated Test Environment**: Use separate test database
3. **No Production Data**: Never use real patient data in tests
4. **Clean Up After Tests**: Delete test data after test runs
5. **Audit Test Access**: Log all test file access

### Test Data Generation

```python
# Use Faker library for generating synthetic PHI
from faker import Faker

fake = Faker()
synthetic_patient = {
    "name": fake.name(),
    "mrn": fake.uuid4(),
    "dob": fake.date_of_birth(),
    # Never use real patient data
}
```

## Incident Response

### If PHI is Breached:

1. **Immediate Actions**:
   - Contain the breach
   - Assess scope of exposure
   - Notify security team
   - Preserve evidence

2. **Notification Requirements**:
   - Notify affected individuals within 60 days
   - Notify HHS within 60 days (if >500 affected)
   - Notify media (if >500 affected)
   - Document all actions

3. **Remediation**:
   - Fix security vulnerability
   - Review and update policies
   - Retrain staff if needed
   - Monitor for additional breaches

## Compliance Checklist

- [ ] All PHI access is logged and audited
- [ ] Encryption at rest and in transit implemented
- [ ] Access controls and RBAC configured
- [ ] Business Associate Agreements in place
- [ ] Incident response plan documented
- [ ] Staff trained on HIPAA requirements
- [ ] Regular security audits performed
- [ ] Data retention policies implemented
- [ ] Backup and recovery procedures tested
- [ ] Security monitoring and alerting configured

## Additional Resources

- **HIPAA Regulations**: https://www.hhs.gov/hipaa
- **NIST Cybersecurity Framework**: https://www.nist.gov/cyberframework
- **OWASP Top 10**: https://owasp.org/www-project-top-ten/
- **HITRUST CSF**: https://hitrustalliance.net/

## Contact

For security concerns or questions about PHI handling:
- Security Team: security@example.com
- Compliance Officer: compliance@example.com
- Emergency: security-incident@example.com

---

**Last Updated**: 2024-12-20
**Version**: 1.0
**Classification**: Internal Use Only

