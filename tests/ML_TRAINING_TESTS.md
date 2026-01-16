# ML Training Pipeline Tests

Comprehensive test suite for the ML training pipeline using production-quality synthetic data.

## Test Files

### 1. `test_ml_training_pipeline.py` - Comprehensive Integration Tests

Full pytest test suite covering:
- ✅ Synthetic data generation
- ✅ Data collection from database
- ✅ Feature extraction
- ✅ Data preparation
- ✅ Data exploration
- ✅ Model training
- ✅ Model evaluation
- ✅ Feature importance
- ✅ Historical data checking
- ✅ Full end-to-end pipeline
- ✅ Data quality validation
- ✅ Multiple specialties
- ✅ Denial rate distribution

**Run with pytest:**
```bash
# Run all ML training tests
pytest tests/test_ml_training_pipeline.py -v

# Run only integration tests
pytest tests/test_ml_training_pipeline.py::TestMLTrainingPipeline -v

# Run only unit tests
pytest tests/test_ml_training_pipeline.py::TestMLDataCollector -v
pytest tests/test_ml_training_pipeline.py::TestMLFeatureExtractor -v
pytest tests/test_ml_training_pipeline.py::TestMLRiskPredictor -v
```

### 2. `test_ml_pipeline_quick.py` - Quick Validation Script

Standalone script for quick pipeline validation without pytest:
- Generates synthetic data
- Loads into database
- Trains model
- Tests predictions

**Run directly:**
```bash
python tests/test_ml_pipeline_quick.py
```

### 3. `test_ml_service.py` - Existing ML Service Tests

Tests for MLService placeholder predictions (already exists).

## Test Coverage

### Integration Tests (`TestMLTrainingPipeline`)

1. **test_data_generation** - Validates synthetic data generator
2. **test_data_collection** - Tests data collection from database
3. **test_feature_extraction** - Tests feature extraction
4. **test_data_preparation** - Tests data preparation script
5. **test_data_exploration** - Tests data exploration
6. **test_model_training** - Tests model training
7. **test_model_evaluation** - Tests model evaluation
8. **test_feature_importance** - Tests feature importance extraction
9. **test_historical_data_check** - Tests data availability check
10. **test_full_pipeline** - End-to-end pipeline test
11. **test_data_quality_validation** - Tests data quality checks
12. **test_multiple_specialties** - Tests specialty variety
13. **test_denial_rate_distribution** - Tests realistic denial rates

### Unit Tests

**TestMLDataCollector:**
- `test_collect_training_data_insufficient` - Error handling
- `test_historical_statistics` - Historical stats calculation

**TestMLFeatureExtractor:**
- `test_extract_basic_features` - Basic feature extraction
- `test_extract_coding_features` - Coding features
- `test_extract_financial_features` - Financial features
- `test_extract_temporal_features` - Temporal features

**TestMLRiskPredictor:**
- `test_train_model` - Model training
- `test_predict` - Model prediction
- `test_save_load_model` - Model persistence
- `test_evaluate_model` - Model evaluation

## Running Tests

### Quick Test (Recommended First)

```bash
# Quick validation of entire pipeline
python tests/test_ml_pipeline_quick.py
```

This will:
1. Generate 150 synthetic episodes
2. Load into database
3. Train a model
4. Test predictions
5. Clean up

**Time**: ~30-60 seconds

### Full Test Suite

```bash
# All ML training tests
pytest tests/test_ml_training_pipeline.py -v

# With coverage
pytest tests/test_ml_training_pipeline.py --cov=ml --cov-report=html -v

# Specific test class
pytest tests/test_ml_training_pipeline.py::TestMLTrainingPipeline::test_full_pipeline -v
```

### Individual Components

```bash
# Test data generation only
pytest tests/test_ml_training_pipeline.py::TestMLTrainingPipeline::test_data_generation -v

# Test model training only
pytest tests/test_ml_training_pipeline.py::TestMLTrainingPipeline::test_model_training -v

# Test feature extraction only
pytest tests/test_ml_training_pipeline.py::TestMLFeatureExtractor -v
```

## Test Data

Tests use the synthetic data generator (`ml/training/generate_training_data.py`) which creates:
- 150 episodes (claims + remittances)
- 25% denial rate
- Multiple specialties
- Realistic CPT codes and diagnoses
- Proper EDI formatting

## Expected Results

### Integration Tests
- ✅ All tests should pass
- ✅ Models should train successfully
- ✅ Predictions should be in [0, 1] range
- ✅ Feature importance should be available
- ✅ Data quality checks should pass

### Performance
- Data generation: ~5-10 seconds
- Data loading: ~10-20 seconds
- Model training: ~10-30 seconds
- Total pipeline: ~30-60 seconds

## Troubleshooting

### "Insufficient training data" Error
**Solution**: The synthetic data generator creates 150 episodes, which should be enough. If you see this, check:
- Database connection
- Episode linking worked correctly
- Date ranges in queries

### "Model not trained" Error
**Solution**: Check that:
- Training data was collected successfully
- Features were extracted correctly
- Model training completed without errors

### Import Errors
**Solution**: Make sure you're running from project root:
```bash
cd /path/to/mARB\ 2.0
python tests/test_ml_pipeline_quick.py
```

## Next Steps

After tests pass:
1. Generate larger dataset (500-1000 episodes)
2. Train production model
3. Evaluate model performance
4. Deploy model

## Continuous Integration

These tests can be integrated into CI/CD:
```yaml
# Example GitHub Actions
- name: Test ML Pipeline
  run: |
    pytest tests/test_ml_training_pipeline.py -v
    python tests/test_ml_pipeline_quick.py
```




