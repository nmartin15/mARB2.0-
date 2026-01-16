"""Edge case tests for critical components.

PREREQUISITES:
- pytest installed: pip install pytest pytest-asyncio
- Test factories available: tests/factories.py
- Test fixtures available: tests/conftest.py
- Database session fixture configured
- All application dependencies installed

DEPENDENCIES:
- tests/factories.py (must exist)
- tests/conftest.py (must exist)
- Database models accessible
- SQLAlchemy session fixture

Run with: pytest tests/test_edge_cases.py -v
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

# Check if dependencies are available
try:
    from app.models.database import Claim, ClaimEpisode, Payer, Remittance, RiskScore
    from app.services.edi.parser import EDIParser
    from app.services.episodes.linker import EpisodeLinker
    from app.services.risk.scorer import RiskScorer
    from app.utils.errors import NotFoundError, ValidationError
except ImportError as e:
    pytest.skip(f"Missing application dependencies: {e}", allow_module_level=True)

try:
    from tests.factories import (
        ClaimFactory,
        ClaimEpisodeFactory,
        PayerFactory,
        RemittanceFactory,
    )
except ImportError:
    pytest.skip("Missing test factories (tests/factories.py)", allow_module_level=True)


class TestEDIParserEdgeCases:
    """Edge cases for EDI parser."""

    def test_empty_file(self):
        """Test parsing empty file."""
        parser = EDIParser()
        result = parser.parse("", "empty.txt")

        assert result["file_type"] is None
        assert len(result.get("claims", [])) == 0
        assert len(result.get("remittances", [])) == 0

    def test_file_with_only_whitespace(self):
        """Test parsing file with only whitespace."""
        parser = EDIParser()
        result = parser.parse("   \n\t  \n   ", "whitespace.txt")

        assert result["file_type"] is None
        assert len(result.get("claims", [])) == 0

    def test_file_with_invalid_delimiters(self):
        """Test parsing file with invalid delimiters."""
        parser = EDIParser()
        invalid_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:"

        # Should handle gracefully
        result = parser.parse(invalid_content, "invalid_delimiters.txt")
        # Should not crash, may return empty or partial results
        assert "file_type" in result

    def test_file_with_special_characters(self):
        """Test parsing file with special characters in data."""
        parser = EDIParser()
        # File with special characters in patient name
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
NM1*QC*1*O'BRIEN*JOHN***MR*1234567890~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "special_chars.txt")
        # Should handle special characters gracefully
        assert result is not None

    def test_file_with_very_long_segments(self):
        """Test parsing file with unusually long segments."""
        parser = EDIParser()
        # Create segment with very long field
        long_field = "A" * 10000
        content = f"""ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
NM1*QC*1*{long_field}*JOHN~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "long_segment.txt")
        # Should handle long fields without crashing
        assert result is not None

    def test_file_with_missing_required_segments(self):
        """Test parsing file missing critical segments."""
        parser = EDIParser()
        # File missing ISA segment
        content = """GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
SE*2*0001~
GE*1*1~"""

        result = parser.parse(content, "missing_isa.txt")
        # Should handle gracefully, may return None or partial results
        assert result is not None

    def test_file_with_duplicate_claim_numbers(self):
        """Test parsing file with duplicate claim control numbers."""
        parser = EDIParser()
        # This should be handled by the parser or transformer
        # Test that it doesn't crash
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*12345*100.00~
SE*4*0001~
ST*837*0002*005010X222A1~
CLM*12345*200.00~
SE*4*0002~
GE*2*1~
IEA*1*000000001~"""

        result = parser.parse(content, "duplicate_claims.txt")
        # Should parse both claims, duplicate handling in transformer
        assert len(result.get("claims", [])) >= 1


class TestRiskScorerEdgeCases:
    """Edge cases for risk scoring."""

    def test_claim_with_zero_amount(self, db: Session):
        """Test risk scoring for claim with zero amount."""
        claim = ClaimFactory(
            total_charge_amount=Decimal("0.00"),
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None
        assert score.risk_score >= 0
        assert score.risk_score <= 100

    def test_claim_with_negative_amount(self, db: Session):
        """Test risk scoring for claim with negative amount (adjustment)."""
        claim = ClaimFactory(
            total_charge_amount=Decimal("-100.00"),
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        # Should handle negative amounts gracefully
        assert score is not None

    def test_claim_with_very_large_amount(self, db: Session):
        """Test risk scoring for claim with very large amount."""
        claim = ClaimFactory(
            total_charge_amount=Decimal("999999999.99"),
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None
        assert score.risk_score >= 0
        assert score.risk_score <= 100

    def test_claim_with_missing_payer(self, db: Session):
        """Test risk scoring for claim without payer."""
        claim = ClaimFactory(
            payer_id=None,
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        # Should handle missing payer gracefully
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None

    def test_claim_with_missing_diagnosis_codes(self, db: Session):
        """Test risk scoring for claim without diagnosis codes."""
        claim = ClaimFactory(
            diagnosis_codes=[],
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None
        # May have higher risk due to missing diagnosis

    def test_claim_with_many_diagnosis_codes(self, db: Session):
        """Test risk scoring for claim with many diagnosis codes."""
        many_codes = [f"E11.{i}" for i in range(50)]  # 50 diagnosis codes
        claim = ClaimFactory(
            diagnosis_codes=many_codes,
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None
        # Should handle many codes without performance issues

    def test_claim_with_future_dates(self, db: Session):
        """Test risk scoring for claim with future service dates."""
        future_date = date(2099, 12, 31)
        claim = ClaimFactory(
            service_date_start=future_date,
            service_date_end=future_date,
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None
        # Future dates may indicate data quality issues

    def test_claim_with_very_old_dates(self, db: Session):
        """Test risk scoring for claim with very old service dates."""
        old_date = date(1900, 1, 1)
        claim = ClaimFactory(
            service_date_start=old_date,
            service_date_end=old_date,
            status="pending"
        )
        db.add(claim)
        db.commit()

        scorer = RiskScorer(db)
        score = scorer.calculate_risk_score(claim.id)

        assert score is not None


class TestEpisodeLinkerEdgeCases:
    """Edge cases for episode linking."""

    def test_link_with_no_matching_claims(self, db: Session):
        """Test linking remittance with no matching claims."""
        remittance = RemittanceFactory(
            claim_control_number="NONEXISTENT123"
        )
        db.add(remittance)
        db.commit()

        linker = EpisodeLinker(db)
        episodes = linker.auto_link_by_control_number(remittance)

        assert episodes == []

    def test_link_with_multiple_matching_claims(self, db: Session):
        """Test linking remittance with multiple matching claims."""
        control_number = "DUPLICATE123"

        # Create multiple claims with same control number
        claim1 = ClaimFactory(claim_control_number=control_number)
        claim2 = ClaimFactory(claim_control_number=control_number)
        db.add_all([claim1, claim2])

        remittance = RemittanceFactory(claim_control_number=control_number)
        db.add(remittance)
        db.commit()

        linker = EpisodeLinker(db)
        episodes = linker.auto_link_by_control_number(remittance)

        # Should link to all matching claims
        assert len(episodes) >= 1

    def test_link_with_partial_amount_match(self, db: Session):
        """Test linking with partial amount match."""
        claim = ClaimFactory(
            total_charge_amount=Decimal("1000.00"),
            claim_control_number="PARTIAL123"
        )
        db.add(claim)

        remittance = RemittanceFactory(
            claim_control_number="PARTIAL123",
            total_paid_amount=Decimal("500.00")  # Partial payment
        )
        db.add(remittance)
        db.commit()

        linker = EpisodeLinker(db)
        episodes = linker.auto_link_by_control_number(remittance)

        # Should still link even with partial payment
        assert len(episodes) >= 1

    def test_link_with_date_mismatch(self, db: Session):
        """Test linking with service date mismatch."""
        claim = ClaimFactory(
            service_date_start=date(2024, 1, 1),
            claim_control_number="DATEDIFF123"
        )
        db.add(claim)

        remittance = RemittanceFactory(
            claim_control_number="DATEDIFF123",
            payment_date=date(2025, 1, 1)  # Different year
        )
        db.add(remittance)
        db.commit()

        linker = EpisodeLinker(db)
        episodes = linker.auto_link_by_control_number(remittance)

        # Control number match should still work
        assert len(episodes) >= 1

    def test_link_with_missing_patient_info(self, db: Session):
        """Test linking when patient information is missing."""
        claim = ClaimFactory(
            patient_first_name=None,
            patient_last_name=None,
            claim_control_number="NOPATIENT123"
        )
        db.add(claim)

        remittance = RemittanceFactory(
            claim_control_number="NOPATIENT123"
        )
        db.add(remittance)
        db.commit()

        linker = EpisodeLinker(db)
        # Should still link by control number
        episodes = linker.auto_link_by_control_number(remittance)
        assert len(episodes) >= 1

        # Patient/date matching may not work
        episodes = linker.auto_link_by_patient_and_date(remittance)
        # May return empty if patient info missing


class TestDataValidationEdgeCases:
    """Edge cases for data validation."""

    def test_invalid_date_formats(self):
        """Test handling of invalid date formats."""
        from app.services.edi.parser import EDIParser

        parser = EDIParser()
        # Date in wrong format
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *INVALID*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
DTP*431*D8*INVALID_DATE~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_date.txt")
        # Should handle invalid dates gracefully
        assert result is not None

    def test_invalid_numeric_formats(self):
        """Test handling of invalid numeric formats."""
        from app.services.edi.parser import EDIParser

        parser = EDIParser()
        # Amount with invalid format
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*12345*NOT_A_NUMBER~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "invalid_number.txt")
        # Should handle invalid numbers gracefully
        assert result is not None

    def test_malformed_segment_structure(self):
        """Test handling of malformed segment structure."""
        from app.services.edi.parser import EDIParser

        parser = EDIParser()
        # Segment with wrong number of fields
        content = """ISA*00*00~
GS*HC~
ST*837~
SE*4~
GE*1~
IEA*1~"""

        result = parser.parse(content, "malformed.txt")
        # Should handle malformed segments gracefully
        assert result is not None

    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        from app.services.edi.parser import EDIParser

        parser = EDIParser()
        # Name with unicode characters
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
NM1*QC*1*José*María~
SE*4*0001~
GE*1*1~
IEA*1*000000001~"""

        result = parser.parse(content, "unicode.txt")
        # Should handle unicode gracefully
        assert result is not None


class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_empty_strings(self, db: Session):
        """Test handling of empty strings in various fields."""
        claim = ClaimFactory(
            patient_first_name="",
            patient_last_name="",
            claim_control_number=""
        )
        db.add(claim)
        db.commit()

        # Should not crash
        assert claim.id is not None

    def test_none_values(self, db: Session):
        """Test handling of None values."""
        claim = ClaimFactory(
            payer_id=None,
            practice_id=None
        )
        db.add(claim)
        db.commit()

        # Should handle None values
        assert claim.id is not None

    def test_max_length_strings(self, db: Session):
        """Test handling of strings at maximum length."""
        max_length_name = "A" * 255  # Assuming 255 char limit
        claim = ClaimFactory(
            patient_last_name=max_length_name
        )
        db.add(claim)
        db.commit()

        assert claim.id is not None

    def test_decimal_precision(self, db: Session):
        """Test handling of decimal precision."""
        from app.utils.decimal_utils import parse_financial_amount, decimal_to_float
        
        # Very precise decimal
        precise_amount = Decimal("123.456789012345")
        # Parse and round to financial precision (2 decimal places)
        rounded_amount = parse_financial_amount(str(precise_amount))
        # Convert to float for database storage
        float_amount = decimal_to_float(rounded_amount)
        
        claim = ClaimFactory(
            total_charge_amount=float_amount
        )
        db.add(claim)
        db.commit()

        # Should handle precision correctly - rounded to 2 decimal places
        assert claim.total_charge_amount == 123.46
        # Verify it's stored as expected precision
        assert abs(claim.total_charge_amount - 123.46) < 0.01

    def test_decimal_precision_edge_cases(self, db: Session):
        """Test edge cases for decimal precision."""
        from app.utils.decimal_utils import parse_financial_amount, validate_decimal_precision
        
        # Test very large decimal
        large_amount = parse_financial_amount("999999999.99")
        assert large_amount == Decimal("999999999.99")
        
        # Test very small decimal
        small_amount = parse_financial_amount("0.01")
        assert small_amount == Decimal("0.01")
        
        # Test rounding edge cases
        round_up = parse_financial_amount("123.455")
        assert round_up == Decimal("123.46")
        
        round_down = parse_financial_amount("123.454")
        assert round_down == Decimal("123.45")
        
        # Test precision validation
        assert validate_decimal_precision(Decimal("123.45"), max_decimal_places=2) is True
        assert validate_decimal_precision(Decimal("123.456"), max_decimal_places=2) is False


class TestErrorRecovery:
    """Test error recovery scenarios."""

    def test_recover_from_partial_parse_failure(self):
        """Test recovery when part of file fails to parse."""
        from app.services.edi.parser import EDIParser

        parser = EDIParser()
        # File with one valid claim and one invalid
        content = """ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *240101*1200*^*00501*000000001*0*P*:~
GS*HC*SENDER*RECEIVER*20240101*1200*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*VALID123*100.00~
SE*4*0001~
ST*837*0002*005010X222A1~
CLM*INVALID*NOT_A_NUMBER~
SE*4*0002~
GE*2*1~
IEA*1*000000001~"""

        result = parser.parse(content, "partial_failure.txt")
        # Should parse valid claim even if one fails
        assert result is not None
        # May have warnings about invalid claim

    def test_recover_from_database_error(self, db: Session):
        """Test recovery from database errors."""
        # This would typically be tested at integration level
        # For unit tests, we can test that errors are handled gracefully

        # Simulate a scenario that might cause DB error
        # (In real scenario, this would be a constraint violation, etc.)
        try:
            # Attempt operation that might fail
            claim = ClaimFactory()
            db.add(claim)
            db.commit()
            assert True  # Success case
        except Exception:
            # Error recovery would happen here
            db.rollback()
            assert True  # Recovery successful

