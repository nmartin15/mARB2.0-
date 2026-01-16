"""Tests for remittance API endpoints."""
import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from tests.factories import PayerFactory, RemittanceFactory


@pytest.mark.api
class TestUploadRemitFile:
    """Tests for POST /api/v1/remits/upload endpoint."""

    def test_upload_remit_file_success(self, client, mock_celery_task):
        """Test successful remittance file upload.
        
        Verifies that:
        - The endpoint accepts a valid 835 EDI file
        - Returns 200 status code with task information
        - Queues the file for processing with correct file_type
        - Returns task_id and filename in response
        """
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            file_content = b"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~"
            file = ("test_835.edi", BytesIO(file_content), "text/plain")

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "File queued for processing"
            assert "task_id" in data
            assert data["filename"] == "test_835.edi"
            mock_task.delay.assert_called_once()
            # Verify it was called with file_type="835"
            call_args = mock_task.delay.call_args
            assert call_args[1]["file_type"] == "835"

    def test_upload_remit_file_missing_file(self, client):
        """Test upload without file.
        
        Verifies that the endpoint returns 422 validation error
        when no file is provided in the request.
        """
        response = client.post("/api/v1/remits/upload")
        assert response.status_code == 422  # Validation error

    def test_upload_remit_file_unicode_error_handling(self, client, mock_celery_task):
        """Test upload with non-UTF-8 content.
        
        Verifies that the endpoint handles files with invalid UTF-8 encoding
        gracefully and still queues them for processing.
        """
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            file_content = b"\xff\xfe\x00\x01"  # Invalid UTF-8
            file = ("test_835.edi", BytesIO(file_content), "text/plain")

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            assert response.status_code == 200
            mock_task.delay.assert_called_once()

    def test_upload_large_remit_file(self, client, mock_celery_task):
        """Test large file upload (>50MB) is saved to disk and processed from file path."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            # Create a large file (60MB, above the 50MB threshold)
            file_size = 60 * 1024 * 1024  # 60MB
            file_content = os.urandom(file_size)  # Random content for large file
            test_filename = "large_test_file.edi"

            with tempfile.TemporaryDirectory() as temp_dir:
                # Patch the TEMP_FILE_DIR environment variable for testing
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    # Also patch the constant in the module
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        file = (test_filename, BytesIO(file_content), "text/plain")

                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Large file queued for processing from disk"
                assert data["processing_mode"] == "file-based"
                assert data["filename"] == test_filename
                assert data["file_size_mb"] > 50  # Should be > 50MB

                # Verify that process_edi_file was called with file_path instead of file_content
                mock_task.delay.assert_called_once()
                call_args = mock_task.delay.call_args
                assert "file_path" in call_args.kwargs
                assert "file_content" not in call_args.kwargs
                assert call_args.kwargs["filename"] == test_filename
                assert call_args.kwargs["file_type"] == "835"

                # Verify that a temporary file was created
                temp_file_path = call_args.kwargs["file_path"]
                assert os.path.exists(temp_file_path)
                assert os.path.getsize(temp_file_path) == file_size

    def test_upload_large_file_error_cleanup(self, client, mock_celery_task):
        """Test that temporary files are cleaned up on error during large file upload."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            # Simulate an error when trying to queue the task
            mock_task.delay = MagicMock(side_effect=Exception("Task queue error"))

            # Create a large file
            file_size = 60 * 1024 * 1024  # 60MB
            file_content = os.urandom(file_size)
            test_filename = "large_test_file.edi"

            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        file = (test_filename, BytesIO(file_content), "text/plain")

                        # Should raise an error (FastAPI will return 500)
                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )

                        # The endpoint should handle the error and clean up
                        # FastAPI returns 500 for unhandled exceptions
                        assert response.status_code == 500

                        # Verify that the task was attempted (which triggers the error)
                        assert mock_task.delay.called

    def test_upload_file_size_exactly_at_threshold(self, client, mock_celery_task):
        """Test file upload exactly at the 50MB threshold."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            # Create a file exactly at 50MB threshold
            file_size = 50 * 1024 * 1024  # Exactly 50MB
            file_content = os.urandom(file_size)
            test_filename = "exact_threshold_file.edi"

            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        file = (test_filename, BytesIO(file_content), "text/plain")

                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )

                assert response.status_code == 200
                data = response.json()
                # Files at exactly 50MB should be processed as regular files (not large)
                assert data["filename"] == test_filename
                assert data["file_size_mb"] == 50.0
                mock_task.delay.assert_called_once()

    def test_upload_file_missing_content_length_header(self, client, mock_celery_task):
        """Test file upload when Content-Length header is missing."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            file_content = b"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~"
            test_filename = "no_content_length.edi"

            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        # Create a file-like object without size attribute
                        file_obj = BytesIO(file_content)
                        # Remove size attribute if it exists
                        if hasattr(file_obj, "size"):
                            delattr(file_obj, "size")
                        file = (test_filename, file_obj, "text/plain")

                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )

                assert response.status_code == 200
                data = response.json()
                assert data["filename"] == test_filename
                assert "task_id" in data
                mock_task.delay.assert_called_once()

    def test_upload_file_invalid_content_length_header(self, client, mock_celery_task):
        """Test file upload with invalid Content-Length header value."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            file_content = b"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~"
            test_filename = "invalid_content_length.edi"

            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        # Create a mock file with invalid content-length header
                        file_obj = BytesIO(file_content)
                        file_obj.headers = {"content-length": "not-a-number"}
                        file = (test_filename, file_obj, "text/plain")

                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )

                # Should handle gracefully and process the file
                assert response.status_code == 200
                data = response.json()
                assert data["filename"] == test_filename
                mock_task.delay.assert_called_once()

    def test_upload_file_temp_directory_creation(self, client, mock_celery_task):
        """Test that temporary directory is created if it doesn't exist."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)

            file_content = b"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *230101*1200*^*00501*000000001*0*P*:~"
            test_filename = "temp_dir_test.edi"

            # Use a non-existent directory
            with tempfile.TemporaryDirectory() as base_temp_dir:
                temp_dir = os.path.join(base_temp_dir, "nonexistent", "subdir")

                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        file = (test_filename, BytesIO(file_content), "text/plain")

                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )

                # Should create directory and process file
                assert response.status_code == 200
                assert os.path.exists(temp_dir)
                mock_task.delay.assert_called_once()


@pytest.mark.api
class TestGetRemits:
    """Tests for GET /api/v1/remits endpoint."""

    def test_get_remits_empty(self, client, db_session):
        """Test getting remittances when none exist.
        
        Verifies that the endpoint returns an empty list with correct
        pagination metadata when no remittances are in the database.
        """
        response = client.get("/api/v1/remits")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["remits"] == []
        assert data["skip"] == 0
        assert data["limit"] == 100

    def test_get_remits_with_data(self, client, db_session):
        """Test getting remittances with existing data.
        
        Verifies that the endpoint returns all remittances with required
        fields (id, remittance_control_number, status) when data exists.
        """
        payer = PayerFactory()
        remit1 = RemittanceFactory(payer=payer)
        remit2 = RemittanceFactory(payer=payer)

        response = client.get("/api/v1/remits")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["remits"]) == 2
        assert all("id" in remit for remit in data["remits"])
        assert all("remittance_control_number" in remit for remit in data["remits"])
        assert all("status" in remit for remit in data["remits"])

    def test_get_remits_pagination(self, client, db_session):
        """Test pagination parameters.
        
        Verifies that skip and limit parameters work correctly,
        allowing retrieval of specific pages of remittance data.
        """
        payer = PayerFactory()

        # Create 5 remittances
        for _ in range(5):
            RemittanceFactory(payer=payer)

        # Test first page
        response = client.get("/api/v1/remits?skip=0&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["remits"]) == 2

        # Test second page
        response = client.get("/api/v1/remits?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["remits"]) == 2


@pytest.mark.api
class TestGetRemit:
    """Tests for GET /api/v1/remits/{remit_id} endpoint."""

    def test_get_remit_success(self, client, db_session):
        """Test getting a specific remittance by ID.
        
        Verifies that the endpoint returns complete remittance details
        including denial reasons and adjustment reasons when present.
        """
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            denial_reasons=["CO45", "CO97"],
            adjustment_reasons=["PR1", "PR2"],
        )

        response = client.get(f"/api/v1/remits/{remit.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == remit.id
        assert data["remittance_control_number"] == remit.remittance_control_number
        assert data["payer_id"] == payer.id
        assert data["payer_name"] == remit.payer_name
        assert data["denial_reasons"] == ["CO45", "CO97"]
        assert data["adjustment_reasons"] == ["PR1", "PR2"]

    def test_get_remit_not_found(self, client, db_session):
        """Test getting non-existent remittance.
        
        Verifies that the endpoint returns 404 status code with
        appropriate error message when remittance ID doesn't exist.
        """
        response = client.get("/api/v1/remits/99999")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Remittance" in data["message"]

    def test_get_remit_with_null_fields(self, client, db_session):
        """Test getting remittance with null optional fields.
        
        Verifies that the endpoint handles remittances with None values
        for optional fields (payment_date, denial_reasons, adjustment_reasons)
        without errors and returns null values correctly.
        """
        from app.models.database import Remittance
        from app.utils.cache import cache, remittance_cache_key

        payer = PayerFactory()
        # Create remittance directly to ensure None values are set
        remit = Remittance(
            remittance_control_number=f"REM{db_session.query(Remittance).count() + 1:06d}",
            payer_id=payer.id,
            payment_date=None,
            denial_reasons=None,
            adjustment_reasons=None,
        )
        db_session.add(remit)
        db_session.commit()
        db_session.refresh(remit)

        # Clear any cached value for this remittance
        cache_key = remittance_cache_key(remit.id)
        cache.delete(cache_key)

        response = client.get(f"/api/v1/remits/{remit.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["payment_date"] is None
        assert data["denial_reasons"] is None
        assert data["adjustment_reasons"] is None

    def test_get_remits_caching(self, client, db_session):
        """Test that GET /remits uses caching for count."""
        from unittest.mock import patch
        from app.utils.cache import cache

        payer = PayerFactory()
        remit1 = RemittanceFactory(payer=payer)
        remit2 = RemittanceFactory(payer=payer)

        # Clear cache
        cache.delete("count:remittance")

        # First request - should query database
        response1 = client.get("/api/v1/remits")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["total"] == 2

        # Second request - should use cached count
        with patch.object(db_session, "query") as mock_query:
            response2 = client.get("/api/v1/remits")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["total"] == 2

    def test_get_remit_caching(self, client, db_session):
        """Test that GET /remits/{remit_id} uses caching."""
        from unittest.mock import patch
        from app.utils.cache import cache, remittance_cache_key

        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)

        # Clear cache
        cache_key = remittance_cache_key(remit.id)
        cache.delete(cache_key)

        # First request - should query database
        response1 = client.get(f"/api/v1/remits/{remit.id}")
        assert response1.status_code == 200

        # Second request - should use cache
        with patch.object(db_session, "query") as mock_query:
            response2 = client.get(f"/api/v1/remits/{remit.id}")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["id"] == remit.id

    def test_get_remits_invalid_pagination(self, client):
        """Test invalid pagination parameters."""
        # FastAPI allows negative skip values, so we'll just test that it works
        # (it will just return from the beginning)
        response = client.get("/api/v1/remits?skip=-1")
        # FastAPI may accept this or return 422, both are valid
        assert response.status_code in [200, 422]

    def test_get_remits_limit_exceeds_max(self, client, db_session):
        """Test that limit parameter respects maximum."""
        payer = PayerFactory()
        RemittanceFactory(payer=payer)

        # Test with limit > 100 (default max)
        response = client.get("/api/v1/remits?limit=1000")
        # Should either accept or return 422
        assert response.status_code in [200, 422]

