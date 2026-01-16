"""Extract payer information from SBR/NM1 segments."""
from typing import Dict, List

from app.services.edi.config import PAYER_RESPONSIBILITY_SEQ_MAP, ParserConfig
from app.services.edi.validator import SegmentValidator
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PayerExtractor:
    """Extract payer/subscriber information."""

    def __init__(self, config: ParserConfig):
        self.config = config
        self.validator = SegmentValidator(config)

    def extract(self, block: List[List[str]], warnings: List[str]) -> Dict:
        """Extract payer data from SBR and NM1 segments."""
        payer_data = {}

        # Find primary payer (SBR with P)
        primary_sbr = self._find_sbr_by_responsibility(block, "P")
        if primary_sbr:
            sbr_data = self._extract_sbr_data(primary_sbr, warnings)
            payer_data.update(sbr_data)

            # Find corresponding NM1 PR (payer) segment
            nm1_pr = self._find_nm1_after_sbr(block, primary_sbr, "PR")
            if nm1_pr:
                nm1_data = self._extract_nm1_data(nm1_pr, warnings)
                payer_data.update(nm1_data)
            else:
                warnings.append("NM1 PR segment not found for primary payer")
        else:
            warnings.append("Primary payer SBR segment not found")

        return payer_data

    def _find_sbr_by_responsibility(self, block: List[List[str]], responsibility: str) -> List[str]:
        """Find SBR segment with specific responsibility code."""
        for seg in block:
            if seg and len(seg) > 0 and seg[0] == "SBR":
                if len(seg) > 1 and seg[1] == responsibility:
                    return seg
        return None

    def _find_nm1_after_sbr(
        self, block: List[List[str]], sbr_segment: List[str], entity_id: str
    ) -> List[str]:
        """Find NM1 segment with entity ID that follows SBR."""
        sbr_index = None
        for i, seg in enumerate(block):
            if seg == sbr_segment:
                sbr_index = i
                break

        if sbr_index is None:
            return None

        # Look for NM1 with entity_id after this SBR
        for i in range(sbr_index + 1, len(block)):
            seg = block[i]
            if seg and len(seg) > 0:
                if seg[0] == "NM1" and len(seg) > 1 and seg[1] == entity_id:
                    return seg
                # Stop if we hit another SBR
                if seg[0] == "SBR":
                    break

        return None

    def _extract_sbr_data(self, sbr_seg: List[str], warnings: List[str]) -> Dict:
        """Extract data from SBR segment."""
        sbr_data = {}

        if len(sbr_seg) < 2:
            warnings.append("SBR segment has insufficient elements")
            return sbr_data

        # Payer responsibility sequence (SBR01)
        responsibility = self.validator.safe_get_element(sbr_seg, 1)
        sbr_data["payer_responsibility"] = responsibility
        sbr_data["payer_responsibility_desc"] = PAYER_RESPONSIBILITY_SEQ_MAP.get(
            responsibility, "Unknown"
        )

        # Individual relationship code (SBR02)
        sbr_data["relationship_code"] = self.validator.safe_get_element(sbr_seg, 2)

        # Claim filing indicator (SBR09)
        if len(sbr_seg) > 9:
            sbr_data["claim_filing_indicator"] = self.validator.safe_get_element(sbr_seg, 9)

        return sbr_data

    def _extract_nm1_data(self, nm1_seg: List[str], warnings: List[str]) -> Dict:
        """Extract data from NM1 segment."""
        nm1_data = {}

        if len(nm1_seg) < 10:
            warnings.append("NM1 segment has insufficient elements")
            return nm1_data

        # Entity name (NM103)
        nm1_data["payer_name"] = self.validator.safe_get_element(nm1_seg, 3)

        # Identification code qualifier (NM108)
        nm1_data["payer_id_qualifier"] = self.validator.safe_get_element(nm1_seg, 8)

        # Payer identifier (NM109)
        nm1_data["payer_id"] = self.validator.safe_get_element(nm1_seg, 9)

        return nm1_data

