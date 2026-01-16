"""Base adapter interface for external system integrations."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.database import Claim, Remittance
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BaseAdapter(ABC):
    """
    Base adapter interface for external system integrations.
    
    All adapters (EHR, clearinghouse, etc.) should inherit from this class
    and implement the required methods.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.
        
        Args:
            config: Configuration dictionary with connection details, credentials, etc.
        """
        self.config = config
        self.connected = False

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to external system.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from external system."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection to external system.
        
        Returns:
            True if connection is working, False otherwise
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class EHRAdapter(BaseAdapter):
    """
    Base adapter for Electronic Health Record (EHR) systems.
    
    Handles integration with EHR systems like Epic, Cerner, Allscripts, etc.
    """

    @abstractmethod
    def fetch_claims(
        self, start_date: datetime, end_date: datetime, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch claims from EHR system.
        
        Args:
            start_date: Start date for claim retrieval
            end_date: End date for claim retrieval
            filters: Optional filters (provider, patient, status, etc.)
            
        Returns:
            List of claim dictionaries in standard format
        """
        pass

    @abstractmethod
    def fetch_patient_info(self, patient_id: str) -> Dict[str, Any]:
        """
        Fetch patient information from EHR.
        
        Args:
            patient_id: Patient identifier in EHR system
            
        Returns:
            Dictionary with patient information
        """
        pass

    @abstractmethod
    def submit_claim(self, claim: Claim) -> Dict[str, Any]:
        """
        Submit claim to EHR system (if supported).
        
        Args:
            claim: Claim object to submit
            
        Returns:
            Dictionary with submission result (status, reference_id, etc.)
        """
        pass

    def transform_to_edi(self, claim_data: Dict[str, Any]) -> str:
        """
        Transform EHR claim data to EDI 837 format.
        
        Args:
            claim_data: Claim data from EHR
            
        Returns:
            EDI 837 formatted string
        """
        # Default implementation - can be overridden by specific adapters
        logger.warning("Default EDI transformation used. Consider implementing adapter-specific transformation.")
        # This would call the EDI transformer service
        from app.services.edi.transformer import EDITransformer

        # Transform claim_data to Claim model, then to EDI
        # Implementation depends on EHR-specific data format
        raise NotImplementedError("EHR-specific transformation required")


class ClearinghouseAdapter(BaseAdapter):
    """
    Base adapter for clearinghouse integrations.
    
    Handles integration with clearinghouses like Change Healthcare, Availity, Office Ally, etc.
    """

    @abstractmethod
    def submit_claim(self, claim: Claim) -> Dict[str, Any]:
        """
        Submit claim to clearinghouse.
        
        Args:
            claim: Claim object to submit
            
        Returns:
            Dictionary with submission result (status, tracking_id, etc.)
        """
        pass

    @abstractmethod
    def fetch_remittance(self, claim_id: str, remittance_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch remittance advice from clearinghouse.
        
        Args:
            claim_id: Claim identifier
            remittance_id: Optional remittance identifier
            
        Returns:
            Dictionary with remittance data
        """
        pass

    @abstractmethod
    def get_claim_status(self, claim_id: str) -> Dict[str, Any]:
        """
        Get claim status from clearinghouse.
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            Dictionary with claim status information
        """
        pass

    def transform_from_edi(self, edi_content: str) -> Dict[str, Any]:
        """
        Transform EDI 835 remittance to standard format.
        
        Args:
            edi_content: EDI 835 formatted string
            
        Returns:
            Dictionary with remittance data
        """
        # Default implementation uses existing EDI parser
        from app.services.edi.parser import EDIParser

        parser = EDIParser()
        result = parser.parse(edi_content, "remittance_835.edi")
        return result


class EpicAdapter(EHRAdapter):
    """Adapter for Epic EHR system."""

    def connect(self) -> bool:
        """Connect to Epic system."""
        # Epic uses FHIR API or MyChart API
        # Implementation would use OAuth2 authentication
        logger.info("Connecting to Epic EHR system")
        # Placeholder implementation
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from Epic."""
        self.connected = False

    def test_connection(self) -> bool:
        """Test Epic connection."""
        return self.connected

    def fetch_claims(
        self, start_date: datetime, end_date: datetime, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch claims from Epic."""
        # Epic FHIR API implementation
        # Would use requests/httpx to call Epic FHIR endpoints
        logger.info("Fetching claims from Epic", start_date=start_date, end_date=end_date)
        return []

    def fetch_patient_info(self, patient_id: str) -> Dict[str, Any]:
        """Fetch patient info from Epic."""
        logger.info("Fetching patient info from Epic", patient_id=patient_id)
        return {}

    def submit_claim(self, claim: Claim) -> Dict[str, Any]:
        """Submit claim to Epic."""
        logger.info("Submitting claim to Epic", claim_id=claim.id)
        return {"status": "submitted", "reference_id": f"EPIC-{claim.id}"}


class ChangeHealthcareAdapter(ClearinghouseAdapter):
    """Adapter for Change Healthcare clearinghouse."""

    def connect(self) -> bool:
        """Connect to Change Healthcare."""
        # Change Healthcare uses REST API with API keys
        logger.info("Connecting to Change Healthcare")
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from Change Healthcare."""
        self.connected = False

    def test_connection(self) -> bool:
        """Test Change Healthcare connection."""
        return self.connected

    def submit_claim(self, claim: Claim) -> Dict[str, Any]:
        """Submit claim to Change Healthcare."""
        logger.info("Submitting claim to Change Healthcare", claim_id=claim.id)
        # Would transform claim to X12 837 and submit via API
        return {"status": "submitted", "tracking_id": f"CHC-{claim.id}"}

    def fetch_remittance(self, claim_id: str, remittance_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch remittance from Change Healthcare."""
        logger.info("Fetching remittance from Change Healthcare", claim_id=claim_id)
        return {}

    def get_claim_status(self, claim_id: str) -> Dict[str, Any]:
        """Get claim status from Change Healthcare."""
        logger.info("Getting claim status from Change Healthcare", claim_id=claim_id)
        return {"status": "processing", "claim_id": claim_id}

