"""Format profile management for different 837 file formats."""
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from app.models.database import PracticeConfig
from app.utils.logger import get_logger
import json

logger = get_logger(__name__)


class FormatProfile:
    """Manages format profiles for different practices/ASCs."""

    def __init__(self, profile_data: Dict):
        self.profile_data = profile_data
        self.practice_id = profile_data.get("practice_id")
        self.format_name = profile_data.get("format_name", "default")
        self.version = profile_data.get("version")
        self.segment_expectations = profile_data.get("segment_expectations", {})
        self.element_counts = profile_data.get("element_counts", {})
        self.date_formats = profile_data.get("date_formats", {})
        self.diagnosis_qualifiers = profile_data.get("diagnosis_qualifiers", {})
        self.facility_codes = profile_data.get("facility_codes", {})

    def to_dict(self) -> Dict:
        """Convert profile to dictionary."""
        return {
            "practice_id": self.practice_id,
            "format_name": self.format_name,
            "version": self.version,
            "segment_expectations": self.segment_expectations,
            "element_counts": self.element_counts,
            "date_formats": self.date_formats,
            "diagnosis_qualifiers": self.diagnosis_qualifiers,
            "facility_codes": self.facility_codes,
        }

    @classmethod
    def from_practice_config(cls, practice_config: PracticeConfig) -> Optional["FormatProfile"]:
        """Create format profile from PracticeConfig."""
        if not practice_config.segment_expectations:
            return None
        
        return cls({
            "practice_id": practice_config.practice_id,
            "format_name": practice_config.practice_name,
            "segment_expectations": practice_config.segment_expectations,
        })

    def save_to_practice_config(self, db: Session, practice_id: str) -> None:
        """Save format profile to PracticeConfig."""
        practice_config = (
            db.query(PracticeConfig)
            .filter(PracticeConfig.practice_id == practice_id)
            .first()
        )
        
        if not practice_config:
            practice_config = PracticeConfig(
                practice_id=practice_id,
                practice_name=self.format_name,
                segment_expectations=self.segment_expectations,
            )
            db.add(practice_config)
        else:
            # Update existing config
            if not practice_config.segment_expectations:
                practice_config.segment_expectations = {}
            
            # Merge format profile data
            practice_config.segment_expectations.update({
                "format_profile": self.to_dict(),
            })
        
        db.commit()
        logger.info("Format profile saved", practice_id=practice_id, format_name=self.format_name)


class FormatProfileManager:
    """Manages multiple format profiles."""

    def __init__(self, db: Session):
        self.db = db
        self.profiles: Dict[str, FormatProfile] = {}

    def load_profile(self, practice_id: str) -> Optional[FormatProfile]:
        """Load format profile for a practice."""
        if practice_id in self.profiles:
            return self.profiles[practice_id]
        
        practice_config = (
            self.db.query(PracticeConfig)
            .filter(PracticeConfig.practice_id == practice_id)
            .first()
        )
        
        if practice_config:
            profile = FormatProfile.from_practice_config(practice_config)
            if profile:
                self.profiles[practice_id] = profile
                return profile
        
        return None

    def create_profile_from_analysis(
        self, practice_id: str, format_name: str, analysis: Dict
    ) -> FormatProfile:
        """Create format profile from format analysis."""
        profile_data = {
            "practice_id": practice_id,
            "format_name": format_name,
            "version": analysis.get("version"),
            "segment_expectations": {
                "critical": ["ISA", "GS", "ST", "CLM"],
                "important": list(analysis.get("segment_frequency", {}).keys())[:10],
                "optional": [],
            },
            "element_counts": analysis.get("element_counts", {}),
            "date_formats": analysis.get("date_formats", {}),
            "diagnosis_qualifiers": analysis.get("diagnosis_qualifiers", {}),
            "facility_codes": analysis.get("facility_codes", {}),
        }
        
        profile = FormatProfile(profile_data)
        profile.save_to_practice_config(self.db, practice_id)
        self.profiles[practice_id] = profile
        
        logger.info(
            "Format profile created",
            practice_id=practice_id,
            format_name=format_name,
        )
        
        return profile

    def get_or_create_profile(
        self, practice_id: str, format_name: str, analysis: Optional[Dict] = None
    ) -> FormatProfile:
        """Get existing profile or create new one from analysis."""
        profile = self.load_profile(practice_id)
        
        if profile:
            return profile
        
        if analysis:
            return self.create_profile_from_analysis(practice_id, format_name, analysis)
        
        # Return default profile
        return FormatProfile({
            "practice_id": practice_id,
            "format_name": "default",
            "segment_expectations": {
                "critical": ["ISA", "GS", "ST", "CLM"],
                "important": ["SBR", "NM1", "DTP", "HI"],
                "optional": ["PRV", "REF", "N4", "LX", "SV2"],
            },
        })

