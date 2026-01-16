"""Data preparation utility for ML training."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.config.database import get_db
from ml.services.data_collector import DataCollector
from ml.training.explore_data import explore_dataset
from app.utils.logger import get_logger

logger = get_logger(__name__)


def prepare_training_dataset(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    output_file: str = "ml/training/training_data.csv",
    min_episodes: int = 100,
    include_historical: bool = True,
    explore: bool = True,
) -> pd.DataFrame:
    """
    Prepare and export training dataset.
    
    Args:
        start_date: Start date for data collection
        end_date: End date for data collection
        output_file: Path to save CSV file
        min_episodes: Minimum number of episodes required
        
    Returns:
        Training dataframe
    """
    if not start_date:
        start_date = datetime.now() - timedelta(days=180)
    if not end_date:
        end_date = datetime.now()

    logger.info(
        "Preparing training dataset",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    # Get database session
    db = next(get_db())

    try:
        # Collect data
        collector = DataCollector(db)
        df = collector.collect_training_data(
            start_date=start_date,
            end_date=end_date,
            min_episodes=min_episodes,
            include_historical=include_historical,
        )

        # Save to CSV
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        logger.info(
            "Training dataset prepared and saved",
            rows=len(df),
            columns=len(df.columns),
            output_file=output_file,
        )

        # Explore dataset if requested
        if explore:
            explore_dataset(df)

        return df

    except Exception as e:
        logger.error("Data preparation failed", error=str(e))
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare training dataset")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD)",
        default=None,
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ml/training/training_data.csv",
        help="Output CSV file path",
    )
    parser.add_argument(
        "--min-episodes",
        type=int,
        default=100,
        help="Minimum number of episodes required",
    )
    parser.add_argument(
        "--no-historical",
        action="store_true",
        help="Exclude historical features (faster but less informative)",
    )
    parser.add_argument(
        "--no-explore",
        action="store_true",
        help="Skip data exploration",
    )

    args = parser.parse_args()

    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    prepare_training_dataset(
        start_date=start_date,
        end_date=end_date,
        output_file=args.output,
        min_episodes=args.min_episodes,
        include_historical=not args.no_historical,
        explore=not args.no_explore,
    )

