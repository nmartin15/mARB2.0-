"""True streaming EDI parser that processes segments incrementally."""
import gc
from typing import Dict, List, Optional, Generator, Iterator, Union, TextIO, Tuple
from io import StringIO

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

# Try to import performance monitor, but make it optional
try:
    from app.services.edi.performance_monitor import PerformanceMonitor
    PERFORMANCE_MONITORING_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITORING_AVAILABLE = False
    PerformanceMonitor = None


class StreamingEDIParser:
    """
    True streaming EDI parser that processes segments incrementally.
    
    This parser reads and processes segments one at a time, yielding claims/remittances
    as they are completed. This provides maximum memory efficiency for large files.
    """

    def __init__(self, practice_id: Optional[str] = None, auto_detect_format: bool = True):
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

    def parse(
        self, 
        file_content: Optional[str] = None, 
        file_path: Optional[str] = None,
        filename: str = "unknown"
    ) -> Dict:
        """
        Parse EDI file with true streaming processing.
        
        Supports both string content and file path inputs.
        Processes segments incrementally and yields results as they're completed.
        
        Args:
            file_content: EDI file content as string (for small files)
            file_path: Path to EDI file (for large files)
            filename: Name of the file being parsed
            
        Returns:
            Dict with parsed data and parsing metadata
        """
        logger.info(
            "Starting streaming EDI parsing",
            filename=filename,
            practice_id=self.practice_id,
            has_file_content=file_content is not None,
            has_file_path=file_path is not None,
        )

        # Validate input - check for empty files
        if file_content is not None:
            if not file_content or not file_content.strip():
                logger.error(
                    "Empty EDI file content provided",
                    filename=filename,
                    practice_id=self.practice_id,
                )
                raise ValueError(f"EDI file '{filename}' is empty or contains only whitespace")
        
        # Import os for file operations
        import os
        
        if file_path:
            if not os.path.exists(file_path):
                logger.error(
                    "EDI file not found",
                    filename=filename,
                    file_path=file_path,
                    practice_id=self.practice_id,
                )
                raise FileNotFoundError(f"EDI file not found: {file_path}")
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error(
                    "Empty EDI file",
                    filename=filename,
                    file_path=file_path,
                    practice_id=self.practice_id,
                )
                raise ValueError(f"EDI file '{filename}' is empty (0 bytes)")

        # Start performance monitoring for large files
        monitor = None
        if PERFORMANCE_MONITORING_AVAILABLE:
            file_size = len(file_content.encode("utf-8")) if file_content else 0
            if file_path:
                file_size = os.path.getsize(file_path)
            if file_size > 1024 * 1024:  # >1MB
                monitor = PerformanceMonitor(f"streaming_parse_edi_{filename}")
                monitor.start()
                monitor.checkpoint("start", {"file_size_mb": file_size / (1024 * 1024)})

        # Create segment generator
        if file_path:
            segment_gen = self._read_segments_from_file(file_path)
        elif file_content:
            segment_gen = self._read_segments_from_string(file_content)
        else:
            raise ValueError("Either file_content or file_path must be provided")

        # Parse envelope segments first (ISA, GS, ST)
        envelope_data, file_type, initial_segments = self._parse_envelope_streaming(segment_gen)

        if monitor:
            monitor.checkpoint("envelope_parsed", {"file_type": file_type})

        # Process file based on type
        if file_type == "837":
            result = self._parse_837_streaming(
                segment_gen, envelope_data, initial_segments, filename, monitor
            )
        elif file_type == "835":
            result = self._parse_835_streaming(
                segment_gen, envelope_data, initial_segments, filename, monitor
            )
        else:
            if monitor:
                monitor.finish()
            raise ValueError(f"Unknown file type: {file_type}")

        if monitor:
            perf_summary = monitor.finish()
            result["_performance"] = perf_summary

        return result

    def _read_segments_from_string(self, content: str) -> Generator[List[str], None, None]:
        """
        Read segments from string content incrementally.
        
        Yields segments one at a time as they are parsed.
        Optimized string operations:
        - Uses cached translation table for newline removal
        - Uses string slicing instead of character-by-character with list appends
        - Reduces memory allocations by processing in chunks
        """
        # Remove newlines/carriage returns in one pass using cached translation table
        if "\r" in content or "\n" in content:
            content = content.translate(_NEWLINE_TRANSLATION_TABLE)

        # Optimized: Use split() for segment delimiters, then process elements
        # This is much faster than character-by-character processing
        segment_strings = content.split("~")
        
        for seg_str in segment_strings:
            if not seg_str:
                continue
            
            # Split by element delimiter (*) - faster than character-by-character
            elements = seg_str.split("*")
            
            # Filter out empty elements (can occur with trailing delimiters)
            if elements:
                # Only yield non-empty segments
                if elements[0]:  # First element (segment ID) must exist
                    yield elements

    def _read_segments_from_file(self, file_path: str) -> Generator[List[str], None, None]:
        """
        Read segments from file incrementally.
        
        Yields segments one at a time as they are read from the file.
        This provides true streaming for very large files.
        Optimized string operations:
        - Uses list accumulation instead of string concatenation
        - Processes segments using split() instead of character-by-character
        - Reduces memory allocations
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            # Use list for buffer accumulation (faster than string concatenation)
            buffer_parts = []
            buffer_size = 0

            # Read file in chunks for efficiency
            chunk_size = 8192  # 8KB chunks

            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                # Accumulate in list instead of string concatenation
                buffer_parts.append(chunk)
                buffer_size += len(chunk)

                # Process when buffer is large enough or at end
                # Join buffer parts and process segments
                if buffer_size >= chunk_size * 2:  # Process when buffer is 2x chunk size
                    buffer = "".join(buffer_parts)
                    # Remove newlines using cached translation table
                    buffer = buffer.translate(_NEWLINE_TRANSLATION_TABLE)
                    
                    # Find last complete segment (ends with ~)
                    last_segment_end = buffer.rfind("~")
                    if last_segment_end >= 0:
                        # Process complete segments
                        to_process = buffer[:last_segment_end + 1]
                        remaining = buffer[last_segment_end + 1:]
                        
                        # Split and yield segments
                        segment_strings = to_process.split("~")
                        for seg_str in segment_strings:
                            if not seg_str:
                                continue
                            elements = seg_str.split("*")
                            if elements and elements[0]:  # First element (segment ID) must exist
                                yield elements
                        
                        # Reset buffer with remaining unprocessed data
                        buffer_parts = [remaining] if remaining else []
                        buffer_size = len(remaining)
                    else:
                        # No complete segments yet, keep accumulating
                        buffer_parts = [buffer]
                        buffer_size = len(buffer)

            # Process remaining buffer
            if buffer_parts:
                buffer = "".join(buffer_parts)
                # Remove newlines using cached translation table
                buffer = buffer.translate(_NEWLINE_TRANSLATION_TABLE)
                
                # Process all remaining segments
                segment_strings = buffer.split("~")
                for seg_str in segment_strings:
                    if not seg_str:
                        continue
                    elements = seg_str.split("*")
                    if elements and elements[0]:  # First element (segment ID) must exist
                        yield elements

    def _parse_envelope_streaming(
        self, segment_gen: Generator[List[str], None, None]
    ) -> Tuple[Dict, str, List[List[str]]]:
        """
        Parse envelope segments (ISA, GS, ST) from streaming generator.
        
        Returns:
            Tuple of (envelope_data, file_type, initial_segments_buffer)
            
        Raises:
            ValueError: If required envelope segments are missing or file is invalid
        """
        envelope = {}
        warnings = []
        initial_segments = []
        file_type = None
        segment_count = 0

        # Process segments until we have envelope info
        for seg in segment_gen:
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

        # Validate that we found required envelope segments
        if segment_count == 0:
            logger.error(
                "No segments found in EDI file",
                practice_id=self.practice_id,
            )
            raise ValueError("Invalid EDI file: No segments found. File may be empty or malformed.")
        
        if "isa" not in envelope:
            logger.error(
                "Missing ISA segment in EDI file",
                segments_found=segment_count,
                practice_id=self.practice_id,
            )
            raise ValueError(
                "Invalid EDI file: Missing required ISA (Interchange Control Header) segment. "
                "File may be malformed or not a valid EDI file."
            )
        
        if "gs" not in envelope:
            logger.error(
                "Missing GS segment in EDI file",
                segments_found=segment_count,
                practice_id=self.practice_id,
            )
            raise ValueError(
                "Invalid EDI file: Missing required GS (Functional Group Header) segment. "
                "File may be malformed or not a valid EDI file."
            )
        
        if "st" not in envelope:
            logger.error(
                "Missing ST segment in EDI file",
                segments_found=segment_count,
                practice_id=self.practice_id,
            )
            raise ValueError(
                "Invalid EDI file: Missing required ST (Transaction Set Header) segment. "
                "File may be malformed or not a valid EDI file."
            )

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
            logger.warning(
                "Could not determine file type from envelope, defaulting to 837",
                practice_id=self.practice_id,
            )
            file_type = "837"

        if warnings:
            logger.warning("Envelope parsing warnings", warnings=warnings, practice_id=self.practice_id)

        return envelope, file_type, initial_segments

    def _parse_837_streaming(
        self,
        segment_gen: Generator[List[str], None, None],
        envelope: Dict,
        initial_segments: List[List[str]],
        filename: str,
        monitor: Optional[PerformanceMonitor] = None,
    ) -> Dict:
        """
        Parse 837 claim file with true streaming processing.
        
        Processes segments incrementally and yields claims as blocks are completed.
        """
        logger.info("Parsing 837 claim file (streaming mode)", filename=filename)

        parsed_claims = []
        all_warnings = []
        current_claim_block = []
        segment_count = 0
        claim_count = 0

        # Build current claim block from initial segments if it was started
        # (but don't process it yet - wait for generator to complete it)
        for seg in initial_segments:
            if not seg or len(seg) == 0:
                continue

            seg_id = seg[0]

            # Check if this is a subscriber-level HL segment (index 3 = '22')
            if seg_id == "HL":
                if len(seg) >= 4 and seg[3] == "22":
                    # New claim block - if we have a previous one, it should have been completed
                    # Start new claim block
                    if current_claim_block:
                        # This shouldn't happen, but handle it gracefully
                        logger.warning(
                            "Found new claim block while previous block incomplete",
                            filename=filename,
                        )
                    current_claim_block = [seg]
                elif current_claim_block:
                    # HL segment but not subscriber level - add to current claim
                    current_claim_block.append(seg)
            elif current_claim_block:
                # Add segment to current claim block
                current_claim_block.append(seg)

            segment_count += 1

        # Process remaining segments from generator
        termination_segments = {"SE", "GE", "IEA"}

        for seg in segment_gen:
            if not seg or len(seg) == 0:
                continue

            segment_count += 1
            seg_id = seg[0]

            # Check if this is a subscriber-level HL segment (index 3 = '22')
            if seg_id == "HL":
                if len(seg) >= 4 and seg[3] == "22":
                    # New claim block - process previous if exists
                    if current_claim_block:
                        try:
                            claim_data = self._parse_claim_block(current_claim_block, claim_count)
                            parsed_claims.append(claim_data)
                            claim_count += 1
                            if claim_data.get("warnings"):
                                all_warnings.extend(claim_data["warnings"])

                            # Memory cleanup for large files
                            if claim_count % 100 == 0:
                                gc.collect(0)  # Collect generation 0 only
                        except Exception as e:
                            logger.error(
                                "Failed to parse claim block",
                                block_index=claim_count,
                                error=str(e),
                                exc_info=True,
                            )
                            all_warnings.append(f"Failed to parse claim block {claim_count}: {str(e)}")
                        current_claim_block = []

                    # Start new claim block
                    current_claim_block.append(seg)
                elif current_claim_block:
                    # HL segment but not subscriber level - add to current claim
                    current_claim_block.append(seg)
            elif current_claim_block:
                # Add segment to current claim block
                if seg_id in termination_segments:
                    # Termination segment - process current block and stop
                    # Don't add termination segment to block
                    try:
                        claim_data = self._parse_claim_block(current_claim_block, claim_count)
                        parsed_claims.append(claim_data)
                        claim_count += 1
                        if claim_data.get("warnings"):
                            all_warnings.extend(claim_data["warnings"])
                    except Exception as e:
                        logger.error(
                            "Failed to parse claim block",
                            block_index=claim_count,
                            error=str(e),
                            exc_info=True,
                        )
                        all_warnings.append(f"Failed to parse claim block {claim_count}: {str(e)}")
                    current_claim_block = []  # Clear block to prevent reprocessing
                    break
                else:
                    current_claim_block.append(seg)

            # Log progress for large files
            if segment_count > 0 and segment_count % 10000 == 0:
                logger.info(
                    "Streaming parsing progress",
                    segments_processed=segment_count,
                    claims_parsed=claim_count,
                )

        # Process last claim block if exists (only if we didn't break due to termination)
        if current_claim_block:
            try:
                claim_data = self._parse_claim_block(current_claim_block, claim_count)
                parsed_claims.append(claim_data)
                if claim_data.get("warnings"):
                    all_warnings.extend(claim_data["warnings"])
            except Exception as e:
                logger.error(
                    "Failed to parse final claim block",
                    block_index=claim_count,
                    error=str(e),
                    exc_info=True,
                )
                all_warnings.append(f"Failed to parse final claim block: {str(e)}")

        if monitor:
            monitor.checkpoint("parsing_complete", {"claims_parsed": len(parsed_claims)})

        logger.info(
            "837 file parsing complete (streaming)",
            filename=filename,
            claims_parsed=len(parsed_claims),
            segments_processed=segment_count,
            warnings_count=len(all_warnings),
        )

        return {
            "file_type": "837",
            "envelope": envelope,
            "claims": parsed_claims,
            "warnings": all_warnings,
            "claim_count": len(parsed_claims),
        }

    def _parse_835_streaming(
        self,
        segment_gen: Generator[List[str], None, None],
        envelope: Dict,
        initial_segments: List[List[str]],
        filename: str,
        monitor: Optional[PerformanceMonitor] = None,
    ) -> Dict:
        """
        Parse 835 remittance file with true streaming processing.
        
        Processes segments incrementally and yields remittances as blocks are completed.
        """
        logger.info("Parsing 835 remittance file (streaming mode)", filename=filename)

        parsed_remittances = []
        all_warnings = []
        current_remittance_block = []
        segment_count = 0
        remittance_count = 0
        bpr_data = {}
        payer_data = {}

        # Extract BPR and payer info from initial segments
        for seg in initial_segments:
            if not seg or len(seg) == 0:
                continue

            seg_id = seg[0]

            # Extract BPR segment
            if seg_id == "BPR" and not bpr_data:
                bpr_data = {
                    "transaction_handling_code": seg[1] if len(seg) > 1 else None,
                    "total_payment_amount": self._parse_decimal(seg[2]) if len(seg) > 2 else None,
                    "credit_debit_flag": seg[3] if len(seg) > 3 else None,
                    "payment_method_code": seg[4] if len(seg) > 4 else None,
                    "payment_format_code": seg[5] if len(seg) > 5 else None,
                    "check_number": seg[4] if len(seg) > 4 and seg[4] else None,
                    "effective_payment_date": seg[16] if len(seg) > 16 else None,
                }

            # Extract payer from N1*PR segment
            if seg_id == "N1" and len(seg) > 1 and seg[1] == "PR" and not payer_data:
                payer_data["name"] = seg[2] if len(seg) > 2 else None
                # Look for N3 and N4 segments that follow
                seg_index = initial_segments.index(seg)
                for i in range(seg_index + 1, min(seg_index + 6, len(initial_segments))):
                    next_seg = initial_segments[i]
                    if not next_seg or len(next_seg) == 0:
                        continue
                    next_seg_id = next_seg[0]
                    if next_seg_id == "N3":
                        payer_data["address"] = next_seg[1] if len(next_seg) > 1 else None
                    elif next_seg_id == "N4":
                        payer_data["city"] = next_seg[1] if len(next_seg) > 1 else None
                        payer_data["state"] = next_seg[2] if len(next_seg) > 2 else None
                        payer_data["zip"] = next_seg[3] if len(next_seg) > 3 else None
                    elif next_seg_id in {"LX", "CLP", "BPR", "TRN"}:
                        break

            # Check if this is an LX segment (starts a new remittance block)
            if seg_id == "LX":
                if current_remittance_block:
                    # Process previous remittance block
                    try:
                        remittance_data = self._parse_remittance_block(
                            current_remittance_block, remittance_count, bpr_data, payer_data
                        )
                        parsed_remittances.append(remittance_data)
                        remittance_count += 1
                        if remittance_data.get("warnings"):
                            all_warnings.extend(remittance_data["warnings"])
                    except Exception as e:
                        logger.error(
                            "Failed to parse remittance block",
                            block_index=remittance_count,
                            error=str(e),
                            exc_info=True,
                        )
                        all_warnings.append(
                            f"Failed to parse remittance block {remittance_count}: {str(e)}"
                        )
                    current_remittance_block = []

                # Start new remittance block
                current_remittance_block.append(seg)
            elif current_remittance_block:
                # Add segment to current remittance block
                current_remittance_block.append(seg)

            segment_count += 1

        # Process remaining segments from generator
        termination_segments = {"SE", "GE", "IEA"}

        for seg in segment_gen:
            if not seg or len(seg) == 0:
                continue

            segment_count += 1
            seg_id = seg[0]

            # Extract BPR segment if not already found
            if seg_id == "BPR" and not bpr_data:
                bpr_data = {
                    "transaction_handling_code": seg[1] if len(seg) > 1 else None,
                    "total_payment_amount": self._parse_decimal(seg[2]) if len(seg) > 2 else None,
                    "credit_debit_flag": seg[3] if len(seg) > 3 else None,
                    "payment_method_code": seg[4] if len(seg) > 4 else None,
                    "payment_format_code": seg[5] if len(seg) > 5 else None,
                    "check_number": seg[4] if len(seg) > 4 and seg[4] else None,
                    "effective_payment_date": seg[16] if len(seg) > 16 else None,
                }

            # Extract payer from N1*PR segment if not already found
            if seg_id == "N1" and len(seg) > 1 and seg[1] == "PR" and not payer_data:
                payer_data["name"] = seg[2] if len(seg) > 2 else None
                # Look ahead for N3 and N4 segments (will be handled in next iterations)

            # Check if this is an LX segment (starts a new remittance block)
            if seg_id == "LX":
                if current_remittance_block:
                    # Process previous remittance block
                    try:
                        remittance_data = self._parse_remittance_block(
                            current_remittance_block, remittance_count, bpr_data, payer_data
                        )
                        parsed_remittances.append(remittance_data)
                        remittance_count += 1
                        if remittance_data.get("warnings"):
                            all_warnings.extend(remittance_data["warnings"])

                        # Memory cleanup for large files
                        if remittance_count % 100 == 0:
                            gc.collect(0)  # Collect generation 0 only
                    except Exception as e:
                        logger.error(
                            "Failed to parse remittance block",
                            block_index=remittance_count,
                            error=str(e),
                            exc_info=True,
                        )
                        all_warnings.append(
                            f"Failed to parse remittance block {remittance_count}: {str(e)}"
                        )
                    current_remittance_block = []

                # Start new remittance block
                current_remittance_block.append(seg)
            elif current_remittance_block:
                # Add segment to current remittance block
                # Also check for N3/N4 segments for payer info
                if seg_id == "N3" and payer_data and "address" not in payer_data:
                    payer_data["address"] = seg[1] if len(seg) > 1 else None
                elif seg_id == "N4" and payer_data and "city" not in payer_data:
                    payer_data["city"] = seg[1] if len(seg) > 1 else None
                    payer_data["state"] = seg[2] if len(seg) > 2 else None
                    payer_data["zip"] = seg[3] if len(seg) > 3 else None

                if seg_id in termination_segments:
                    # Termination segment - process current block and stop
                    # Don't add termination segment to block
                    if current_remittance_block:
                        try:
                            remittance_data = self._parse_remittance_block(
                                current_remittance_block, remittance_count, bpr_data, payer_data
                            )
                            parsed_remittances.append(remittance_data)
                            remittance_count += 1
                            if remittance_data.get("warnings"):
                                all_warnings.extend(remittance_data["warnings"])
                        except Exception as e:
                            logger.error(
                                "Failed to parse remittance block",
                                block_index=remittance_count,
                                error=str(e),
                                exc_info=True,
                            )
                            all_warnings.append(
                                f"Failed to parse remittance block {remittance_count}: {str(e)}"
                            )
                    current_remittance_block = []  # Clear block to prevent reprocessing
                    break
                else:
                    current_remittance_block.append(seg)

            # Log progress for large files
            if segment_count > 0 and segment_count % 10000 == 0:
                logger.info(
                    "Streaming parsing progress",
                    segments_processed=segment_count,
                    remittances_parsed=remittance_count,
                )

        # Process last remittance block if exists (only if we didn't break due to termination)
        if current_remittance_block:
            try:
                remittance_data = self._parse_remittance_block(
                    current_remittance_block, remittance_count, bpr_data, payer_data
                )
                parsed_remittances.append(remittance_data)
                if remittance_data.get("warnings"):
                    all_warnings.extend(remittance_data["warnings"])
            except Exception as e:
                logger.error(
                    "Failed to parse final remittance block",
                    block_index=remittance_count,
                    error=str(e),
                    exc_info=True,
                )
                all_warnings.append(f"Failed to parse final remittance block: {str(e)}")

        if monitor:
            monitor.checkpoint("parsing_complete", {"remittances_parsed": len(parsed_remittances)})

        logger.info(
            "835 file parsing complete (streaming)",
            filename=filename,
            remittances_parsed=len(parsed_remittances),
            segments_processed=segment_count,
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

    def _parse_claim_block(self, block: List[List[str]], block_index: int) -> Dict:
        """Parse a single claim block (reused from original parser)."""
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
        """Parse a single remittance block (reused from original parser)."""
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
            service_line = {
                "line_number": svc_idx + 1,
                "service_code": svc_seg[1] if len(svc_seg) > 1 else None,
                "charge_amount": self._parse_decimal(svc_seg[2]) if len(svc_seg) > 2 else None,
                "payment_amount": self._parse_decimal(svc_seg[3]) if len(svc_seg) > 3 else None,
                "product_service_id": svc_seg[4] if len(svc_seg) > 4 else None,
                "quantity": self._parse_decimal(svc_seg[5]) if len(svc_seg) > 5 else None,
            }

            # Find CAS segments that follow this SVC (service-level adjustments)
            svc_position = None
            block_len = len(block)
            for i in range(block_len):
                if block[i] is svc_seg or block[i] == svc_seg:
                    svc_position = i
                    break

            if svc_position is not None:
                service_adjustments = []
                termination_segments = {"SVC", "CLP", "LX"}
                for i in range(svc_position + 1, block_len):
                    seg = block[i]
                    if not seg:
                        continue
                    seg_id = seg[0]
                    if seg_id == "CAS":
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
        """Parse decimal value from EDI string. Optimized to reduce string operations."""
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

    def _find_segment_in_block(
        self, block: List[List[str]], segment_id: str
    ) -> Optional[List[str]]:
        """Find first occurrence of a segment in a claim block."""
        try:
            return next(seg for seg in block if seg and seg[0] == segment_id)
        except (StopIteration, IndexError):
            return None

    def _find_all_segments_in_block(
        self, block: List[List[str]], segment_id: str
    ) -> List[List[str]]:
        """Find all occurrences of a segment in a claim block."""
        result = []
        for seg in block:
            if seg and seg[0] == segment_id:
                result.append(seg)
        return result

