"""Transform parsed EDI data to database models."""
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.database import (
    Claim,
    ClaimLine,
    ClaimStatus,
    ParserLog,
    Payer,
    Provider,
    Remittance,
    RemittanceStatus,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """Convert datetime and other non-serializable objects to strings. Optimized for performance."""
    # Optimize: check most common types first
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        # Optimize: use dict comprehension for better performance
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    else:
        return obj


class EDITransformer:
    """Transform parsed EDI data to database models."""

    def __init__(self, db: Session, practice_id: str = None, filename: str = None):
        self.db = db
        self.practice_id = practice_id
        self.filename = filename
        # Cache for providers and payers to reduce database queries
        self._provider_cache: Dict[str, Provider] = {}
        self._payer_cache: Dict[str, Payer] = {}

    def preload_providers_and_payers(self, provider_npis: List[str], payer_ids: List[str]) -> None:
        """
        Pre-load providers and payers in batch to reduce database queries.

        This should be called before processing multiple claims/remittances
        to minimize database round trips.
        
        Args:
            provider_npis: List of provider NPI numbers to preload
            payer_ids: List of payer IDs to preload
        """
        # Batch load existing providers
        if provider_npis:
            existing_providers = self.db.query(Provider).filter(
                Provider.npi.in_(provider_npis)
            ).all()
            for provider in existing_providers:
                self._provider_cache[provider.npi] = provider

        # Batch load existing payers
        if payer_ids:
            existing_payers = self.db.query(Payer).filter(
                Payer.payer_id.in_(payer_ids)
            ).all()
            for payer in existing_payers:
                self._payer_cache[payer.payer_id] = payer

    def transform_837_claim(self, parsed_data: Dict) -> Claim:
        """
        Transform parsed 837 claim data to Claim model.
        
        Args:
            parsed_data: Dictionary containing parsed claim data from EDI parser
            
        Returns:
            Claim model instance with associated claim lines and parsing logs
        """
        claim_data = parsed_data

        # Create or get provider
        provider = None
        attending_provider_npi = claim_data.get("attending_provider_npi")
        if attending_provider_npi:
            try:
                provider = self._get_or_create_provider(attending_provider_npi)
            except ValueError as e:
                logger.warning(
                    "Failed to get or create provider",
                    npi=attending_provider_npi,
                    error=str(e),
                    filename=self.filename,
                    practice_id=self.practice_id,
                )
                # Continue without provider - claim will be marked as incomplete
                claim_data.setdefault("warnings", []).append(
                    f"Invalid or missing provider NPI: {attending_provider_npi}"
                )

        # Create or get payer
        payer = None
        payer_id = claim_data.get("payer_id")
        if payer_id:
            try:
                payer = self._get_or_create_payer(payer_id, claim_data.get("payer_name"))
            except ValueError as e:
                logger.warning(
                    "Failed to get or create payer",
                    payer_id=payer_id,
                    error=str(e),
                    filename=self.filename,
                    practice_id=self.practice_id,
                )
                # Continue without payer - claim will be marked as incomplete
                claim_data.setdefault("warnings", []).append(
                    f"Invalid or missing payer ID: {payer_id}"
                )

        # Create claim
        claim = Claim(
            claim_control_number=claim_data.get("claim_control_number") or f"TEMP_{datetime.now().timestamp()}",
            patient_control_number=claim_data.get("patient_control_number"),
            provider_id=provider.id if provider else None,
            payer_id=payer.id if payer else None,
            total_charge_amount=claim_data.get("total_charge_amount"),
            facility_type_code=claim_data.get("facility_type_code"),
            claim_frequency_type=claim_data.get("claim_frequency_type"),
            assignment_code=claim_data.get("assignment_code"),
            statement_date=claim_data.get("statement_date"),
            admission_date=claim_data.get("admission_date"),
            discharge_date=claim_data.get("discharge_date"),
            service_date=claim_data.get("service_date"),
            diagnosis_codes=claim_data.get("diagnosis_codes"),
            principal_diagnosis=claim_data.get("principal_diagnosis"),
            raw_edi_data=str(claim_data.get("raw_block", [])),
            parsed_segments=_make_json_serializable(claim_data),
            status=ClaimStatus.PENDING,
            is_incomplete=claim_data.get("is_incomplete", False),
            parsing_warnings=claim_data.get("warnings", []),
            practice_id=self.practice_id,
        )

        # Create claim lines
        lines_data = claim_data.get("lines", [])
        for line_data in lines_data:
            claim_line = ClaimLine(
                claim=claim,
                line_number=line_data.get("line_number"),
                revenue_code=line_data.get("revenue_code"),
                procedure_code=line_data.get("procedure_code"),
                procedure_modifier=line_data.get("procedure_modifier"),
                charge_amount=line_data.get("charge_amount"),
                unit_count=line_data.get("unit_count"),
                unit_type=line_data.get("unit_type"),
                service_date=line_data.get("service_date"),
                raw_segment_data=line_data,
            )
            claim.claim_lines.append(claim_line)

        # Log parsing warnings (batch add for better performance)
        warnings_list = claim_data.get("warnings")
        if warnings_list:
            # Optimize: use bulk_insert_mappings for better performance (bypasses ORM overhead)
            parser_log_mappings = [
                {
                    "file_name": self.filename or "unknown",
                    "file_type": "837",
                    "log_level": "warning",
                    "segment_type": "CLM",
                    "issue_type": "parsing_warning",
                    "message": warning,
                    "claim_control_number": claim.claim_control_number,
                    "practice_id": self.practice_id,
                }
                for warning in warnings_list
            ]
            # Batch insert all logs at once (more efficient than bulk_save_objects)
            self.db.bulk_insert_mappings(ParserLog, parser_log_mappings)

        return claim

    def _get_or_create_provider(self, npi: str) -> Provider:
        """
        Get or create provider by NPI. Optimized with caching.
        
        Args:
            npi: Provider NPI number
            
        Returns:
            Provider model instance (existing or newly created)
            
        Raises:
            ValueError: If NPI is None, empty, or invalid format
        """
        # Validate NPI input
        if npi is None:
            logger.warning(
                "Missing provider NPI",
                filename=self.filename,
                practice_id=self.practice_id,
            )
            raise ValueError("Provider NPI is required but was not provided")
        
        # Convert to string and strip whitespace
        npi = str(npi).strip() if npi else ""
        
        if not npi:
            logger.warning(
                "Empty provider NPI",
                filename=self.filename,
                practice_id=self.practice_id,
            )
            raise ValueError("Provider NPI cannot be empty")
        
        # Validate NPI format (should be 10 digits)
        if not npi.isdigit() or len(npi) != 10:
            logger.warning(
                "Invalid provider NPI format",
                npi=npi,
                filename=self.filename,
                practice_id=self.practice_id,
            )
            raise ValueError(f"Invalid provider NPI format: expected 10 digits, got '{npi}'")
        
        # Check cache first
        if npi in self._provider_cache:
            return self._provider_cache[npi]

        # Query database
        provider = self.db.query(Provider).filter(Provider.npi == npi).first()
        if not provider:
            provider = Provider(npi=npi, name="Unknown")  # Name would come from NM1 segment
            self.db.add(provider)
            self.db.flush()

        # Cache for future use
        self._provider_cache[npi] = provider
        return provider

    def _get_or_create_payer(self, payer_id: str, payer_name: str = None) -> Payer:
        """
        Get or create payer by ID. Optimized with caching.
        
        Args:
            payer_id: Payer identifier
            payer_name: Optional payer name (used when creating new payer)
            
        Returns:
            Payer model instance (existing or newly created)
            
        Raises:
            ValueError: If payer_id is None or empty
        """
        # Validate payer_id input
        if payer_id is None:
            logger.warning(
                "Missing payer ID",
                filename=self.filename,
                practice_id=self.practice_id,
            )
            raise ValueError("Payer ID is required but was not provided")
        
        # Convert to string and strip whitespace
        payer_id = str(payer_id).strip() if payer_id else ""
        
        if not payer_id:
            logger.warning(
                "Empty payer ID",
                filename=self.filename,
                practice_id=self.practice_id,
            )
            raise ValueError("Payer ID cannot be empty")
        
        # Check cache first
        if payer_id in self._payer_cache:
            return self._payer_cache[payer_id]

        # Query database
        payer = self.db.query(Payer).filter(Payer.payer_id == payer_id).first()
        if not payer:
            payer = Payer(payer_id=payer_id, name=payer_name or "Unknown")
            self.db.add(payer)
            self.db.flush()

        # Cache for future use
        self._payer_cache[payer_id] = payer
        return payer

    def transform_835_remittance(self, parsed_data: Dict, bpr_data: Dict = None) -> Remittance:
        """
        Transform parsed 835 remittance data to Remittance model.

        Args:
            parsed_data: Parsed remittance block data from parser
            bpr_data: BPR segment data (payment header information)

        Returns:
            Remittance model instance
        """
        # Extract payer information
        payer = None
        payer_name = None

        # Try to get payer from N1*PR segment or envelope
        if parsed_data.get("payer"):
            payer_name = parsed_data["payer"].get("name")
            payer_id = parsed_data["payer"].get("payer_id")
        else:
            # Try to extract from references or use default
            payer_id = None

        # Get or create payer
        if payer_id:
            try:
                payer = self._get_or_create_payer(payer_id, payer_name)
            except ValueError as e:
                logger.warning(
                    "Failed to get or create payer",
                    payer_id=payer_id,
                    error=str(e),
                    filename=self.filename,
                    practice_id=self.practice_id,
                )
                # Continue without payer - remittance will be marked as incomplete
                parsed_data.setdefault("warnings", []).append(
                    f"Invalid or missing payer ID: {payer_id}"
                )
        elif payer_name:
            # Use payer name as ID if no ID provided
            try:
                payer = self._get_or_create_payer(payer_name, payer_name)
            except ValueError as e:
                logger.warning(
                    "Failed to get or create payer using name as ID",
                    payer_name=payer_name,
                    error=str(e),
                    filename=self.filename,
                    practice_id=self.practice_id,
                )
                # Continue without payer - remittance will be marked as incomplete
                parsed_data.setdefault("warnings", []).append(
                    f"Invalid payer name used as ID: {payer_name}"
                )

        # Parse payment date from BPR or service date
        payment_date = None
        if bpr_data and bpr_data.get("effective_payment_date"):
            payment_date = self._parse_edi_date(bpr_data["effective_payment_date"])
        elif parsed_data.get("service_date"):
            payment_date = self._parse_edi_date(parsed_data["service_date"])

        # Generate remittance control number
        claim_control_number = parsed_data.get("claim_control_number") or parsed_data.get("payer_claim_control_number")
        remittance_control_number = (
            f"REM_{claim_control_number}" if claim_control_number
            else f"REM_{datetime.now().timestamp()}"
        )

        # Extract adjustment codes and map to denial reasons
        adjustments = parsed_data.get("adjustments", [])
        adjustment_reasons = []
        denial_reasons = []

        for adj in adjustments:
            group_code = adj.get("group_code", "")
            reason_code = adj.get("reason_code", "")
            amount = adj.get("amount", 0)

            # Create adjustment reason entry
            adjustment_reasons.append({
                "group_code": group_code,
                "reason_code": reason_code,
                "amount": amount,
            })

            # Map to denial reasons based on group code and status
            # CO (Contractual Obligation) and OA (Other Adjustment) often indicate denials
            claim_status = parsed_data.get("claim_status_code", "")
            if claim_status == "4" or (group_code in ("CO", "OA") and amount < 0):
                denial_reasons.append(f"{group_code}{reason_code}")

        # If claim is denied (status code 4) or payment is 0, add to denial reasons
        if parsed_data.get("claim_status_code") == "4" or parsed_data.get("payment_amount", 0) == 0:
            if not denial_reasons:
                denial_reasons.append("CLAIM_DENIED")

        # Get check number from BPR or references
        check_number = None
        if bpr_data and bpr_data.get("check_number"):
            check_number = bpr_data["check_number"]
        elif parsed_data.get("references"):
            # Try to find check number in references
            refs = parsed_data["references"]
            check_number = refs.get("EV") or refs.get("TRN")

        # Create remittance
        remittance = Remittance(
            remittance_control_number=remittance_control_number,
            payer_id=payer.id if payer else None,
            payer_name=payer_name or (payer.name if payer else None),
            payment_amount=parsed_data.get("payment_amount") or parsed_data.get("claim_payment_amount"),
            payment_date=payment_date,
            check_number=check_number,
            claim_control_number=claim_control_number,
            denial_reasons=denial_reasons if denial_reasons else None,
            adjustment_reasons=adjustment_reasons if adjustment_reasons else None,
            raw_edi_data=str(parsed_data.get("raw_block", [])),
            parsed_segments=_make_json_serializable(parsed_data),
            status=RemittanceStatus.PENDING,
            parsing_warnings=parsed_data.get("warnings", []),
        )

        # Log parsing warnings (batch add for better performance)
        warnings_list = parsed_data.get("warnings")
        if warnings_list:
            # Optimize: use bulk_insert_mappings for better performance (bypasses ORM overhead)
            parser_log_mappings = [
                {
                    "file_name": self.filename or "unknown",
                    "file_type": "835",
                    "log_level": "warning",
                    "segment_type": "CLP",
                    "issue_type": "parsing_warning",
                    "message": warning,
                    "claim_control_number": claim_control_number,
                    "practice_id": self.practice_id,
                }
                for warning in warnings_list
            ]
            # Batch insert all logs at once (more efficient than bulk_save_objects)
            self.db.bulk_insert_mappings(ParserLog, parser_log_mappings)

        return remittance

    def _parse_edi_date(self, date_str: str) -> datetime:
        """
        Parse EDI date string to datetime. Optimized for performance.

        EDI dates are typically in format: YYYYMMDD or YYMMDD

        Args:
            date_str: The date string to parse.

        Returns:
            A datetime object, or None if parsing fails.
        """
        if not date_str:
            return None

        date_str = date_str.strip()
        if not date_str:  # Check after stripping
            return None

        date_len = len(date_str)
        try:
            # Handle YYYYMMDD format (most common)
            if date_len == 8:
                try:
                    # Optimize: use direct string slicing instead of strptime for better performance
                    return datetime(
                        int(date_str[0:4]), int(date_str[4:6]), int(date_str[6:8])
                    )
                except ValueError:
                    logger.warning("Invalid YYYYMMDD date", date_str=date_str)
                    return None
            # Handle YYMMDD format (assume 20XX)
            elif date_len == 6:
                try:
                    year = int("20" + date_str[0:2])
                    month = int(date_str[2:4])
                    day = int(date_str[4:6])
                    return datetime(year, month, day)
                except ValueError:
                    logger.warning("Invalid YYMMDD date", date_str=date_str)
                    return None
            else:
                logger.warning("Unknown date format", date_str=date_str)
                return None
        except (AttributeError, TypeError) as e:
            logger.warning("Failed to parse date", date_str=date_str, error=str(e))
            return None

