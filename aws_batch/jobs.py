"""AWS Batch job management."""

import os
import time
import boto3
from botocore.exceptions import ClientError


class JobManager:
    """Manages AWS Batch job submission and monitoring.
    
    Inspired by nextstrain/cli/runner/aws_batch/jobs.py
    """
    
    def __init__(self, region="us-east-1"):
        """Initialize the job manager.

        Args:
            region: AWS region
        """
        self.batch = boto3.client("batch", region_name=region)
        self.region = region
        
    def submit_job(
        self,
        job_name,
        job_definition,
        job_queue,
        workdir_url,
        cpus=None,
        memory=None,
        gpu=None,
        environment=None,
    ):
        """Submit a job to AWS Batch.
        
        Args:
            job_name: Name for the job
            job_definition: AWS Batch job definition name or ARN
            job_queue: AWS Batch job queue name
            workdir_url: S3 URL for the working directory
            cpus: Number of CPUs (optional override)
            memory: Memory in MB (optional override)
            gpu: Number of GPUs (optional)
            environment: Additional environment variables
            
        Returns:
            Job ID
        """
        # Build container overrides
        container_overrides = {
            "environment": [
                {"name": "TREESORT_AWS_BATCH_WORKDIR_URL", "value": workdir_url},
            ]
        }
        
        # Add any additional environment variables
        if environment:
            for key, value in environment.items():
                container_overrides["environment"].append({
                    "name": key,
                    "value": value
                })
        
        # Add resource requirements if specified
        if cpus or memory or gpu:
            resource_requirements = []
            if cpus:
                resource_requirements.append({
                    "type": "VCPU",
                    "value": str(cpus)
                })
            if memory:
                resource_requirements.append({
                    "type": "MEMORY",
                    "value": str(memory)
                })
            if gpu:
                resource_requirements.append({
                    "type": "GPU",
                    "value": str(gpu)
                })
            container_overrides["resourceRequirements"] = resource_requirements
        
        # Submit the job
        response = self.batch.submit_job(
            jobName=job_name,
            jobQueue=job_queue,
            jobDefinition=job_definition,
            containerOverrides=container_overrides,
        )
        
        return response["jobId"]
    
    def lookup_job(self, job_id):
        """Look up job details by ID.
        
        Args:
            job_id: AWS Batch job ID
            
        Returns:
            Job details
        """
        response = self.batch.describe_jobs(jobs=[job_id])
        
        if not response["jobs"]:
            raise ValueError(f"Job {job_id} not found")
        
        return response["jobs"][0]
    
    def get_job_status(self, job_id):
        """Get the current status of a job.
        
        Args:
            job_id: AWS Batch job ID
            
        Returns:
            Job status (SUBMITTED, PENDING, RUNNABLE, STARTING, RUNNING, SUCCEEDED, FAILED)
        """
        job = self.lookup_job(job_id)
        return job["status"]
    
    def wait_for_job(
        self,
        job_id,
        poll_interval=10,
        callback=None,
    ):
        """Wait for a job to complete.
        
        Args:
            job_id: AWS Batch job ID
            poll_interval: Seconds between status checks
            callback: Optional callback for status changes
            
        Returns:
            Final job details
        """
        last_status = None
        
        while True:
            job = self.lookup_job(job_id)
            status = job["status"]
            
            # Notify on status change
            if status != last_status:
                if callback:
                    callback(job)
                last_status = status
            
            # Check if job is in terminal state
            if status in ["SUCCEEDED", "FAILED"]:
                return job
            
            time.sleep(poll_interval)
    
    def cancel_job(self, job_id, reason="User requested cancellation"):
        """Cancel a running job.
        
        Args:
            job_id: AWS Batch job ID
            reason: Cancellation reason
        """
        try:
            self.batch.cancel_job(jobId=job_id, reason=reason)
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidJobStateException":
                raise
    
    def list_jobs(
        self,
        job_queue=None,
        status=None,
        max_results=100,
    ):
        """List jobs in a queue.
        
        Args:
            job_queue: Job queue name (optional)
            status: Filter by status (optional)
            max_results: Maximum number of results
            
        Returns:
            List of job summaries
        """
        params = {"maxResults": max_results}
        
        if job_queue:
            params["jobQueue"] = job_queue
        
        if status:
            params["jobStatus"] = status
        
        response = self.batch.list_jobs(**params)
        return response["jobSummaryList"]


def format_job_status(job):
    """Format job status for display.
    
    Args:
        job: Job details from AWS Batch
        
    Returns:
        Formatted status string
    """
    status = job["status"]
    job_name = job["jobName"]
    job_id = job["jobId"]
    
    # Add color codes for terminal output
    status_colors = {
        "SUBMITTED": "\033[94m",  # Blue
        "PENDING": "\033[93m",    # Yellow
        "RUNNABLE": "\033[93m",   # Yellow
        "STARTING": "\033[93m",   # Yellow
        "RUNNING": "\033[92m",    # Green
        "SUCCEEDED": "\033[92m",  # Green
        "FAILED": "\033[91m",     # Red
    }
    
    color = status_colors.get(status, "")
    reset = "\033[0m" if color else ""
    
    status_msg = f"{color}{status}{reset}"
    
    # Add additional info for certain states
    if status == "RUNNING" and "startedAt" in job:
        started = job["startedAt"]
        duration = int((time.time() * 1000 - started) / 1000)
        minutes, seconds = divmod(duration, 60)
        status_msg += f" ({minutes}m {seconds}s)"
    elif status == "FAILED" and "statusReason" in job:
        status_msg += f" - {job['statusReason']}"
    
    return f"Job {job_name} ({job_id}): {status_msg}"


def get_job_exit_code(job):
    """Extract exit code from a completed job.
    
    Args:
        job: Job details from AWS Batch
        
    Returns:
        Exit code or None if not available
    """
    if "container" in job and "exitCode" in job["container"]:
        return job["container"]["exitCode"]
    
    # Check attempts for multi-attempt jobs
    if "attempts" in job and job["attempts"]:
        last_attempt = job["attempts"][-1]
        if "container" in last_attempt and "exitCode" in last_attempt["container"]:
            return last_attempt["container"]["exitCode"]
    
    return None