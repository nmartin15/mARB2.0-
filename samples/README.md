# Sample EDI and Plan Design Files

This directory contains production-realistic sample files for testing and development of the mARB 2.0 claim risk engine.

## Files

### `sample_835.txt`
**EDI X12 835 Remittance Advice File**

A comprehensive 835 remittance file containing:
- **8 claims** with various payment scenarios:
  - Fully paid claims with adjustments
  - Partially paid claims
  - Denied claims (prior authorization, non-covered)
  - Zero payment scenarios
- **Multiple service lines** per claim
- **Adjustment reason codes** (CAS segments):
  - CO45: Charge exceeds fee schedule
  - CO96: Non-covered charges
  - CO97: Benefit maximum reached
  - CO253: Patient eligibility issues
  - OA23: Prior payer impact
  - PR1/PR2: Patient responsibility (deductible/coinsurance)
- **Real-world EDI structure** following X12 005010X221A1 standard
- **Synthetic PHI/PII** for HIPAA-compliant testing

**Use Cases:**
- Testing 835 parser implementation
- Episode linking between claims and remittances
- Denial pattern detection
- Payment reconciliation testing
- Risk scoring validation

### `sample_plan_design.json`
**Insurance Plan Design Configuration**

A comprehensive plan design file modeling a PPO Gold plan with:
- **Deductibles**: Individual ($1,500) and family ($3,000)
- **Out-of-pocket maximums**: Individual ($5,000) and family ($10,000)
- **Copays**: Primary care, specialist, urgent care, ER, pharmacy tiers
- **Coinsurance**: 20% in-network, 40% out-of-network
- **Benefit limits**: Annual visit limits, lifetime maximums
- **Prior authorization rules**: Surgery, imaging, specialty drugs
- **Network rules**: In-network vs out-of-network benefits
- **Coverage rules**: Preventive care, maternity, mental health parity
- **CPT code rules**: Allowed amounts, prior auth requirements, frequency limits
- **Denial reason codes**: Comprehensive mapping of adjustment codes
- **Exclusions**: Cosmetic, experimental, weight loss, fertility

**Use Cases:**
- Risk scoring based on plan rules
- Prior authorization checking
- Benefit calculation
- Denial prediction
- Coverage verification

### `SECURITY_AND_HIPAA.md`
**Security and HIPAA Compliance Documentation**

Comprehensive guide covering:
- PHI/PII data handling requirements
- HIPAA compliance checklist
- Security best practices
- Incident response procedures
- Testing guidelines

## Usage

### Testing 835 Parser

```python
from app.services.edi.parser import EDIParser

# Read sample file
with open("samples/sample_835.txt", "r") as f:
    content = f.read()

# Parse 835 file
parser = EDIParser()
result = parser.parse(content, "sample_835.txt")

# Access parsed remittances
for remittance in result.get("remittances", []):
    print(f"Claim: {remittance['claim_control_number']}")
    print(f"Payment: ${remittance['payment_amount']}")
    print(f"Denial Reasons: {remittance.get('denial_reasons', [])}")
```

### Testing Plan Design Rules

```python
import json
from app.models.database import Plan

# Load plan design
with open("samples/sample_plan_design.json", "r") as f:
    plan_design = json.load(f)

# Store in database
plan = Plan(
    payer_id=1,
    plan_name=plan_design["plan_name"],
    plan_type=plan_design["plan_type"],
    benefit_rules=plan_design
)
db.add(plan)
db.commit()

# Use for risk scoring
from app.services.risk.scorer import RiskScorer
scorer = RiskScorer()
risk_score = scorer.calculate_risk(claim, plan)
```

## Important Security Notes

⚠️ **CRITICAL**: These files contain synthetic PHI/PII data. 

- **Never commit real patient data** to version control
- **Always use encryption** for PHI at rest and in transit
- **Log all PHI access** for audit purposes
- **Restrict file permissions** (chmod 600)
- **Use separate test database** for development
- **Review SECURITY_AND_HIPAA.md** before use

## File Format Details

### 835 File Structure

```
ISA*...~          # Interchange Header
GS*HP*...~        # Functional Group Header (HP = Health Care Claim Payment)
ST*835*...~       # Transaction Set Header
BPR*...~          # Financial Information
TRN*...~          # Trace Number
N1*PR*...~        # Payer Identification
LX*...~           # Claim Loop Start
  CLP*...~        # Claim Payment Information
  CAS*...~        # Claim Adjustments
  NM1*QC*...~     # Patient Information
  NM1*82*...~     # Rendering Provider
  SVC*...~        # Service Line Payment
  CAS*...~        # Service Line Adjustments
SE*...~           # Transaction Set Trailer
GE*...~           # Functional Group Trailer
IEA*...~          # Interchange Trailer
```

### Plan Design JSON Structure

```json
{
  "plan_name": "string",
  "plan_type": "PPO|HMO|EPO|POS",
  "deductibles": {...},
  "copays": {...},
  "coinsurance": {...},
  "benefit_limits": {...},
  "prior_authorization_requirements": {...},
  "cpt_code_rules": {...},
  "denial_reason_codes": {...}
}
```

## Validation

### EDI File Validation

```bash
# Check file format
file samples/sample_835.txt

# Validate segment structure (basic check)
grep -c "^ISA" samples/sample_835.txt  # Should be 1
grep -c "^IEA" samples/sample_835.txt  # Should be 1
grep -c "^CLP" samples/sample_835.txt  # Should match claim count
```

### JSON Validation

```bash
# Validate JSON syntax
python -m json.tool samples/sample_plan_design.json > /dev/null && echo "Valid JSON"
```

## Contributing

When adding new sample files:

1. **Use synthetic data only** - Never use real patient information
2. **Follow EDI standards** - Use proper X12 segment structure
3. **Document changes** - Update this README
4. **Security review** - Ensure HIPAA compliance
5. **Test thoroughly** - Validate with parser before committing

## Support

For questions or issues with sample files:
- Check `SECURITY_AND_HIPAA.md` for compliance questions
- Review parser implementation in `app/services/edi/parser.py`
- Contact development team for technical questions

---

**Last Updated**: 2024-12-20
**Version**: 1.0

