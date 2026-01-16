# ML Model Development Guide

This directory contains the machine learning infrastructure for risk prediction in mARB 2.0.

## Overview

The ML system predicts claim denial risk using historical claim and remittance data. The model is trained on features extracted from claims and their outcomes (denials/payments).

## Directory Structure

```
ml/
├── models/              # ML model definitions
│   ├── risk_predictor.py    # Risk prediction model
│   ├── pattern_learner.py   # Pattern learning (future)
│   └── saved/               # Trained model files (.pkl)
├── services/            # ML services
│   ├── feature_extractor.py # Feature extraction from claims
│   └── data_collector.py    # Training data collection
└── training/           # Training scripts
    ├── train_models.py      # Main training script
    ├── prepare_data.py      # Data preparation utility
    ├── explore_data.py      # Data exploration and analysis
    ├── evaluate_models.py   # Model evaluation utilities
    └── tune_hyperparameters.py  # Hyperparameter tuning
```

## Prerequisites

Before training models, ensure you have:

1. **Historical Data**: At least 100+ claims with linked remittances (outcomes)
2. **Database**: PostgreSQL database with populated `claims`, `remittances`, and `claim_episodes` tables
3. **Dependencies**: All ML dependencies installed (`scikit-learn`, `pandas`, `numpy`, `joblib`)

### Check Your Historical Data

First, check what historical data you have available:

```bash
python ml/training/check_historical_data.py
```

This will show:
- Total claims, remittances, and episodes in your database
- Date ranges of available data
- Number of episodes with outcomes (ready for training)
- Whether you have enough data to train models

For more information about data sources:

```bash
python ml/training/check_historical_data.py --show-sources
```

### Generate Synthetic Training Data

If you don't have enough real historical data, generate realistic synthetic data:

```bash
python ml/training/generate_training_data.py \
  --episodes 500 \
  --denial-rate 0.25 \
  --output-dir samples/training
```

This creates:
- Realistic 837 claim files with diverse scenarios
- Matching 835 remittance files with proper denial codes
- Properly linked episodes (claims + remittances)
- Realistic payment patterns and adjustments

**Features:**
- ✅ Realistic denial codes (CO-16, CO-18, CO-50, CO-96, CO-97, OA-23)
- ✅ Diverse payment scenarios (paid, denied, partial, adjusted)
- ✅ Realistic CPT codes and diagnosis codes
- ✅ Proper temporal relationships (service dates, payment dates)
- ✅ Multiple payers and providers
- ✅ Configurable denial rates

**Then upload the generated files:**
```bash
# Upload 837 claims
curl -X POST "http://localhost:8000/api/v1/claims/upload" \
  -F "file=@samples/training/training_837_claims.edi"

# Upload 835 remittances
curl -X POST "http://localhost:8000/api/v1/remits/upload" \
  -F "file=@samples/training/training_835_remittances.edi"
```

### Real Data Sources

For real historical data, see:
- **`ml/REAL_DATA_SOURCES.md`** - Comprehensive guide to real data sources
- Practice Management Systems (Epic, Cerner, Allscripts, etc.)
- Clearinghouses (Availity, Change Healthcare, Office Ally, etc.)
- Billing Software (Kareo, AdvancedMD, CareCloud, etc.)

## Quick Start

### 1. Explore and Prepare Training Data

First, explore your data to understand its characteristics:

```bash
source venv/bin/activate
python ml/training/explore_data.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --output-report ml/training/data_report.txt
```

This will show:
- Dataset overview (samples, features, memory usage)
- Label distribution and class imbalance
- Missing values analysis
- Feature statistics and correlations
- Data quality issues

Then, collect and prepare your training dataset:

```bash
python ml/training/prepare_data.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --output ml/training/training_data.csv
```

This will:
- Collect claims with known outcomes (linked to remittances)
- Extract enhanced features from claims (including temporal and interaction features)
- Extract labels (denial rates, payment rates) from remittances
- Validate data quality
- Save to CSV for inspection
- Automatically run data exploration

### 2. Train the Model

Train a risk prediction model with default hyperparameters:

```bash
python ml/training/train_models.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --model-type random_forest \
    --n-estimators 100 \
    --output-dir ml/models/saved
```

Options:
- `--model-type`: `random_forest` or `gradient_boosting`
- `--n-estimators`: Number of trees (default: 100)
- `--max-depth`: Maximum tree depth (optional)
- `--test-size`: Proportion for testing (default: 0.2)
- `--output-dir`: Where to save the model

### 2b. Tune Hyperparameters (Recommended)

For better performance, tune hyperparameters first:

```bash
python ml/training/tune_hyperparameters.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --model-type random_forest \
    --n-iter 50 \
    --cv 5 \
    --output-dir ml/models/saved
```

This will:
- Use randomized search to find optimal hyperparameters
- Perform cross-validation for robust evaluation
- Save the best-tuned model automatically

Options:
- `--model-type`: `random_forest` or `gradient_boosting`
- `--n-iter`: Number of hyperparameter combinations to try (default: 20)
- `--cv`: Number of cross-validation folds (default: 5)

### 3. Model Evaluation

The training script automatically provides comprehensive evaluation, but you can also run detailed evaluation:

```bash
python ml/training/evaluate_models.py \
    --model-path ml/models/saved/risk_predictor_random_forest_20240101_120000.pkl \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --cv-folds 5 \
    --output ml/training/evaluation_report.csv
```

This will:
- Evaluate on test set with comprehensive metrics
- Perform cross-validation
- Show regression metrics (R², RMSE, MAE)
- Show classification metrics (Accuracy, Precision, Recall, F1, ROC AUC)
- Display confusion matrix
- Show feature importance
- Generate evaluation report

The evaluation includes:
- **Regression Metrics**: R², RMSE, MAE, MSE
- **Classification Metrics**: Accuracy, Precision, Recall, F1, ROC AUC
- **Confusion Matrix**: True/False Positives/Negatives
- **Feature Importance**: Top predictive features
- **Prediction Statistics**: Mean, std, percentiles

### 4. Deploy Model

The trained model is automatically loaded by `MLService` when available. The service:
- Looks for the latest model in `ml/models/saved/`
- Falls back to placeholder prediction if no model found
- Uses the model for risk prediction in the risk scoring pipeline

## Features

The model uses **31+ features** (27 base + 4 historical):

### Basic Features (8)
1. Total charge amount
2. Claim completeness status (binary)
3. Principal diagnosis presence (binary)
4. Diagnosis code count
5. Claim line count
6. Charge per line (interaction feature)
7. Diagnosis per line (interaction feature)
8. Claim age in days

### Coding Features (5)
9. Unique procedure codes
10. Modifier count
11. Unique modifiers
12. Revenue code presence (binary)
13. Revenue code count

### Financial Features (6)
14. Total line charges
15. Maximum line charge
16. Minimum line charge
17. Average line charge
18. Median line charge
19. Standard deviation of charges

### Provider Features (5)
20. Attending provider presence (binary)
21. Operating provider presence (binary)
22. Referring provider presence (binary)
23. Provider presence (binary)
24. Total provider count

### Temporal Features (4)
25. Service date day of week (0-6)
26. Service date month (1-12)
27. Service date quarter (1-4)
28. Is weekend (binary)

### Historical Features (4) - Optional
29. Historical payer denial rate (90-day lookback)
30. Historical provider denial rate (90-day lookback)
31. Historical diagnosis denial rate (90-day lookback)
32. Historical average payment rate (90-day lookback)

## Model Types

### Random Forest
- **Pros**: Robust, handles non-linear relationships, feature importance
- **Cons**: Can overfit with small datasets
- **Best for**: General use, when you have sufficient data

### Gradient Boosting
- **Pros**: Often better accuracy, handles complex patterns
- **Cons**: More prone to overfitting, slower training
- **Best for**: When you have large datasets and want maximum accuracy

## Model Output

The model predicts a **denial rate** (0.0 to 1.0), which is converted to a **risk score** (0-100) in the risk scoring pipeline.

- **0.0-0.25**: Low risk (0-25 score)
- **0.25-0.50**: Medium risk (25-50 score)
- **0.50-0.75**: High risk (50-75 score)
- **0.75-1.0**: Critical risk (75-100 score)

## Integration

The ML model is integrated into the risk scoring pipeline:

```python
# In RiskScorer.calculate_risk_score()
historical_risk = self.ml_service.predict_risk(claim)
```

The historical risk contributes 15% to the overall risk score:
- Payer risk: 20%
- Coding risk: 25%
- Documentation risk: 20%
- **Historical risk (ML): 15%**
- Pattern risk: 20%

## Monitoring

Monitor model performance:

1. **Training Metrics**: Check R², RMSE during training
2. **Test Metrics**: Evaluate on held-out test set
3. **Feature Importance**: Review which features matter most
4. **Production Performance**: Monitor actual denial rates vs predictions

## Retraining

Retrain models periodically as new data becomes available:

```bash
# Retrain with latest 6 months of data
python ml/training/train_models.py \
    --start-date $(date -d '6 months ago' +%Y-%m-%d) \
    --model-type random_forest
```

Best practices:
- Retrain monthly or quarterly
- Use rolling window (e.g., last 6 months)
- Compare new model performance to previous
- A/B test before full deployment

## Troubleshooting

### Insufficient Training Data
**Error**: "Insufficient training data: found X episodes, minimum 100 required"

**Solution**: 
- Collect more historical data
- Reduce `--min-episodes` threshold (not recommended)
- Use placeholder prediction until sufficient data

### Model Not Loading
**Issue**: Model not found or fails to load

**Solution**:
- Check `ml/models/saved/` directory exists
- Verify model file exists and is readable
- Check logs for specific error messages
- Service falls back to placeholder prediction automatically

### Poor Model Performance
**Issue**: Low R² or high RMSE

**Solutions**:
- Collect more training data
- Try different model types
- Tune hyperparameters (n_estimators, max_depth)
- Review feature importance - remove irrelevant features
- Check for data quality issues

## Future Enhancements

- [ ] Pattern learning model for denial pattern detection
- [ ] Deep learning models for complex patterns
- [ ] Online learning for continuous model updates
- [ ] Model versioning and A/B testing
- [ ] Automated hyperparameter tuning
- [ ] Feature engineering pipeline
- [ ] Model explainability (SHAP values)

## References

- [Scikit-learn Documentation](https://scikit-learn.org/stable/)
- [Random Forest Regressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)
- [Gradient Boosting Regressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.GradientBoostingRegressor.html)

