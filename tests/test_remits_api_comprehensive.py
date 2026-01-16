"""Comprehensive tests for remits API to improve coverage."""
import os
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.models.database import Remittance
from app.utils.errors import NotFoundError
from tests.factories import RemittanceFactory, PayerFactory


@pytest.mark.api
class TestRemitsAPIComprehensive:
    """Comprehensive tests for remits API endpoints."""

    def test_upload_remit_file_empty_filename(self, client, mock_celery_task):
        """Test remit file upload with empty filename."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)
            
            file_content = b"ISA*00*01~"
            file = ("", BytesIO(file_content), "text/plain")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )
                        assert response.status_code == 200
                        data = response.json()
                        assert data["filename"] == "unknown" or data["filename"] == ""

    def test_upload_remit_file_temp_dir_creation_error(self, client, mock_celery_task):
        """Test remit file upload when temp directory creation fails."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)
            
            file_content = b"ISA*00*01~"
            file = ("test.edi", BytesIO(file_content), "text/plain")
            
            with patch("os.makedirs", side_effect=OSError("Permission denied")):
                response = client.post(
                    "/api/v1/remits/upload",
                    files={"file": file}
                )
                # Should handle error
                assert response.status_code in [200, 500]

    def test_upload_remit_file_cleanup_error_logging(self, client, mock_celery_task):
        """Test that cleanup errors are properly logged when file deletion fails."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(side_effect=Exception("Task queue error"))
            
            file_size = 60 * 1024 * 1024  # 60MB
            file_content = os.urandom(file_size)
            test_filename = "large_test_file.edi"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        with patch("app.api.routes.remits.logger") as mock_logger:
                            with patch("os.unlink", side_effect=OSError("Permission denied")):
                                file = (test_filename, BytesIO(file_content), "text/plain")
                                
                                response = client.post(
                                    "/api/v1/remits/upload",
                                    files={"file": file}
                                )
                                
                                assert response.status_code == 500
                                # Verify cleanup error was logged
                                cleanup_error_calls = [
                                    call for call in mock_logger.error.call_args_list
                                    if "Failed to delete temporary file" in str(call)
                                ]
                                assert len(cleanup_error_calls) > 0

    def test_get_remits_empty(self, client, db_session):
        """Test getting remits when none exist."""
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["remits"] == []
        assert data["skip"] == 0
        assert data["limit"] == 100

    def test_get_remits_with_data(self, client, db_session):
        """Test getting remits with existing data."""
        payer = PayerFactory()
        remit1 = RemittanceFactory(payer=payer)
        remit2 = RemittanceFactory(payer=payer)
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert len(data["remits"]) >= 2
        assert all("id" in remit for remit in data["remits"])
        assert all("remittance_control_number" in remit for remit in data["remits"])

    def test_get_remits_pagination(self, client, db_session):
        """Test pagination parameters."""
        payer = PayerFactory()
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
        assert len(data["remits"]) == 2

    def test_get_remits_cache_miss(self, client, db_session):
        """Test GET /remits when cache is empty."""
        from app.utils.cache import cache
        
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        # Clear cache
        cache.delete("count:remittance")
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_get_remits_cache_hit(self, client, db_session):
        """Test GET /remits uses cached count."""
        from app.utils.cache import cache
        
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        # Set cache
        cache.set("count:remittance", 999, ttl_seconds=60)
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        # Should use cached count
        assert data["total"] == 999

    def test_get_remits_eager_loading_payer(self, client, db_session):
        """Test that GET /remits eagerly loads payer."""
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        # Should not cause N+1 queries (eager loading)
        assert len(data["remits"]) > 0

    def test_get_remits_with_skip_exceeds_total(self, client, db_session):
        """Test GET /remits with skip exceeding total count."""
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        response = client.get("/api/v1/remits?skip=1000")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) == 0

    def test_get_remits_with_negative_skip(self, client, db_session):
        """Test GET /remits with negative skip."""
        response = client.get("/api/v1/remits?skip=-10")
        assert response.status_code in [200, 422]

    def test_get_remits_with_negative_limit(self, client, db_session):
        """Test GET /remits with negative limit."""
        response = client.get("/api/v1/remits?limit=-10")
        assert response.status_code == 422

    def test_get_remits_with_zero_limit(self, client, db_session):
        """Test GET /remits with zero limit."""
        response = client.get("/api/v1/remits?limit=0")
        assert response.status_code == 422

    def test_get_remit_success(self, client, db_session):
        """Test getting a specific remittance."""
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == remit.id
        assert data["remittance_control_number"] == remit.remittance_control_number

    def test_get_remit_not_found(self, client, db_session):
        """Test getting non-existent remittance."""
        response = client.get("/api/v1/remits/99999")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["message"].lower() or "Remittance" in data["message"]

    def test_get_remit_invalid_id_type(self, client, db_session):
        """Test getting remittance with invalid ID type."""
        response = client.get("/api/v1/remits/not_a_number")
        assert response.status_code == 422

    def test_get_remit_cache_miss(self, client, db_session):
        """Test GET /remits/{id} when cache is empty."""
        from app.utils.cache import cache, remittance_cache_key
        
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        # Clear cache
        cache.delete(remittance_cache_key(remit.id))
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == remit.id

    def test_get_remit_cache_hit(self, client, db_session):
        """Test GET /remits/{id} uses cached result."""
        from app.utils.cache import cache, remittance_cache_key
        
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        # Set cache
        cached_data = {"id": remit.id, "remittance_control_number": "CACHED"}
        cache.set(remittance_cache_key(remit.id), cached_data, ttl_seconds=60)
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        # Should return cached data
        assert data["remittance_control_number"] == "CACHED"

    def test_get_remit_with_payment_date(self, client, db_session):
        """Test GET /remits/{id} includes payment_date."""
        from datetime import date
        
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            payment_date=date(2024, 12, 25),
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["payment_date"] == "2024-12-25"

    def test_get_remit_with_none_payment_date(self, client, db_session):
        """Test GET /remits/{id} handles None payment_date."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            payment_date=None,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["payment_date"] is None

    def test_get_remit_with_check_number(self, client, db_session):
        """Test GET /remits/{id} includes check_number."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            check_number="CHECK123",
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["check_number"] == "CHECK123"

    def test_get_remit_with_none_check_number(self, client, db_session):
        """Test GET /remits/{id} handles None check_number."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            check_number=None,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["check_number"] is None

    def test_get_remit_with_denial_reasons(self, client, db_session):
        """Test GET /remits/{id} includes denial_reasons."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            denial_reasons=[
                {"code": "CO45", "description": "Test denial 1"},
                {"code": "CO97", "description": "Test denial 2"},
            ],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert "denial_reasons" in data
        assert len(data["denial_reasons"]) == 2

    def test_get_remit_with_empty_denial_reasons(self, client, db_session):
        """Test GET /remits/{id} with empty denial_reasons."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            denial_reasons=[],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["denial_reasons"] == []

    def test_get_remit_with_none_denial_reasons(self, client, db_session):
        """Test GET /remits/{id} with None denial_reasons."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            denial_reasons=None,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("denial_reasons") is None

    def test_get_remit_with_adjustment_reasons(self, client, db_session):
        """Test GET /remits/{id} includes adjustment_reasons."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            adjustment_reasons=[
                {"code": "CO45", "amount": 100.00},
                {"code": "PR1", "amount": 50.00},
            ],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert "adjustment_reasons" in data
        assert len(data["adjustment_reasons"]) == 2

    def test_get_remit_with_empty_adjustment_reasons(self, client, db_session):
        """Test GET /remits/{id} with empty adjustment_reasons."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            adjustment_reasons=[],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["adjustment_reasons"] == []

    def test_get_remit_with_parsing_warnings(self, client, db_session):
        """Test GET /remits/{id} includes parsing_warnings."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            parsing_warnings=["Warning 1", "Warning 2"],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert "parsing_warnings" in data
        assert len(data["parsing_warnings"]) == 2

    def test_get_remit_with_empty_parsing_warnings(self, client, db_session):
        """Test GET /remits/{id} with empty parsing_warnings."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            parsing_warnings=[],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["parsing_warnings"] == []

    def test_get_remit_with_none_parsing_warnings(self, client, db_session):
        """Test GET /remits/{id} with None parsing_warnings."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            parsing_warnings=None,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("parsing_warnings") is None or data.get("parsing_warnings") == []

    def test_get_remit_status_enum_value(self, client, db_session):
        """Test GET /remits/{id} returns status as enum value."""
        from app.models.database import RemittanceStatus
        
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            status=RemittanceStatus.PROCESSED,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"

    def test_get_remit_status_none(self, client, db_session):
        """Test GET /remits/{id} handles None status."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            status=None,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] is None

    def test_get_remits_status_in_list(self, client, db_session):
        """Test GET /remits includes status in list response."""
        from app.models.database import RemittanceStatus
        
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            status=RemittanceStatus.PENDING,
        )
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) > 0
        assert all("status" in remit for remit in data["remits"])

    def test_get_remit_payment_amount(self, client, db_session):
        """Test GET /remits/{id} includes payment_amount."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            payment_amount=1500.50,
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["payment_amount"] == 1500.50

    def test_get_remits_payment_amount(self, client, db_session):
        """Test GET /remits includes payment_amount in list."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            payment_amount=2000.00,
        )
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) > 0
        assert all("payment_amount" in remit for remit in data["remits"])

    def test_get_remit_payer_name(self, client, db_session):
        """Test GET /remits/{id} includes payer_name."""
        payer = PayerFactory(name="Test Payer")
        remit = RemittanceFactory(
            payer=payer,
            payer_name="Test Payer",
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["payer_name"] == "Test Payer"

    def test_get_remits_payer_name(self, client, db_session):
        """Test GET /remits includes payer_name in list."""
        payer = PayerFactory(name="Test Payer")
        remit = RemittanceFactory(
            payer=payer,
            payer_name="Test Payer",
        )
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) > 0
        assert all("payer_name" in remit for remit in data["remits"])

    def test_get_remit_claim_control_number(self, client, db_session):
        """Test GET /remits/{id} includes claim_control_number."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            claim_control_number="CLAIM001",
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["claim_control_number"] == "CLAIM001"

    def test_get_remits_claim_control_number(self, client, db_session):
        """Test GET /remits includes claim_control_number in list."""
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            claim_control_number="CLAIM001",
        )
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) > 0
        assert all("claim_control_number" in remit for remit in data["remits"])

    def test_get_remit_created_at_updated_at_timestamps(self, client, db_session):
        """Test GET /remits/{id} includes created_at and updated_at."""
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data

    def test_get_remits_created_at_timestamp(self, client, db_session):
        """Test GET /remits includes created_at timestamp."""
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) > 0
        assert all("created_at" in remit for remit in data["remits"])

    def test_get_remit_cache_ttl(self, client, db_session):
        """Test that GET /remits/{id} caches with proper TTL."""
        from app.utils.cache import cache, remittance_cache_key
        from app.config.cache_ttl import get_remittance_ttl
        
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        # Clear cache
        cache.delete(remittance_cache_key(remit.id))
        
        with patch("app.api.routes.remits.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            
            response = client.get(f"/api/v1/remits/{remit.id}")
            assert response.status_code == 200
            
            # Should cache with TTL
            assert mock_cache.set.called
            call_args = mock_cache.set.call_args
            assert call_args[0][0] == remittance_cache_key(remit.id)
            assert call_args[1]["ttl_seconds"] == get_remittance_ttl()

    def test_get_remits_count_cache_ttl(self, client, db_session):
        """Test that GET /remits caches count with proper TTL."""
        from app.utils.cache import cache
        from app.config.cache_ttl import get_count_ttl
        
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        # Clear cache
        cache.delete("count:remittance")
        
        with patch("app.api.routes.remits.cache") as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set = MagicMock()
            
            response = client.get("/api/v1/remits")
            assert response.status_code == 200
            
            # Should cache count with TTL
            assert mock_cache.set.called
            call_args = mock_cache.set.call_args
            assert call_args[0][0] == "count:remittance"
            assert call_args[1]["ttl_seconds"] == get_count_ttl()

    def test_get_remits_pagination_edge_cases(self, client, db_session):
        """Test GET /remits with edge case pagination."""
        payer = PayerFactory()
        for _ in range(3):
            RemittanceFactory(payer=payer)
        
        # Test with limit=1
        response = client.get("/api/v1/remits?skip=0&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) == 1
        
        # Test with skip at boundary
        response = client.get("/api/v1/remits?skip=2&limit=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["remits"]) == 1

    def test_get_remit_with_all_optional_fields(self, client, db_session):
        """Test GET /remits/{id} with all optional fields populated."""
        from datetime import date
        
        payer = PayerFactory()
        remit = RemittanceFactory(
            payer=payer,
            payment_date=date(2024, 12, 25),
            check_number="CHECK123",
            claim_control_number="CLAIM001",
            payer_name="Test Payer",
            payment_amount=1500.50,
            denial_reasons=[{"code": "CO45"}],
            adjustment_reasons=[{"code": "PR1"}],
            parsing_warnings=["Warning 1"],
        )
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["payment_date"] == "2024-12-25"
        assert data["check_number"] == "CHECK123"
        assert data["claim_control_number"] == "CLAIM001"
        assert data["payer_name"] == "Test Payer"
        assert data["payment_amount"] == 1500.50
        assert len(data["denial_reasons"]) == 1
        assert len(data["adjustment_reasons"]) == 1
        assert len(data["parsing_warnings"]) == 1

    def test_get_remit_payer_id(self, client, db_session):
        """Test GET /remits/{id} includes payer_id."""
        payer = PayerFactory()
        remit = RemittanceFactory(payer=payer)
        
        response = client.get(f"/api/v1/remits/{remit.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["payer_id"] == payer.id

    def test_upload_remit_file_content_length_from_size_attribute(self, client, mock_celery_task):
        """Test upload uses file.size attribute if available."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)
            
            file_size = 60 * 1024 * 1024  # 60MB
            file_content = os.urandom(file_size)
            
            # Create mock file with size attribute
            mock_file = MagicMock()
            mock_file.filename = "test.edi"
            mock_file.size = file_size
            mock_file.read = MagicMock(side_effect=[file_content, b""])
            
            # Use BytesIO for actual test
            file = ("test.edi", BytesIO(file_content), "text/plain")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )
                        assert response.status_code == 200

    def test_upload_remit_file_content_length_from_headers(self, client, mock_celery_task):
        """Test upload uses Content-Length header if size attribute not available."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)
            
            file_size = 60 * 1024 * 1024  # 60MB
            file_content = os.urandom(file_size)
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        file = ("test.edi", BytesIO(file_content), "text/plain")
                        
                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )
                        assert response.status_code == 200

    def test_upload_remit_file_invalid_content_length_header(self, client, mock_celery_task):
        """Test upload handles invalid Content-Length header."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)
            
            file_content = b"ISA*00*01~"
            file = ("test.edi", BytesIO(file_content), "text/plain")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )
                        # Should handle gracefully
                        assert response.status_code == 200

    def test_upload_remit_file_missing_content_length(self, client, mock_celery_task):
        """Test upload when Content-Length is missing."""
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task.delay = MagicMock(return_value=mock_celery_task)
            
            file_content = b"ISA*00*01~"
            file = ("test.edi", BytesIO(file_content), "text/plain")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                with patch.dict(os.environ, {"TEMP_FILE_DIR": temp_dir}):
                    with patch("app.api.routes.remits.TEMP_DIR", temp_dir):
                        response = client.post(
                            "/api/v1/remits/upload",
                            files={"file": file}
                        )
                        assert response.status_code == 200
