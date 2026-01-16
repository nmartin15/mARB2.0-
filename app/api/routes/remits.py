"""Remittance endpoints."""
import os
import tempfile
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session, joinedload

from app.config.database import get_db
from app.config.cache_ttl import get_remittance_ttl, get_count_ttl
from app.services.queue.tasks import process_edi_file
from app.utils.logger import get_logger
from app.utils.cache import cache, remittance_cache_key, count_cache_key

router = APIRouter()
logger = get_logger(__name__)

# Configuration constants
LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB - use file-based processing
TEMP_DIR = os.getenv("TEMP_FILE_DIR", "/tmp/marb_edi_files")


@router.post("/remits/upload")
async def upload_remit_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload and process 835 remittance file.
    
    This endpoint accepts EDI 835 remittance advice files and queues them for processing.
    The file is processed asynchronously via Celery tasks.
    
    **File Processing:**
    - Small files (<50MB): Processed in memory for better performance
    - Large files (>=50MB): Saved to temporary storage and processed from disk
    - Files exceeding threshold during streaming are automatically switched to file-based processing
    
    **File Format:**
    - Accepts EDI 835 (Electronic Remittance Advice) files
    - File extension: .edi, .txt, or any text format
    - Encoding: UTF-8 (other encodings handled with error recovery)
    - Content: Must contain valid EDI 835 segments (ISA, GS, ST, BPR, etc.)
    
    **Response:**
    - Returns task_id for tracking processing status
    - File is queued immediately, processing happens asynchronously
    
    **Error Handling:**
    - Temporary files are automatically cleaned up on errors
    - Invalid files are still queued but will fail during processing
    """
    filename = file.filename or "unknown"
    logger.info("Received remittance file upload", filename=filename)
    
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
            prefix=f"edi_835_{filename}_",
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
                file_type="835",
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
    # This avoids loading the entire file into memory, which is important for:
    # - Files approaching the LARGE_FILE_THRESHOLD (but not exceeding it)
    # - Memory efficiency in high-concurrency scenarios
    # - Consistent processing path for all file sizes
    # 
    # By streaming to disk even for smaller files, we:
    # - Avoid memory spikes that could affect other requests
    # - Use a consistent processing model (file-based) for all files
    # - Allow the Celery worker to handle file I/O independently
    # 
    # This is more efficient than loading into memory and then writing to disk,
    # as it avoids the double memory allocation (original + decoded string).
    # Ensure temp directory exists
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Create temporary file
    temp_file = tempfile.NamedTemporaryFile(
        mode='wb',
        delete=False,
        dir=TEMP_DIR,
        prefix=f"edi_835_{filename}_",
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
            file_type="835",
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


@router.get("/remits")
async def get_remits(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get list of remittances."""
    from app.models.database import Remittance
    
    # Use cached count for better performance
    count_key = count_cache_key("remittance")
    cached_count = cache.get(count_key)
    if cached_count is not None:
        total = cached_count
    else:
        total = db.query(Remittance).count()
        cache.set(count_key, total, ttl_seconds=get_count_ttl())
    
    remits = (
        db.query(Remittance)
        .options(joinedload(Remittance.payer))
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    return {
        "remits": [
            {
                "id": remit.id,
                "remittance_control_number": remit.remittance_control_number,
                "claim_control_number": remit.claim_control_number,
                "payer_name": remit.payer_name,
                "payment_amount": remit.payment_amount,
                "status": remit.status.value if remit.status else None,
                "created_at": remit.created_at.isoformat() if remit.created_at else None,
            }
            for remit in remits
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/remits/{remit_id}")
async def get_remit(remit_id: int, db: Session = Depends(get_db)):
    """Get remittance by ID (cached)."""
    from app.models.database import Remittance
    from app.utils.errors import NotFoundError
    
    # Try cache first
    cache_key = remittance_cache_key(remit_id)
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    remit = db.query(Remittance).filter(Remittance.id == remit_id).first()
    
    if not remit:
        raise NotFoundError("Remittance", str(remit_id))
    
    result = {
        "id": remit.id,
        "remittance_control_number": remit.remittance_control_number,
        "payer_id": remit.payer_id,
        "payer_name": remit.payer_name,
        "payment_amount": remit.payment_amount,
        "payment_date": remit.payment_date.isoformat() if remit.payment_date else None,
        "check_number": remit.check_number,
        "claim_control_number": remit.claim_control_number,
        "denial_reasons": remit.denial_reasons,
        "adjustment_reasons": remit.adjustment_reasons,
        "status": remit.status.value if remit.status else None,
        "parsing_warnings": remit.parsing_warnings,
        "created_at": remit.created_at.isoformat() if remit.created_at else None,
        "updated_at": remit.updated_at.isoformat() if remit.updated_at else None,
    }
    
    # Cache with configured TTL
    cache.set(cache_key, result, ttl_seconds=get_remittance_ttl())
    return result

