# Quick Start: Getting Training Data

## Option 1: Generate Synthetic Data (Fastest) ⚡

**Best for**: Development, testing, or when you don't have real data yet

```bash
# Generate 500 episodes with 25% denial rate
python ml/training/generate_training_data.py \
  --episodes 500 \
  --denial-rate 0.25 \
  --output-dir samples/training

# Upload to system
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@samples/training/training_837_claims.edi"

curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@samples/training/training_835_remittances.edi"

# Verify data
python ml/training/check_historical_data.py
```

**Time**: ~2 minutes  
**Result**: 500 realistic episodes ready for training

## Option 2: Use Sample Files (Quick Test) 🧪

**Best for**: Quick testing or learning the system

```bash
# Upload existing sample files
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@samples/sample_837.txt"

curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@samples/sample_835.txt"

# Check if you have enough
python ml/training/check_historical_data.py
```

**Time**: ~1 minute  
**Result**: 8 episodes (good for testing, not enough for training)

## Option 3: Get Real Data (Best for Production) 🏥

**Best for**: Production model training with real patterns

### Step 1: Identify Your Data Source
- **Practice Management System**: Epic, Cerner, Allscripts, etc.
- **Clearinghouse**: Availity, Change Healthcare, Office Ally, etc.
- **Billing Software**: Kareo, AdvancedMD, CareCloud, etc.

### Step 2: Request EDI Export
Contact your IT department or system administrator:
- Request EDI 837 files (claims) - Last 6-12 months
- Request EDI 835 files (remittances) - Last 6-12 months
- Specify X12 EDI format (not CSV)

### Step 3: Upload Files
```bash
# Upload your real 837 file
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@your_real_837_file.edi"

# Upload your real 835 file
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@your_real_835_file.edi"
```

**Time**: Varies (depends on IT response time)  
**Result**: Real historical data with actual denial patterns

**See `ml/REAL_DATA_SOURCES.md` for detailed instructions**

## Verify You Have Enough Data

```bash
python ml/training/check_historical_data.py
```

**You need**: At least 100 episodes with outcomes

**You'll see**:
- ✅ READY FOR TRAINING: 500+ episodes available
- ❌ INSUFFICIENT DATA: Need more episodes

## Next Steps

Once you have 100+ episodes:

1. **Explore Data**:
   ```bash
   python ml/training/explore_data.py
   ```

2. **Prepare Training Data**:
   ```bash
   python ml/training/prepare_data.py
   ```

3. **Train Model**:
   ```bash
   python ml/training/train_models.py
   ```

## Comparison

| Option | Time | Quality | Use Case |
|--------|------|---------|----------|
| **Synthetic** | 2 min | High (realistic) | Development, testing |
| **Sample Files** | 1 min | Low (limited) | Quick testing only |
| **Real Data** | Days/Weeks | Highest | Production training |

## Recommendation

**For Development/Testing**: Use synthetic data generator
```bash
python ml/training/generate_training_data.py --episodes 500
```

**For Production**: Get real data from your systems
- See `ml/REAL_DATA_SOURCES.md` for detailed instructions
- Contact your IT department or clearinghouse

## Troubleshooting

### "Insufficient training data" Error
**Solution**: Generate more synthetic data or upload more real files
```bash
python ml/training/generate_training_data.py --episodes 1000
```

### "No episodes found" Error
**Solution**: Ensure remittances are linked to claims
- Episodes are auto-created when 835 files reference claim control numbers
- Check that claim numbers match between 837 and 835 files

### "Files won't upload" Error
**Solution**: 
- Check file format (must be X12 EDI)
- Check file size (large files use file-based processing)
- Check API is running: `http://localhost:8000/docs`

## Need Help?

- **Synthetic Data**: `python ml/training/generate_training_data.py --help`
- **Real Data Sources**: See `ml/REAL_DATA_SOURCES.md`
- **Data Check**: `python ml/training/check_historical_data.py --show-sources`

