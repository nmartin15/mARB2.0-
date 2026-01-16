"""
Celery task definitions for asynchronous EDI file processing.

This module defines background tasks for processing EDI files (837 claims and 835 remittances)
asynchronously using Celery. Tasks handle file parsing, transformation, database storage,
episode linking, and pattern detection.

Key Features:
- Supports both memory-based (small files <50MB) and file-based (large files >=50MB) processing
- Automatic episode linking after remittance processing
- Pattern detection and learning from historical data
- Memory monitoring and performance tracking
- Comprehensive error handling with Sentry integration
- WebSocket notifications for real-time updates

Tasks:
- process_edi_file: Main task for processing EDI files (837 or 835)
"""
import os
from celery import Task
from sqlalchemy.orm import Session
from app.config.celery import celery_app
from app.config.database import SessionLocal
from app.services.edi.parser import EDIParser
from app.services.edi.parser_optimized import OptimizedEDIParser
from app.services.edi.transformer import EDITransformer
from app.services.episodes.linker import EpisodeLinker
from app.services.learning.pattern_detector import PatternDetector
from app.models.database import (
    Claim,
    Remittance,
    ClaimStatus,
    RemittanceStatus,
    Payer,
    ClaimEpisode,
    EpisodeStatus,
)
from app.utils.logger import get_logger
from app.utils.notifications import (
    notify_file_processed,
    notify_claim_processed,
    notify_remittance_processed,
    notify_file_progress,
)
from app.config.sentry import capture_exception, add_breadcrumb, settings
from app.utils.memory_monitor import get_memory_usage, log_memory_checkpoint

logger = get_logger(__name__)

# Try to import performance monitor, but make it optional
try:
    from app.services.edi.performance_monitor import PerformanceMonitor
    PERFORMANCE_MONITORING_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITORING_AVAILABLE = False
    PerformanceMonitor = None


@celery_app.task(bind=True, name="process_edi_file")
def process_edi_file(
    self: Task,
    file_content: str = None,
    file_path: str = None,
    filename: str = None,
    file_type: str = None,
    practice_id: str = None,
):
    """
    Process EDI file (837 or 835).
    
    Supports two modes:
    - Memory-based: file_content provided (for files <50MB)
    - File-based: file_path provided (for files >50MB)
    """
    # Validate inputs
    if not file_content and not file_path:
        raise ValueError("Either file_content or file_path must be provided")
    if file_content and file_path:
        raise ValueError("Cannot provide both file_content and file_path")
    
    # Load content from file if file_path provided
    if file_path:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.info(
            "Processing EDI file from disk",
            filename=filename,
            file_path=file_path,
            file_type=file_type,
            task_id=self.request.id,
            practice_id=practice_id,
        )
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            file_size = os.path.getsize(file_path)
        except Exception as e:
            logger.error("Failed to read file", error=str(e), file_path=file_path)
            # Clean up temp file
            try:
                os.unlink(file_path)
            except:
                pass
            raise
    else:
        file_size = len(file_content.encode("utf-8"))
        logger.info(
            "Processing EDI file from memory",
            filename=filename,
            file_type=file_type,
            task_id=self.request.id,
            practice_id=practice_id,
        )
    
    db: Session = SessionLocal()
    
    # Start performance monitoring for large files
    monitor = None
    if PERFORMANCE_MONITORING_AVAILABLE and file_size > 1024 * 1024:  # >1MB
        monitor = PerformanceMonitor(f"process_edi_file_{filename}")
        monitor.start()
        monitor.checkpoint("task_started", {"file_size_mb": file_size / (1024 * 1024)})
    
    try:
        # Determine file size and choose parser
        file_size_mb = file_size / (1024 * 1024)
        use_optimized = file_size_mb > 10  # Use optimized parser for files > 10MB
        
        # Send initial progress notification
        try:
            notify_file_progress(
                filename=filename,
                file_type=file_type or "unknown",
                task_id=self.request.id,
                stage="parsing",
                progress=0.1,
                current=0,
                total=1,
                message=f"Starting to parse {filename} ({file_size_mb:.1f} MB)",
            )
        except Exception as e:
            logger.warning("Failed to send initial progress notification", error=str(e))
        
        # Parse EDI file
        if use_optimized:
            logger.info("Using optimized parser for large file", filename=filename, size_mb=file_size_mb)
            parser = OptimizedEDIParser(practice_id=practice_id)
            # Pass file_path if available for true streaming from disk
            parsed_data = parser.parse(
                file_content=file_content if not file_path else None,
                filename=filename,
                file_path=file_path if file_path else None
            )
        else:
            parser = EDIParser(practice_id=practice_id)
            parsed_data = parser.parse(file_content, filename)
        
        if monitor:
            monitor.checkpoint("parsing_complete", {
                "file_type": parsed_data.get("file_type"),
                "claims_count": len(parsed_data.get("claims", [])),
                "remittances_count": len(parsed_data.get("remittances", [])),
            })
        
        # Send parsing complete progress
        try:
            notify_file_progress(
                filename=filename,
                file_type=parsed_data.get("file_type", file_type or "unknown"),
                task_id=self.request.id,
                stage="processing",
                progress=0.3,
                current=0,
                total=len(parsed_data.get("claims", [])) + len(parsed_data.get("remittances", [])),
                message=f"Parsing complete, processing {len(parsed_data.get('claims', []))} claims / {len(parsed_data.get('remittances', []))} remittances",
            )
        except Exception as e:
            logger.warning("Failed to send parsing progress notification", error=str(e))
        
        # Auto-detect file type if not provided
        if not file_type:
            file_type = parsed_data.get("file_type", "837")
        
        if file_type == "837":
            # Transform and save claims with batch processing
            transformer = EDITransformer(db, practice_id=practice_id, filename=filename)
            claims_created = []
            claims_to_add = []
            batch_size = 50
            
            claims_data = parsed_data.get("claims", [])
            total_claims = len(claims_data)
            
            logger.info(
                "Processing claims",
                total_claims=total_claims,
                batch_size=batch_size,
                filename=filename,
            )
            
            for idx, claim_data in enumerate(claims_data):
                try:
                    claim = transformer.transform_837_claim(claim_data)
                    claims_to_add.append(claim)
                    
                    # Commit in batches to reduce memory usage and improve performance
                    if len(claims_to_add) >= batch_size:
                        db.bulk_save_objects(claims_to_add)
                        db.flush()
                        
                        # Get IDs after flush
                        for c in claims_to_add:
                            claims_created.append(c.id)
                        
                        claims_to_add = []
                        
                        # Send progress notification for large files
                        if total_claims > 50:
                            progress = 0.3 + (0.4 * (idx + 1) / total_claims)  # 30% to 70%
                            try:
                                notify_file_progress(
                                    filename=filename,
                                    file_type="837",
                                    task_id=self.request.id,
                                    stage="saving",
                                    progress=progress,
                                    current=idx + 1,
                                    total=total_claims,
                                    message=f"Processing claims: {idx + 1}/{total_claims}",
                                )
                            except Exception as e:
                                logger.warning("Failed to send progress notification", error=str(e))
                        
                        # Log progress for large files
                        if total_claims > 100 and (idx + 1) % 100 == 0:
                            logger.info(
                                "Claim processing progress",
                                processed=idx + 1,
                                total=total_claims,
                                progress_pct=((idx + 1) / total_claims) * 100,
                            )
                    
                except Exception as e:
                    logger.error(
                        "Failed to transform claim",
                        error=str(e),
                        claim_data=claim_data.get("claim_control_number"),
                        exc_info=True,
                    )
                    # Continue processing other claims
                    continue
            
            # Commit remaining claims
            if claims_to_add:
                db.bulk_save_objects(claims_to_add)
                db.flush()
                for c in claims_to_add:
                    claims_created.append(c.id)
            
            db.commit()
            
            logger.info(
                "837 file processed successfully",
                filename=filename,
                claims_created=len(claims_created),
            )
            
            if monitor:
                monitor.checkpoint("database_commit_complete", {"claims_created": len(claims_created)})
            
            result = {
                "status": "success",
                "filename": filename,
                "file_type": file_type,
                "claims_created": len(claims_created),
                "warnings": parsed_data.get("warnings", []),
            }
            
            if monitor:
                perf_summary = monitor.finish()
                result["_performance"] = perf_summary
            
            # Send WebSocket notification for file processing
            try:
                notify_file_processed(filename, file_type, result)
            except Exception as e:
                logger.warning("Failed to send file processed notification", error=str(e), filename=filename)
            
            # Send notifications for each claim processed
            # Optimize: batch load claims instead of querying one by one
            if claims_created:
                try:
                    claims = db.query(Claim).filter(Claim.id.in_(claims_created)).all()
                    # Ensure all claims are in the dictionary
                    claim_dict = {claim.id: claim for claim in claims}

                    for claim_id in claims_created:
                        claim = claim_dict.get(claim_id)
                        if not claim:
                            logger.warning("Claim not found in batch load", claim_id=claim_id)
                            continue

                        try:
                            notify_claim_processed(
                                claim_id,
                                {
                                    "claim_control_number": claim.claim_control_number,
                                    "status": claim.status.value if claim.status else None,
                                },
                            )
                        except Exception as e:
                            logger.warning("Failed to send claim processed notification", error=str(e), claim_id=claim_id)
                except Exception as e:
                    logger.warning("Failed to batch load claims for notifications", error=str(e))
            
            # Clean up temporary file if file_path was provided
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.info("Cleaned up temporary file", file_path=file_path)
                except Exception as e:
                    logger.warning("Failed to clean up temporary file", error=str(e), file_path=file_path)
            
            return result
        
        elif file_type == "835":
            # Transform and save remittances with batch processing
            transformer = EDITransformer(db, practice_id=practice_id, filename=filename)
            remittances_created = []
            remittances_to_add = []
            remittance_ids_for_linking = []
            bpr_data = parsed_data.get("bpr", {})
            batch_size = 50
            
            remittances_data = parsed_data.get("remittances", [])
            total_remittances = len(remittances_data)
            
            logger.info(
                "Processing remittances",
                total_remittances=total_remittances,
                batch_size=batch_size,
                filename=filename,
            )
            
            for idx, remittance_data in enumerate(remittances_data):
                try:
                    remittance = transformer.transform_835_remittance(remittance_data, bpr_data)
                    remittances_to_add.append(remittance)
                    
                    # Commit in batches to reduce memory usage and improve performance
                    if len(remittances_to_add) >= batch_size:
                        db.bulk_save_objects(remittances_to_add)
                        db.flush()
                        
                        # Get IDs after flush and queue linking tasks
                        for r in remittances_to_add:
                            remittances_created.append(r.id)
                            remittance_ids_for_linking.append(r.id)
                        
                        remittances_to_add = []
                        
                        # Send progress notification for large files
                        if total_remittances > 50:
                            progress = 0.3 + (0.4 * (idx + 1) / total_remittances)  # 30% to 70%
                            try:
                                notify_file_progress(
                                    filename=filename,
                                    file_type="835",
                                    task_id=self.request.id,
                                    stage="saving",
                                    progress=progress,
                                    current=idx + 1,
                                    total=total_remittances,
                                    message=f"Processing remittances: {idx + 1}/{total_remittances}",
                                )
                            except Exception as e:
                                logger.warning("Failed to send progress notification", error=str(e))
                        
                        # Log progress for large files
                        if total_remittances > 100 and (idx + 1) % 100 == 0:
                            logger.info(
                                "Remittance processing progress",
                                processed=idx + 1,
                                total=total_remittances,
                                progress_pct=((idx + 1) / total_remittances) * 100,
                            )
                    
                except Exception as e:
                    logger.error(
                        "Failed to transform remittance",
                        error=str(e),
                        claim_control_number=remittance_data.get("claim_control_number"),
                        exc_info=True,
                    )
                    # Continue processing other remittances
                    continue
            
            # Commit remaining remittances
            if remittances_to_add:
                db.bulk_save_objects(remittances_to_add)
                db.flush()
                for r in remittances_to_add:
                    remittances_created.append(r.id)
                    remittance_ids_for_linking.append(r.id)
            
            db.commit()
            
            # Queue episode linking tasks in batches (after commit)
            for remittance_id in remittance_ids_for_linking:
                try:
                    link_episodes.delay(remittance_id)
                except Exception as e:
                    logger.warning(
                        "Failed to queue episode linking task",
                        error=str(e),
                        remittance_id=remittance_id,
                    )
            
            logger.info(
                "835 file processed successfully",
                filename=filename,
                remittances_created=len(remittances_created),
            )
            
            if monitor:
                monitor.checkpoint("database_commit_complete", {"remittances_created": len(remittances_created)})
            
            result = {
                "status": "success",
                "filename": filename,
                "file_type": file_type,
                "remittances_created": len(remittances_created),
                "warnings": parsed_data.get("warnings", []),
            }
            
            if monitor:
                perf_summary = monitor.finish()
                result["_performance"] = perf_summary
            
            # Send final progress notification
            try:
                notify_file_progress(
                    filename=filename,
                    file_type=file_type,
                    task_id=self.request.id,
                    stage="complete",
                    progress=1.0,
                    current=len(remittances_created),
                    total=len(remittances_created),
                    message=f"File {filename} processed successfully",
                )
            except Exception as e:
                logger.warning("Failed to send completion progress notification", error=str(e))
            
            # Send WebSocket notification for file processing
            try:
                notify_file_processed(filename, file_type, result)
            except Exception as e:
                logger.warning("Failed to send file processed notification", error=str(e), filename=filename)
            
            # Send notifications for each remittance processed
            # Optimize: batch load remittances instead of querying one by one
            if remittances_created:
                try:
                    remittances = db.query(Remittance).filter(Remittance.id.in_(remittances_created)).all()
                    remittance_dict = {remittance.id: remittance for remittance in remittances}

                    for remittance_id in remittances_created:
                        remittance = remittance_dict.get(remittance_id)
                        if not remittance:
                            logger.warning("Remittance not found in batch load", remittance_id=remittance_id)
                            continue

                        try:
                            notify_remittance_processed(
                                remittance_id,
                                {
                                    "claim_control_number": remittance.claim_control_number,
                                    "payment_amount": remittance.payment_amount,
                                    "status": remittance.status.value if remittance.status else None,
                                },
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to send remittance processed notification",
                                error=str(e),
                                remittance_id=remittance_id,
                            )
                except Exception as e:
                    logger.warning("Failed to batch load remittances for notifications", error=str(e))
            
            # Clean up temporary file if file_path was provided
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.info("Cleaned up temporary file", file_path=file_path)
                except Exception as e:
                    logger.warning("Failed to clean up temporary file", error=str(e), file_path=file_path)
            
            return result
        
        else:
            raise ValueError(f"Unknown file type: {file_type}")
    
    except Exception as e:
        logger.error("Failed to process EDI file", filename=filename, error=str(e), exc_info=True)
        
        # Clean up temporary file if file_path was provided
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
                logger.info("Cleaned up temporary file after error", file_path=file_path)
            except Exception as cleanup_error:
                logger.warning("Failed to clean up temporary file after error", error=str(cleanup_error), file_path=file_path)
        
        # Add breadcrumb for context
        add_breadcrumb(
            message=f"EDI file processing failed: {filename}",
            category="celery_task",
            level="error",
            data={
                "task": "process_edi_file",
                "filename": filename,
                "file_type": file_type,
                "practice_id": practice_id,
                "task_id": self.request.id,
            },
        )
        
        # Send to Sentry with context
        if settings.enable_alerts:
            capture_exception(
                e,
                level="error",
                context={
                    "task": {
                        "name": "process_edi_file",
                        "id": self.request.id,
                        "retries": self.request.retries,
                        "max_retries": getattr(self.request, 'max_retries', 3),
                    },
                    "file": {
                        "filename": filename,
                        "file_type": file_type,
                        "size_bytes": len(file_content) if file_content else None,
                        "practice_id": practice_id,
                    },
                },
                tags={
                    "task": "process_edi_file",
                    "file_type": file_type or "unknown",
                    "error_type": type(e).__name__,
                },
            )
        
        if monitor:
            monitor.checkpoint("error", {"error": str(e)})
            monitor.finish()
        db.rollback()
        raise
    
    finally:
        if monitor and not monitor.checkpoints:  # If no checkpoints were recorded, finish anyway
            monitor.finish()
        db.close()


@celery_app.task(bind=True, name="link_episodes")
def link_episodes(self: Task, remittance_id: int):
    """
    Link a remittance to its corresponding claim(s).

    This task automatically links a remittance to matching claims using:
    - Control number matching (primary method)
    - Patient ID and date range matching (fallback method)
    
    After linking, episodes are marked as complete if the remittance is fully processed.

    Args:
        self: Celery task instance (bound task)
        remittance_id: The ID of the remittance to link to claims
        
    Returns:
        Dict with status and episode count:
        {
            "status": "success" or "error",
            "remittance_id": int,
            "episodes_linked": int
        }
    """
    logger.info("Linking episodes", remittance_id=remittance_id, task_id=self.request.id)
    
    db: Session = SessionLocal()
    
    try:
        remittance = db.query(Remittance).filter(Remittance.id == remittance_id).first()
        
        if not remittance:
            logger.warning("Remittance not found", remittance_id=remittance_id)
            return {"status": "error", "message": "Remittance not found"}
        
        linker = EpisodeLinker(db)
        episodes = linker.auto_link_by_control_number(remittance)
        
        # If no matches by control number, try patient/date matching
        if not episodes:
            logger.info(
                "No matches by control number, trying patient/date matching",
                remittance_id=remittance_id,
            )
            episodes = linker.auto_link_by_patient_and_date(remittance)
        
        # Mark episodes as complete if remittance is fully processed
        # Optimize: Batch check remittance status instead of individual queries
        completed_episode_ids = []
        if episodes:
            episode_ids = [ep.id for ep in episodes]
            # Batch update episodes that are ready to be marked complete
            from sqlalchemy.orm import joinedload
            
            ready_episodes = (
                db.query(ClaimEpisode)
                .options(joinedload(ClaimEpisode.remittance))
                .filter(
                    ClaimEpisode.id.in_(episode_ids),
                    ClaimEpisode.status != EpisodeStatus.COMPLETE,
                )
                .all()
            )
            
            for episode in ready_episodes:
                if episode.remittance and episode.remittance.status == RemittanceStatus.PROCESSED:
                    linker.mark_episode_complete(episode.id)
                    completed_episode_ids.append(episode.id)
        
        db.commit()
        
        # Invalidate cache for all newly created/updated episodes
        # This ensures the episodes list endpoint shows the new/updated episodes
        from app.utils.cache import cache, episode_cache_key
        
        all_episode_ids = [ep.id for ep in episodes] + completed_episode_ids
        for episode_id in all_episode_ids:
            # Invalidate the specific episode cache
            cache_key = episode_cache_key(episode_id)
            cache.delete(cache_key)
            
            # Invalidate pattern-based variations (defensive measure)
            cache.delete_pattern(f"episode:{episode_id}*")
        
        # Invalidate count caches for episodes (both filtered and unfiltered)
        # This ensures count queries reflect the new/updated episodes
        cache.delete_pattern("count:episode*")
        
        logger.info("Episodes linked", remittance_id=remittance_id, episode_count=len(episodes))
        
        return {
            "status": "success",
            "remittance_id": remittance_id,
            "episodes_linked": len(episodes),
        }
    
    except Exception as e:
        logger.error("Failed to link episodes", remittance_id=remittance_id, error=str(e), exc_info=True)
        
        # Add breadcrumb for context
        add_breadcrumb(
            message=f"Episode linking failed for remittance {remittance_id}",
            category="celery_task",
            level="error",
            data={
                "task": "link_episodes",
                "remittance_id": remittance_id,
                "task_id": self.request.id,
            },
        )
        
        # Send to Sentry with context
        if settings.enable_alerts:
            capture_exception(
                e,
                level="error",
                context={
                    "task": {
                        "name": "link_episodes",
                        "id": self.request.id,
                        "retries": self.request.retries,
                        "max_retries": getattr(self.request, 'max_retries', 3),
                    },
                    "remittance": {
                        "id": remittance_id,
                    },
                },
                tags={
                    "task": "link_episodes",
                    "error_type": type(e).__name__,
                },
            )
        
        db.rollback()
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True, name="detect_patterns")
def detect_patterns(self: Task, payer_id: int = None, days_back: int = 90):
    """
    Detect denial patterns for a payer or all payers with memory monitoring.

    This task analyzes historical claim episodes to identify denial patterns.
    Patterns are stored in the DenialPattern model and can be used for risk prediction.

    Args:
        self: Celery task instance (bound task)
        payer_id: The ID of the payer to detect patterns for. 
                  If None, patterns are detected for all payers. Defaults to None.
        days_back: The number of days back from today to analyze historical data.
                   Defaults to 90 days.
                   
    Returns:
        Dict with status and pattern counts:
        {
            "status": "success" or "error",
            "payer_id": int (if single payer),
            "payers_processed": int (if all payers),
            "patterns_detected": int or "total_patterns": int
        }
    """
    start_memory = get_memory_usage()
    logger.info(
        "Detecting patterns",
        payer_id=payer_id,
        days_back=days_back,
        task_id=self.request.id,
    )
    
    log_memory_checkpoint(
        "detect_patterns",
        "task_started",
        start_memory_mb=start_memory,
        metadata={"payer_id": payer_id, "days_back": days_back, "task_id": self.request.id},
    )
    
    db: Session = SessionLocal()
    
    try:
        detector = PatternDetector(db)
        
        if payer_id:
            # Detect patterns for specific payer
            payer = db.query(Payer).filter(Payer.id == payer_id).first()
            if not payer:
                logger.warning("Payer not found", payer_id=payer_id)
                return {"status": "error", "message": "Payer not found"}
            
            log_memory_checkpoint(
                "detect_patterns",
                "before_detection",
                start_memory_mb=start_memory,
                metadata={"payer_id": payer_id, "mode": "single_payer"},
            )
            
            patterns = detector.detect_patterns_for_payer(payer_id, days_back)
            db.commit()
            
            log_memory_checkpoint(
                "detect_patterns",
                "detection_complete",
                start_memory_mb=start_memory,
                metadata={"payer_id": payer_id, "pattern_count": len(patterns)},
            )
            
            logger.info(
                "Patterns detected for payer",
                payer_id=payer_id,
                pattern_count=len(patterns),
            )
            
            return {
                "status": "success",
                "payer_id": payer_id,
                "patterns_detected": len(patterns),
            }
        else:
            # Detect patterns for all payers
            log_memory_checkpoint(
                "detect_patterns",
                "before_detection",
                start_memory_mb=start_memory,
                metadata={"mode": "all_payers"},
            )
            
            all_patterns = detector.detect_all_patterns(days_back)
            db.commit()
            
            total_patterns = sum(len(patterns) for patterns in all_patterns.values())
            
            log_memory_checkpoint(
                "detect_patterns",
                "detection_complete",
                start_memory_mb=start_memory,
                metadata={
                    "payer_count": len(all_patterns),
                    "total_patterns": total_patterns,
                },
            )
            
            logger.info(
                "Patterns detected for all payers",
                payer_count=len(all_patterns),
                total_patterns=total_patterns,
            )
            
            return {
                "status": "success",
                "payers_processed": len(all_patterns),
                "total_patterns": total_patterns,
            }
    
    except Exception as e:
        logger.error(
            "Failed to detect patterns",
            payer_id=payer_id,
            error=str(e),
            exc_info=True,
        )
        
        # Add breadcrumb for context
        add_breadcrumb(
            message=f"Pattern detection failed",
            category="celery_task",
            level="error",
            data={
                "task": "detect_patterns",
                "payer_id": payer_id,
                "days_back": days_back,
                "task_id": self.request.id,
            },
        )
        
        # Send to Sentry with context
        if settings.enable_alerts:
            capture_exception(
                e,
                level="error",
                context={
                    "task": {
                        "name": "detect_patterns",
                        "id": self.request.id,
                        "retries": self.request.retries,
                        "max_retries": getattr(self.request, 'max_retries', 3),
                    },
                    "pattern_detection": {
                        "payer_id": payer_id,
                        "days_back": days_back,
                    },
                },
                tags={
                    "task": "detect_patterns",
                    "error_type": type(e).__name__,
                },
            )
        
        db.rollback()
        raise
    
    finally:
        db.close()


@celery_app.task(bind=True, name="retrain_ml_model", max_retries=3)
def retrain_ml_model(
    self: Task,
    start_date: str = None,
    end_date: str = None,
    model_type: str = "random_forest",
    n_estimators: int = 100,
    days_back: int = 90,
    output_dir: str = "ml/models/saved",
    run_pattern_detection: bool = True,
):
    """
    Retrain ML model and run pattern detection (scheduled task).
    
    This task can be scheduled to run periodically (e.g., monthly) to:
    - Retrain the risk prediction model with latest data
    - Update denial patterns from recent remittances
    
    Args:
        start_date: Start date for training data (ISO format, default: 6 months ago)
        end_date: End date for training data (ISO format, default: today)
        model_type: Type of model ('random_forest' or 'gradient_boosting')
        n_estimators: Number of trees
        days_back: Days to look back for pattern detection
        output_dir: Directory to save trained model
        run_pattern_detection: Whether to run pattern detection
    """
    from datetime import datetime, timedelta
    from ml.training.continuous_learning_pipeline import ContinuousLearningPipeline
    
    task_id = self.request.id
    logger.info(
        "Starting ML model retraining task",
        task_id=task_id,
        model_type=model_type,
        run_pattern_detection=run_pattern_detection,
    )
    
    # Add breadcrumb for Sentry
    add_breadcrumb(
        message="ML model retraining task started",
        category="ml_training",
        level="info",
        data={
            "task_id": task_id,
            "model_type": model_type,
        },
    )
    
    db = SessionLocal()
    
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = datetime.now() - timedelta(days=180)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
        else:
            end_dt = datetime.now()
        
        # Run pipeline
        pipeline = ContinuousLearningPipeline(db)
        results = pipeline.run_full_pipeline(
            start_date=start_dt,
            end_date=end_dt,
            model_type=model_type,
            n_estimators=n_estimators,
            days_back=days_back,
            output_dir=output_dir,
            run_pattern_detection=run_pattern_detection,
        )
        
        # Log results
        logger.info(
            "ML model retraining completed",
            task_id=task_id,
            steps_completed=len(results["steps_completed"]),
            errors=len(results["errors"]),
            model_metrics=results.get("model_metrics", {}),
        )
        
        # Send to Sentry if there were errors
        if results["errors"]:
            capture_exception(
                Exception(f"ML retraining completed with errors: {', '.join(results['errors'])}"),
                level="warning",
                context={
                    "task": {
                        "name": "retrain_ml_model",
                        "id": task_id,
                        "retries": self.request.retries,
                    },
                    "results": results,
                },
                tags={
                    "task": "retrain_ml_model",
                    "model_type": model_type,
                },
            )
        
        return {
            "status": "success" if not results["errors"] else "partial_success",
            "steps_completed": results["steps_completed"],
            "errors": results["errors"],
            "model_metrics": results.get("model_metrics", {}),
            "pattern_detection": results.get("pattern_detection", {}),
        }
        
    except Exception as e:
        logger.error(
            "ML model retraining failed",
            task_id=task_id,
            error=str(e),
            exc_info=True,
        )
        
        # Send to Sentry
        capture_exception(
            e,
            level="error",
            context={
                "task": {
                    "name": "retrain_ml_model",
                    "id": task_id,
                    "retries": self.request.retries,
                    "max_retries": getattr(self.request, 'max_retries', 3),
                },
                "parameters": {
                    "model_type": model_type,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            },
            tags={
                "task": "retrain_ml_model",
                "error_type": type(e).__name__,
            },
        )
        
        db.rollback()
        raise self.retry(exc=e, countdown=3600)  # Retry after 1 hour
    
    finally:
        db.close()

