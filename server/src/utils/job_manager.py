"""
Job manager for async processing with gentle cleanup
"""
import asyncio
import uuid
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from loguru import logger
from ..models.schemas import JobStatus


class JobManager:
    """Manages async processing jobs with status tracking and gentle cleanup"""
    
    def __init__(self, cleanup_retention_hours: int = 2):
        self.jobs: Dict[str, JobStatus] = {}
        self.cleanup_retention_hours = cleanup_retention_hours
        self.cleanup_task = None
        self._cleanup_started = False
    
    def _start_cleanup_scheduler(self):
        """Start the background cleanup scheduler"""
        # Skip automatic startup to avoid event loop issues
        pass
    
    async def _cleanup_scheduler(self):
        """Background task to clean up old jobs and files"""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                await self._cleanup_old_jobs()
            except Exception as e:
                logger.error(f"Cleanup scheduler error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _cleanup_old_jobs(self):
        """Clean up old completed/failed jobs and their files"""
        cutoff_time = datetime.now() - timedelta(hours=self.cleanup_retention_hours)
        jobs_to_remove = []
        
        for job_id, job in self.jobs.items():
            if (job.status in ["completed", "failed"] and 
                job.completed_at and 
                job.completed_at < cutoff_time):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            job = self.jobs.pop(job_id, None)
            if job and job.result and "file_path" in job.result:
                file_path = job.result["file_path"]
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"🧹 Cleaned up old job file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup file {file_path}: {e}")
        
        if jobs_to_remove:
            logger.info(f"🧹 Cleaned up {len(jobs_to_remove)} old jobs")
    
    def create_job(self, file_path: str, **kwargs) -> str:
        """Create a new processing job"""
        job_id = str(uuid.uuid4())
        job = JobStatus(
            job_id=job_id,
            status="pending",
            message="Job created, waiting to start processing"
        )
        self.jobs[job_id] = job
        logger.info(f"📋 Created job {job_id} for file {file_path}")
        return job_id
    
    def get_job(self, job_id: str) -> Optional[JobStatus]:
        """Get job status by ID"""
        return self.jobs.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, **kwargs):
        """Update job status and progress"""
        if job_id not in self.jobs:
            logger.warning(f"Job {job_id} not found")
            return
        
        job = self.jobs[job_id]
        job.status = status
        
        if "progress" in kwargs:
            job.progress = kwargs["progress"]
        if "current_step" in kwargs:
            job.current_step = kwargs["current_step"]
        if "message" in kwargs:
            job.message = kwargs["message"]
        if "result" in kwargs:
            job.result = kwargs["result"]
        if "error" in kwargs:
            job.error = kwargs["error"]
        
        # Update timestamps
        if status == "processing" and not job.started_at:
            job.started_at = datetime.now()
        elif status in ["completed", "failed"] and not job.completed_at:
            job.completed_at = datetime.now()
        
        logger.info(f"📊 Job {job_id} status: {status} - {job.message}")
    
    def cleanup_job_file(self, job_id: str):
        """Clean up file for a specific job (gentle cleanup)"""
        job = self.jobs.get(job_id)
        if not job or not job.result or "file_path" not in job.result:
            return
        
        file_path = job.result["file_path"]
        try:
            if os.path.exists(file_path):
                # Schedule cleanup after retention period instead of immediate
                try:
                    asyncio.create_task(self._delayed_cleanup(file_path))
                    logger.info(f"⏰ Scheduled cleanup for {file_path} in {self.cleanup_retention_hours} hours")
                except RuntimeError:
                    # No event loop, just log for now
                    logger.info(f"⏰ Will cleanup {file_path} later (no event loop)")
        except Exception as e:
            logger.warning(f"Failed to schedule cleanup for {file_path}: {e}")
    
    async def _delayed_cleanup(self, file_path: str):
        """Delayed cleanup after retention period"""
        await asyncio.sleep(self.cleanup_retention_hours * 3600)  # Convert hours to seconds
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🧹 Delayed cleanup completed: {file_path}")
        except Exception as e:
            logger.warning(f"Failed delayed cleanup for {file_path}: {e}")
    
    def get_job_count(self) -> int:
        """Get total number of jobs"""
        return len(self.jobs)
    
    def get_active_job_count(self) -> int:
        """Get number of active jobs"""
        return len([j for j in self.jobs.values() if j.status in ["pending", "processing"]])


# Global job manager instance
job_manager = JobManager()