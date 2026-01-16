"""Data exploration and analysis utilities for ML training."""
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.services.data_collector import DataCollector
from app.utils.logger import get_logger

logger = get_logger(__name__)


def explore_dataset(df: pd.DataFrame, output_file: Optional[str] = None) -> None:
    """
    Explore and analyze training dataset.
    
    Args:
        df: Training dataframe
        output_file: Optional file to save exploration report
    """
    print("\n" + "=" * 70)
    print("DATASET EXPLORATION REPORT")
    print("=" * 70)

    # Basic statistics
    print("\n--- Dataset Overview ---")
    print(f"Total samples:        {len(df):,}")
    print(f"Total features:        {len(df.columns):,}")
    print(f"Memory usage:          {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

    # Label distribution
    if "is_denied" in df.columns:
        print("\n--- Label Distribution ---")
        denied_count = (df["is_denied"] == 1).sum()
        paid_count = (df["is_denied"] == 0).sum()
        denied_rate = denied_count / len(df) * 100

        print(f"Denied claims:         {denied_count:,} ({denied_rate:.2f}%)")
        print(f"Paid claims:           {paid_count:,} ({100 - denied_rate:.2f}%)")
        print(f"Class imbalance ratio: {max(denied_count, paid_count) / min(denied_count, paid_count):.2f}:1")

    # Denial rate statistics
    if "denial_rate" in df.columns:
        print("\n--- Denial Rate Statistics ---")
        print(f"Mean:                  {df['denial_rate'].mean():.4f}")
        print(f"Median:                {df['denial_rate'].median():.4f}")
        print(f"Std:                   {df['denial_rate'].std():.4f}")
        print(f"Min:                   {df['denial_rate'].min():.4f}")
        print(f"Max:                   {df['denial_rate'].max():.4f}")
        print(f"25th percentile:       {df['denial_rate'].quantile(0.25):.4f}")
        print(f"75th percentile:       {df['denial_rate'].quantile(0.75):.4f}")

    # Payment rate statistics
    if "payment_rate" in df.columns:
        print("\n--- Payment Rate Statistics ---")
        print(f"Mean:                  {df['payment_rate'].mean():.4f}")
        print(f"Median:                {df['payment_rate'].median():.4f}")
        print(f"Std:                   {df['payment_rate'].std():.4f}")
        print(f"Min:                   {df['payment_rate'].min():.4f}")
        print(f"Max:                   {df['payment_rate'].max():.4f}")

    # Missing values
    print("\n--- Missing Values ---")
    missing_counts = df.isnull().sum()
    missing_pct = (missing_counts / len(df) * 100).round(2)
    missing_df = pd.DataFrame(
        {
            "Missing Count": missing_counts,
            "Missing %": missing_pct,
        }
    )
    missing_df = missing_df[missing_df["Missing Count"] > 0].sort_values(
        "Missing Count", ascending=False
    )

    if len(missing_df) > 0:
        print(missing_df.to_string())
    else:
        print("No missing values found!")

    # Feature statistics
    print("\n--- Feature Statistics (Numeric) ---")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    exclude_cols = ["claim_id", "is_denied", "denial_rate", "payment_rate", "denial_count", "adjustment_count", "payment_amount"]
    feature_cols = [col for col in numeric_cols if col not in exclude_cols]

    if len(feature_cols) > 0:
        feature_stats = df[feature_cols].describe().T
        feature_stats = feature_stats.sort_values("std", ascending=False)
        print(feature_stats.head(20).to_string())

    # Correlation with target
    if "denial_rate" in df.columns and len(feature_cols) > 0:
        print("\n--- Top Correlations with Denial Rate ---")
        correlations = df[feature_cols + ["denial_rate"]].corr()["denial_rate"].abs()
        correlations = correlations.drop("denial_rate").sort_values(ascending=False)
        print(correlations.head(15).to_string())

    # Constant features
    print("\n--- Constant Features (No Variance) ---")
    constant_features = []
    for col in feature_cols:
        if df[col].nunique() <= 1:
            constant_features.append(col)

    if constant_features:
        print(f"Found {len(constant_features)} constant features:")
        for feat in constant_features:
            print(f"  - {feat}")
    else:
        print("No constant features found!")

    # Highly correlated features
    if len(feature_cols) > 1:
        print("\n--- Highly Correlated Feature Pairs (>0.95) ---")
        corr_matrix = df[feature_cols].corr().abs()
        high_corr_pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                corr_val = corr_matrix.iloc[i, j]
                if corr_val > 0.95:
                    high_corr_pairs.append(
                        (corr_matrix.columns[i], corr_matrix.columns[j], corr_val)
                    )

        if high_corr_pairs:
            print(f"Found {len(high_corr_pairs)} highly correlated pairs:")
            for feat1, feat2, corr in sorted(high_corr_pairs, key=lambda x: x[2], reverse=True)[:10]:
                print(f"  - {feat1} <-> {feat2}: {corr:.4f}")
        else:
            print("No highly correlated feature pairs found!")

    # Date range
    if "service_date_day_of_week" in df.columns:
        print("\n--- Temporal Distribution ---")
        if "service_date_month" in df.columns:
            month_counts = df["service_date_month"].value_counts().sort_index()
            print("Claims by month:")
            for month, count in month_counts.items():
                print(f"  Month {int(month)}: {count:,}")

    print("\n" + "=" * 70)

    # Save report if requested
    if output_file:
        report_lines = []
        report_lines.append("Dataset Exploration Report")
        report_lines.append("=" * 70)
        report_lines.append(f"\nTotal samples: {len(df):,}")
        report_lines.append(f"Total features: {len(df.columns):,}")
        
        if "is_denied" in df.columns:
            denied_rate = (df["is_denied"] == 1).mean() * 100
            report_lines.append(f"\nDenial rate: {denied_rate:.2f}%")
        
        if "denial_rate" in df.columns:
            report_lines.append(f"\nDenial rate statistics:")
            report_lines.append(f"  Mean: {df['denial_rate'].mean():.4f}")
            report_lines.append(f"  Std: {df['denial_rate'].std():.4f}")
        
        report_lines.append(f"\nMissing values: {df.isnull().sum().sum()}")
        report_lines.append(f"Constant features: {len(constant_features)}")
        report_lines.append(f"Highly correlated pairs: {len(high_corr_pairs)}")
        
        with open(output_file, "w") as f:
            f.write("\n".join(report_lines))
        
        logger.info("Exploration report saved", output_file=output_file)


def main():
    """Main data exploration script."""
    parser = argparse.ArgumentParser(description="Explore and analyze training dataset")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date for data collection (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date for data collection (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--input-file",
        type=str,
        help="Input CSV file (if data already prepared)",
        default=None,
    )
    parser.add_argument(
        "--output-report",
        type=str,
        help="Output file for exploration report",
        default=None,
    )
    parser.add_argument(
        "--min-episodes",
        type=int,
        default=100,
        help="Minimum number of episodes required",
    )

    args = parser.parse_args()

    try:
        if args.input_file:
            # Load from file
            logger.info("Loading dataset from file", input_file=args.input_file)
            df = pd.read_csv(args.input_file)
        else:
            # Collect from database
            start_date = None
            end_date = None

            if args.start_date:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
            else:
                start_date = datetime.now() - timedelta(days=180)

            if args.end_date:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
            else:
                end_date = datetime.now()

            logger.info(
                "Collecting data from database",
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )

            db = next(get_db())
            collector = DataCollector(db)
            df = collector.collect_training_data(
                start_date=start_date,
                end_date=end_date,
                min_episodes=args.min_episodes,
                include_historical=True,
            )

        # Explore dataset
        explore_dataset(df, output_file=args.output_report)

        logger.info("Data exploration completed successfully")

    except Exception as e:
        logger.error("Data exploration failed", error=str(e))
        raise


if __name__ == "__main__":
    main()

