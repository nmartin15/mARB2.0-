"""Data collection utilities for ML model training."""
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, case

from app.models.database import Claim, Remittance, ClaimEpisode, RiskScore
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DataCollector:
    """Collect and prepare training data from historical claims and remittances."""

    def __init__(self, db: Session):
        self.db = db

    def collect_training_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_episodes: int = 100,
        include_historical: bool = True,
    ) -> pd.DataFrame:
        """
        Collect training data from claims with known outcomes (remittances).
        
        Args:
            start_date: Start date for data collection (default: 6 months ago)
            end_date: End date for data collection (default: today)
            min_episodes: Minimum number of episodes required
            include_historical: Whether to include historical features (slower but more informative)
            
        Returns:
            DataFrame with features and labels (denial_rate, payment_rate)
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=180)
        if not end_date:
            end_date = datetime.now()

        logger.info(
            "Collecting training data",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            include_historical=include_historical,
        )

        # Query claims with linked episodes and remittances
        # Use eager loading to avoid N+1 queries
        from sqlalchemy.orm import joinedload

        episodes = (
            self.db.query(ClaimEpisode)
            .join(Claim)
            .join(Remittance, isouter=True)
            .options(
                joinedload(ClaimEpisode.claim).joinedload(Claim.claim_lines),
                joinedload(ClaimEpisode.remittance),
            )
            .filter(
                and_(
                    Claim.created_at >= start_date,
                    Claim.created_at <= end_date,
                    ClaimEpisode.remittance_id.isnot(None),  # Only claims with outcomes
                )
            )
            .all()
        )

        if len(episodes) < min_episodes:
            logger.warning(
                "Insufficient training data",
                episodes_found=len(episodes),
                min_required=min_episodes,
            )
            raise ValueError(
                f"Insufficient training data: found {len(episodes)} episodes, "
                f"minimum {min_episodes} required"
            )

        logger.info("Found episodes with outcomes", count=len(episodes))

        # Build training dataset
        training_data = []
        skipped_count = 0
        
        for episode in episodes:
            claim = episode.claim
            remittance = episode.remittance

            if not claim or not remittance:
                skipped_count += 1
                continue

            try:
                # Extract features from claim
                features = self._extract_claim_features(claim, include_historical=include_historical)

                # Extract labels from remittance
                labels = self._extract_outcome_labels(remittance, episode)

                # Combine features and labels
                row = {**features, **labels}
                training_data.append(row)
            except KeyError as e:
                # Missing key in data structure - log and skip
                logger.warning(
                    "Missing key during feature extraction",
                    episode_id=episode.id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                skipped_count += 1
                continue
            except AttributeError as e:
                # Missing attribute errors - log and skip
                logger.warning(
                    "Missing attribute during feature extraction",
                    episode_id=episode.id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                skipped_count += 1
                continue
            except ValueError as e:
                # Data validation errors - log and re-raise as they may indicate data issues
                logger.error(
                    "Invalid value during feature extraction",
                    episode_id=episode.id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise
            except Exception as e:
                # Unexpected errors - log with full context and re-raise if critical
                logger.error(
                    "Unexpected error during feature extraction",
                    episode_id=episode.id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                # For critical errors (database, memory), re-raise to stop processing
                if isinstance(e, (MemoryError, SystemError)):
                    raise
                skipped_count += 1
                continue

        if skipped_count > 0:
            logger.warning("Skipped episodes during data collection", count=skipped_count)

        df = pd.DataFrame(training_data)
        
        # Validate data quality
        self._validate_data_quality(df)
        
        logger.info(
            "Training dataset created",
            rows=len(df),
            columns=len(df.columns),
            skipped=skipped_count,
        )

        return df

    def _extract_claim_features(self, claim: Claim, include_historical: bool = True) -> Dict:
        """
        Extract features from a claim for training.
        
        Args:
            claim: The claim to extract features from
            include_historical: Whether to include historical features
        """
        claim_lines = claim.claim_lines or []
        diagnosis_codes = claim.diagnosis_codes or []

        # Basic features
        features = {
            "claim_id": claim.id,
            "total_charge_amount": claim.total_charge_amount or 0.0,
            "is_incomplete": 1.0 if claim.is_incomplete else 0.0,
            "has_principal_diagnosis": 1.0 if claim.principal_diagnosis else 0.0,
            "diagnosis_count": len(diagnosis_codes),
            "claim_line_count": len(claim_lines),
            "facility_type_code": claim.facility_type_code or "",
            "payer_id": claim.payer_id or 0,
            "provider_id": claim.provider_id or 0,
        }

        # Coding features
        procedure_codes = [line.procedure_code for line in claim_lines if line.procedure_code]
        modifiers = [line.procedure_modifier for line in claim_lines if line.procedure_modifier]
        revenue_codes = [line.revenue_code for line in claim_lines if line.revenue_code]

        features.update(
            {
                "unique_procedure_codes": len(set(procedure_codes)),
                "modifier_count": len(modifiers),
                "unique_modifiers": len(set(modifiers)),
                "has_revenue_code": 1.0 if any(revenue_codes) else 0.0,
                "revenue_code_count": len([rc for rc in revenue_codes if rc]),
            }
        )

        # Financial features
        line_amounts = [line.charge_amount or 0.0 for line in claim_lines]
        if line_amounts:
            features.update(
                {
                    "total_line_charges": sum(line_amounts),
                    "max_line_charge": max(line_amounts),
                    "min_line_charge": min(line_amounts),
                    "avg_line_charge": sum(line_amounts) / len(line_amounts),
                    "median_line_charge": sorted(line_amounts)[len(line_amounts) // 2] if line_amounts else 0.0,
                    "std_line_charge": float(np.std(line_amounts)) if len(line_amounts) > 1 else 0.0,
                }
            )
        else:
            features.update(
                {
                    "total_line_charges": 0.0,
                    "max_line_charge": 0.0,
                    "min_line_charge": 0.0,
                    "avg_line_charge": 0.0,
                    "median_line_charge": 0.0,
                    "std_line_charge": 0.0,
                }
            )

        # Provider features
        features.update(
            {
                "has_attending_provider": 1.0 if claim.attending_provider_npi else 0.0,
                "has_operating_provider": 1.0 if claim.operating_provider_npi else 0.0,
                "has_referring_provider": 1.0 if claim.referring_provider_npi else 0.0,
                "provider_count": sum([
                    1 if claim.attending_provider_npi else 0,
                    1 if claim.operating_provider_npi else 0,
                    1 if claim.referring_provider_npi else 0,
                ]),
            }
        )

        # Date features (temporal patterns)
        if claim.service_date:
            features["service_date_day_of_week"] = claim.service_date.weekday()
            features["service_date_month"] = claim.service_date.month
            features["service_date_quarter"] = (claim.service_date.month - 1) // 3 + 1
            features["service_date_is_weekend"] = 1.0 if claim.service_date.weekday() >= 5 else 0.0
        else:
            features["service_date_day_of_week"] = 0
            features["service_date_month"] = 0
            features["service_date_quarter"] = 0
            features["service_date_is_weekend"] = 0.0

        # Claim age (days since creation)
        if claim.created_at:
            days_since_creation = (datetime.now() - claim.created_at).days
            features["claim_age_days"] = float(days_since_creation)
        else:
            features["claim_age_days"] = 0.0

        # Interaction features (combinations that might be predictive)
        features["charge_per_line"] = (
            features["total_charge_amount"] / features["claim_line_count"]
            if features["claim_line_count"] > 0
            else 0.0
        )
        features["diagnosis_per_line"] = (
            features["diagnosis_count"] / features["claim_line_count"]
            if features["claim_line_count"] > 0
            else 0.0
        )

        # Historical features (if requested)
        if include_historical:
            try:
                historical_stats = self.get_historical_statistics(claim, lookback_days=90)
                features.update(historical_stats)
            except Exception as e:
                logger.warning("Failed to extract historical features", claim_id=claim.id, error=str(e))
                # Add placeholder historical features
                features.update(
                    {
                        "historical_payer_denial_rate": 0.0,
                        "historical_provider_denial_rate": 0.0,
                        "historical_diagnosis_denial_rate": 0.0,
                        "historical_avg_payment_rate": 0.0,
                    }
                )

        return features

    def _extract_outcome_labels(self, remittance: Remittance, episode: ClaimEpisode) -> Dict:
        """Extract outcome labels from remittance."""
        denial_reasons = remittance.denial_reasons or []
        adjustment_reasons = remittance.adjustment_reasons or []

        # Calculate denial rate (0.0 to 1.0)
        # Optimize: Use any() with generator expression for better performance
        has_denial = any(denial_reasons) if denial_reasons else False
        denial_rate = 1.0 if has_denial else 0.0

        # Calculate payment rate (0.0 to 1.0)
        claim_charge = episode.claim.total_charge_amount or 0.0
        payment_amount = episode.payment_amount or remittance.payment_amount or 0.0
        payment_rate = (
            payment_amount / claim_charge if claim_charge > 0 else 0.0
        )

        # Binary classification target: denied (1) or paid (0)
        is_denied = 1 if has_denial else 0

        return {
            "denial_rate": denial_rate,
            "payment_rate": payment_rate,
            "is_denied": is_denied,
            "denial_count": len(denial_reasons),
            "adjustment_count": len(adjustment_reasons),
            "payment_amount": payment_amount,
        }

    def get_historical_statistics(
        self, claim: Claim, lookback_days: int = 90
    ) -> Dict[str, float]:
        """
        Get historical statistics for a claim (for feature extraction).
        
        Args:
            claim: The claim to get historical statistics for
            lookback_days: Number of days to look back for historical data (default: 90)
        
        Returns:
            Dictionary with historical statistics (all values are floats between 0.0 and 1.0):
            - historical_payer_denial_rate: Proportion of claims denied for this payer (0.0-1.0)
            - historical_provider_denial_rate: Proportion of claims denied for this provider (0.0-1.0)
            - historical_diagnosis_denial_rate: Proportion of claims denied for this diagnosis (0.0-1.0)
            - historical_avg_payment_rate: Average payment rate (payment/charge) for similar claims (0.0-1.0)
            
            All rates are proportions (0.0 = 0%, 1.0 = 100%), not percentages.
        """
        cutoff_date = claim.created_at - timedelta(days=lookback_days)

        # Historical denial rate for payer
        payer_denial_rate = self._calculate_payer_denial_rate(claim.payer_id, cutoff_date)

        # Historical denial rate for provider
        provider_denial_rate = self._calculate_provider_denial_rate(
            claim.provider_id, cutoff_date
        )

        # Historical denial rate for similar diagnosis codes
        diagnosis_denial_rate = self._calculate_diagnosis_denial_rate(
            claim.principal_diagnosis, cutoff_date
        )

        # Average payment rate for similar claims
        avg_payment_rate = self._calculate_avg_payment_rate(
            claim.payer_id, claim.provider_id, cutoff_date
        )

        return {
            "historical_payer_denial_rate": payer_denial_rate,
            "historical_provider_denial_rate": provider_denial_rate,
            "historical_diagnosis_denial_rate": diagnosis_denial_rate,
            "historical_avg_payment_rate": avg_payment_rate,
        }

    def _calculate_payer_denial_rate(self, payer_id: Optional[int], cutoff_date: datetime) -> float:
        """Calculate historical denial rate for a payer."""
        if not payer_id:
            return 0.0

        episodes = (
            self.db.query(ClaimEpisode)
            .join(Claim)
            .join(Remittance)
            .filter(
                and_(
                    Claim.payer_id == payer_id,
                    Claim.created_at >= cutoff_date,
                    ClaimEpisode.remittance_id.isnot(None),
                )
            )
            .all()
        )

        if not episodes:
            return 0.0

        denied_count = sum(
            1
            for ep in episodes
            if ep.remittance and ep.remittance.denial_reasons and any(ep.remittance.denial_reasons)
        )

        return denied_count / len(episodes)

    def _calculate_provider_denial_rate(
        self, provider_id: Optional[int], cutoff_date: datetime
    ) -> float:
        """Calculate historical denial rate for a provider."""
        if not provider_id:
            return 0.0

        episodes = (
            self.db.query(ClaimEpisode)
            .join(Claim)
            .join(Remittance)
            .filter(
                and_(
                    Claim.provider_id == provider_id,
                    Claim.created_at >= cutoff_date,
                    ClaimEpisode.remittance_id.isnot(None),
                )
            )
            .all()
        )

        if not episodes:
            return 0.0

        denied_count = sum(
            1
            for ep in episodes
            if ep.remittance and ep.remittance.denial_reasons and any(ep.remittance.denial_reasons)
        )

        return denied_count / len(episodes)

    def _calculate_diagnosis_denial_rate(
        self, diagnosis_code: Optional[str], cutoff_date: datetime
    ) -> float:
        """Calculate historical denial rate for a diagnosis code."""
        if not diagnosis_code:
            return 0.0

        # Optimized query: join claims, episodes, and remittances in a single query
        # This avoids N+1 queries by loading all related data at once
        # Use eager loading to avoid additional queries when accessing remittance data
        from sqlalchemy.orm import joinedload

        episodes = (
            self.db.query(ClaimEpisode)
            .join(Claim, ClaimEpisode.claim_id == Claim.id)
            .join(Remittance, ClaimEpisode.remittance_id == Remittance.id)
            .options(joinedload(ClaimEpisode.remittance))
            .filter(
                and_(
                    Claim.created_at >= cutoff_date,
                    Claim.principal_diagnosis == diagnosis_code,
                    ClaimEpisode.remittance_id.isnot(None),
                )
            )
            .all()
        )

        if not episodes:
            return 0.0

        # Count denials: check if remittance has denial_reasons (non-null, non-empty array)
        denied_count = sum(
            1
            for ep in episodes
            if ep.remittance
            and ep.remittance.denial_reasons
            and any(ep.remittance.denial_reasons)
        )

        return float(denied_count) / float(len(episodes))

    def _calculate_avg_payment_rate(
        self,
        payer_id: Optional[int],
        provider_id: Optional[int],
        cutoff_date: datetime,
    ) -> float:
        """Calculate average payment rate for similar claims."""
        episodes = (
            self.db.query(ClaimEpisode)
            .join(Claim)
            .join(Remittance)
            .filter(
                and_(
                    Claim.created_at >= cutoff_date,
                    ClaimEpisode.remittance_id.isnot(None),
                )
            )
        )

        if payer_id:
            episodes = episodes.filter(Claim.payer_id == payer_id)
        if provider_id:
            episodes = episodes.filter(Claim.provider_id == provider_id)

        episodes = episodes.all()

        if not episodes:
            return 0.0

        payment_rates = []
        for ep in episodes:
            claim_charge = ep.claim.total_charge_amount or 0.0
            payment_amount = ep.payment_amount or (ep.remittance.payment_amount if ep.remittance else 0.0) or 0.0
            if claim_charge > 0:
                payment_rates.append(payment_amount / claim_charge)

        return sum(payment_rates) / len(payment_rates) if payment_rates else 0.0

    def _validate_data_quality(self, df: pd.DataFrame) -> None:
        """
        Validate data quality and log warnings for issues.
        
        Args:
            df: Training dataframe to validate
        """
        if df.empty:
            raise ValueError("Training dataset is empty")

        # Check for missing values
        missing_counts = df.isnull().sum()
        if missing_counts.sum() > 0:
            logger.warning(
                "Missing values found in training data",
                missing_counts=missing_counts[missing_counts > 0].to_dict(),
            )

        # Check for infinite values
        inf_counts = np.isinf(df.select_dtypes(include=[np.number])).sum()
        if inf_counts.sum() > 0:
            logger.warning(
                "Infinite values found in training data",
                inf_counts=inf_counts[inf_counts > 0].to_dict(),
            )

        # Check label distribution
        if "is_denied" in df.columns:
            denied_rate = df["is_denied"].mean()
            if denied_rate < 0.05 or denied_rate > 0.95:
                logger.warning(
                    "Highly imbalanced dataset",
                    denied_rate=denied_rate,
                    denied_count=(df["is_denied"] == 1).sum(),
                    total_count=len(df),
                )

        # Check for constant features (no variance)
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        constant_features = []
        for col in numeric_cols:
            if col not in ["claim_id", "is_denied", "denial_rate", "payment_rate"]:
                if df[col].nunique() <= 1:
                    constant_features.append(col)

        if constant_features:
            logger.warning(
                "Constant features found (no variance)",
                constant_features=constant_features,
            )

        # Check for highly correlated features
        if len(numeric_cols) > 1:
            corr_matrix = df[numeric_cols].corr().abs()
            high_corr_pairs = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i + 1, len(corr_matrix.columns)):
                    if corr_matrix.iloc[i, j] > 0.95:
                        high_corr_pairs.append(
                            (corr_matrix.columns[i], corr_matrix.columns[j], corr_matrix.iloc[i, j])
                        )

            if high_corr_pairs:
                logger.info(
                    "Highly correlated feature pairs found",
                    pairs=high_corr_pairs[:10],  # Log first 10
                )

        logger.info("Data quality validation complete", rows=len(df), columns=len(df.columns))

