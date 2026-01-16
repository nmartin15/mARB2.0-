"""Feature extraction for ML models."""
from typing import Dict, List, Optional
import numpy as np
from datetime import datetime

from app.models.database import Claim, ClaimLine, ClaimEpisode
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FeatureExtractor:
    """Extract features from claims for ML model training and prediction."""

    def extract_features(
        self, claim: Claim, include_historical: bool = True, db_session: Optional[object] = None
    ) -> np.ndarray:
        """
        Extract features from a claim for ML model.
        
        Args:
            claim: The claim to extract features from
            include_historical: Whether to include historical features (requires DB queries)
            db_session: Optional database session for historical feature extraction
            
        Returns:
            numpy array of features
        """
        features = []

        # Basic claim features
        features.extend(self._extract_basic_features(claim))

        # Coding features
        features.extend(self._extract_coding_features(claim))

        # Financial features
        features.extend(self._extract_financial_features(claim))

        # Provider features
        features.extend(self._extract_provider_features(claim))

        # Temporal features (date-based patterns)
        features.extend(self._extract_temporal_features(claim))
        
        # Historical features (if requested and available)
        if include_historical:
            features.extend(self._extract_historical_features(claim, db_session=db_session))

        return np.array(features, dtype=np.float32)

    def _extract_basic_features(self, claim: Claim) -> List[float]:
        """Extract basic claim features."""
        claim_lines = claim.claim_lines or []
        diagnosis_codes = claim.diagnosis_codes or []
        line_count = len(claim_lines)
        
        # Interaction features
        charge_per_line = (
            (claim.total_charge_amount or 0.0) / line_count
            if line_count > 0
            else 0.0
        )
        diagnosis_per_line = (
            len(diagnosis_codes) / line_count
            if line_count > 0
            else 0.0
        )
        
        # Claim age (days since creation)
        from datetime import datetime
        claim_age_days = 0.0
        if claim.created_at:
            claim_age_days = float((datetime.now() - claim.created_at).days)
        
        return [
            claim.total_charge_amount or 0.0,
            1.0 if claim.is_incomplete else 0.0,
            1.0 if claim.principal_diagnosis else 0.0,
            len(diagnosis_codes),
            line_count,
            charge_per_line,  # Charge per line
            diagnosis_per_line,  # Diagnosis per line
            claim_age_days,  # Claim age in days
        ]

    def _extract_coding_features(self, claim: Claim) -> List[float]:
        """Extract coding-related features."""
        claim_lines = claim.claim_lines or []
        
        procedure_codes = [line.procedure_code for line in claim_lines if line.procedure_code]
        modifiers = [line.procedure_modifier for line in claim_lines if line.procedure_modifier]
        revenue_codes = [line.revenue_code for line in claim_lines if line.revenue_code]
        
        return [
            len(set(procedure_codes)),  # Unique procedure codes
            len(modifiers),  # Total modifiers
            len(set(modifiers)),  # Unique modifiers
            1.0 if any(revenue_codes) else 0.0,  # Has revenue code
            len([rc for rc in revenue_codes if rc]),  # Revenue code count
        ]

    def _extract_financial_features(self, claim: Claim) -> List[float]:
        """Extract financial features."""
        claim_lines = claim.claim_lines or []
        
        line_amounts = [line.charge_amount or 0.0 for line in claim_lines]
        
        if line_amounts:
            sorted_amounts = sorted(line_amounts)
            median = sorted_amounts[len(sorted_amounts) // 2] if sorted_amounts else 0.0
            return [
                sum(line_amounts),  # Total line charges
                max(line_amounts),  # Max line charge
                min(line_amounts),  # Min line charge
                np.mean(line_amounts),  # Average line charge
                median,  # Median line charge
                np.std(line_amounts) if len(line_amounts) > 1 else 0.0,  # Std dev of charges
            ]
        else:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def _extract_provider_features(self, claim: Claim) -> List[float]:
        """Extract provider-related features."""
        provider_count = sum([
            1 if claim.attending_provider_npi else 0,
            1 if claim.operating_provider_npi else 0,
            1 if claim.referring_provider_npi else 0,
        ])
        
        return [
            1.0 if claim.attending_provider_npi else 0.0,
            1.0 if claim.operating_provider_npi else 0.0,
            1.0 if claim.referring_provider_npi else 0.0,
            1.0 if claim.provider_id else 0.0,
            float(provider_count),  # Total provider count
        ]

    def _extract_temporal_features(self, claim: Claim) -> List[float]:
        """Extract temporal/date-based features."""
        if claim.service_date:
            return [
                float(claim.service_date.weekday()),  # Day of week (0=Monday, 6=Sunday)
                float(claim.service_date.month),  # Month (1-12)
                float((claim.service_date.month - 1) // 3 + 1),  # Quarter (1-4)
                1.0 if claim.service_date.weekday() >= 5 else 0.0,  # Is weekend
            ]
        else:
            return [0.0, 0.0, 0.0, 0.0]

    def _extract_historical_features(self, claim: Claim, db_session: Optional[object] = None) -> List[float]:
        """
        Extract historical features based on past episodes.
        
        Args:
            claim: The claim to extract features from
            db_session: Optional database session for historical queries
            
        Note: This requires database queries, so it's optional.
        """
        if not db_session:
            # Return placeholders if no DB session provided
            return [0.0, 0.0, 0.0, 0.0]

        try:
            # Import here to avoid circular dependency
            from ml.services.data_collector import DataCollector

            collector = DataCollector(db_session)
            stats = collector.get_historical_statistics(claim, lookback_days=90)

            return [
                stats.get("historical_payer_denial_rate", 0.0),
                stats.get("historical_provider_denial_rate", 0.0),
                stats.get("historical_diagnosis_denial_rate", 0.0),
                stats.get("historical_avg_payment_rate", 0.0),
            ]
        except Exception as e:
            logger.warning("Failed to extract historical features", error=str(e))
            # Return placeholders if historical data unavailable
            return [0.0, 0.0, 0.0, 0.0]

    def extract_features_dict(
        self, claim: Claim, include_historical: bool = False, db_session: Optional[object] = None
    ) -> Dict[str, float]:
        """
        Extract features as a dictionary for easier inspection.
        
        Args:
            claim: The claim to extract features from
            include_historical: Whether to include historical features
            db_session: Optional database session for historical feature extraction
            
        Returns:
            Dictionary mapping feature names to values
        """
        features = self.extract_features(claim, include_historical=include_historical, db_session=db_session)
        
        feature_names = [
            "total_charge_amount",
            "is_incomplete",
            "has_principal_diagnosis",
            "diagnosis_count",
            "claim_line_count",
            "charge_per_line",
            "diagnosis_per_line",
            "claim_age_days",
            "unique_procedure_codes",
            "modifier_count",
            "unique_modifiers",
            "has_revenue_code",
            "revenue_code_count",
            "total_line_charges",
            "max_line_charge",
            "min_line_charge",
            "avg_line_charge",
            "median_line_charge",
            "std_line_charge",
            "has_attending_provider",
            "has_operating_provider",
            "has_referring_provider",
            "has_provider",
            "provider_count",
            "service_date_day_of_week",
            "service_date_month",
            "service_date_quarter",
            "service_date_is_weekend",
        ]
        
        if include_historical:
            feature_names.extend([
                "historical_payer_denial_rate",
                "historical_provider_denial_rate",
                "historical_diagnosis_denial_rate",
                "historical_avg_payment_rate",
            ])
        
        return dict(zip(feature_names, features.tolist()))
