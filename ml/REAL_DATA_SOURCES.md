# Real Historical Data Sources for ML Training

This document lists **actual, real-world sources** where you can obtain historical EDI data for training ML models.

## 🏥 Healthcare Data Sources

### 1. **Practice Management Systems**

Most practice management systems can export historical EDI files:

#### Epic Systems
- **Export Location**: MyChart > Reports > Billing > EDI Export
- **Format**: X12 837 (claims) and 835 (remittances)
- **Access**: Requires Epic access credentials
- **Contact**: Your Epic administrator or IT department

#### Cerner
- **Export Location**: Revenue Cycle > Reports > EDI Transactions
- **Format**: X12 837/835
- **Access**: Requires Cerner access
- **Contact**: Cerner support or your IT department

#### Allscripts
- **Export Location**: Practice Management > Reports > EDI Export
- **Format**: X12 837/835
- **Contact**: Allscripts support

#### eClinicalWorks
- **Export Location**: Reports > Billing > EDI Export
- **Format**: X12 837/835
- **Contact**: eClinicalWorks support

#### NextGen
- **Export Location**: Reports > Billing > EDI History
- **Format**: X12 837/835
- **Contact**: NextGen support

#### Athenahealth
- **Export Location**: Reports > Billing > EDI Files
- **Format**: X12 837/835
- **Contact**: Athenahealth support

### 2. **Clearinghouses**

Clearinghouses process and store all your EDI transactions:

#### Availity
- **Portal**: https://www.availity.com
- **Export Location**: Reports > Transaction History > Download EDI Files
- **Data Available**: Up to 2+ years of historical data
- **Format**: X12 837/835
- **Access**: Requires Availity account
- **Contact**: 1-800-AVAILITY or your account representative

#### Change Healthcare (formerly Emdeon)
- **Portal**: https://www.changehealthcare.com
- **Export Location**: Reports > EDI Transaction History
- **Data Available**: Up to 3+ years
- **Format**: X12 837/835
- **Contact**: Your Change Healthcare account manager

#### Office Ally
- **Portal**: https://www.officeally.com
- **Export Location**: Reports > EDI Files > Download
- **Data Available**: Up to 1+ year
- **Format**: X12 837/835
- **Contact**: Office Ally support

#### Trizetto (now part of Cognizant)
- **Portal**: https://www.cognizant.com
- **Export Location**: Reports > EDI History
- **Data Available**: Up to 2+ years
- **Format**: X12 837/835
- **Contact**: Trizetto support

#### Navicure
- **Portal**: https://www.navicure.com
- **Export Location**: Reports > Transaction Reports > EDI Export
- **Data Available**: Up to 2+ years
- **Format**: X12 837/835
- **Contact**: Navicure support

#### Waystar
- **Portal**: https://www.waystar.com
- **Export Location**: Reports > EDI Files
- **Data Available**: Up to 3+ years
- **Format**: X12 837/835
- **Contact**: Waystar support

### 3. **Billing Software**

If you use standalone billing software:

#### Kareo
- **Export Location**: Reports > Billing > EDI Export
- **Format**: X12 837/835
- **Contact**: Kareo support

#### AdvancedMD
- **Export Location**: Reports > Billing > EDI History
- **Format**: X12 837/835
- **Contact**: AdvancedMD support

#### CareCloud
- **Export Location**: Reports > EDI Transactions
- **Format**: X12 837/835
- **Contact**: CareCloud support

#### DrChrono
- **Export Location**: Reports > Billing > EDI Files
- **Format**: X12 837/835
- **Contact**: DrChrono support

#### SimplePractice
- **Export Location**: Reports > Billing > EDI Export
- **Format**: X12 837/835
- **Contact**: SimplePractice support

### 4. **Electronic Health Records (EHR)**

Many EHR systems also handle billing and can export EDI:

- **Epic MyChart**
- **Cerner PowerChart**
- **Allscripts Professional EHR**
- **athenahealth**
- **eClinicalWorks**
- **NextGen**

**Export Process**: Usually under Billing/Revenue Cycle Management section

### 5. **Hospital Information Systems (HIS)**

For hospital-based practices:

- **Epic (Hospital)**
- **Cerner (Hospital)**
- **Meditech**
- **Allscripts (Hospital)**
- **eClinicalWorks (Hospital)**

**Export Process**: Contact your IT department or revenue cycle management team

## 📊 How to Request Data

### Step 1: Identify Your System
1. Determine which system(s) you use for billing
2. Check if you have a clearinghouse account
3. Identify your IT contact or system administrator

### Step 2: Request EDI Export
**Email Template:**
```
Subject: Request for Historical EDI Data Export

Dear [IT Department/System Administrator],

I need to export historical EDI transaction files for machine learning 
model training. Please provide:

1. EDI 837 files (claims) - Last 6-12 months
2. EDI 835 files (remittances) - Last 6-12 months
3. Date range: [Start Date] to [End Date]

Format: X12 EDI format (standard EDI files)
Delivery: Via secure file transfer or download portal

Please let me know:
- How to access/download these files
- Any required approvals or forms
- Estimated timeline for delivery

Thank you,
[Your Name]
```

### Step 3: Download/Receive Files
- Most systems allow direct download from portal
- Some require IT to export and provide files
- Files are typically large (MB to GB), so plan accordingly

### Step 4: Upload to mARB 2.0
```bash
# Upload 837 claims file
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@your_837_file.edi"

# Upload 835 remittances file
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@your_835_file.edi"
```

## 🔒 Security & Compliance

### HIPAA Considerations
- **Encryption**: Ensure files are encrypted during transfer
- **Access Control**: Limit access to authorized personnel only
- **Audit Logging**: Log all data access
- **Data Retention**: Follow your organization's data retention policies

### Best Practices
1. **Use Secure Transfer**: SFTP, encrypted email, or secure portal
2. **Verify Data**: Check file integrity after download
3. **Store Securely**: Encrypt files at rest
4. **Access Logging**: Log who accessed what data and when
5. **Data Minimization**: Only request data you need

## 📈 Data Requirements

### Minimum for Training
- **100 episodes** (linked claims + remittances)
- **6 months** of data
- **Mix of outcomes** (denied, paid, partial)

### Recommended
- **500+ episodes**
- **12+ months** of data
- **Multiple payers** (Medicare, Medicaid, Commercial)
- **Diverse claim types**

### Ideal
- **1000+ episodes**
- **24+ months** of data
- **All major payers**
- **All claim types** (office visits, procedures, etc.)

## 🚀 Quick Start with Real Data

1. **Identify Source**: Check which system you use
2. **Request Export**: Contact IT/system administrator
3. **Download Files**: Get 837 and 835 EDI files
4. **Upload to mARB**: Use API endpoints
5. **Verify Linking**: Check that episodes are created
6. **Train Model**: Run training scripts

## 💡 Tips

- **Start Small**: Request 3-6 months first, then expand
- **Multiple Sources**: If you use multiple systems, get data from all
- **Date Ranges**: Request overlapping date ranges to ensure completeness
- **File Formats**: Confirm X12 EDI format (not CSV or other formats)
- **File Sizes**: Large files may need to be split or processed in batches

## ❓ Troubleshooting

### "Can't find EDI export option"
- Contact your system administrator
- Check if you have the right permissions
- Look in Reports, Billing, or Revenue Cycle sections

### "Files are in wrong format"
- Request X12 EDI format specifically
- Some systems export as CSV - you'll need EDI format
- Contact vendor support for EDI export instructions

### "Files are too large"
- Request data in smaller date ranges
- Split files by month or quarter
- Use file-based upload for large files (>50MB)

## 📞 Support Contacts

If you need help:
- **System Vendor**: Contact your EHR/PMS vendor support
- **Clearinghouse**: Contact your clearinghouse account manager
- **IT Department**: Your organization's IT team
- **mARB Support**: Check documentation or contact development team

---

**Note**: Always ensure you have proper authorization and follow HIPAA guidelines when accessing and using patient data.

