# Tested Upload Commands for Training Data

## Prerequisites

Before uploading, make sure:
1. **Server is running**: The FastAPI server must be running on `http://localhost:8000`
2. **Files exist**: Training data files must be generated first
3. **Database is set up**: PostgreSQL must be running and migrations applied

## Quick Start (Easiest Method)

Use the provided script:

```bash
./upload_training_data.sh
```

This script will:
- Check if the server is running
- Verify files exist
- Upload both claims and remittances
- Show success/error messages

## Manual Upload (Tested Commands)

If you prefer to run commands manually, here are the **tested and working** commands:

### 1. Check Server is Running

```bash
curl http://localhost:8000/api/v1/health
```

Expected response: `{"status":"healthy"}` or similar JSON

### 2. Upload Claims (837 file)

```bash
curl -X POST http://localhost:8000/api/v1/claims/upload -F "file=@samples/training/training_837_claims.edi"
```

### 3. Upload Remittances (835 file)

```bash
curl -X POST http://localhost:8000/api/v1/remits/upload -F "file=@samples/training/training_835_remittances.edi"
```

## Starting the Server

If the server isn't running, start it:

```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python run.py
```

**Note**: The server requires:
- PostgreSQL database running
- Redis running (for Celery tasks)
- Database migrations applied (`alembic upgrade head`)

## Troubleshooting

### "Connection refused" error
- Server is not running - start it with `python run.py`
- Check if port 8000 is in use: `lsof -ti:8000`

### "File not found" error
- Generate training data first: `python ml/training/generate_training_data.py --episodes 200`

### "Database connection" error
- Make sure PostgreSQL is running
- Check `.env` file has correct `DATABASE_URL`
- Run migrations: `alembic upgrade head`

### Upload returns 202 (Accepted)
- This is normal! The file is being processed asynchronously by Celery
- Check Celery worker logs to see processing status

## Verification

After uploading, verify the data:

```bash
# Check how many claims were created
curl http://localhost:8000/api/v1/claims?limit=10

# Check historical data
python ml/training/check_historical_data.py
```

## Next Steps

After successful upload:

1. **Check data quality**:
   ```bash
   python ml/training/check_historical_data.py
   ```

2. **Train ML models**:
   ```bash
   python ml/training/train_models.py --start-date 2024-01-01 --end-date 2024-12-31
   ```

3. **Train deep learning model** (optional):
   ```python
   from ml.models.deep_risk_predictor import DeepRiskPredictor
   # Use in training script
   ```

