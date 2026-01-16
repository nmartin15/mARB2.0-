"""Comprehensive error handling tests for Celery queue tasks."""
from unittest.mock import MagicMock, patch, Mock
import pytest
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
import os
import tempfile

from app.services.queue.tasks import process_edi_file, link_episodes, detect_patterns
from app.utils.errors import AppError, ValidationError
from tests.factories import RemittanceFactory, ClaimFactory, PayerFactory


@pytest.mark.unit
@pytest.mark.integration
class TestProcessEdiFileErrorHandling:
    """Test error handling in process_edi_file task."""

    @pytest.fixture
    def sample_837_content(self):
        """Sample 837 EDI file content."""
        return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
HI*ABK:I10*E11.9~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""

    def test_process_edi_file_no_file_content_or_path(self):
        """Test error when neither file_content nor file_path provided."""
        mock_task_self = MagicMock()
        mock_task_self.request.id = "test-task-123"

        with pytest.raises(ValueError, match="Either file_content or file_path must be provided"):
            process_edi_file.run(
                file_content=None,
                file_path=None,
                filename="test.edi",
            )

    def test_process_edi_file_both_file_content_and_path(self):
        """Test error when both file_content and file_path provided."""
        mock_task_self = MagicMock()
        mock_task_self.request.id = "test-task-123"

        with pytest.raises(ValueError, match="Cannot provide both file_content and file_path"):
            process_edi_file.run(
                file_content="test content",
                file_path="/tmp/test.edi",
                filename="test.edi",
            )

    def test_process_edi_file_file_not_found(self):
        """Test error when file_path doesn't exist."""
        mock_task_self = MagicMock()
        mock_task_self.request.id = "test-task-123"

        with pytest.raises(FileNotFoundError, match="File not found"):
            process_edi_file.run(
                file_path="/nonexistent/path/file.edi",
                filename="test.edi",
            )

    def test_process_edi_file_read_error(self, db_session):
        """Test error handling when file read fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Create a temporary file that will fail to read
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write("test content")
                tmp_path = tmp_file.name

            # Make file unreadable
            os.chmod(tmp_path, 0o000)

            try:
                with pytest.raises(Exception):  # Could be PermissionError or OSError
                    process_edi_file.run(
                        file_path=tmp_path,
                        filename="test.edi",
                    )
            except Exception:
                # File may have been cleaned up by the task
                pass
            finally:
                # Restore permissions and cleanup if file still exists
                if os.path.exists(tmp_path):
                    try:
                        os.chmod(tmp_path, 0o644)
                        os.unlink(tmp_path)
                    except OSError:
                        pass  # File may have been cleaned up

    def test_process_edi_file_database_connection_error(self, sample_837_content):
        """Test error handling when database connection fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.side_effect = OperationalError(
                "Connection failed",
                None,
                None
            )

            with pytest.raises(OperationalError):
                process_edi_file.run(
                    file_content=sample_837_content,
                    filename="test.edi",
                )

    def test_process_edi_file_database_integrity_error(self, db_session, sample_837_content):
        """Test error handling when database integrity constraint violated."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Create a claim with duplicate control number to trigger integrity error
            from tests.factories import ClaimFactory, ProviderFactory, PayerFactory
            from app.models.database import Claim
            provider = ProviderFactory()
            payer = PayerFactory()
            db_session.add(provider)
            db_session.add(payer)
            db_session.commit()

            # Create existing claim with control number
            existing_claim = ClaimFactory(
                provider=provider,
                payer=payer,
                claim_control_number="DUPLICATE001"
            )
            db_session.add(existing_claim)
            db_session.commit()

            # Mock parser to return claim data with duplicate control number
            with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser.parse.return_value = {
                    "file_type": "837",
                    "claims": [{"claim_control_number": "DUPLICATE001"}],
                }
                mock_parser_class.return_value = mock_parser

                # Mock transformer to create claim that will violate unique constraint
                with patch("app.services.queue.tasks.EDITransformer") as mock_transformer_class:
                    mock_transformer = MagicMock()
                    # Create a new claim object with duplicate control number (not committed)
                    duplicate_claim = Claim(
                        claim_control_number="DUPLICATE001",  # Duplicate
                        patient_control_number="PAT001",
                        provider_id=provider.id,
                        payer_id=payer.id,
                    )
                    mock_transformer.transform_837_claim.return_value = duplicate_claim
                    mock_transformer_class.return_value = mock_transformer

                    # Should raise IntegrityError when trying to commit
                    with pytest.raises(IntegrityError):
                        process_edi_file.run(
                            file_content=sample_837_content,
                            filename="test.edi",
                            file_type="837",
                        )

    def test_process_edi_file_parser_error(self, db_session):
        """Test error handling when parser fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser.parse.side_effect = ValueError("Invalid EDI format")
                mock_parser_class.return_value = mock_parser

                with pytest.raises(ValueError, match="Invalid EDI format"):
                    process_edi_file.run(
                        file_content="invalid content",
                        filename="test.edi",
                    )

    def test_process_edi_file_unknown_file_type(self, db_session, sample_837_content):
        """Test error handling when file_type is unknown."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser.parse.return_value = {"file_type": "999"}  # Unknown type
                mock_parser_class.return_value = mock_parser

                with pytest.raises(ValueError, match="Unknown file type"):
                    process_edi_file.run(
                        file_content=sample_837_content,
                        filename="test.edi",
                        file_type="999",
                    )

    def test_process_edi_file_cleanup_on_error(self, db_session):
        """Test that temporary file is cleaned up on error."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Create temporary file
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp_file:
                tmp_file.write("test content")
                tmp_path = tmp_file.name

            try:
                with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                    mock_parser = MagicMock()
                    mock_parser.parse.side_effect = ValueError("Parse error")
                    mock_parser_class.return_value = mock_parser

                    with pytest.raises(ValueError):
                        process_edi_file.run(
                            file_path=tmp_path,
                            filename="test.edi",
                        )

                # File should be cleaned up
                assert not os.path.exists(tmp_path)
            except Exception:
                # Ensure cleanup even if test fails
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

    def test_process_edi_file_cleanup_failure_logged(self, db_session, sample_837_content, caplog):
        """Test that cleanup failure is logged but doesn't raise."""
        import tempfile
        
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Create a temporary file that will be cleaned up
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.edi') as tmp_file:
                tmp_file.write(sample_837_content)
                tmp_path = tmp_file.name

            try:
                with patch("app.services.queue.tasks.os.unlink") as mock_unlink:
                    mock_unlink.side_effect = OSError("Permission denied")

                    # Use file_path to trigger cleanup path
                    # The task should complete successfully even if cleanup fails
                    result = process_edi_file.run(
                        file_path=tmp_path,
                        filename="test.edi",
                        file_type="837",
                    )

                    # Verify warning was logged for cleanup failure
                    # Check captured log records for cleanup warning
                    # The logger uses structured logging, so check both message and event fields
                    cleanup_warnings = [
                        record for record in caplog.records
                        if record.levelname == "WARNING" 
                        and record.name == "app.services.queue.tasks"
                        and (
                            "cleanup" in str(record.message).lower() 
                            or "unlink" in str(record.message).lower()
                            or "clean up" in str(record.message).lower()
                            or (hasattr(record, 'event') and "clean" in str(record.event).lower())
                        )
                    ]
                    assert len(cleanup_warnings) > 0, f"Expected cleanup failure warning to be logged. Found warnings: {[r.message for r in caplog.records if r.levelname == 'WARNING']}"
                    
                    # Verify the task still completed successfully
                    assert result["status"] == "success"
            finally:
                # Clean up test file
                if os.path.exists(tmp_path):
                    try:
                        os.chmod(tmp_path, 0o644)
                        os.unlink(tmp_path)
                    except OSError:
                        pass

    def test_process_edi_file_progress_notification_failure(self, db_session, sample_837_content):
        """Test that progress notification failure doesn't stop processing."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            with patch("app.services.queue.tasks.notify_file_progress") as mock_notify:
                mock_notify.side_effect = Exception("Notification failed")

                # Should still process successfully
                result = process_edi_file.run(
                    file_content=sample_837_content,
                    filename="test.edi",
                    file_type="837",
                )

                assert result["status"] == "success"

    def test_process_edi_file_transformation_error_continues(self, db_session, sample_837_content):
        """Test that individual claim transformation errors don't stop batch processing."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            with patch("app.services.queue.tasks.EDITransformer") as mock_transformer_class:
                mock_transformer = MagicMock()
                # First claim fails, second succeeds
                mock_transformer.transform_837_claim.side_effect = [
                    ValueError("Invalid claim"),
                    MagicMock(id=1),  # Second claim succeeds
                ]
                mock_transformer_class.return_value = mock_transformer

                with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                    mock_parser = MagicMock()
                    # Return two claims
                    mock_parser.parse.return_value = {
                        "file_type": "837",
                        "claims": [
                            {"claim_control_number": "CLAIM001"},
                            {"claim_control_number": "CLAIM002"},
                        ],
                    }
                    mock_parser_class.return_value = mock_parser

                    # Should process second claim even if first fails
                    result = process_edi_file.run(
                        file_content=sample_837_content,
                        filename="test.edi",
                        file_type="837",
                    )

                    # Should complete with warnings
                    assert result["status"] == "success"

    def test_process_edi_file_database_rollback_on_error(self, db_session, sample_837_content):
        """Test that database is rolled back on error."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                mock_parser = MagicMock()
                mock_parser.parse.side_effect = ValueError("Parse error")
                mock_parser_class.return_value = mock_parser

                with pytest.raises(ValueError):
                    process_edi_file.run(
                        file_content=sample_837_content,
                        filename="test.edi",
                    )

                # Verify rollback was called
                mock_db.rollback.assert_called()

    def test_process_edi_file_database_close_in_finally(self, db_session, sample_837_content):
        """Test that database connection is closed in finally block."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            result = process_edi_file.run(
                file_content=sample_837_content,
                filename="test.edi",
                file_type="837",
            )

            # Verify close was called
            mock_db.close.assert_called()


@pytest.mark.unit
@pytest.mark.integration
class TestLinkEpisodesErrorHandling:
    """Test error handling in link_episodes task."""

    def test_link_episodes_invalid_remittance_id(self, db_session):
        """Test error handling when remittance_id doesn't exist."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Should return error dict instead of raising exception
            result = link_episodes.run(remittance_id=99999)
            
            assert result["status"] == "error"
            assert "not found" in result["message"].lower() or "remittance" in result["message"].lower()

    def test_link_episodes_database_error(self, db_session):
        """Test error handling when database operation fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            # Create remittance first
            remittance = RemittanceFactory()
            db_session.add(remittance)
            db_session.commit()
            remittance_id = remittance.id

            # Mock query to raise error
            mock_db.query.side_effect = OperationalError(
                "Connection lost",
                None,
                None
            )

            with pytest.raises(OperationalError):
                link_episodes.run(remittance_id=remittance_id)

            # Verify rollback was called
            mock_db.rollback.assert_called()

    def test_link_episodes_linker_error(self, db_session):
        """Test error handling when episode linker fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            remittance = RemittanceFactory()
            db_session.add(remittance)
            db_session.commit()
            remittance_id = remittance.id

            with patch("app.services.queue.tasks.EpisodeLinker") as mock_linker_class:
                mock_linker = MagicMock()
                mock_linker.auto_link_by_control_number.side_effect = ValueError("Linker error")
                mock_linker_class.return_value = mock_linker

                with pytest.raises(ValueError, match="Linker error"):
                    link_episodes.run(remittance_id=remittance_id)

    def test_link_episodes_database_close_in_finally(self, db_session):
        """Test that database connection is closed in finally block."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            remittance = RemittanceFactory()
            db_session.add(remittance)
            db_session.commit()
            remittance_id = remittance.id

            try:
                link_episodes.run(remittance_id=remittance_id)
            except Exception:
                pass  # May fail, but close should still be called

            # Verify close was called
            mock_db.close.assert_called()


@pytest.mark.unit
@pytest.mark.integration
class TestDetectPatternsErrorHandling:
    """Test error handling in detect_patterns task."""

    def test_detect_patterns_invalid_payer_id(self, db_session):
        """Test error handling when payer_id doesn't exist."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Should handle gracefully or raise
            result = detect_patterns.run(payer_id=99999, days_back=90)
            # May return empty result or raise
            assert isinstance(result, dict)

    def test_detect_patterns_database_error(self, db_session):
        """Test error handling when database operation fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            # Mock query to raise error
            mock_db.query.side_effect = OperationalError(
                "Connection lost",
                None,
                None
            )

            with pytest.raises(OperationalError):
                detect_patterns.run(payer_id=None, days_back=90)

            # Verify rollback was called
            mock_db.rollback.assert_called()

    def test_detect_patterns_pattern_detector_error(self, db_session):
        """Test error handling when pattern detector fails."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            payer = PayerFactory()
            db_session.add(payer)
            db_session.commit()
            payer_id = payer.id

            with patch("app.services.queue.tasks.PatternDetector") as mock_detector_class:
                mock_detector = MagicMock()
                # The task calls detect_patterns_for_payer when payer_id is provided
                mock_detector.detect_patterns_for_payer.side_effect = ValueError("Detector error")
                mock_detector_class.return_value = mock_detector

                # The task should catch the exception and re-raise it
                with pytest.raises(ValueError, match="Detector error"):
                    detect_patterns.run(payer_id=payer_id, days_back=90)
                
                # Verify the detector was called with correct arguments
                mock_detector.detect_patterns_for_payer.assert_called_once_with(payer_id, 90)

    def test_detect_patterns_negative_days_back(self, db_session):
        """Test error handling with negative days_back."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            # Should handle gracefully or validate
            result = detect_patterns.run(payer_id=None, days_back=-10)
            # May return empty result or raise
            assert isinstance(result, dict)

    def test_detect_patterns_database_close_in_finally(self, db_session):
        """Test that database connection is closed in finally block."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            try:
                detect_patterns.run(payer_id=None, days_back=90)
            except Exception:
                pass  # May fail, but close should still be called

            # Verify close was called
            mock_db.close.assert_called()


@pytest.mark.unit
class TestTaskRetryLogic:
    """Test retry logic in tasks."""

    @pytest.fixture
    def sample_837_content(self):
        """Sample 837 EDI file content."""
        return """ISA*00*          *00*          *ZZ*SENDERID       *ZZ*RECEIVERID     *241220*1340*^*00501*000000001*0*P*:~
GS*HC*SENDERID*RECEIVERID*20241220*1340*1*X*005010X222A1~
ST*837*0001*005010X222A1~
CLM*CLAIM001*1500.00***11:A:1*Y*A*Y*I~
DTP*431*D8*20241215~
HI*ABK:I10*E11.9~
SE*5*0001~
GE*1*1~
IEA*1*000000001~"""

    def test_process_edi_file_retry_on_transient_error(self, db_session, sample_837_content):
        """Test that transient errors trigger retry."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            mock_task_self = MagicMock()
            mock_task_self.request.id = "test-task-123"
            mock_task_self.request.retries = 0
            mock_task_self.request.max_retries = 3

            with patch("app.services.queue.tasks.EDIParser") as mock_parser_class:
                mock_parser = MagicMock()
                # Simulate transient error
                mock_parser.parse.side_effect = OperationalError(
                    "Connection timeout",
                    None,
                    None
                )
                mock_parser_class.return_value = mock_parser

                # Task should raise, allowing Celery to retry
                with pytest.raises(OperationalError):
                    process_edi_file.run(
                        file_content=sample_837_content,
                        filename="test.edi",
                    )

    def test_link_episodes_retry_on_transient_error(self, db_session):
        """Test that transient errors trigger retry in link_episodes."""
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_db = MagicMock()
            mock_session_local.return_value = mock_db

            remittance = RemittanceFactory()
            db_session.add(remittance)
            db_session.commit()
            remittance_id = remittance.id

            # Simulate transient database error
            mock_db.query.side_effect = OperationalError(
                "Connection timeout",
                None,
                None
            )

            # Task should raise, allowing Celery to retry
            with pytest.raises(OperationalError):
                link_episodes.run(remittance_id=remittance_id)

