"""
Claim endpoints for 837 EDI file processing.

This module provides API endpoints for uploading, retrieving, and managing
healthcare claims (837 EDI format). Claims are processed asynchronously via
Celery tasks and can be queried with pagination and filtering.

**Documentation References:**
- API Documentation: `API_DOCUMENTATION.md` → "Claims (837 Files)" section
- EDI Format Guide: `EDI_FORMAT_GUIDE.md`
- EDI Processing: `.cursorrules` → "EDI Processing" section
- Celery Tasks: `app/services/queue/tasks.py` (module docstring)
- Quick Reference: `DOCUMENTATION_QUICK_REFERENCE.md` → "I'm adding a new API endpoint"
"""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.config.database import get_db
from app.config.cache_ttl import get_claim_ttl, get_count_ttl
from app.services.queue.tasks import process_edi_file
from app.utils.logger import get_logger
from app.utils.cache import cache, claim_cache_key, count_cache_key

router = APIRouter()
logger = get_logger(__name__)

# Configuration constants
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB - use file-based processing
TEMP_DIR = os.getenv("TEMP_FILE_DIR", "/tmp/marb_edi_files")


@router.post("/claims/upload")
async def upload_claim_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload and process 837 claim file.
    
    This endpoint accepts EDI 837 claim files and queues them for processing.
    The file is processed asynchronously via Celery tasks.
    
    **File Processing:**
    - Small files (<50MB): Processed in memory for better performance
    - Large files (>=50MB): Saved to temporary storage and processed from disk
    
    **File Format:**
    - Accepts EDI 837 (Professional/Institutional) claim files
    - File extension: .edi, .txt, or any text format
    - Encoding: UTF-8 (other encodings handled with error recovery)
    
    **Response:**
    - Returns task_id for tracking processing status
    - File is queued immediately, processing happens asynchronously
    
    **Error Handling:**
    - Temporary files are automatically cleaned up on errors
    - Invalid files are still queued but will fail during processing
    """
    filename = file.filename or "unknown"
    logger.info("Received claim file upload", filename=filename)
    
    # Check file size from Content-Length header if available
    content_length = None
    if hasattr(file, "size") and file.size:
        content_length = file.size
    elif hasattr(file, "headers"):
        content_length_header = file.headers.get("content-length")
        if content_length_header:
            try:
                content_length = int(content_length_header)
            except (ValueError, TypeError):
                pass
    
    # For files with known large size, stream directly to disk
    if content_length and content_length > LARGE_FILE_THRESHOLD:
        # Ensure temp directory exists
        os.makedirs(TEMP_DIR, exist_ok=True)
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='wb',
            delete=False,
            dir=TEMP_DIR,
            prefix=f"edi_837_{filename}_",
            suffix=".edi"
        )
        temp_file_path = temp_file.name
        
        try:
            # Stream file directly to disk
            file_size = 0
            chunk_size = 8192  # 8KB chunks
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                temp_file.write(chunk)
                file_size += len(chunk)
            temp_file.close()
            
            file_size_mb = file_size / (1024 * 1024)
            logger.info(
                "Saved large file to temporary storage",
                filename=filename,
                temp_path=temp_file_path,
                size_mb=round(file_size_mb, 2),
            )
            
            # Queue task with file path instead of content
            task = process_edi_file.delay(
                file_path=temp_file_path,
                filename=filename,
                file_type="837",
            )
            
            return {
                "message": "Large file queued for processing from disk",
                "task_id": task.id,
                "filename": filename,
                "file_size_mb": round(file_size_mb, 2),
                "processing_mode": "file-based",
            }
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_file_path)
            except:
                pass
            logger.error("Failed to save large file", error=str(e), filename=filename)
            raise
    
    # For smaller files, stream directly to temporary file in chunks
    # This avoids loading the entire file into memory
    # Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode='wb',
        delete=False,
        dir=TEMP_DIR,
        prefix=f"edi_837_{filename}_",
        suffix=".edi"
    )
    temp_file_path = temp_file.name
    file_size = 0
    
    try:
        # Stream file in chunks directly to disk without accumulating in memory
        chunk_size = 8192  # 8KB chunks
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            temp_file.write(chunk)
            file_size += len(chunk)
        temp_file.close()
        
        file_size_mb = file_size / (1024 * 1024)
        logger.info(
            "Streamed file to temporary storage",
            filename=filename,
            temp_path=temp_file_path,
            size_mb=round(file_size_mb, 2),
        )
        
        # Queue task with file path (avoids loading entire file into memory)
        task = process_edi_file.delay(
            file_path=temp_file_path,
            filename=filename,
            file_type="837",
        )
        
        return {
            "message": "File queued for processing",
            "task_id": task.id,
            "filename": filename,
            "file_size_mb": round(file_size_mb, 2),
            "processing_mode": "file-based",
        }
    except Exception as e:
        # Clean up temp file on error
        try:
            temp_file.close()
            os.unlink(temp_file_path)
        except Exception as cleanup_error:
            logger.error(
                "Failed to delete temporary file during error cleanup",
                error=str(cleanup_error),
                filename=filename,
                temp_path=temp_file_path,
            )
        logger.error("Failed to stream file", error=str(e), filename=filename)
        raise


@router.get("/claims/unlinked")
async def get_unlinked_claims(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """Get claims that haven't been linked to remittances."""
    from app.services.episodes.linker import EpisodeLinker
    
    linker = EpisodeLinker(db)
    claims = linker.get_unlinked_claims(limit=limit)

    return {
        "claims": [
            {
                "id": claim.id,
                "claim_control_number": claim.claim_control_number,
                "total_charge_amount": claim.total_charge_amount,
                "service_date": claim.service_date.isoformat() if claim.service_date else None,
                "payer_name": claim.payer_name if hasattr(claim, "payer_name") else None,
            }
            for claim in claims
        ],
        "total": len(claims),
        "skip": skip,
        "limit": limit,
    }


@router.get("/claims")
async def get_claims(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """Get list of claims."""
    from app.models.database import Claim
    
    # Use cached count for better performance
    count_key = count_cache_key("claim")
    cached_count = cache.get(count_key)
    if cached_count is not None:
        total = cached_count
    else:
        total = db.query(Claim).count()
        cache.set(count_key, total, ttl_seconds=get_count_ttl())
    
    claims = (
        db.query(Claim)
        .options(joinedload(Claim.claim_lines))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return {
        "claims": [
            {
                "id": claim.id,
                "claim_control_number": claim.claim_control_number,
                "patient_control_number": claim.patient_control_number,
                "total_charge_amount": claim.total_charge_amount,
                "status": claim.status.value if claim.status else None,
                "is_incomplete": claim.is_incomplete,
                "created_at": claim.created_at.isoformat() if claim.created_at else None,
            }
            for claim in claims
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: int, db: Session = Depends(get_db)):
    """Get claim by ID (cached)."""
    from app.models.database import Claim
    from app.utils.errors import NotFoundError
    
    # Try cache first
    cache_key = claim_cache_key(claim_id)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    claim = (
        db.query(Claim)
        .options(joinedload(Claim.claim_lines))
        .filter(Claim.id == claim_id)
        .first()
    )
    
    if not claim:
        raise NotFoundError("Claim", str(claim_id))
    
    result = {
        "id": claim.id,
        "claim_control_number": claim.claim_control_number,
        "patient_control_number": claim.patient_control_number,
        "provider_id": claim.provider_id,
        "payer_id": claim.payer_id,
        "total_charge_amount": claim.total_charge_amount,
        "facility_type_code": claim.facility_type_code,
        "claim_frequency_type": claim.claim_frequency_type,
        "assignment_code": claim.assignment_code,
        "statement_date": claim.statement_date.isoformat() if claim.statement_date else None,
        "admission_date": claim.admission_date.isoformat() if claim.admission_date else None,
        "discharge_date": claim.discharge_date.isoformat() if claim.discharge_date else None,
        "service_date": claim.service_date.isoformat() if claim.service_date else None,
        "diagnosis_codes": claim.diagnosis_codes,
        "principal_diagnosis": claim.principal_diagnosis,
        "status": claim.status.value if claim.status else None,
        "is_incomplete": claim.is_incomplete,
        "parsing_warnings": claim.parsing_warnings,
        "practice_id": claim.practice_id,
        "claim_lines": [
            {
                "id": line.id,
                "line_number": line.line_number,
                "procedure_code": line.procedure_code,
                "charge_amount": line.charge_amount,
                "service_date": line.service_date.isoformat() if line.service_date else None,
            }
            for line in claim.claim_lines
        ],
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
        "updated_at": claim.updated_at.isoformat() if claim.updated_at else None,
    }
    
    # Cache with configured TTL
    cache.set(cache_key, result, ttl_seconds=get_claim_ttl())
    return result

