# mARB 2.0 - EDI File Format Guide

## Overview

mARB 2.0 supports processing of EDI X12 files in two formats:
- **837**: Health Care Claim (Professional/Institutional)
- **835**: Health Care Claim Payment/Advice

The parser is resilient and handles variations, missing segments, and different format implementations gracefully.

## Supported Standards

- **X12 Version**: 005010X222A1 (837), 005010X221A1 (835)
- **Character Encoding**: UTF-8 (with fallback handling)
- **Delimiters**: Standard X12 delimiters (`*`, `~`, `:`)

## File Structure

### Envelope Structure

All EDI files follow the standard X12 envelope structure:

```
ISA*...~          # Interchange Header
GS*...~           # Functional Group Header
ST*...~           # Transaction Set Header
  [Transaction Data]
SE*...~           # Transaction Set Trailer
GE*...~           # Functional Group Trailer
IEA*...~          # Interchange Trailer
```

---

## 837 Claim File Format

### Overview

837 files contain health care claims submitted to payers. The parser extracts claims, patient information, provider details, diagnosis codes, and service lines.

### Key Segments

#### Interchange Header (ISA)
- **Purpose**: Identifies sender and receiver
- **Required**: Yes
- **Example**: `ISA*00*          *00*          *ZZ*SENDERID*ZZ*RECEIVERID*241220*1340*^*00501*000000001*0*P*:~`

#### Functional Group Header (GS)
- **Purpose**: Groups related transactions
- **Required**: Yes
- **Example**: `GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~`

#### Transaction Set Header (ST)
- **Purpose**: Marks start of 837 transaction
- **Required**: Yes
- **Example**: `ST*837*0001*005010X222A1~`

#### Claim Segment (CLM)
- **Purpose**: Contains claim-level information
- **Required**: Yes
- **Key Fields**:
  - Claim control number
  - Total charge amount
  - Claim frequency type (1=Original, 7=Corrected, 8=Void)
  - Facility type code
- **Example**: `CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~`

#### Subscriber Information (SBR)
- **Purpose**: Insurance information
- **Required**: Usually yes
- **Key Fields**:
  - Payer responsibility sequence (P=Primary, S=Secondary, T=Tertiary)
  - Insurance type code
- **Example**: `SBR*P*18*GROUP123******CI~`

#### Patient Demographics (DMG)
- **Purpose**: Patient date of birth and gender
- **Required**: Usually yes
- **Example**: `DMG*D8*19800101*M~`

#### Diagnosis Codes (HI)
- **Purpose**: Diagnosis codes (ICD-10)
- **Required**: Yes
- **Qualifiers**:
  - `ABK`: Principal diagnosis
  - `ABJ`: Principal diagnosis (alternate)
  - `APR`: Other diagnoses
  - `ABF`: Other diagnoses (alternate)
- **Example**: `HI*ABK:I10*E11.9~` (Principal: E11.9)

#### Service Lines (SV1/SV2)
- **Purpose**: Procedure/service information
- **Required**: Yes (at least one)
- **Key Fields**:
  - Procedure code (CPT/HCPCS)
  - Charge amount
  - Service date
  - Units
- **Example**: `SV1*HC:99213*1500.00*UN*1***1~`

#### Dates (DTP)
- **Purpose**: Various dates (service date, statement date, etc.)
- **Required**: Usually yes
- **Qualifiers**:
  - `431`: Claim statement period start
  - `484`: Claim statement period end
  - `472`: Service date
- **Date Formats**:
  - `D8`: CCYYMMDD (e.g., 20241215)
  - `D6`: YYMMDD
  - `RD8`: Date range
- **Example**: `DTP*472*D8*20241215~`

#### Provider Information (NM1)
- **Purpose**: Provider, billing provider, rendering provider
- **Required**: Usually yes
- **Entity Types**:
  - `85`: Billing provider
  - `87`: Pay-to provider
  - `82`: Rendering provider
- **Example**: `NM1*85*2*PROVIDER NAME*****XX*1234567890~`

#### References (REF)
- **Purpose**: Additional identifiers
- **Required**: Sometimes
- **Qualifiers**:
  - `D9`: Patient account number
  - `EI`: Employer identification number
  - `1W`: Member ID
- **Example**: `REF*D9*PATIENT001~`

### 837 File Example

```
ISA*00*          *00*          *ZZ*SENDERID*ZZ*RECEIVERID*241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*1234567890*20241220*1340*CH~
NM1*41*2*SAMPLE MEDICAL PRACTICE*****46*1234567890~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
DTP*472*D8*20241215~
HI*ABK:I10*E11.9~
LX*1~
SV1*HC:99213*1500.00*UN*1***1~
DTP*472*D8*20241215~
SE*24*0001~
GE*1*1~
IEA*1*000000001~
```

### Parsing Behavior

The parser handles:
- **Missing optional segments**: Logs warnings but continues processing
- **Missing critical segments**: Marks claim as incomplete
- **Multiple claims**: Processes all claims in file
- **Variations in segment order**: Adapts to different formats
- **Format detection**: Automatically detects format characteristics

---

## 835 Remittance File Format

### Overview

835 files contain payment and remittance advice from payers. The parser extracts payment information, adjustments, denials, and service line details.

### Key Segments

#### Interchange Header (ISA)
- **Purpose**: Identifies sender and receiver
- **Required**: Yes
- **Example**: `ISA*00*          *00*          *ZZ*PAYERID*ZZ*PROVIDERID*241220*1430*^*00501*000000001*0*P*:~`

#### Functional Group Header (GS)
- **Purpose**: Groups related transactions
- **Required**: Yes
- **Note**: Uses `HP` (Health Care Claim Payment) instead of `HC`
- **Example**: `GS*HP*PAYERID*PROVIDERID*20241220*1430*1*X*005010X221A1~`

#### Transaction Set Header (ST)
- **Purpose**: Marks start of 835 transaction
- **Required**: Yes
- **Example**: `ST*835*0001*005010X221A1~`

#### Financial Information (BPR)
- **Purpose**: Payment information
- **Required**: Yes
- **Key Fields**:
  - Payment method (I=Check, C=ACH)
  - Total payment amount
  - Check/EFT number
  - Payment date
- **Example**: `BPR*I*28750.00*C*CHK987654321*20241220*123456789*01*987654321*DA*1234567890*20241220~`

#### Trace Number (TRN)
- **Purpose**: Remittance trace number
- **Required**: Usually yes
- **Example**: `TRN*1*REM20241220001*987654321~`

#### Claim Payment Information (CLP)
- **Purpose**: Claim-level payment details
- **Required**: Yes
- **Key Fields**:
  - Claim control number
  - Claim status code (1=Processed, 2=Denied, 3=Pending, etc.)
  - Total charge amount
  - Payment amount
  - Patient responsibility amount
  - Claim filing indicator
- **Example**: `CLP*CLAIM001*1*1500.00*1200.00*0*11*1234567890*20241215*1~`

#### Claim Adjustments (CAS)
- **Purpose**: Adjustment reason codes and amounts
- **Required**: Sometimes
- **Adjustment Categories**:
  - `CO`: Contractual obligation
  - `CR`: Correction and reversal
  - `OA`: Other adjustments
  - `PI`: Payer initiated reductions
  - `PR`: Patient responsibility
- **Common Reason Codes**:
  - `CO45`: Charge exceeds fee schedule
  - `CO96`: Non-covered charges
  - `CO97`: Benefit maximum reached
  - `PR1`: Patient responsibility - deductible
  - `PR2`: Patient responsibility - coinsurance
  - `OA23`: Impact of prior payer
- **Example**: `CAS*CO*45*100.00~` (Contractual obligation, reason 45, amount $100)

#### Service Line Payment (SVC)
- **Purpose**: Service line payment details
- **Required**: Usually yes
- **Key Fields**:
  - Procedure code (CPT/HCPCS)
  - Charge amount
  - Payment amount
  - Units
- **Example**: `SVC*HC:99213*1500.00*1200.00*UN*1~`

#### Service Line Adjustments (CAS)
- **Purpose**: Service line-level adjustments
- **Required**: Sometimes
- **Format**: Same as claim-level CAS segments

#### Amounts (AMT)
- **Purpose**: Various monetary amounts
- **Required**: Sometimes
- **Qualifiers**:
  - `AU`: Coverage amount
  - `D`: Deductible
  - `F5`: Coinsurance
- **Example**: `AMT*AU*200.00~`

### 835 File Example

```
ISA*00*          *00*          *ZZ*PAYERID*ZZ*PROVIDERID*241220*1430*^*00501*000000001*0*P*:~
GS*HP*PAYERID*PROVIDERID*20241220*1430*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220*123456789*01*987654321*DA*1234567890*20241220~
TRN*1*REM20241220001*987654321~
N1*PR*BLUE CROSS BLUE SHIELD~
LX*1~
CLP*CLAIM001*1*1500.00*1200.00*0*11*1234567890*20241215*1~
CAS*PR*1*50.00~
CAS*PR*2*150.00~
CAS*CO*45*100.00~
SVC*HC:99213*1500.00*1200.00*UN*1~
CAS*CO*45*100.00~
SE*24*0001~
GE*1*1~
IEA*1*000000001~
```

### Claim Status Codes

The CLP segment includes a claim status code:
- `1`: Processed as Primary
- `2`: Processed as Secondary
- `3`: Processed as Tertiary
- `4`: Denied
- `19`: Processed as Primary, Forwarded to Additional Payer(s)
- `20`: Processed as Secondary, Forwarded to Additional Payer(s)
- `21`: Processed as Tertiary, Forwarded to Additional Payer(s)
- `22`: Reversal of Previous Payment

---

## Format Detection

mARB 2.0 includes automatic format detection that adapts to different file formats from various practices and clearinghouses.

### Detected Characteristics

- **Segment patterns**: Which segments are present and frequency
- **Element counts**: Number of elements per segment type
- **Date formats**: Date qualifiers used (D8, RD8, TM, DT)
- **Diagnosis qualifiers**: Which diagnosis code qualifiers are used
- **Facility codes**: Facility type codes in the data
- **Version**: EDI version/release number

### Format Profile

Format profiles are stored per practice and help the parser adapt to practice-specific variations.

---

## Common Issues and Solutions

### Missing Segments

**Issue**: File is missing optional segments  
**Solution**: Parser logs warnings but continues processing. Claims are marked as incomplete if critical segments are missing.

### Invalid Date Formats

**Issue**: Date format doesn't match expected format  
**Solution**: Parser attempts to parse common date formats (D8, D6, RD8) and logs warnings for unrecognized formats.

### Malformed Segments

**Issue**: Segment has incorrect number of elements  
**Solution**: Parser attempts to extract available data and logs warnings for missing elements.

### Encoding Issues

**Issue**: File encoding is not UTF-8  
**Solution**: Parser attempts UTF-8 decoding with error handling, falling back to error-tolerant decoding.

### Multiple Transactions

**Issue**: File contains multiple transactions  
**Solution**: Parser processes all transactions in the file and returns all extracted claims/remittances.

---

## File Validation

### Basic Validation

Before uploading, you can perform basic validation:

```bash
# Check file has ISA segment
grep -c "^ISA" file.txt  # Should be 1

# Check file has IEA segment
grep -c "^IEA" file.txt  # Should be 1

# Check for CLM segments (837) or CLP segments (835)
grep -c "^CLM" file.txt  # 837 files
grep -c "^CLP" file.txt  # 835 files
```

### Format Validation

The parser performs validation during processing:
- Envelope structure validation
- Segment structure validation
- Required segment presence
- Data type validation (dates, amounts, codes)

---

## Best Practices

### File Preparation

1. **Encoding**: Ensure files are UTF-8 encoded
2. **Line Endings**: Standardize line endings (Unix LF recommended)
3. **Delimiters**: Use standard X12 delimiters
4. **Validation**: Validate files before upload when possible

### Error Handling

1. **Review Warnings**: Check parsing warnings in API responses
2. **Incomplete Claims**: Review claims marked as incomplete
3. **Logs**: Check application logs for detailed error information

### Performance

1. **File Size**: Large files (>10MB) may take longer to process
2. **Batch Processing**: Consider splitting very large files
3. **Async Processing**: Files are processed asynchronously - use task IDs to track status

---

## Sample Files

Sample files are available in the `samples/` directory:
- `sample_837.txt`: Example 837 claim file
- `sample_835.txt`: Example 835 remittance file

See `samples/README.md` for detailed information about sample files.

---

## Support

For EDI format questions:
- Review sample files in `samples/` directory
- Check parser implementation in `app/services/edi/parser.py`
- Review format detection documentation in `app/services/edi/FORMAT_DETECTION.md`
- See `TROUBLESHOOTING.md` for common issues

---

**Last Updated**: 2024-12-20  
**Version**: 2.0.0

