# ML Model Development Workflow Guide

This guide covers the complete workflow for ML model development, training, and continuous learning in mARB 2.0.

## Overview

The ML system includes:
- **Risk Prediction Models**: Predict claim denial risk using historical data
- **Pattern Detection**: Learn denial patterns from historical remittances
- **Continuous Learning**: Automated retraining and pattern updates

## Quick Start

### 1. Check Data Availability

First, check if you have enough historical data for training:

```bash
python ml/training/check_historical_data.py
```

This will show:
- Total claims, remittances, and episodes
- Date ranges of available data
- Whether you have enough data (minimum 100 episodes with outcomes)

### 2. Run Full Pipeline

The easiest way to get started is to run the complete pipeline:

```bash
python ml/training/ml_workflow.py full
```

This will:
1. Check data availability
2. Collect training data
3. Train the risk prediction model
4. Run pattern detection on all payers
5. Generate reports

## Detailed Workflow

### Step 1: Check Historical Data

```bash
# Basic check
python ml/training/check_historical_data.py

# With data source information
python ml/training/check_historical_data.py --show-sources
```

**What it does:**
- Counts available claims, remittances, and episodes
- Checks date ranges
- Verifies you have enough data for training (minimum 100 episodes)

**Output:**
- Database statistics
- Training readiness status
- Recommendations

### Step 2: Prepare Training Data

```bash
python ml/training/prepare_data.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --output ml/training/training_data.csv
```

**What it does:**
- Collects claims with known outcomes (linked to remittances)
- Extracts features from claims (31+ features)
- Extracts labels (denial rates, payment rates)
- Validates data quality
- Saves to CSV for inspection

### Step 3: Train Model

```bash
python ml/training/train_models.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --model-type random_forest \
    --n-estimators 100 \
    --output-dir ml/models/saved
```

**What it does:**
- Collects training data
- Trains risk prediction model (Random Forest or Gradient Boosting)
- Evaluates on test set
- Saves trained model to disk

**Options:**
- `--model-type`: `random_forest` or `gradient_boosting`
- `--n-estimators`: Number of trees (default: 100)
- `--max-depth`: Maximum tree depth (optional)
- `--test-size`: Proportion for testing (default: 0.2)

### Step 4: Evaluate Model

```bash
python ml/training/evaluate_models.py \
    --model-path ml/models/saved/risk_predictor_random_forest_20240101_120000.pkl \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --cv-folds 5 \
    --output ml/training/evaluation_report.csv
```

**What it does:**
- Evaluates model on test set
- Performs cross-validation
- Shows regression metrics (R², RMSE, MAE)
- Shows classification metrics (Accuracy, Precision, Recall, F1, ROC AUC)
- Displays confusion matrix
- Shows feature importance

### Step 5: Run Pattern Detection

```bash
python ml/training/run_pattern_detection.py \
    --days-back 90 \
    --min-frequency 0.05
```

**What it does:**
- Analyzes historical remittances for all payers
- Detects recurring denial patterns
- Saves patterns to database
- Generates summary report

**Options:**
- `--days-back`: Number of days to look back (default: 90)
- `--min-frequency`: Minimum frequency threshold (default: 0.05 = 5%)
- `--payer-id`: Run for specific payer only (optional)

## Continuous Learning Pipeline

The continuous learning pipeline automates the entire workflow:

```bash
python ml/training/continuous_learning_pipeline.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --model-type random_forest \
    --n-estimators 100 \
    --days-back 90 \
    --output-dir ml/models/saved \
    --output-json ml/training/pipeline_results.json
```

**What it does:**
1. Checks data availability
2. Collects training data
3. Trains/retrains model
4. Evaluates model performance
5. Runs pattern detection
6. Generates comprehensive report

**Use cases:**
- Monthly model retraining
- Quarterly pattern updates
- Automated ML operations

## Automated Retraining (Celery Task)

For production, you can schedule automated retraining using Celery:

```python
from app.services.queue.tasks import retrain_ml_model
from datetime import datetime

# Schedule monthly retraining
result = retrain_ml_model.delay(
    start_date=(datetime.now() - timedelta(days=180)).isoformat(),
    end_date=datetime.now().isoformat(),
    model_type="random_forest",
    n_estimators=100,
    days_back=90,
    run_pattern_detection=True,
)
```

**Scheduling with Celery Beat:**

Add to your Celery beat schedule:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'retrain-ml-model-monthly': {
        'task': 'retrain_ml_model',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),  # 2 AM on 1st of month
        'kwargs': {
            'model_type': 'random_forest',
            'n_estimators': 100,
            'days_back': 90,
            'run_pattern_detection': True,
        },
    },
}
```

## Unified Workflow Script

The `ml_workflow.py` script provides a unified interface for all operations:

```bash
# Check data
python ml/training/ml_workflow.py check

# Prepare data
python ml/training/ml_workflow.py prepare --start-date 2024-01-01

# Train model
python ml/training/ml_workflow.py train --model-type random_forest

# Evaluate model
python ml/training/ml_workflow.py evaluate --model-path ml/models/saved/...

# Run pattern detection
python ml/training/ml_workflow.py patterns --days-back 90

# Run full pipeline
python ml/training/ml_workflow.py full
```

## Model Features

The risk prediction model uses **31+ features**:

### Basic Features (8)
- Total charge amount
- Claim completeness status
- Principal diagnosis presence
- Diagnosis code count
- Claim line count
- Charge per line (interaction)
- Diagnosis per line (interaction)
- Claim age in days

### Coding Features (5)
- Unique procedure codes
- Modifier count
- Unique modifiers
- Revenue code presence
- Revenue code count

### Financial Features (6)
- Total line charges
- Maximum line charge
- Minimum line charge
- Average line charge
- Median line charge
- Standard deviation of charges

### Provider Features (5)
- Attending provider presence
- Operating provider presence
- Referring provider presence
- Provider presence
- Total provider count

### Temporal Features (4)
- Service date day of week
- Service date month
- Service date quarter
- Service date is weekend

### Historical Features (4)
- Historical payer denial rate
- Historical provider denial rate
- Historical diagnosis denial rate
- Historical average payment rate

## Pattern Detection

Pattern detection analyzes historical remittances to identify recurring denial patterns:

**Pattern Types:**
- Denial reason codes
- Procedure code patterns
- Diagnosis code patterns
- Payer-specific patterns

**Pattern Properties:**
- Frequency: How often the pattern occurs
- Confidence: Confidence in pattern detection
- Occurrence count: Number of times seen
- Conditions: Conditions that trigger the pattern

**Integration:**
- Patterns are automatically integrated into risk scoring
- Risk scorer uses pattern matches to adjust risk scores
- Patterns are cached for performance

## Best Practices

### Data Collection
- Collect at least 100 episodes with outcomes before training
- Use 6+ months of historical data for better performance
- Ensure both claims (837) and remittances (835) are uploaded
- Episodes are automatically linked when remittances are processed

### Model Training
- Retrain monthly or quarterly with latest data
- Use rolling window (e.g., last 6 months) for training
- Compare new model performance to previous
- A/B test before full deployment

### Pattern Detection
- Run pattern detection monthly or quarterly
- Review learned patterns regularly
- Adjust frequency thresholds based on needs
- Monitor pattern confidence scores

### Performance Monitoring
- Track model metrics (R², RMSE, accuracy)
- Monitor prediction performance over time
- Review feature importance regularly
- Update features based on domain knowledge

## Troubleshooting

### Insufficient Training Data
**Error**: "Insufficient training data: found X episodes, minimum 100 required"

**Solution:**
- Upload more historical EDI files
- Ensure both 837 (claims) and 835 (remittances) are uploaded
- Wait for more data to accumulate

### Model Not Loading
**Issue**: Model not found or fails to load

**Solution:**
- Check `ml/models/saved/` directory exists
- Verify model file exists and is readable
- Service falls back to placeholder prediction automatically

### Poor Model Performance
**Issue**: Low R² or high RMSE

**Solutions:**
- Collect more training data
- Try different model types
- Tune hyperparameters
- Review feature importance
- Check for data quality issues

## Related Documentation

- `ml/README.md` - Detailed ML documentation
- `ml/HISTORICAL_DATA_SOURCES.md` - Data source information
- `ml/training/check_historical_data.py` - Data availability checker
- `app/services/learning/pattern_detector.py` - Pattern detection implementation
- `app/services/risk/ml_service.py` - ML service integration

## Next Steps

1. **Check your data**: Run `check_historical_data.py`
2. **Train initial model**: Run `ml_workflow.py full`
3. **Review results**: Check model metrics and patterns
4. **Set up automation**: Schedule Celery task for monthly retraining
5. **Monitor performance**: Track model metrics over time

