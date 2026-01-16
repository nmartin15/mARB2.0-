# Historical Data Sources for ML Training

This document explains where to find historical data for training ML models in mARB 2.0.

## Quick Check

First, check what data you already have:

```bash
python ml/training/check_historical_data.py
```

This will show:
- How many claims, remittances, and episodes you have
- Date ranges of your data
- Whether you have enough data for training (minimum 100 episodes)

## Data Sources

### 1. **Existing Database Data** ✅

Your database already contains historical data from:
- Previously uploaded EDI files (837 claims and 835 remittances)
- Processed claims and remittances
- Linked episodes (claims connected to their outcomes)

**Check your data:**
```bash
python ml/training/check_historical_data.py
```

### 2. **Sample Files** (For Testing/Development)

Sample EDI files are available in the `samples/` directory:

- **`samples/sample_837.txt`** - Sample 837 claim file
- **`samples/sample_835.txt`** - Sample 835 remittance file  
- **`samples/large/`** - Larger sample files for testing
  - `large_837_100claims.edi` - 100 claims
  - `large_837_500claims.edi` - 500 claims
  - `large_835_500remits.edi` - 500 remittances

**Upload sample files:**

```bash
# Upload 837 claim file
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@samples/sample_837.txt"

# Upload 835 remittance file
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@samples/sample_835.txt"
```

Or use the FastAPI Swagger UI at `http://localhost:8000/docs`

### 3. **Import from Practice Management System**

Export EDI files from your practice management system:

**Common Systems:**
- Epic
- Cerner
- Allscripts
- eClinicalWorks
- NextGen
- Athenahealth

**Export Process:**
1. Navigate to billing/claims section
2. Export claims as EDI 837 files
3. Export remittances as EDI 835 files
4. Upload to mARB 2.0 via API

**File Format:**
- Claims: X12 EDI 837 (Professional, Institutional, or Dental)
- Remittances: X12 EDI 835 (Health Care Claim Payment/Advice)

### 4. **Import from Clearinghouse**

Most clearinghouses allow you to download historical EDI files:

**Popular Clearinghouses:**
- Availity
- Change Healthcare (formerly Emdeon)
- Office Ally
- Trizetto
- Navicure
- Waystar

**Download Process:**
1. Log into clearinghouse portal
2. Navigate to reports/downloads section
3. Select date range
4. Download 837 and 835 files
5. Upload to mARB 2.0

### 5. **Billing Software Exports**

If you use billing software, export historical data:

**Common Billing Software:**
- Kareo
- AdvancedMD
- CareCloud
- DrChrono
- SimplePractice

**Export Format:**
- Usually can export as EDI 837/835
- May need to request EDI format specifically
- Some systems export as CSV (would need conversion)

### 6. **Generate Synthetic Data** (Development Only)

For development/testing, you can generate synthetic EDI files:

```bash
# Generate large 837 file with 500 claims
python scripts/generate_large_edi_files.py \
  --type 837 \
  --count 500 \
  --output samples/generated_837_500.edi

# Generate large 835 file with 500 remittances
python scripts/generate_large_edi_files.py \
  --type 835 \
  --count 500 \
  --output samples/generated_835_500.edi
```

⚠️ **Warning:** Synthetic data is for development/testing only. Don't use for production model training.

## Data Requirements

### Minimum Requirements

- **100 episodes** with outcomes (claims + remittances linked)
- Both 837 (claims) and 835 (remittances) files
- Episodes must be linked (automatic when remittances are uploaded)

### Recommended

- **500+ episodes** for better model performance
- **6+ months** of historical data
- **Balanced dataset** (mix of denied and paid claims)
- **Multiple payers** for better generalization

### Ideal

- **1000+ episodes**
- **12+ months** of data
- **Diverse payers** (Medicare, Medicaid, Commercial)
- **Various claim types** (different procedures, specialties)

## How Data Flows

1. **Upload 837 Claim File** → Stored in `claims` table
2. **Upload 835 Remittance File** → Stored in `remittances` table
3. **Automatic Linking** → Creates `claim_episodes` linking claims to remittances
4. **ML Training** → Uses episodes with outcomes for training

## Linking Claims and Remittances

Episodes are automatically created when:
- Remittances are uploaded and processed
- Claim control numbers match between 837 and 835 files

**Manual Linking:**
```bash
# Link a remittance to claims
curl -X POST "http://localhost:8000/api/v1/remits/{remittance_id}/link"

# Manually link an episode
curl -X POST "http://localhost:8000/api/v1/episodes/{episode_id}/link" \
  -H "Content-Type: application/json" \
  -d '{"claim_id": 123, "remittance_id": 456}'
```

## Checking Data Quality

After uploading data, check quality:

```bash
# Check data availability
python ml/training/check_historical_data.py

# Explore the dataset
python ml/training/explore_data.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31

# Prepare training data
python ml/training/prepare_data.py \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --output ml/training/training_data.csv
```

## Troubleshooting

### "Insufficient training data" Error

**Problem:** Less than 100 episodes with outcomes

**Solutions:**
1. Upload more 837 and 835 files
2. Ensure remittances are linked to claims (check episodes)
3. Use sample files for testing: `samples/sample_837.txt` and `samples/sample_835.txt`

### "No episodes found" Error

**Problem:** Claims and remittances aren't linked

**Solutions:**
1. Check that claim control numbers match between 837 and 835 files
2. Manually link episodes via API
3. Verify remittances reference the correct claim control numbers

### "No historical features" Warning

**Problem:** Historical features require 90+ days of data

**Solutions:**
1. Upload older historical data (6+ months)
2. Disable historical features: `--no-historical` flag
3. Use placeholder historical features (defaults to 0.0)

## Next Steps

Once you have sufficient data:

1. **Check Data:**
   ```bash
   python ml/training/check_historical_data.py
   ```

2. **Explore Data:**
   ```bash
   python ml/training/explore_data.py
   ```

3. **Prepare Training Data:**
   ```bash
   python ml/training/prepare_data.py
   ```

4. **Train Model:**
   ```bash
   python ml/training/train_models.py
   ```

5. **Tune Hyperparameters:**
   ```bash
   python ml/training/tune_hyperparameters.py
   ```

6. **Evaluate Model:**
   ```bash
   python ml/training/evaluate_models.py --model-path ml/models/saved/...
   ```

## Additional Resources

- **Sample Files:** `samples/README.md`
- **API Documentation:** `API_DOCUMENTATION.md`
- **ML Development Guide:** `ml/README.md`
- **Data Collection:** `ml/services/data_collector.py`

## Questions?

- Check existing data: `python ml/training/check_historical_data.py --show-sources`
- Review API docs: `http://localhost:8000/docs`
- Check logs for upload/processing errors

