"""Quick test script for ML training pipeline.

This script tests the complete ML pipeline without requiring pytest.
Useful for quick validation of the training system.
"""
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import get_db
from app.models.database import Remittance
from app.services.edi.parser import EDIParser
from app.services.edi.transformer import EDITransformer
from app.services.episodes.linker import EpisodeLinker
from ml.training.check_historical_data import check_historical_data
from ml.training.generate_training_data import generate_training_dataset
from ml.training.prepare_data import prepare_training_dataset
from ml.training.train_models import train_model


def test_full_pipeline():
    """Test the complete ML training pipeline."""
    print("\n" + "=" * 70)
    print("ML TRAINING PIPELINE TEST")
    print("=" * 70)

    # Create temp directory
    temp_dir = Path(tempfile.mkdtemp())
    print(f"\nUsing temp directory: {temp_dir}")

    try:
        # Step 1: Generate synthetic data
        print("\n[1/6] Generating synthetic training data...")
        output_dir = temp_dir / "synthetic"
        start_date = datetime.now() - timedelta(days=180)

        generate_training_dataset(
            num_episodes=150,
            output_dir=output_dir,
            start_date=start_date,
            denial_rate=0.25,
        )
        print("✓ Synthetic data generated")

        # Step 2: Load data into database
        print("\n[2/6] Loading data into database...")
        db = next(get_db())

        parser = EDIParser()
        transformer = EDITransformer(db)

        # Process claims
        claims_file = output_dir / "training_837_claims.edi"
        with open(claims_file, "r", encoding="utf-8") as f:
            claims_content = f.read()

        claims_result = parser.parse(claims_content, "training_837_claims.edi")
        claim_count = 0
        for claim_data in claims_result.get("claims", []):
            claim = transformer.transform_837_claim(claim_data)
            db.add(claim)
            claim_count += 1
        db.commit()
        print(f"✓ Loaded {claim_count} claims")

        # Process remittances
        remittances_file = output_dir / "training_835_remittances.edi"
        with open(remittances_file, "r", encoding="utf-8") as f:
            remittances_content = f.read()

        remittances_result = parser.parse(remittances_content, "training_835_remittances.edi")
        bpr_data = remittances_result.get("bpr_data", {})

        remittance_count = 0
        for remittance_data in remittances_result.get("remittances", []):
            remittance = transformer.transform_835_remittance(remittance_data, bpr_data)
            db.add(remittance)
            remittance_count += 1
        db.commit()
        print(f"✓ Loaded {remittance_count} remittances")

        # Link episodes
        linker = EpisodeLinker(db)
        remittances = db.query(Remittance).all()
        episode_count = 0
        for remittance in remittances:
            episodes = linker.auto_link_by_control_number(remittance)
            episode_count += len(episodes)
        db.commit()
        print(f"✓ Linked {episode_count} episodes")

        # Step 3: Check data availability
        print("\n[3/6] Checking data availability...")
        stats = check_historical_data(db)
        print(f"✓ Found {stats['episodes_with_outcomes']} episodes with outcomes")
        assert stats["episodes_with_outcomes"] >= 50, "Need at least 50 episodes"

        # Step 4: Prepare training data
        print("\n[4/6] Preparing training data...")
        data_file = temp_dir / "training_data.csv"
        df = prepare_training_dataset(
            start_date=start_date,
            end_date=datetime.now(),
            output_file=str(data_file),
            min_episodes=50,
            include_historical=False,
            explore=False,
        )
        print(f"✓ Prepared {len(df)} training samples")
        assert len(df) >= 50, "Should have at least 50 samples"

        # Step 5: Train model
        print("\n[5/6] Training model...")
        model = train_model(
            db_session=db,
            start_date=start_date,
            end_date=datetime.now(),
            model_type="random_forest",
            n_estimators=50,
            max_depth=10,
            test_size=0.2,
            random_state=42,
            output_dir=str(temp_dir / "models"),
        )
        print("✓ Model trained successfully")
        assert model.is_trained, "Model should be trained"

        # Step 6: Test prediction
        print("\n[6/6] Testing predictions...")
        from app.models.database import Claim
        from ml.services.feature_extractor import FeatureExtractor

        claim = db.query(Claim).first()
        if claim:
            extractor = FeatureExtractor()
            features = extractor.extract_features(
                claim, include_historical=False, db_session=None
            )

            prediction = model.predict_single(features)
            print(f"✓ Prediction: {prediction:.4f} (denial rate)")
            assert 0.0 <= prediction <= 1.0, "Prediction should be in [0, 1]"

        print("\n" + "=" * 70)
        print("✓ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nPipeline is working correctly!")
        print(f"\nModel saved to: {temp_dir / 'models'}")
        print(f"Training data saved to: {data_file}")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        db.close()


if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)

