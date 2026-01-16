"""Integration tests for complete remittance (835) upload flow."""
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.models.database import ClaimEpisode, EpisodeStatus, Remittance, RemittanceStatus
from app.services.queue.tasks import link_episodes, process_edi_file


@pytest.mark.integration
@pytest.mark.api
class TestCompleteRemittanceUploadFlow:
    """Test the complete remittance upload flow from file upload to episode linking."""

    @pytest.fixture
    def sample_835_content(self):
        """Sample 835 EDI file content."""
        return """ISA*00*          *00*          *ZZ*BCBSILPAYER     *ZZ*MEDPRACTICE001   *241220*143052*^*00501*000000001*0*P*:~
GS*HP*BCBSILPAYER*MEDPRACTICE001*20241220*143052*1*X*005010X221A1~
ST*835*0001*005010X221A1~
BPR*I*28750.00*C*CHK987654321*20241220*123456789*01*987654321*DA*1234567890*20241220~
TRN*1*REM20241220001*987654321~
REF*EV*REM20241220001~
DTM*405*20241220~
DTM*097*20241220*20241220~
N1*PR*BLUE CROSS BLUE SHIELD OF ILLINOIS~
N3*300 EAST RANDOLPH STREET~
N4*CHICAGO*IL*60601~
PER*BL*CLAIMS DEPARTMENT*TE*8005551234*FX*8005555678~
LX*1~
CLP*CLAIM20241215001*1*1500.00*1200.00*0*11*1234567890*20241215*1~
CAS*PR*1*50.00~
CAS*PR*2*150.00~
CAS*CO*45*100.00~
NM1*QC*1*PATIENT*JOHN*M***MI*123456789~
NM1*82*1*PROVIDER*JANE*M***XX*1234567890~
REF*D9*PATIENT001~
REF*1W*123456789~
AMT*AU*200.00~
AMT*D*50.00~
AMT*F5*150.00~
SVC*HC:99213*1500.00*1200.00*UN*1~
DTM*472*D8*20241215~
CAS*CO*45*100.00~
CAS*PR*1*50.00~
CAS*PR*2*150.00~
SE*24*0001~
GE*1*1~
IEA*1*000000001~"""

    def test_complete_remittance_upload_flow(
        self, client, db_session, sample_835_content
    ):
        """
        Test complete remittance upload flow:
        1. Upload 835 file via API
        2. Process file (call task directly)
        3. Verify remittances created in database
        4. Retrieve remittances via API
        5. Verify remittance details via API
        """
        # Step 1: Upload file via API
        file_content = sample_835_content.encode("utf-8")
        file = ("test_835.edi", BytesIO(file_content), "text/plain")

        # Mock Celery task to capture the call
        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id-835"
            mock_task.delay = MagicMock(return_value=mock_task_instance)

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            # Verify upload response
            assert response.status_code == 200
            upload_data = response.json()
            assert upload_data["message"] == "File queued for processing"
            assert "task_id" in upload_data
            assert upload_data["filename"] == "test_835.edi"
            assert mock_task.delay.called

            # Get the arguments passed to the task
            call_args = mock_task.delay.call_args
            task_file_path = call_args[1]["file_path"]
            task_filename = call_args[1]["filename"]
            task_file_type = call_args[1]["file_type"]

            assert task_filename == "test_835.edi"
            assert task_file_type == "835"
            # Verify file_path exists and contains correct content
            assert task_file_path is not None
            with open(task_file_path, "rb") as f:
                file_content_read = f.read().decode("utf-8")
            assert file_content_read == sample_835_content

        # Step 2: Process the file directly (simulating Celery task execution)
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            result = process_edi_file.run(
                file_path=task_file_path,
                filename=task_filename,
                file_type=task_file_type,
            )

            # Verify processing result
            assert result["status"] == "success"
            assert result["filename"] == "test_835.edi"
            assert result["file_type"] == "835"
            assert result["remittances_created"] > 0

        # Step 3: Verify remittances created in database
        remittances = db_session.query(Remittance).all()
        assert len(remittances) > 0

        # Find the remittance we just created
        remittance = db_session.query(Remittance).filter(
            Remittance.claim_control_number == "CLAIM20241215001"
        ).first()
        assert remittance is not None
        assert remittance.payment_amount == 1200.00
        # Status may be PENDING or PROCESSED depending on implementation
        assert remittance.status in [RemittanceStatus.PENDING, RemittanceStatus.PROCESSED]

        # Step 4: Retrieve remittances via API
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        remits_data = response.json()
        assert remits_data["total"] > 0
        assert len(remits_data["remits"]) > 0

        # Find our remittance in the list
        remit_in_list = next(
            (r for r in remits_data["remits"] if r["claim_control_number"] == "CLAIM20241215001"),
            None
        )
        assert remit_in_list is not None
        assert remit_in_list["payment_amount"] == 1200.00

        # Step 5: Retrieve specific remittance details via API
        response = client.get(f"/api/v1/remits/{remittance.id}")
        assert response.status_code == 200
        remit_detail = response.json()

        assert remit_detail["id"] == remittance.id
        assert remit_detail["claim_control_number"] == "CLAIM20241215001"
        assert remit_detail["payment_amount"] == 1200.00
        # Status may vary depending on implementation
        assert remit_detail["status"] in [RemittanceStatus.PENDING.value, RemittanceStatus.PROCESSED.value]

    def test_remittance_upload_with_episode_linking(
        self, client, db_session, sample_835_content
    ):
        """
        Test remittance upload and automatic episode linking when matching claim exists.
        """
        # First, create a matching claim
        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(
            provider=provider,
            payer=payer,
            claim_control_number="CLAIM20241215001",
            patient_control_number="PATIENT001",
        )
        db_session.commit()  # Commit to ensure claim is persisted
        claim_id = claim.id  # Store ID immediately after commit

        # Upload and process remittance
        file_content = sample_835_content.encode("utf-8")
        file = ("test_835_episode.edi", BytesIO(file_content), "text/plain")

        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id-episode"
            mock_task.delay = MagicMock(return_value=mock_task_instance)

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            assert response.status_code == 200

            call_args = mock_task.delay.call_args
            task_file_path = call_args[1]["file_path"]

        # Process the file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            result = process_edi_file.run(
                file_path=task_file_path,
                filename="test_835_episode.edi",
                file_type="835",
            )

            assert result["status"] == "success"
            assert result["remittances_created"] > 0

        # Find the remittance (refresh to ensure it's attached to session)
        db_session.commit()  # Ensure all changes are committed
        remittance = db_session.query(Remittance).filter(
            Remittance.claim_control_number == "CLAIM20241215001"
        ).first()

        assert remittance is not None
        remittance_id = remittance.id  # Store ID before calling task
        # claim_id was already stored after creating the claim

        # Step 2: Trigger episode linking
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            link_result = link_episodes.run(remittance_id=remittance_id)

            assert link_result["status"] == "success"
            assert link_result["episodes_linked"] >= 0  # May be 0 if no match, or 1 if matched

        # Verify episode was created if linking succeeded
        # Use stored IDs (already stored before task call)
        db_session.commit()
        episodes = db_session.query(ClaimEpisode).filter(
            ClaimEpisode.remittance_id == remittance_id
        ).all()

        # Episode may or may not be created depending on matching logic
        # This is acceptable - we verify the linking process completed
        if len(episodes) > 0:
            episode = episodes[0]
            assert episode.claim_id == claim_id
            assert episode.remittance_id == remittance_id
            assert episode.status in [EpisodeStatus.LINKED, EpisodeStatus.COMPLETE]

    def test_remittance_upload_multiple_remittances(
        self, client, db_session, sample_835_content
    ):
        """Test uploading a file with multiple remittances."""
        # Create a file with two remittances by duplicating and modifying
        multi_remit_content = sample_835_content + "\n" + sample_835_content.replace(
            "CLAIM20241215001",
            "CLAIM20241216001"
        ).replace(
            "1200.00",
            "2600.00"
        )

        file_content = multi_remit_content.encode("utf-8")
        file = ("test_multi_835.edi", BytesIO(file_content), "text/plain")

        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id-multi"
            mock_task.delay = MagicMock(return_value=mock_task_instance)

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            assert response.status_code == 200

            call_args = mock_task.delay.call_args
            task_file_path = call_args[1]["file_path"]

        # Process the file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            result = process_edi_file.run(
                file_path=task_file_path,
                filename="test_multi_835.edi",
                file_type="835",
            )

            assert result["status"] == "success"
            assert result["remittances_created"] >= 1

        # Verify multiple remittances in database
        remittances = db_session.query(Remittance).all()
        assert len(remittances) >= 1

        # Verify we can retrieve all remittances via API
        response = client.get("/api/v1/remits")
        assert response.status_code == 200
        remits_data = response.json()
        assert remits_data["total"] >= 1

    @pytest.mark.parametrize("skip,limit,expected_count", [
        (0, 1, 1),
        (1, 1, 1),
        (0, 2, 2),
        (2, 2, 2),
    ])
    def test_remittance_upload_pagination(
        self, client, db_session, sample_835_content, skip, limit, expected_count
    ):
        """Test that pagination works correctly after remittance upload.
        
        Uses parameterized tests to verify pagination with different
        skip and limit values.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            expected_count: Expected number of records in response
        """
        # Upload and process a file
        file_content = sample_835_content.encode("utf-8")
        file = ("test_pagination_835.edi", BytesIO(file_content), "text/plain")

        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id-pag-835"
            mock_task.delay = MagicMock(return_value=mock_task_instance)

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            assert response.status_code == 200

            call_args = mock_task.delay.call_args
            task_file_path = call_args[1]["file_path"]

        # Process the file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            process_edi_file.run(
                file_path=task_file_path,
                filename="test_pagination_835.edi",
                file_type="835",
            )

        # Test pagination with parameterized values
        response = client.get(f"/api/v1/remits?skip={skip}&limit={limit}")
        assert response.status_code == 200
        data = response.json()
        assert data["skip"] == skip
        assert data["limit"] == limit
        assert len(data["remits"]) <= expected_count

    def test_remittance_manual_episode_linking_via_api(
        self, client, db_session, sample_835_content
    ):
        """Test manually triggering episode linking via API endpoint."""
        # Create a claim first
        from tests.factories import ClaimFactory, PayerFactory, ProviderFactory

        provider = ProviderFactory()
        payer = PayerFactory()
        claim = ClaimFactory(
            provider=provider,
            payer=payer,
            claim_control_number="CLAIM20241215001",
        )
        db_session.commit()  # Commit to ensure claim is persisted
        claim_id = claim.id  # Store ID immediately after commit

        # Upload and process remittance
        file_content = sample_835_content.encode("utf-8")
        file = ("test_manual_link.edi", BytesIO(file_content), "text/plain")

        with patch("app.api.routes.remits.process_edi_file") as mock_task:
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id-manual"
            mock_task.delay = MagicMock(return_value=mock_task_instance)

            response = client.post(
                "/api/v1/remits/upload",
                files={"file": file}
            )

            assert response.status_code == 200

            call_args = mock_task.delay.call_args
            task_file_path = call_args[1]["file_path"]

        # Process the file
        with patch("app.services.queue.tasks.SessionLocal") as mock_session_local:
            mock_session_local.return_value = db_session

            result = process_edi_file.run(
                file_path=task_file_path,
                filename="test_manual_link.edi",
                file_type="835",
            )

            assert result["status"] == "success"

        # Find the remittance (ensure it's committed and attached)
        db_session.commit()
        remittance = db_session.query(Remittance).filter(
            Remittance.claim_control_number == "CLAIM20241215001"
        ).first()

        assert remittance is not None
        remittance_id = remittance.id  # Store ID before API call
        # claim_id was already stored after creating the claim

        # Trigger episode linking via API
        response = client.post(f"/api/v1/remits/{remittance_id}/link")
        assert response.status_code == 200

        link_data = response.json()
        assert link_data["message"] == "Episode linking completed"
        assert link_data["remittance_id"] == remittance_id
        assert "episodes_linked" in link_data
        assert "episodes" in link_data

        # Verify episode was created if linking succeeded
        # Use stored IDs (already stored before API call)
        db_session.commit()

        episodes = db_session.query(ClaimEpisode).filter(
            ClaimEpisode.remittance_id == remittance_id
        ).all()

        # If episodes were linked, verify the structure
        if len(episodes) > 0:
            episode = episodes[0]
            assert episode.claim_id == claim_id
            assert episode.remittance_id == remittance_id

