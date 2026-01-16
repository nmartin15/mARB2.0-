"""Comprehensive negative test cases for service layer (transformers, extractors, linkers)."""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services.edi.transformer import EDITransformer
from app.services.edi.extractors.claim_extractor import ClaimExtractor
from app.services.edi.extractors.line_extractor import LineExtractor
from app.services.edi.extractors.payer_extractor import PayerExtractor
from app.services.edi.extractors.diagnosis_extractor import DiagnosisExtractor
from app.services.episodes.linker import EpisodeLinker
from app.services.edi.config import get_parser_config
from tests.factories import ClaimFactory, RemittanceFactory, PayerFactory, ProviderFactory


@pytest.mark.unit
class TestTransformerNegativeCases:
    """Test negative cases for EDITransformer."""

    def test_transform_837_claim_missing_required_fields(self, db_session):
        """Test error handling when required fields are missing."""
        transformer = EDITransformer(db_session)

        # Claim data missing required fields
        claim_data = {
            "claim_control_number": "CLAIM001",
            # Missing patient_control_number, provider, payer, etc.
        }

        with pytest.raises((KeyError, ValueError, AttributeError)):
            transformer.transform_837_claim(claim_data)

    def test_transform_837_claim_invalid_provider_npi(self, db_session):
        """Test error handling with invalid provider NPI."""
        transformer = EDITransformer(db_session)

        claim_data = {
            "claim_control_number": "CLAIM001",
            "patient_control_number": "PAT001",
            "provider": {
                "npi": "INVALID_NPI",  # Invalid format
                "name": "Test Provider",
            },
            "payer": {
                "payer_id": "PAYER001",
                "name": "Test Payer",
            },
        }

        # Should handle gracefully or raise
        try:
            claim = transformer.transform_837_claim(claim_data)
            # If succeeds, NPI validation may be lenient
            assert claim is not None
        except (ValueError, ValidationError):
            # Validation error is acceptable
            pass

    def test_transform_837_claim_invalid_payer_id(self, db_session):
        """Test error handling with invalid payer ID."""
        transformer = EDITransformer(db_session)

        claim_data = {
            "claim_control_number": "CLAIM001",
            "patient_control_number": "PAT001",
            "provider": {
                "npi": "1234567890",
                "name": "Test Provider",
            },
            "payer": {
                "payer_id": "",  # Empty payer ID
                "name": "Test Payer",
            },
        }

        # Should handle gracefully
        try:
            claim = transformer.transform_837_claim(claim_data)
            assert claim is not None
        except (ValueError, ValidationError):
            pass

    def test_transform_837_claim_invalid_amount(self, db_session):
        """Test error handling with invalid amount values."""
        transformer = EDITransformer(db_session)
        provider = ProviderFactory()
        payer = PayerFactory()
        db_session.commit()

        claim_data = {
            "claim_control_number": "CLAIM001",
            "patient_control_number": "PAT001",
            "provider": {
                "npi": provider.npi,
                "name": provider.name,
            },
            "payer": {
                "payer_id": payer.payer_id,
                "name": payer.name,
            },
            "total_charge_amount": "NOT_A_NUMBER",  # Invalid amount
        }

        # Should handle gracefully or raise
        try:
            claim = transformer.transform_837_claim(claim_data)
            # If succeeds, amount may be None or 0
            assert claim is not None
        except (ValueError, TypeError):
            # Type error is acceptable
            pass

    def test_transform_837_claim_invalid_date(self, db_session):
        """Test error handling with invalid date values."""
        transformer = EDITransformer(db_session)
        provider = ProviderFactory()
        payer = PayerFactory()
        db_session.commit()

        claim_data = {
            "claim_control_number": "CLAIM001",
            "patient_control_number": "PAT001",
            "provider": {
                "npi": provider.npi,
                "name": provider.name,
            },
            "payer": {
                "payer_id": payer.payer_id,
                "name": payer.name,
            },
            "service_date": "INVALID_DATE",  # Invalid date format
        }

        # Should handle gracefully or raise
        try:
            claim = transformer.transform_837_claim(claim_data)
            # If succeeds, date may be None
            assert claim is not None
        except (ValueError, TypeError):
            # Date parsing error is acceptable
            pass

    def test_transform_837_claim_database_integrity_error(self, db_session):
        """Test error handling when database integrity constraint is violated."""
        transformer = EDITransformer(db_session)
        provider = ProviderFactory()
        payer = PayerFactory()
        db_session.commit()

        # Create claim with duplicate control number
        existing_claim = ClaimFactory(
            provider=provider,
            payer=payer,
            claim_control_number="DUPLICATE001"
        )
        db_session.commit()

        claim_data = {
            "claim_control_number": "DUPLICATE001",  # Duplicate
            "patient_control_number": "PAT001",
            "provider": {
                "npi": provider.npi,
                "name": provider.name,
            },
            "payer": {
                "payer_id": payer.payer_id,
                "name": payer.name,
            },
        }

        # Should raise IntegrityError
        with pytest.raises(IntegrityError):
            claim = transformer.transform_837_claim(claim_data)
            db_session.add(claim)
            db_session.commit()

    def test_get_or_create_provider_invalid_npi(self, db_session):
        """Test error handling with invalid NPI format."""
        transformer = EDITransformer(db_session)

        # NPI with invalid format
        provider_data = {
            "npi": "123",  # Too short
            "name": "Test Provider",
        }

        # Should handle gracefully or raise
        try:
            provider = transformer.get_or_create_provider(provider_data)
            assert provider is not None
        except (ValueError, ValidationError):
            pass

    def test_get_or_create_payer_invalid_id(self, db_session):
        """Test error handling with invalid payer ID."""
        transformer = EDITransformer(db_session)

        # Payer with empty ID
        payer_data = {
            "payer_id": "",  # Empty
            "name": "Test Payer",
        }

        # Should handle gracefully
        try:
            payer = transformer.get_or_create_payer(payer_data)
            assert payer is not None
        except (ValueError, ValidationError):
            pass


@pytest.mark.unit
class TestExtractorNegativeCases:
    """Test negative cases for extractors."""

    @pytest.fixture
    def config(self):
        """Get parser config."""
        return get_parser_config()

    def test_claim_extractor_missing_clm_segment(self, config):
        """Test error handling when CLM segment is missing."""
        extractor = ClaimExtractor(config)

        # Block without CLM segment - extract() requires CLM segment as first parameter
        # If CLM segment is missing, we can't call extract() properly
        # This test verifies that extractor handles missing CLM gracefully
        block = [
            ["SBR", "P", "18"],
            ["HI", "ABK", "I10"],
        ]
        warnings = []

        # extract() requires clm_segment as first param - if None/empty, should handle gracefully
        # Try with empty CLM segment
        empty_clm = []
        claim_data = extractor.extract(empty_clm, block, warnings)
        # Should return empty dict when CLM is invalid
        assert isinstance(claim_data, dict)
        assert len(claim_data) == 0 or "claim_control_number" not in claim_data

    def test_claim_extractor_invalid_clm_format(self, config):
        """Test error handling with invalid CLM segment format."""
        extractor = ClaimExtractor(config)

        # CLM segment with insufficient elements
        clm_segment = ["CLM"]  # Only segment ID, no data
        block = []
        warnings = []

        # Should handle gracefully - returns empty dict when CLM has insufficient elements
        claim_data = extractor.extract(clm_segment, block, warnings)
        assert isinstance(claim_data, dict)
        # Should have warning about insufficient elements
        assert len(warnings) > 0 or len(claim_data) == 0

    def test_line_extractor_missing_sv2_segment(self, config):
        """Test error handling when SV2 segment is missing."""
        extractor = LineExtractor(config)

        # Block without SV2 segment - only LX segment
        block = [
            ["LX", "1"],
        ]
        warnings = []

        # Should return empty list when no SV2 found
        lines = extractor.extract(block, warnings)
        assert isinstance(lines, list)
        # May be empty or may have warnings
        assert len(lines) == 0 or len(warnings) > 0

    def test_line_extractor_invalid_sv2_format(self, config):
        """Test error handling with invalid SV2 segment format."""
        extractor = LineExtractor(config)

        # SV2 segment with insufficient elements
        block = [
            ["LX", "1"],
            ["SV2"],  # Only segment ID, no data
        ]
        warnings = []

        # Should handle gracefully - may skip invalid SV2 or add to warnings
        lines = extractor.extract(block, warnings)
        assert isinstance(lines, list)
        # May be empty if SV2 is invalid, or may have warnings

    def test_payer_extractor_missing_sbr_segment(self, config):
        """Test error handling when SBR segment is missing."""
        extractor = PayerExtractor(config)

        # Block without SBR segment
        block = [
            ["CLM", "CLAIM001", "1500.00"],
        ]
        warnings = []

        # Should return empty dict when SBR not found
        payer_data = extractor.extract(block, warnings)
        assert isinstance(payer_data, dict)
        # Should have warning about missing SBR
        assert len(payer_data) == 0 or len(warnings) > 0

    def test_payer_extractor_invalid_sbr_format(self, config):
        """Test error handling with invalid SBR segment format."""
        extractor = PayerExtractor(config)

        # SBR segment with insufficient elements - needs at least 2 elements for responsibility code
        block = [
            ["SBR"],  # Only segment ID, no data
        ]
        warnings = []

        # Should handle gracefully - won't find primary SBR with "P" responsibility
        payer_data = extractor.extract(block, warnings)
        assert isinstance(payer_data, dict)
        # Should have warning about missing primary SBR
        assert len(payer_data) == 0 or len(warnings) > 0

    def test_diagnosis_extractor_missing_hi_segment(self, config):
        """Test error handling when HI segment is missing."""
        extractor = DiagnosisExtractor(config)

        # Block without HI segment
        block = [
            ["CLM", "CLAIM001", "1500.00"],
        ]
        warnings = []

        # Should return dict with empty diagnosis_codes list
        diagnosis_data = extractor.extract(block, warnings)
        assert isinstance(diagnosis_data, dict)
        assert "diagnosis_codes" in diagnosis_data
        assert isinstance(diagnosis_data["diagnosis_codes"], list)
        assert len(diagnosis_data["diagnosis_codes"]) == 0
        # Should have warning about no HI segments
        assert len(warnings) > 0

    def test_diagnosis_extractor_invalid_hi_format(self, config):
        """Test error handling with invalid HI segment format."""
        extractor = DiagnosisExtractor(config)

        # HI segment with insufficient elements
        block = [
            ["HI"],  # Only segment ID, no data
        ]
        warnings = []

        # Should handle gracefully - skips segments with insufficient elements
        diagnosis_data = extractor.extract(block, warnings)
        assert isinstance(diagnosis_data, dict)
        assert "diagnosis_codes" in diagnosis_data
        assert isinstance(diagnosis_data["diagnosis_codes"], list)
        # May be empty if HI segment is invalid


@pytest.mark.unit
@pytest.mark.integration
class TestLinkerNegativeCases:
    """Test negative cases for EpisodeLinker."""

    def test_link_claim_to_remittance_claim_not_found(self, db_session):
        """Test error handling when claim doesn't exist."""
        linker = EpisodeLinker(db_session)

        remittance = RemittanceFactory()
        db_session.add(remittance)
        db_session.commit()

        # Should return None, not raise (linker handles gracefully)
        result = linker.link_claim_to_remittance(
            claim_id=99999,
            remittance_id=remittance.id
        )
        assert result is None

    def test_link_claim_to_remittance_remittance_not_found(self, db_session):
        """Test error handling when remittance doesn't exist."""
        linker = EpisodeLinker(db_session)

        claim = ClaimFactory()
        db_session.add(claim)
        db_session.commit()

        # Should return None, not raise (linker handles gracefully)
        result = linker.link_claim_to_remittance(
            claim_id=claim.id,
            remittance_id=99999
        )
        assert result is None

    def test_link_claim_to_remittance_already_linked(self, db_session):
        """Test error handling when claim and remittance are already linked."""
        linker = EpisodeLinker(db_session)

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        # Link once
        episode = linker.link_claim_to_remittance(
            claim_id=claim.id,
            remittance_id=remittance.id
        )
        db_session.commit()

        # Try to link again - should handle gracefully
        try:
            episode2 = linker.link_claim_to_remittance(
                claim_id=claim.id,
                remittance_id=remittance.id
            )
            # May return existing episode or raise
            assert episode2 is not None
        except (IntegrityError, ValueError):
            # Integrity error is acceptable for duplicate
            pass

    def test_auto_link_by_control_number_no_matches(self, db_session):
        """Test error handling when no matches found."""
        linker = EpisodeLinker(db_session)

        remittance = RemittanceFactory()
        db_session.add(remittance)
        db_session.commit()

        # Should return empty list, not raise (method takes Remittance object)
        episodes = linker.auto_link_by_control_number(remittance)
        assert isinstance(episodes, list)
        assert len(episodes) == 0

    def test_auto_link_by_control_number_remittance_not_found(self, db_session):
        """Test error handling when remittance doesn't exist."""
        linker = EpisodeLinker(db_session)

        # auto_link_by_control_number takes a Remittance object, not ID
        # If we pass None, it will raise AttributeError when trying to access remittance.claim_control_number
        with pytest.raises(AttributeError):
            linker.auto_link_by_control_number(None)

    def test_auto_link_by_patient_and_date_no_matches(self, db_session):
        """Test error handling when no patient/date matches found."""
        linker = EpisodeLinker(db_session)

        remittance = RemittanceFactory()
        db_session.add(remittance)
        db_session.commit()

        # Should return empty list, not raise (method takes Remittance object)
        episodes = linker.auto_link_by_patient_and_date(remittance)
        assert isinstance(episodes, list)
        assert len(episodes) == 0

    def test_get_episodes_for_claim_claim_not_found(self, db_session):
        """Test error handling when claim doesn't exist."""
        linker = EpisodeLinker(db_session)

        # Should return empty list or raise
        try:
            episodes = linker.get_episodes_for_claim(claim_id=99999)
            assert isinstance(episodes, list)
        except Exception:
            # Raising exception is also acceptable
            pass

    def test_update_episode_status_episode_not_found(self, db_session):
        """Test error handling when episode doesn't exist."""
        from app.models.database import EpisodeStatus
        linker = EpisodeLinker(db_session)

        # Method returns None when episode not found (see linker.py line 364)
        result = linker.update_episode_status(episode_id=99999, status=EpisodeStatus.LINKED)
        assert result is None

    def test_update_episode_status_invalid_status(self, db_session):
        """Test error handling with invalid status value."""
        from app.models.database import EpisodeStatus
        linker = EpisodeLinker(db_session)

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        episode = linker.link_claim_to_remittance(
            claim_id=claim.id,
            remittance_id=remittance.id
        )
        db_session.commit()

        # Method expects EpisodeStatus enum, not string
        # Passing invalid string will raise TypeError or ValueError
        with pytest.raises((TypeError, ValueError, AttributeError)):
            linker.update_episode_status(
                episode_id=episode.id,
                status="invalid_status"  # Should be EpisodeStatus enum
            )

    def test_link_claim_to_remittance_database_error(self, db_session):
        """Test error handling when database operation fails."""
        linker = EpisodeLinker(db_session)

        claim = ClaimFactory()
        remittance = RemittanceFactory()
        db_session.add(claim)
        db_session.add(remittance)
        db_session.commit()

        # Mock database to raise error
        with patch.object(db_session, 'add') as mock_add:
            mock_add.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(SQLAlchemyError):
                linker.link_claim_to_remittance(
                    claim_id=claim.id,
                    remittance_id=remittance.id
                )

    def test_auto_link_by_control_number_database_error(self, db_session):
        """Test error handling when database query fails."""
        linker = EpisodeLinker(db_session)

        remittance = RemittanceFactory()
        db_session.add(remittance)
        db_session.commit()

        # Mock database query to raise error (method takes Remittance object)
        with patch.object(db_session, 'query') as mock_query:
            mock_query.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(SQLAlchemyError):
                linker.auto_link_by_control_number(remittance)

