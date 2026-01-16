"""Optimized EDI parser for large files with streaming and batch processing."""
from typing import List, Dict, Optional, Iterator, Tuple, Generator
import gc
from app.services.edi.config import get_parser_config, ParserConfig
from app.services.edi.validator import SegmentValidator
from app.services.edi.extractors.claim_extractor import ClaimExtractor
from app.services.edi.extractors.line_extractor import LineExtractor
from app.services.edi.extractors.payer_extractor import PayerExtractor
from app.services.edi.extractors.diagnosis_extractor import DiagnosisExtractor
from app.services.edi.format_detector import FormatDetector
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Cache translation table for newline removal (created once, reused)
_NEWLINE_TRANSLATION_TABLE = str.maketrans("", "", "\r\n")

# Configuration constants
LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB - use streaming parser
STREAMING_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB - use file-based streaming
BATCH_SIZE = 50  # Process claims/remittances in batches
SEGMENT_BUFFER_SIZE = 1000  # Buffer segments before processing


class OptimizedEDIParser:
    """Optimized EDI parser with streaming and batch processing for large files."""

    def __init__(self, practice_id: Optional[str] = None, auto_detect_format: bool = True):
        """
        Initialize optimized EDI parser.
        
        Args:
            practice_id: Optional practice identifier for practice-specific parsing configuration
            auto_detect_format: If True, automatically detect and adapt to file format variations.
                               If False, use default configuration only and skip format detection.
        """
        self.practice_id = practice_id
        self.auto_detect_format = auto_detect_format
        self.config = get_parser_config(practice_id)
        # Only instantiate FormatDetector if auto_detect_format is enabled
        self.format_detector = FormatDetector() if auto_detect_format else None
        # SegmentValidator is always needed for validation
        self.validator = SegmentValidator(self.config)
        self.claim_extractor = ClaimExtractor(self.config)
        self.line_extractor = LineExtractor(self.config)
        self.payer_extractor = PayerExtractor(self.config)
        self.diagnosis_extractor = DiagnosisExtractor(self.config)
        self.format_profile = None

    def parse(
        self, 
        file_content: Optional[str] = None, 
        filename: str = "unknown",
        file_path: Optional[str] = None
    ) -> Dict:
        """
        Parse EDI file content with optimized processing for large files.
        
        For large files (>10MB), uses true streaming parser for maximum memory efficiency.
        For smaller files, uses standard processing for better performance.
        
        Supports both string content and file path inputs for maximum flexibility.
        
        Returns:
            Dict with parsed data and parsing metadata
        """
        # Determine file size and read content if file_path provided
        if file_path:
            import os
            file_size = os.path.getsize(file_path)
            # Read file content if not provided
            if file_content is None:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
        elif file_content:
            file_size = len(file_content.encode("utf-8"))
        else:
            raise ValueError("Either file_content or file_path must be provided")
        
        is_large_file = file_size > LARGE_FILE_THRESHOLD
        use_streaming = is_large_file
        
        logger.info(
            "Starting EDI parsing (optimized)",
            filename=filename,
            practice_id=self.practice_id,
            file_size_mb=file_size / (1024 * 1024),
            is_large_file=is_large_file,
            use_streaming=use_streaming,
        )
        
        # Use streaming parser for large files
        if use_streaming:
            logger.info("Using streaming parser for large file", filename=filename)
            from app.services.edi.parser_streaming import StreamingEDIParser
            
            streaming_parser = StreamingEDIParser(
                practice_id=self.practice_id,
                auto_detect_format=self.auto_detect_format
            )
            return streaming_parser.parse(
                file_content=file_content,
                file_path=file_path,
                filename=filename
            )
        else:
            # Use standard parser for smaller files (faster for small files)
            return self._parse_standard(file_content, filename)

    def _parse_standard(self, file_content: str, filename: str) -> Dict:
        """
        Standard parsing for smaller files using optimized extractors.
        
        This method uses the extractors directly instead of delegating to EDIParser,
        providing better performance and avoiding unnecessary object instantiation.
        
        Args:
            file_content: The EDI file content as a string
            filename: The name of the file being parsed
            
        Returns:
            Dict with parsed data and parsing metadata
        """
        # Split into segments
        segments = self._split_segments(file_content)
        
        if not segments:
            raise ValueError("No segments found in EDI file")
        
        # Auto-detect format if enabled
        format_analysis = None
        if self.auto_detect_format and self.format_detector:
            format_analysis = self.format_detector.analyze_file(segments)
            self.format_profile = format_analysis.get("format_profile") if format_analysis else None
        
        # Parse envelope
        envelope = self._parse_envelope(segments)
        
        # Detect file type
        file_type = self._detect_file_type(segments)
        
        # Parse based on file type
        if file_type == "837":
            return self._parse_837(segments, envelope, filename)
        elif file_type == "835":
            return self._parse_835(segments, envelope, filename)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _parse_large_file(self, file_content: str, filename: str) -> Dict:
        """
        Placeholder for optimized parsing for large files.

        NOTE: This method is currently unused and not implemented. Large files (>10MB) are
        automatically routed to StreamingEDIParser via the parse() method's routing logic.
        This method exists for potential future use but currently delegates to _parse_standard.
        True streaming/batch processing is not yet implemented in this class.

        Args:
            file_content: The EDI file content as a string.
            filename: The name of the file being parsed.

        Returns:
            Dict with parsed data and parsing metadata.
        """
        return self._parse_standard(file_content, filename)

    def _split_segments_streaming(self, content: str) -> Generator[List[str], None, None]:
        """
        Split EDI content into segments using a generator for memory efficiency.
        
        Optimized to use list-based string building instead of StringIO for better performance.

        Args:
            content: The EDI file content as a string.

        Yields segments one at a time instead of storing all in memory.

        Yields:
            List[str]: A list of strings representing a segment.
        """
        current_segment = []
        # Optimize: Use list for character accumulation instead of StringIO
        # List appends are faster than StringIO.write() for small strings
        element_chars = []

        for char in content:
            if char == "~":
                # Segment delimiter - yield current segment
                if element_chars:
                    current_segment.append("".join(element_chars))
                    element_chars = []

                if current_segment:
                    yield current_segment
                    current_segment = []

            elif char == "*":
                # Element delimiter
                if element_chars:
                    current_segment.append("".join(element_chars))
                    element_chars = []

            elif char in ("\r", "\n"):
                # Skip newlines
                continue

            else:
                element_chars.append(char)

        # Yield last segment if exists
        if element_chars:
            current_segment.append("".join(element_chars))
        if current_segment:
            yield current_segment

    def _parse_envelope_streaming(
        self, segments_generator: Generator[List[str], None, None]
    ) -> Tuple[Dict, str, List[List[str]]]:
        """
        Parse envelope segments from streaming generator.
        
        Returns:
            Tuple of (envelope_data, file_type, initial_segments_buffer)
        """
        envelope = {}
        warnings = []
        initial_segments = []
        file_type = None
        
        # Process first 100 segments to get envelope info
        segment_count = 0
        for seg in segments_generator:
            if not seg or len(seg) == 0:
                continue
            
            segment_count += 1
            initial_segments.append(seg)
            
            seg_id = seg[0] if seg else None
            
            # Find ISA segment
            if seg_id == "ISA" and "isa" not in envelope:
                envelope["isa"] = {
                    "sender_id": seg[6] if len(seg) > 6 else None,
                    "receiver_id": seg[8] if len(seg) > 8 else None,
                    "interchange_date": seg[9] if len(seg) > 9 else None,
                    "interchange_control_number": seg[13] if len(seg) > 13 else None,
                }
            
            # Find GS segment
            if seg_id == "GS" and "gs" not in envelope:
                envelope["gs"] = {
                    "sender_id": seg[2] if len(seg) > 2 else None,
                    "receiver_id": seg[3] if len(seg) > 3 else None,
                    "date": seg[4] if len(seg) > 4 else None,
                    "group_control_number": seg[6] if len(seg) > 6 else None,
                }
                
                # Detect file type from GS segment
                if len(seg) > 8:
                    version = seg[8]
                    if "005010X222" in version or "005010X223" in version:
                        file_type = "837"
                    elif "005010X221" in version:
                        file_type = "835"
            
            # Find ST segment
            if seg_id == "ST" and "st" not in envelope:
                envelope["st"] = {
                    "transaction_set_id": seg[1] if len(seg) > 1 else None,
                    "control_number": seg[2] if len(seg) > 2 else None,
                }
            
            # Stop after we have envelope info and file type
            if "isa" in envelope and "gs" in envelope and "st" in envelope and file_type:
                break
            
            # Safety limit
            if segment_count > 200:
                break
        
        # Fallback file type detection
        if not file_type:
            for seg in initial_segments:
                if not seg or len(seg) == 0:
                    continue
                if seg[0] == "CLM":
                    file_type = "837"
                    break
                elif seg[0] == "CLP":
                    file_type = "835"
                    break
        
        if not file_type:
            logger.warning("Could not determine file type, defaulting to 837")
            file_type = "837"
        
        if warnings:
            logger.warning("Envelope parsing warnings", warnings=warnings)
        
        return envelope, file_type, initial_segments

    def _parse_837_streaming(
        self, initial_segments: List[List[str]], envelope: Dict, filename: str
    ) -> Dict:
        """
        Placeholder for streaming 837 claim file parsing.

        NOTE: This method is not yet implemented. True streaming 837 parsing that processes
        segments incrementally is not available in this class. This method currently raises
        NotImplementedError. For true streaming parsing, use StreamingEDIParser instead.

        Args:
            initial_segments: Initial segments from the file (not the full segment list).
            envelope: Parsed envelope data.
            filename: The name of the file being parsed.

        Returns:
            Dict with parsed data and parsing metadata.

        Raises:
            NotImplementedError: True streaming 837 parsing is not yet implemented in this class.
        """
        logger.warning(
            "_parse_837_streaming called but requires full segment list. "
            "Consider using StreamingEDIParser for true streaming.",
            filename=filename
        )
        raise NotImplementedError(
            "True streaming 837 parsing not yet implemented. "
            "Use StreamingEDIParser or provide full file content to _parse_standard."
        )

    def _parse_835_streaming(
        self, initial_segments: List[List[str]], envelope: Dict, filename: str
    ) -> Dict:
        """
        Placeholder for streaming 835 remittance file parsing.

        NOTE: This method is not yet implemented. True streaming 835 parsing that processes
        segments incrementally is not available in this class. This method currently raises
        NotImplementedError. For true streaming parsing, use StreamingEDIParser instead.

        Args:
            initial_segments: Initial segments from the file (not the full segment list).
            envelope: Parsed envelope data.
            filename: The name of the file being parsed.

        Returns:
            Dict with parsed data and parsing metadata.

        Raises:
            NotImplementedError: True streaming 835 parsing is not yet implemented in this class.
        """
        logger.warning(
            "_parse_835_streaming called but requires full segment list. "
            "Consider using StreamingEDIParser for true streaming.",
            filename=filename
        )
        raise NotImplementedError(
            "True streaming 835 parsing not yet implemented. "
            "Use StreamingEDIParser or provide full file content to _parse_standard."
        )

    def _parse_claim_block(self, block: List[List[str]], block_index: int) -> Dict:
        """
        Parse a single claim block using extractors directly.
        
        Args:
            block: List of segments representing a claim block
            block_index: Index of the block in the file
            
        Returns:
            Dict containing parsed claim data with warnings and metadata
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

    def _parse_remittance_block(
        self, block: List[List[str]], block_index: int, bpr_data: Dict, payer_data: Dict = None
    ) -> Dict:
        """
        Parse a single remittance block using extractors directly.
        
        Args:
            block: List of segments representing a remittance block
            block_index: Index of the block in the file
            bpr_data: BPR segment data (payment header information)
            payer_data: Optional payer information from N1*PR segment
            
        Returns:
            Dict containing parsed remittance data with adjustments and service lines
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
        
        # CLP format: CLP*ClaimControlNumber*ClaimStatusCode*ClaimAmount*...
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
                        "group_code": group_code,
                        "reason_code": reason_code,
                        "amount": amount,
                    })
                i += 2
        
        remittance_data["adjustments"] = adjustments
        
        # Extract adjustment codes by group
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
        
        # Extract patient and provider information (NM1 segments)
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
                if patient_nm1 and provider_nm1:
                    break
        
        if patient_nm1:
            remittance_data["patient"] = {
                "name": patient_nm1[3] if len(patient_nm1) > 3 else None,
                "id": patient_nm1[9] if len(patient_nm1) > 9 else None,
            }
        
        if provider_nm1:
            remittance_data["provider"] = {
                "name": provider_nm1[3] if len(provider_nm1) > 3 else None,
                "npi": provider_nm1[9] if len(provider_nm1) > 9 else None,
            }
        
        # Add BPR and payer data if provided
        if bpr_data:
            remittance_data.update(bpr_data)
        if payer_data:
            remittance_data["payer"] = payer_data
        
        remittance_data["is_incomplete"] = len(warnings) > 0
        
        return remittance_data

    def _extract_bpr_segment(self, segments: List[List[str]]) -> Dict:
        """
        Extract BPR (financial information) segment from 835 file.
        
        Args:
            segments: List of EDI segments to search
            
        Returns:
            Dict containing BPR segment data (payment amounts, dates, check numbers)
        """
        bpr_seg = self._find_segment(segments, "BPR")
        if not bpr_seg:
            return {}
        
        # BPR format: BPR*TransactionHandlingCode*TotalPremiumPaymentAmount*...
        return {
            "transaction_handling_code": bpr_seg[1] if len(bpr_seg) > 1 else None,
            "total_payment_amount": self._parse_decimal(bpr_seg[2]) if len(bpr_seg) > 2 else None,
            "credit_debit_flag": bpr_seg[3] if len(bpr_seg) > 3 else None,
            "payment_method_code": bpr_seg[4] if len(bpr_seg) > 4 else None,
            "payment_format_code": bpr_seg[5] if len(bpr_seg) > 5 else None,
            "check_number": bpr_seg[4] if len(bpr_seg) > 4 and bpr_seg[4] else None,
            "effective_payment_date": bpr_seg[16] if len(bpr_seg) > 16 else None,
        }

    def _extract_payer_from_835(self, segments: List[List[str]]) -> Dict:
        """
        Extract payer information from N1*PR segment in 835 file.
        
        Args:
            segments: List of EDI segments to search
            
        Returns:
            Dict containing payer name, address, city, state, and zip code
        """
        payer_data = {}
        
        # Cache termination segment IDs for faster lookup
        termination_segments = {"LX", "CLP", "BPR", "TRN"}
        
        # Find N1*PR segment (payer information)
        segments_len = len(segments)
        for i in range(segments_len):
            seg = segments[i]
            if not seg:
                continue
            if seg[0] == "N1" and len(seg) > 1 and seg[1] == "PR":
                # N1 format: N1*PR*PayerName*N3*Address*N4*City*State*Zip
                payer_data["name"] = seg[2] if len(seg) > 2 else None
                
                # Look for N3 (address) and N4 (city/state/zip) segments that follow
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
                        break
                
                break
        
        return payer_data

    def _get_remittance_blocks(self, segments: List[List[str]]) -> List[List[List[str]]]:
        """
        Get remittance blocks starting with LX segment.
        Each LX segment starts a new claim remittance.
        
        Args:
            segments: List of all EDI segments in the file
            
        Returns:
            List of remittance blocks, where each block is a list of segments
        """
        remittance_blocks = []
        current_block = []
        
        # Pre-allocate if we can estimate
        estimated_blocks = max(1, len(segments) // 30)
        if estimated_blocks > 10:
            remittance_blocks = [None] * min(estimated_blocks, 1000)
            remittance_blocks.clear()
        
        # Cache termination segment IDs for faster lookup
        termination_segments = {"SE", "GE", "IEA"}
        
        for seg in segments:
            if not seg:
                continue
            
            seg_id = seg[0]
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
                # Stop at next LX, SE, GE, or IEA
                if seg_id in termination_segments:
                    # Termination segment - save current block and don't add termination segment
                    remittance_blocks.append(current_block)
                    current_block = []
                else:
                    # Regular segment - add to current block
                    current_block.append(seg)
        
        # Don't forget the last remittance block
        if current_block:
            remittance_blocks.append(current_block)
        
        return remittance_blocks
    
    # Helper methods (reused from EDIParser for direct access without instantiation)
    
    def _split_segments(self, content: str) -> List[List[str]]:
        """
        Split EDI content into segments with optimized memory usage.
        
        Uses efficient string processing optimized for both small and large files.
        
        Args:
            content: The EDI file content as a string
            
        Returns:
            List of segments, where each segment is a list of element strings
        """
        # Remove newlines/carriage returns using cached translation table
        if "\r" in content or "\n" in content:
            content = content.translate(_NEWLINE_TRANSLATION_TABLE)
        
        # Split by segment delimiter (~)
        segment_strings = content.split("~")
        
        # Pre-allocate list to reduce reallocations
        estimated_count = len(segment_strings)
        segments = []
        if estimated_count > 100:
            segments = [None] * min(estimated_count, 10000)
            segments.clear()
        
        # Process each segment string
        for seg_str in segment_strings:
            # Optimize: check if string needs stripping (most don't)
            # Only strip if first/last char is whitespace
            # Use len check to avoid IndexError on empty strings
            if seg_str:
                seg_len = len(seg_str)
                if seg_len > 0 and (seg_str[0].isspace() or seg_str[seg_len - 1].isspace()):
                    seg_str = seg_str.strip()
                    if not seg_str:
                        continue
                # Split by element delimiter (*)
                elements = seg_str.split("*")
                if elements and elements[0]:  # Ensure first element exists
                    segments.append(elements)
        
        return segments
    
    def _detect_file_type(self, segments: List[List[str]]) -> str:
        """
        Detect if file is 837 (claim) or 835 (remittance).
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            File type string ("837" for claims, "835" for remittances)
        """
        # Check GS segment first (most reliable indicator)
        gs_seg = self._find_segment(segments, "GS")
        if gs_seg and len(gs_seg) > 8:
            version = gs_seg[8]
            if "005010X222" in version or "005010X223" in version:
                return "837"
            elif "005010X221" in version:
                return "835"
        
        # Fallback: check for CLM segment (837) or CLP segment (835)
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
        """
        Parse envelope segments (ISA, GS, ST).
        
        Args:
            segments: List of EDI segments to analyze
            
        Returns:
            Dict containing envelope data (ISA, GS, ST segment information)
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
    
    def _get_claim_blocks(self, segments: List[List[str]]) -> List[List[List[str]]]:
        """
        Get claim blocks starting with HL segment where index 3 = '22' (subscriber level).
        
        Args:
            segments: List of all EDI segments in the file
            
        Returns:
            List of claim blocks, where each block is a list of segments
        """
        claim_blocks = []
        current_claim = []
        
        # Pre-allocate list if we can estimate
        estimated_blocks = max(1, len(segments) // 50)
        if estimated_blocks > 10:
            claim_blocks = [None] * min(estimated_blocks, 1000)
            claim_blocks.clear()
        
        for i, seg in enumerate(segments):
            if not seg:
                continue
            
            seg_id = seg[0]
            if not seg_id:
                continue
            
            # Check if this is a subscriber-level HL segment (index 3 = '22')
            if seg_id == "HL":
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
    
    def _parse_837(self, segments: List[List[str]], envelope: Dict, filename: str) -> Dict:
        """
        Parse 837 claim file with optimized batch processing.
        
        Args:
            segments: List of all EDI segments in the file
            envelope: Parsed envelope data
            filename: The name of the file being parsed
            
        Returns:
            Dict containing parsed claims, warnings, and metadata
        """
        logger.info("Parsing 837 claim file", filename=filename, segment_count=len(segments))
        
        # Get claim blocks
        claim_blocks = self._get_claim_blocks(segments)
        
        if not claim_blocks:
            logger.warning("No claim blocks found in 837 file", filename=filename)
            return {
                "file_type": "837",
                "envelope": envelope,
                "claims": [],
                "warnings": ["No claim blocks found"],
            }
        
        # Process in batches for large files
        batch_size = BATCH_SIZE
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
        
        # Pre-allocate parsed_claims list if we know the size
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
            
            # Memory cleanup for large files
            if is_large_file:
                for block in batch:
                    del block
                del batch
                
                if batch_end % (batch_size * 10) == 0:
                    gc.collect(0)
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
        """
        Parse 835 remittance file with optimized batch processing.
        
        Args:
            segments: List of all EDI segments in the file
            envelope: Parsed envelope data
            filename: The name of the file being parsed
            
        Returns:
            Dict containing parsed remittances, warnings, and metadata
        """
        logger.info("Parsing 835 remittance file", filename=filename, segment_count=len(segments))
        
        all_warnings = []
        
        # Extract BPR segment (financial information)
        bpr_data = self._extract_bpr_segment(segments)
        
        # Extract payer information from N1*PR segment
        payer_data = self._extract_payer_from_835(segments)
        
        # Get remittance blocks
        remittance_blocks = self._get_remittance_blocks(segments)
        
        if not remittance_blocks:
            logger.warning("No remittance blocks found in 835 file", filename=filename)
            return {
                "file_type": "835",
                "envelope": envelope,
                "remittances": [],
                "warnings": ["No remittance blocks found"],
            }
        
        # Process in batches for large files
        batch_size = BATCH_SIZE
        parsed_remittances = []
        
        total_blocks = len(remittance_blocks)
        is_large_file = total_blocks > 500
        logger.info(
            "Processing remittance blocks",
            total_blocks=total_blocks,
            batch_size=batch_size,
            filename=filename,
        )
        
        # Pre-allocate parsed_remittances list if we know the size
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
            
            # Memory cleanup for large files
            if is_large_file:
                for block in batch:
                    del block
                del batch
                
                if batch_end % (batch_size * 10) == 0:
                    gc.collect(0)
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
    
    def _find_segment(self, segments: List[List[str]], segment_id: str) -> Optional[List[str]]:
        """
        Find first occurrence of a segment by ID.
        
        Args:
            segments: List of EDI segments to search
            segment_id: The segment identifier to find (e.g., "ISA", "GS", "CLM")
            
        Returns:
            The first matching segment as a list of elements, or None if not found
        """
        try:
            return next(seg for seg in segments if seg and seg[0] == segment_id)
        except (StopIteration, IndexError):
            return None
    
    def _find_segment_in_block(
        self, block: List[List[str]], segment_id: str
    ) -> Optional[List[str]]:
        """
        Find first occurrence of a segment in a claim block.
        
        Args:
            block: List of segments representing a claim or remittance block
            segment_id: The segment identifier to find
            
        Returns:
            The first matching segment as a list of elements, or None if not found
        """
        try:
            return next(seg for seg in block if seg and seg[0] == segment_id)
        except (StopIteration, IndexError):
            return None
    
    def _find_all_segments_in_block(
        self, block: List[List[str]], segment_id: str
    ) -> List[List[str]]:
        """
        Find all occurrences of a segment in a claim block.
        
        Args:
            block: List of segments representing a claim or remittance block
            segment_id: The segment identifier to find
            
        Returns:
            List of all matching segments, each as a list of elements
        """
        result = []
        for seg in block:
            if seg and seg[0] == segment_id:
                result.append(seg)
        return result
    
    def _parse_decimal(self, value: Optional[str]) -> Optional[float]:
        """
        Parse decimal value from EDI string. Optimized to reduce string operations.
        
        Args:
            value: The string representation of the decimal value
            
        Returns:
            The float representation of the value, or None if parsing fails
        """
        if not value:
            return None
        # Optimize: check if string needs stripping (most values don't)
        # Only strip if first/last char is whitespace
        # Use len check to avoid IndexError on empty strings
        value_len = len(value)
        if value_len > 0 and (value[0].isspace() or value[value_len - 1].isspace()):
            value = value.strip()
            if not value:
                return None
        try:
            return float(value)
        except (ValueError, AttributeError, TypeError):
            return None

