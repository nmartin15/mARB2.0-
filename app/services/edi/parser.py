"""
Resilient EDI parser for 837/835 files.

This module provides a resilient EDI parser that handles variations and missing
segments gracefully. It can parse both 837 (claims) and 835 (remittances) files,
continuing processing even when segments are missing or malformed.

**Documentation References:**
- EDI Format Guide: `EDI_FORMAT_GUIDE.md`
- Format Detection: `app/services/edi/FORMAT_DETECTION.md`
- EDI Processing: `.cursorrules` → "EDI Processing" section
- Extractors: `app/services/edi/extractors/` (see individual extractor modules)
- Quick Reference: `DOCUMENTATION_QUICK_REFERENCE.md` → "I'm processing EDI files"
"""
import gc
from typing import Dict, List, Optional, Generator

from app.services.edi.config import get_parser_config
from app.services.edi.extractors.claim_extractor import ClaimExtractor
from app.services.edi.extractors.diagnosis_extractor import DiagnosisExtractor
from app.services.edi.extractors.line_extractor import LineExtractor
from app.services.edi.extractors.payer_extractor import PayerExtractor
from app.services.edi.format_detector import FormatDetector
from app.services.edi.validator import SegmentValidator
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Cache translation table for newline removal (created once, reused)
_NEWLINE_TRANSLATION_TABLE = str.maketrans("", "", "\r\n")

# Configuration constants for chunked processing
SEGMENT_CHUNK_SIZE = 10000  # Process segments in chunks of 10k
MEMORY_CLEANUP_THRESHOLD = 50000  # Trigger GC after processing this many segments

# Try to import performance monitor, but make it optional
try:
    from app.services.edi.performance_monitor import PerformanceMonitor
    PERFORMANCE_MONITORING_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITORING_AVAILABLE = False
    PerformanceMonitor = None


class EDIParser:
    """Resilient EDI parser that handles variations and missing segments."""

    def __init__(self, practice_id: Optional[str] = None, auto_detect_format: bool = True):
        """
        Initialize EDI parser.
        
        Args:
            practice_id: Optional practice identifier for practice-specific parsing configuration.
                         If provided, parser will use practice-specific segment expectations and rules.
            auto_detect_format: If True, automatically detect and adapt to file format variations.
                                If False, use default configuration only.
        """
        self.practice_id = practice_id
        self.auto_detect_format = auto_detect_format
        self.config = get_parser_config(practice_id)
        self.format_detector = FormatDetector() if auto_detect_format else None
        self.validator = SegmentValidator(self.config)
        self.claim_extractor = ClaimExtractor(self.config)
        self.line_extractor = LineExtractor(self.config)
        self.payer_extractor = PayerExtractor(self.config)
        self.diagnosis_extractor = DiagnosisExtractor(self.config)
        self.format_profile = None

    def parse(self, file_content: str, filename: str) -> Dict:
        """
        Parse EDI file content with optional format detection.

        Returns:
            Dict with parsed data and parsing metadata
        """
        logger.info("Starting EDI parsing", filename=filename, practice_id=self.practice_id)

        # Start performance monitoring for large files
        monitor = None
        if PERFORMANCE_MONITORING_AVAILABLE and len(file_content) > 1024 * 1024:  # >1MB
            monitor = PerformanceMonitor(f"parse_edi_{filename}")
            monitor.start()
            monitor.checkpoint("start", {"file_size_mb": len(file_content) / (1024 * 1024)})

        # Split into segments
        segments = self._split_segments(file_content)

        if monitor:
            monitor.checkpoint("segments_split", {"segment_count": len(segments)})

        if not segments:
            raise ValueError("No segments found in EDI file")

        # Auto-detect format if enabled
        format_analysis = None
        if self.auto_detect_format and self.format_detector:
            format_analysis = self.format_detector.analyze_file(segments)
            logger.info(
                "Format analysis complete",
                version=format_analysis.get("version"),
                segment_count=len(format_analysis.get("segment_frequency", {})),
            )
            # Update config based on detected format if needed
            self._adapt_to_format(format_analysis)

        # Validate envelope segments
        envelope_data = self._parse_envelope(segments)

        # Extract claim blocks (for 837) or remittance data (for 835)
        file_type = self._detect_file_type(segments)

        if monitor:
            monitor.checkpoint("envelope_parsed", {"file_type": file_type})

        if file_type == "837":
            result = self._parse_837(segments, envelope_data, filename)
            # Add format analysis to result
            if format_analysis:
                result["format_analysis"] = format_analysis
            if monitor:
                monitor.checkpoint("parsing_complete", {"claims_parsed": len(result.get("claims", []))})
                perf_summary = monitor.finish()
                result["_performance"] = perf_summary
            return result
        elif file_type == "835":
            result = self._parse_835(segments, envelope_data, filename)
            if monitor:
                monitor.checkpoint(
                    "parsing_complete", {"remittances_parsed": len(result.get("remittances", []))}
                )
                perf_summary = monitor.finish()
                result["_performance"] = perf_summary
            return result
        else:
            if monitor:
                monitor.finish()
            raise ValueError(f"Unknown file type: {file_type}")

    def _adapt_to_format(self, format_analysis: Dict) -> None:
        """Adapt parser configuration based on detected format."""
        # Update segment expectations based on detected segments
        detected_segments = set(format_analysis.get("segment_frequency", {}).keys())

        # Update config with detected segments
        if detected_segments:
            # Keep critical segments
            critical = {"ISA", "GS", "ST", "CLM"}
            important = detected_segments - critical

            # Update config segment expectations
            self.config.segment_expectations["important"] = list(important)[:20]  # Limit to top 20

            logger.debug(
                "Adapted parser config",
                important_segments=len(important),
                detected_segments=len(detected_segments),
            )

    def _split_segments_chunked(self, content: str) -> Generator[List[List[str]], None, None]:
        """
        Split EDI content into segments in chunks for memory-efficient processing.

        Args:
            content: The EDI file content as a string.

        Yields segments in chunks, allowing memory cleanup between chunks.
        Use this for very large files (>50MB) to reduce memory usage.

        Yields:
            List of segments (chunks of SEGMENT_CHUNK_SIZE)
        """
        # Remove newlines/carriage returns using cached translation table
        if "\r" in content or "\n" in content:
            content = content.translate(_NEWLINE_TRANSLATION_TABLE)

        # Split by segment delimiter (~)
        segment_strings = content.split("~")
        
        # Process in chunks
        chunk = []
        # Pre-allocate chunk list to reduce reallocations
        chunk = []
        if len(segment_strings) > SEGMENT_CHUNK_SIZE:
            chunk = [None] * min(SEGMENT_CHUNK_SIZE, 10000)
            chunk.clear()
        
        for seg_str in segment_strings:
            # Optimize: check if string needs stripping (most don't)
            if seg_str:
                # Only strip if first/last char is whitespace
                if seg_str[0].isspace() or seg_str[-1].isspace():
                    seg_str = seg_str.strip()
                    if not seg_str:
                        continue
                # Split segment into elements
                elements = seg_str.split("*")
                if elements and elements[0]:  # Ensure first element exists
                    chunk.append(elements)
            
            # Yield chunk when it reaches threshold
            if len(chunk) >= SEGMENT_CHUNK_SIZE:
                yield chunk
                chunk = []
                
                # Suggest garbage collection for very large files
                if len(segment_strings) > MEMORY_CLEANUP_THRESHOLD:
                    gc.collect(0)  # Collect generation 0 only (faster)
        
        # Yield remaining segments
        if chunk:
            yield chunk

    def _split_segments(self, content: str) -> List[List[str]]:
        """
        Split EDI content into segments with optimized memory usage.

        Uses efficient string processing optimized for both small and large files.
        Optimizations:
        - Single-pass newline removal using translate (faster than replace)
        - Pre-allocated list to reduce reallocations
        - In-place element splitting to reduce memory overhead
        """
        # EDI uses ~ as segment delimiter and * as element delimiter
        # Optimized approach: use split() which is much faster than character-by-character

        # Remove newlines/carriage returns using cached translation table
        # (faster than creating new table each time)
        if "\r" in content or "\n" in content:
            # Use cached translation table for better performance
            content = content.translate(_NEWLINE_TRANSLATION_TABLE)

        # Split by segment delimiter (~)
        segment_strings = content.split("~")

        # Pre-allocate list to reduce reallocations
        # Estimate: most segments are non-empty, but account for trailing empty segments
        estimated_count = len(segment_strings)
        segments = []
        # Reserve capacity for better memory efficiency (Python 3.7+ list growth optimization)
        if estimated_count > 100:
            # Pre-allocate with None, then clear - helps Python optimize list growth
            segments = [None] * min(estimated_count, 10000)  # Cap pre-allocation
            segments.clear()

        # Process each segment string
        for seg_str in segment_strings:
            # Use strip() only if needed (check first char/last char for whitespace)
            # For most segments, there's no leading/trailing whitespace
            if seg_str and (seg_str[0].isspace() or seg_str[-1].isspace()):
                seg_str = seg_str.strip()

            if not seg_str:
                continue

            # Split by element delimiter (*)
            # Most segments have 5-15 elements, so split() is optimal
            elements = seg_str.split("*")
            segments.append(elements)

        return segments

    def _detect_file_type(self, segments: List[List[str]]) -> str:
        """Detect if file is 837 (claim) or 835 (remittance). Optimized with early exit.

        Args:
            segments: List of parsed EDI segments.

        Returns:
            File type as string: "837" for claims, "835" for remittances, defaults to "837".
        """
        # Check GS segment first (most reliable indicator)
        gs_seg = self._find_segment(segments, "GS")
        if gs_seg and len(gs_seg) > 8:
            # GS08 contains version/release, check for 837 or 835
            # Optimize: cache version string and use efficient substring checks
            version = gs_seg[8]
            if version:  # Ensure version is not empty
                if "005010X222" in version or "005010X223" in version:
                    return "837"
                elif "005010X221" in version:
                    return "835"

        # Fallback: check for CLM segment (837) or CLP segment (835)
        # Optimize: use early exit with find_segment
        clm_seg = self._find_segment(segments, "CLM")
        if clm_seg:
            return "837"

        clp_seg = self._find_segment(segments, "CLP")
        if clp_seg:
            return "835"

        # Default to 837 if uncertain
        logger.warning("Could not determine file type, defaulting to 837")
        return "837"

    def _parse_envelope(self, segments: List[List[str]]) -> Dict:
        """Parse envelope segments (ISA, GS, ST).

        Args:
            segments: List of parsed EDI segments.

        Returns:
            Dictionary containing parsed envelope data (isa, gs, st).
        """
        envelope = {}
        warnings = []

        # Find ISA segment
        isa_seg = self._find_segment(segments, "ISA")
        if isa_seg:
            envelope["isa"] = {
                "sender_id": isa_seg[6] if len(isa_seg) > 6 else None,
                "receiver_id": isa_seg[8] if len(isa_seg) > 8 else None,
                "interchange_date": isa_seg[9] if len(isa_seg) > 9 else None,
                "interchange_control_number": isa_seg[13] if len(isa_seg) > 13 else None,
            }
        else:
            warnings.append("ISA segment not found")

        # Find GS segment
        gs_seg = self._find_segment(segments, "GS")
        if gs_seg:
            envelope["gs"] = {
                "sender_id": gs_seg[2] if len(gs_seg) > 2 else None,
                "receiver_id": gs_seg[3] if len(gs_seg) > 3 else None,
                "date": gs_seg[4] if len(gs_seg) > 4 else None,
                "group_control_number": gs_seg[6] if len(gs_seg) > 6 else None,
            }
        else:
            warnings.append("GS segment not found")

        # Find ST segment
        st_seg = self._find_segment(segments, "ST")
        if st_seg:
            envelope["st"] = {
                "transaction_set_id": st_seg[1] if len(st_seg) > 1 else None,
                "control_number": st_seg[2] if len(st_seg) > 2 else None,
            }
        else:
            warnings.append("ST segment not found")

        if warnings:
            logger.warning("Envelope parsing warnings", warnings=warnings)

        return envelope

    def _parse_837(self, segments: List[List[str]], envelope: Dict, filename: str) -> Dict:
        """Parse 837 claim file with optimized batch processing."""
        logger.info("Parsing 837 claim file", filename=filename, segment_count=len(segments))

        # Get claim blocks (HL segments with index 3 = '22' for subscriber level)
        claim_blocks = self._get_claim_blocks(segments)

        if not claim_blocks:
            logger.warning("No claim blocks found in 837 file", filename=filename)
            return {
                "file_type": "837",
                "envelope": envelope,
                "claims": [],
                "warnings": ["No claim blocks found"],
            }

        # Process in batches for large files to reduce memory pressure
        batch_size = 50
        parsed_claims = []
        all_warnings = []

        total_blocks = len(claim_blocks)
        is_large_file = total_blocks > 500
        logger.info(
            "Processing claim blocks",
            total_blocks=total_blocks,
            batch_size=batch_size,
            filename=filename,
        )

        # Pre-allocate parsed_claims list if we know the size (reduces reallocations)
        if total_blocks > 100:
            parsed_claims = [None] * total_blocks
            parsed_claims.clear()

        for batch_start in range(0, total_blocks, batch_size):
            batch_end = min(batch_start + batch_size, total_blocks)
            batch = claim_blocks[batch_start:batch_end]

            for block_idx, block in enumerate(batch):
                actual_idx = batch_start + block_idx
                try:
                    claim_data = self._parse_claim_block(block, actual_idx)
                    parsed_claims.append(claim_data)
                    if claim_data.get("warnings"):
                        all_warnings.extend(claim_data["warnings"])
                except Exception as e:
                    logger.error(
                        "Failed to parse claim block",
                        block_index=actual_idx,
                        error=str(e),
                        exc_info=True,
                    )
                    all_warnings.append(f"Failed to parse claim block {actual_idx}: {str(e)}")

            # Memory cleanup for large files - improved chunked processing
            if is_large_file:
                # Clear individual block references in the batch before deleting batch
                for block in batch:
                    del block
                # Clear batch reference to help GC
                del batch
                
                # Periodic cleanup every 10 batches (more frequent for very large files)
                if batch_end % (batch_size * 10) == 0:
                    # Collect generation 0 (faster, less aggressive)
                    gc.collect(0)
                # Full GC every 50 batches for very large files
                elif batch_end % (batch_size * 50) == 0:
                    gc.collect()

            # Log progress for large files
            if total_blocks > 100 and batch_end % 100 == 0:
                logger.info(
                    "Parsing progress",
                    processed=batch_end,
                    total=total_blocks,
                    progress_pct=(batch_end / total_blocks) * 100,
                )

        logger.info(
            "837 file parsing complete",
            filename=filename,
            claims_parsed=len(parsed_claims),
            warnings_count=len(all_warnings),
        )

        return {
            "file_type": "837",
            "envelope": envelope,
            "claims": parsed_claims,
            "warnings": all_warnings,
            "claim_count": len(parsed_claims),
        }

    def _parse_835(self, segments: List[List[str]], envelope: Dict, filename: str) -> Dict:
        """Parse 835 remittance file with optimized batch processing."""
        logger.info("Parsing 835 remittance file", filename=filename, segment_count=len(segments))

        all_warnings = []

        # Extract BPR segment (financial information)
        bpr_data = self._extract_bpr_segment(segments)

        # Extract payer information from N1*PR segment (appears before LX blocks)
        payer_data = self._extract_payer_from_835(segments)

        # Get remittance blocks (each LX segment starts a new claim)
        remittance_blocks = self._get_remittance_blocks(segments)

        if not remittance_blocks:
            logger.warning("No remittance blocks found in 835 file", filename=filename)
            return {
                "file_type": "835",
                "envelope": envelope,
                "remittances": [],
                "warnings": ["No remittance blocks found"],
            }

        # Process in batches for large files to reduce memory pressure
        batch_size = 50
        parsed_remittances = []

        total_blocks = len(remittance_blocks)
        is_large_file = total_blocks > 500
        logger.info(
            "Processing remittance blocks",
            total_blocks=total_blocks,
            batch_size=batch_size,
            filename=filename,
        )

        # Pre-allocate parsed_remittances list if we know the size (reduces reallocations)
        if total_blocks > 100:
            parsed_remittances = [None] * total_blocks
            parsed_remittances.clear()

        for batch_start in range(0, total_blocks, batch_size):
            batch_end = min(batch_start + batch_size, total_blocks)
            batch = remittance_blocks[batch_start:batch_end]

            for block_idx, block in enumerate(batch):
                actual_idx = batch_start + block_idx
                try:
                    remittance_data = self._parse_remittance_block(
                        block, actual_idx, bpr_data, payer_data
                    )
                    parsed_remittances.append(remittance_data)
                    if remittance_data.get("warnings"):
                        all_warnings.extend(remittance_data["warnings"])
                except Exception as e:
                    logger.error(
                        "Failed to parse remittance block",
                        block_index=actual_idx,
                        error=str(e),
                        exc_info=True,
                    )
                    all_warnings.append(
                        f"Failed to parse remittance block {actual_idx}: {str(e)}"
                    )

            # Memory cleanup for large files - improved chunked processing
            if is_large_file:
                # Clear individual block references in the batch before deleting batch
                for block in batch:
                    del block
                # Clear batch reference to help GC
                del batch
                
                # Periodic cleanup every 10 batches (more frequent for very large files)
                if batch_end % (batch_size * 10) == 0:
                    # Collect generation 0 (faster, less aggressive)
                    gc.collect(0)
                # Full GC every 50 batches for very large files
                elif batch_end % (batch_size * 50) == 0:
                    gc.collect()

            # Log progress for large files
            if total_blocks > 100 and batch_end % 100 == 0:
                logger.info(
                    "Parsing progress",
                    processed=batch_end,
                    total=total_blocks,
                    progress_pct=(batch_end / total_blocks) * 100,
                )

        logger.info(
            "835 file parsing complete",
            filename=filename,
            remittances_parsed=len(parsed_remittances),
            warnings_count=len(all_warnings),
        )

        return {
            "file_type": "835",
            "envelope": envelope,
            "remittances": parsed_remittances,
            "warnings": all_warnings,
            "remittance_count": len(parsed_remittances),
            "bpr": bpr_data,
        }

    def _extract_bpr_segment(self, segments: List[List[str]]) -> Dict:
        """Extract BPR (financial information) segment from 835 file.

        Args:
            segments: List of parsed EDI segments.

        Returns:
            Dictionary containing BPR segment data, or empty dict if not found.
        """
        bpr_seg = self._find_segment(segments, "BPR")
        if not bpr_seg:
            return {}

        # BPR format: BPR*TransactionHandlingCode*TotalPremiumPaymentAmount*CreditDebitFlag*
        #             PaymentMethodCode*PaymentFormatCode*DFIIdentificationNumberQualifier*
        #             DFIIdentificationNumber*AccountNumberQualifier*AccountNumber*
        #             OriginatingCompanyIdentifier*OriginatingCompanySupplementalCode*
        #             DFIIdentificationNumberQualifier*DFIIdentificationNumber*
        #             AccountNumberQualifier*AccountNumber*EffectiveProductionDate*
        #             BusinessFunctionCode*DFIIdentificationNumberQualifier*
        #             DFIIdentificationNumber*AccountNumberQualifier*AccountNumber
        return {
            "transaction_handling_code": bpr_seg[1] if len(bpr_seg) > 1 else None,
            "total_payment_amount": self._parse_decimal(bpr_seg[2]) if len(bpr_seg) > 2 else None,
            "credit_debit_flag": bpr_seg[3] if len(bpr_seg) > 3 else None,
            "payment_method_code": bpr_seg[4] if len(bpr_seg) > 4 else None,
            "payment_format_code": bpr_seg[5] if len(bpr_seg) > 5 else None,
            "check_number": bpr_seg[4] if len(bpr_seg) > 4 and bpr_seg[4] else None,
            "effective_payment_date": bpr_seg[16] if len(bpr_seg) > 16 else None,
        }

    def _get_remittance_blocks(self, segments: List[List[str]]) -> List[List[List[str]]]:
        """
        Get remittance blocks starting with LX segment.
        Each LX segment starts a new claim remittance.

        Optimized single-pass algorithm with reduced allocations.

        Args:
            segments: List of parsed EDI segments.

        Returns:
            List of remittance blocks, where each block is a list of segments.
        """
        remittance_blocks = []
        current_block = []

        # Pre-allocate if we can estimate (rough: ~1 remittance per 30 segments)
        estimated_blocks = max(1, len(segments) // 30)
        if estimated_blocks > 10:
            # Pre-allocate outer list to reduce reallocations
            remittance_blocks = [None] * min(estimated_blocks, 1000)
            remittance_blocks.clear()

        # Cache termination segment IDs for faster lookup (set membership is O(1))
        termination_segments = {"SE", "GE", "IEA"}

        for seg in segments:
            # Optimize: empty list is falsy
            if not seg:
                continue

            # Cache seg_id to avoid repeated indexing
            seg_id = seg[0]
            
            # Check for termination segment early (before checking if seg_id is falsy)
            # This allows early exit for termination segments
            if seg_id and seg_id in termination_segments:
                # Termination segment - save current block and don't add termination segment
                if current_block:
                    remittance_blocks.append(current_block)
                current_block = []
                continue
            
            if not seg_id:
                continue

            # Check if this is an LX segment (starts a new remittance block)
            if seg_id == "LX":
                # If we have a current block, save it
                if current_block:
                    remittance_blocks.append(current_block)
                current_block = []

                # Start new remittance block
                current_block.append(seg)
            elif current_block:
                # Add segment to current remittance block
                # Regular segment - add to current block
                current_block.append(seg)

        # Don't forget the last remittance block
        if current_block:
            remittance_blocks.append(current_block)

        return remittance_blocks

    def _extract_payer_from_835(self, segments: List[List[str]]) -> Dict:
        """Extract payer information from N1*PR segment in 835 file. Optimized with early exit.

        Args:
            segments: List of parsed EDI segments.

        Returns:
            Dictionary containing payer information (name, address, city, state, zip).
        """
        payer_data = {}

        # Cache termination segment IDs for faster lookup (set membership is O(1))
        termination_segments = {"LX", "CLP", "BPR", "TRN"}

        # Find N1*PR segment (payer information)
        segments_len = len(segments)
        for i in range(segments_len):
            seg = segments[i]
            # Optimize: empty list is falsy
            if not seg:
                continue
            # Optimize: check seg[0] first (most common case is not N1)
            if seg[0] == "N1" and len(seg) > 1 and seg[1] == "PR":
                # N1 format: N1*PR*PayerName*N3*Address*N4*City*State*Zip
                payer_data["name"] = seg[2] if len(seg) > 2 else None

                # Look for N3 (address) and N4 (city/state/zip) segments that follow
                # Optimize: limit search window and use early exit
                search_limit = min(i + 5, segments_len)
                for j in range(i + 1, search_limit):
                    next_seg = segments[j]
                    if not next_seg:
                        continue
                    next_seg_id = next_seg[0]
                    if next_seg_id == "N3":
                        payer_data["address"] = next_seg[1] if len(next_seg) > 1 else None
                    elif next_seg_id == "N4":
                        payer_data["city"] = next_seg[1] if len(next_seg) > 1 else None
                        payer_data["state"] = next_seg[2] if len(next_seg) > 2 else None
                        payer_data["zip"] = next_seg[3] if len(next_seg) > 3 else None
                    elif next_seg_id in termination_segments:
                        # Stop at next major segment
                        break

                # Early exit after finding payer info
                break

        return payer_data

    def _parse_remittance_block(
        self, block: List[List[str]], block_index: int, bpr_data: Dict, payer_data: Dict = None
    ) -> Dict:
        """Parse a single remittance block (claim payment information).

        Args:
            block: List of segments representing a remittance block.
            block_index: Index of the remittance block.
            bpr_data: BPR segment data containing financial information.
            payer_data: Optional payer information dictionary.

        Returns:
            Dictionary containing parsed remittance data including claim info, adjustments, and service lines.
        """
        warnings = []
        remittance_data = {
            "block_index": block_index,
            "warnings": warnings,
        }

        # Extract CLP segment (claim payment information)
        clp_seg = self._find_segment_in_block(block, "CLP")
        if not clp_seg:
            warnings.append("CLP segment not found in remittance block")
            remittance_data["is_incomplete"] = True
            return remittance_data

        # CLP format: CLP*ClaimControlNumber*ClaimStatusCode*ClaimAmount*
        #             ClaimPaymentAmount*PatientResponsibilityAmount*
        #             ClaimFilingIndicatorCode*PayerClaimControlNumber*
        #             FacilityCodeValue*ClaimFrequencyCode*PatientStatusCode*
        #             DiagnosisRelatedGroupDRGCode*DiagnosisRelatedGroupDRGWeight*
        #             DischargeFraction*ClaimStatus*ContractualObligationCode*
        #             ServiceAuthorizationExceptionCode*MedicareAssignmentCode*
        #             BenefitsAssignmentCertificationIndicator*ReleaseOfInformationCode
        remittance_data.update({
            "claim_control_number": clp_seg[1] if len(clp_seg) > 1 else None,
            "claim_status_code": clp_seg[2] if len(clp_seg) > 2 else None,
            "claim_amount": self._parse_decimal(clp_seg[3]) if len(clp_seg) > 3 else None,
            "claim_payment_amount": self._parse_decimal(clp_seg[4]) if len(clp_seg) > 4 else None,
            "patient_responsibility_amount": self._parse_decimal(clp_seg[5]) if len(clp_seg) > 5 else None,
            "claim_filing_indicator_code": clp_seg[6] if len(clp_seg) > 6 else None,
            "payer_claim_control_number": clp_seg[7] if len(clp_seg) > 7 else None,
            "service_date": clp_seg[8] if len(clp_seg) > 8 else None,
        })

        # Use claim_payment_amount as payment_amount for consistency
        remittance_data["payment_amount"] = remittance_data.get("claim_payment_amount")

        # Extract CAS segments (claim adjustments)
        cas_segments = self._find_all_segments_in_block(block, "CAS")
        adjustments = []
        for cas_seg in cas_segments:
            # CAS format: CAS*AdjustmentGroupCode*AdjustmentReasonCode*AdjustmentAmount*
            #             AdjustmentQuantity*AdjustmentReasonCode*AdjustmentAmount*...
            if len(cas_seg) < 3:
                continue

            group_code = cas_seg[1] if len(cas_seg) > 1 else None
            # CAS can have multiple adjustment reason/amount pairs
            i = 2
            while i + 1 < len(cas_seg):
                reason_code = cas_seg[i] if i < len(cas_seg) else None
                amount = self._parse_decimal(cas_seg[i + 1]) if i + 1 < len(cas_seg) else None
                if reason_code and amount is not None:
                    adjustments.append({
                        "group_code": group_code,  # CO, PR, OA, etc.
                        "reason_code": reason_code,
                        "amount": amount,
                    })
                i += 2

        remittance_data["adjustments"] = adjustments

        # Extract adjustment codes by group
        # Optimize: single pass through adjustments instead of three list comprehensions
        co_codes = []
        pr_codes = []
        oa_codes = []
        for adj in adjustments:
            group_code = adj.get("group_code")
            if group_code == "CO":
                co_codes.append(adj)
            elif group_code == "PR":
                pr_codes.append(adj)
            elif group_code == "OA":
                oa_codes.append(adj)

        remittance_data["co_adjustments"] = co_codes
        remittance_data["pr_adjustments"] = pr_codes
        remittance_data["oa_adjustments"] = oa_codes

        # Extract patient and provider information (NM1 segments) in single pass
        # Optimize: find both NM1 segments in one pass instead of two
        patient_nm1 = None
        provider_nm1 = None
        for seg in block:
            if not seg or len(seg) < 3:
                continue
            if seg[0] == "NM1":
                if seg[1] == "QC" and patient_nm1 is None:
                    patient_nm1 = seg
                elif seg[1] == "82" and provider_nm1 is None:
                    provider_nm1 = seg
                # Early exit if both found
                if patient_nm1 and provider_nm1:
                    break

        if patient_nm1:
            remittance_data["patient"] = {
                "last_name": patient_nm1[3] if len(patient_nm1) > 3 else None,
                "first_name": patient_nm1[4] if len(patient_nm1) > 4 else None,
                "middle_name": patient_nm1[5] if len(patient_nm1) > 5 else None,
                "identifier": patient_nm1[9] if len(patient_nm1) > 9 else None,
            }

        if provider_nm1:
            remittance_data["provider"] = {
                "last_name": provider_nm1[3] if len(provider_nm1) > 3 else None,
                "first_name": provider_nm1[4] if len(provider_nm1) > 4 else None,
                "identifier": provider_nm1[9] if len(provider_nm1) > 9 else None,
            }

        # Extract REF segments
        ref_segments = self._find_all_segments_in_block(block, "REF")
        references = {}
        for ref_seg in ref_segments:
            if len(ref_seg) >= 3:
                ref_type = ref_seg[1] if len(ref_seg) > 1 else None
                ref_value = ref_seg[2] if len(ref_seg) > 2 else None
                if ref_type and ref_value:
                    references[ref_type] = ref_value

        remittance_data["references"] = references

        # Extract AMT segments
        amt_segments = self._find_all_segments_in_block(block, "AMT")
        amounts = {}
        for amt_seg in amt_segments:
            if len(amt_seg) >= 3:
                amt_type = amt_seg[1] if len(amt_seg) > 1 else None
                amt_value = self._parse_decimal(amt_seg[2]) if len(amt_seg) > 2 else None
                if amt_type and amt_value is not None:
                    amounts[amt_type] = amt_value

        remittance_data["amounts"] = amounts

        # Extract SVC segments (service line payments)
        svc_segments = self._find_all_segments_in_block(block, "SVC")
        service_lines = []
        for svc_idx, svc_seg in enumerate(svc_segments):
            # SVC format: SVC*CompositeMedicalProcedureIdentifier*MonetaryAmount*
            #             MonetaryAmount*ProductServiceID*Quantity*CompositeDiagnosisCodePointer
            service_line = {
                "line_number": svc_idx + 1,
                "service_code": svc_seg[1] if len(svc_seg) > 1 else None,
                "charge_amount": self._parse_decimal(svc_seg[2]) if len(svc_seg) > 2 else None,
                "payment_amount": self._parse_decimal(svc_seg[3]) if len(svc_seg) > 3 else None,
                "product_service_id": svc_seg[4] if len(svc_seg) > 4 else None,
                "quantity": self._parse_decimal(svc_seg[5]) if len(svc_seg) > 5 else None,
            }

            # Find CAS segments that follow this SVC (service-level adjustments)
            # CAS segments immediately after SVC apply to that service
            # Optimize: use identity check first, then equality
            svc_position = None
            block_len = len(block)
            for i in range(block_len):
                if block[i] is svc_seg or block[i] == svc_seg:
                    svc_position = i
                    break

            if svc_position is not None:
                service_adjustments = []
                # Look for CAS segments after this SVC but before next SVC or CLP
                # Cache termination segments for faster lookup
                termination_segments = {"SVC", "CLP", "LX"}
                for i in range(svc_position + 1, block_len):
                    seg = block[i]
                    if not seg:
                        continue
                    seg_id = seg[0]
                    if seg_id == "CAS":
                        # Parse CAS segment
                        if len(seg) >= 3:
                            group_code = seg[1] if len(seg) > 1 else None
                            seg_len = len(seg)
                            j = 2
                            while j + 1 < seg_len:
                                reason_code = seg[j] if j < seg_len else None
                                amount = self._parse_decimal(seg[j + 1]) if j + 1 < seg_len else None
                                if reason_code and amount is not None:
                                    service_adjustments.append({
                                        "group_code": group_code,
                                        "reason_code": reason_code,
                                        "amount": amount,
                                    })
                                j += 2
                    elif seg_id in termination_segments:
                        # Stop at next service, claim, or loop
                        break

                service_line["adjustments"] = service_adjustments

            # Find DTM segment for service date (DTM*472)
            if svc_position is not None:
                termination_segments = {"SVC", "CLP", "LX"}
                for i in range(svc_position + 1, block_len):
                    seg = block[i]
                    if not seg:
                        continue
                    seg_id = seg[0]
                    if seg_id == "DTM" and len(seg) > 2 and seg[1] == "472":
                        service_line["service_date"] = seg[2] if len(seg) > 2 else None
                        break
                    elif seg_id in termination_segments:
                        break

            service_lines.append(service_line)

        remittance_data["service_lines"] = service_lines

        # Add payer information if available
        if payer_data:
            remittance_data["payer"] = payer_data

        # Add BPR data if available
        if bpr_data:
            remittance_data["payment_info"] = bpr_data

        remittance_data["is_incomplete"] = len(warnings) > 0
        remittance_data["raw_block"] = block

        return remittance_data

    def _parse_decimal(self, value: Optional[str]) -> Optional[float]:
        """Parse decimal value from EDI string. Optimized to reduce string operations.

        Args:
            value: The string representation of the decimal value.

        Returns:
            The float representation of the value, or None if parsing fails.
        """
        if not value:
            return None
        # Optimize: check if string needs stripping (most values don't)
        # Only strip if first/last char is whitespace
        if value[0].isspace() or value[-1].isspace():
            value = value.strip()
            if not value:
                return None
        try:
            return float(value)
        except (ValueError, AttributeError, TypeError):
            return None

    def _get_claim_blocks(self, segments: List[List[str]]) -> List[List[List[str]]]:
        """
        Get claim blocks starting with HL segment where index 3 = '22' (subscriber level).

        Optimized single-pass algorithm with reduced allocations and early exits.

        Args:
            segments: List of parsed EDI segments.

        Returns:
            List of claim blocks, where each block is a list of segments.
        """
        claim_blocks = []
        current_claim = []

        # Pre-allocate list if we can estimate (rough: ~1 claim per 50 segments)
        estimated_blocks = max(1, len(segments) // 50)
        if estimated_blocks > 10:
            # Pre-allocate outer list to reduce reallocations
            claim_blocks = [None] * min(estimated_blocks, 1000)
            claim_blocks.clear()

        for i, seg in enumerate(segments):
            # Optimize: empty list is falsy, no need for len check
            if not seg:
                continue

            # Cache seg_id to avoid repeated indexing
            seg_id = seg[0]
            if not seg_id:
                continue

            # Check if this is a subscriber-level HL segment (index 3 = '22')
            # Optimize: check seg_id first (most common case is not HL)
            # Use direct indexing after seg_id check (faster than len check + indexing)
            if seg_id == "HL":
                # Check length and index 3 in one go
                if len(seg) >= 4 and seg[3] == "22":
                    # If we have a current claim, save it
                    if current_claim:
                        claim_blocks.append(current_claim)
                        current_claim = []

                    # Start new claim block
                    current_claim.append(seg)
                elif current_claim:
                    # HL segment but not subscriber level - add to current claim
                    current_claim.append(seg)
            elif current_claim:
                # Add segment to current claim block
                current_claim.append(seg)

        # Don't forget the last claim block
        if current_claim:
            claim_blocks.append(current_claim)

        return claim_blocks

    def _parse_claim_block(self, block: List[List[str]], block_index: int) -> Dict:
        """Parse a single claim block.

        Args:
            block: List of segments representing a claim block.
            block_index: Index of the claim block.

        Returns:
            Dictionary containing parsed claim data including claim info, payer, diagnosis, and lines.
        """
        warnings = []

        # Extract claim header (CLM segment)
        clm_seg = self._find_segment_in_block(block, "CLM")
        if not clm_seg:
            warnings.append("CLM segment not found in claim block")
            return {
                "block_index": block_index,
                "warnings": warnings,
                "is_incomplete": True,
            }

        claim_data = self.claim_extractor.extract(clm_seg, block, warnings)

        # Extract payer information (SBR/NM1 segments)
        payer_data = self.payer_extractor.extract(block, warnings)
        claim_data.update(payer_data)

        # Extract diagnosis codes (HI segments)
        diagnosis_data = self.diagnosis_extractor.extract(block, warnings)
        claim_data.update(diagnosis_data)

        # Extract claim lines (LX/SV2 segments)
        lines_data = self.line_extractor.extract(block, warnings)
        claim_data["lines"] = lines_data

        # Store raw block for reference
        claim_data["raw_block"] = block
        claim_data["block_index"] = block_index
        claim_data["warnings"] = warnings
        claim_data["is_incomplete"] = len(warnings) > 0

        return claim_data

    def _find_segment(self, segments: List[List[str]], segment_id: str) -> Optional[List[str]]:
        """Find first occurrence of a segment by ID. Optimized with early exit.

        Args:
            segments: List of parsed EDI segments.
            segment_id: The segment identifier to search for (e.g., "CLM", "CLP").

        Returns:
            The first matching segment as a list of elements, or None if not found.
        """
        # Optimize: use generator expression with next() for early exit
        # This is faster than manual loop for finding first match
        # Check seg[0] directly after verifying seg is non-empty (faster path)
        try:
            return next(seg for seg in segments if seg and seg[0] == segment_id)
        except (StopIteration, IndexError):
            return None

    def _find_segment_in_block(
        self, block: List[List[str]], segment_id: str
    ) -> Optional[List[str]]:
        """Find first occurrence of a segment in a claim block. Optimized with early exit.

        Args:
            block: List of segments representing a claim or remittance block.
            segment_id: The segment identifier to search for (e.g., "CLM", "CLP").

        Returns:
            The first matching segment as a list of elements, or None if not found.
        """
        # Optimize: check seg[0] directly after verifying seg is non-empty
        try:
            return next(seg for seg in block if seg and seg[0] == segment_id)
        except (StopIteration, IndexError):
            return None

    def _find_all_segments_in_block(
        self, block: List[List[str]], segment_id: str
    ) -> List[List[str]]:
        """Find all occurrences of a segment in a claim block. Optimized with list comprehension.

        Args:
            block: List of segments representing a claim or remittance block.
            segment_id: The segment identifier to search for (e.g., "CAS", "SVC").

        Returns:
            List of all matching segments, each as a list of elements.
        """
        # List comprehension is faster than manual loop for filtering
        # Check seg[0] directly after verifying seg is non-empty (faster path)
        # Use try/except for IndexError to handle edge cases gracefully
        result = []
        for seg in block:
            if seg and seg[0] == segment_id:
                result.append(seg)
        return result

