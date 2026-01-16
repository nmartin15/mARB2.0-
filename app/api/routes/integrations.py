"""API routes for external system integrations."""
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.config.database import get_db
from app.services.integrations.base_adapter import (
    BaseAdapter,
    EHRAdapter,
    ClearinghouseAdapter,
    EpicAdapter,
    ChangeHealthcareAdapter,
)
from app.utils.logger import get_logger
from app.utils.errors import AppError, NotFoundError

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


class IntegrationConfig(BaseModel):
    """Configuration for integration adapter."""

    adapter_type: str  # "ehr" or "clearinghouse"
    adapter_name: str  # "epic", "cerner", "change_healthcare", etc.
    config: Dict[str, str]  # Connection details, credentials, etc.


class ConnectionTestResponse(BaseModel):
    """Response for connection test."""

    connected: bool
    message: str
    adapter_name: str


@router.post("/connect", response_model=ConnectionTestResponse)
async def connect_integration(
    integration_config: IntegrationConfig, db: Session = Depends(get_db)
) -> ConnectionTestResponse:
    """
    Connect to an external system integration.
    
    Args:
        integration_config: Configuration for the integration
        db: Database session
        
    Returns:
        Connection test response
    """
    try:
        adapter = _create_adapter(integration_config.adapter_type, integration_config.adapter_name, integration_config.config)
        
        connected = adapter.connect()
        message = "Connected successfully" if connected else "Connection failed"
        
        return ConnectionTestResponse(
            connected=connected,
            message=message,
            adapter_name=integration_config.adapter_name,
        )
    except Exception as e:
        logger.error("Integration connection failed", error=str(e), adapter=integration_config.adapter_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to {integration_config.adapter_name}: {str(e)}",
        )


@router.get("/test/{adapter_name}")
async def test_integration(
    adapter_name: str,
    adapter_type: str = "ehr",
    db: Session = Depends(get_db),
) -> ConnectionTestResponse:
    """
    Test connection to an integration.
    
    Args:
        adapter_name: Name of the adapter to test
        adapter_type: Type of adapter ("ehr" or "clearinghouse")
        db: Database session
        
    Returns:
        Connection test response
    """
    try:
        # In a real implementation, you'd load config from database
        config = {"api_key": "test", "base_url": "https://api.example.com"}
        adapter = _create_adapter(adapter_type, adapter_name, config)
        
        connected = adapter.test_connection()
        message = "Connection test passed" if connected else "Connection test failed"
        
        return ConnectionTestResponse(
            connected=connected,
            message=message,
            adapter_name=adapter_name,
        )
    except Exception as e:
        logger.error("Integration test failed", error=str(e), adapter=adapter_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test {adapter_name}: {str(e)}",
        )


@router.post("/ehr/fetch-claims")
async def fetch_ehr_claims(
    adapter_name: str,
    start_date: str,
    end_date: str,
    filters: Optional[Dict] = None,
    db: Session = Depends(get_db),
) -> Dict:
    """
    Fetch claims from an EHR system.
    
    Args:
        adapter_name: Name of the EHR adapter
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        filters: Optional filters
        db: Database session
        
    Returns:
        List of claims fetched from EHR
    """
    try:
        from datetime import datetime
        
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        config = {"api_key": "test", "base_url": "https://api.example.com"}
        adapter = _create_adapter("ehr", adapter_name, config)
        
        if not isinstance(adapter, EHRAdapter):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{adapter_name} is not an EHR adapter",
            )
        
        claims = adapter.fetch_claims(start, end, filters)
        
        return {"claims": claims, "count": len(claims)}
    except Exception as e:
        logger.error("Failed to fetch EHR claims", error=str(e), adapter=adapter_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch claims: {str(e)}",
        )


@router.post("/clearinghouse/submit/{claim_id}")
async def submit_claim_to_clearinghouse(
    claim_id: int,
    adapter_name: str,
    db: Session = Depends(get_db),
) -> Dict:
    """
    Submit a claim to a clearinghouse.
    
    Args:
        claim_id: ID of the claim to submit
        adapter_name: Name of the clearinghouse adapter
        db: Database session
        
    Returns:
        Submission result
    """
    try:
        from app.models.database import Claim
        
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            raise NotFoundError("Claim", str(claim_id))
        
        config = {"api_key": "test", "base_url": "https://api.example.com"}
        adapter = _create_adapter("clearinghouse", adapter_name, config)
        
        if not isinstance(adapter, ClearinghouseAdapter):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{adapter_name} is not a clearinghouse adapter",
            )
        
        result = adapter.submit_claim(claim)
        
        return result
    except NotFoundError:
        raise
    except Exception as e:
        logger.error("Failed to submit claim to clearinghouse", error=str(e), claim_id=claim_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit claim: {str(e)}",
        )


def _create_adapter(adapter_type: str, adapter_name: str, config: Dict) -> BaseAdapter:
    """
    Factory function to create adapter instances.
    
    Args:
        adapter_type: Type of adapter ("ehr" or "clearinghouse")
        adapter_name: Name of the specific adapter
        config: Configuration dictionary
        
    Returns:
        Adapter instance
    """
    adapter_map = {
        ("ehr", "epic"): EpicAdapter,
        ("clearinghouse", "change_healthcare"): ChangeHealthcareAdapter,
    }
    
    key = (adapter_type, adapter_name.lower())
    adapter_class = adapter_map.get(key)
    
    if not adapter_class:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown adapter: {adapter_type}/{adapter_name}",
        )
    
    return adapter_class(config)

