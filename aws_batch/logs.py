"""CloudWatch log streaming for AWS Batch jobs."""

import threading
import time
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError


class LogWatcher(threading.Thread):
    """Streams CloudWatch logs for an AWS Batch job.

    Inspired by nextstrain/cli/runner/aws_batch/logs.py
    """

    def __init__(self, job_name, job_id, region="us-east-1"):
        """Initialize the log watcher.

        Args:
            job_name: Name of the job (for display)
            job_id: AWS Batch job ID
            region: AWS region
        """
        super().__init__(name=f"log-watcher-{job_id}")
        self.daemon = True

        self.job_name = job_name
        self.job_id = job_id
        self.region = region
        self.log_group = "/aws/batch/job"
        self.log_stream = None  # Will be determined from job details

        self.batch = boto3.client("batch", region_name=region)
        self.logs = boto3.client("logs", region_name=region)
        self.stopped = threading.Event()
        self.consumed_event_ids = set()
        self.last_timestamp = None
        
    def run(self):
        """Main thread loop for streaming logs."""
        # Wait for job to start and get log stream name
        print("[Waiting for job to start...]", flush=True)

        while not self.stopped.is_set() and self.log_stream is None:
            try:
                response = self.batch.describe_jobs(jobs=[self.job_id])
                if response["jobs"]:
                    job = response["jobs"][0]
                    if "container" in job and "logStreamName" in job["container"]:
                        self.log_stream = job["container"]["logStreamName"]
                        print(f"[Log stream found: {self.log_stream}]", flush=True)
                        break
            except ClientError:
                pass
            time.sleep(2)

        if not self.log_stream:
            return

        while not self.stopped.is_set():
            try:
                for event in self.fetch_events():
                    if event["eventId"] not in self.consumed_event_ids:
                        print(self.format_event(event), flush=True)
                        self.consumed_event_ids.add(event["eventId"])
                        self.last_timestamp = event["timestamp"]
            except ClientError as e:
                # Log stream might not exist yet
                if e.response["Error"]["Code"] != "ResourceNotFoundException":
                    print(f"Error fetching logs: {e}")

            # Poll every 200ms as per nextstrain pattern
            time.sleep(0.2)
    
    def fetch_events(self):
        """Fetch new log events from CloudWatch.

        Yields:
            Log events from CloudWatch
        """
        params = {
            "logGroupName": self.log_group,
            "logStreamNames": [self.log_stream],  # Changed from logStreamName to logStreamNames
        }

        if self.last_timestamp is not None:
            # Start from after the last seen event
            params["startTime"] = self.last_timestamp + 1

        try:
            paginator = self.logs.get_paginator("filter_log_events")
            for page in paginator.paginate(**params):
                for event in page.get("events", []):
                    yield event
        except ClientError:
            # Stream might not exist yet
            pass
    
    def format_event(self, event):
        """Format a log event for display.
        
        Args:
            event: CloudWatch log event
            
        Returns:
            Formatted log message
        """
        timestamp = datetime.fromtimestamp(
            event["timestamp"] / 1000, tz=timezone.utc
        )
        message = event["message"].rstrip("\n")
        
        # Add timestamp prefix for clarity
        return f"[{timestamp.strftime('%H:%M:%S')}] {message}"
    
    def stop(self):
        """Stop the log watcher thread."""
        self.stopped.set()
        self.join(timeout=1)


def stream_job_logs(job_name, job_id, region="us-east-1"):
    """Start streaming logs for a job.
    
    Args:
        job_name: Name of the job
        job_id: AWS Batch job ID
        region: AWS region
        
    Returns:
        LogWatcher thread (already started)
    """
    watcher = LogWatcher(job_name, job_id, region)
    watcher.start()
    return watcher


def tail_log_stream(
    log_group,
    log_stream,
    region="us-east-1",
    follow=False,
):
    """Tail a CloudWatch log stream (for debugging).
    
    Args:
        log_group: CloudWatch log group name
        log_stream: CloudWatch log stream name
        region: AWS region
        follow: Whether to follow the log (like tail -f)
    """
    logs = boto3.client("logs", region_name=region)
    last_timestamp = None
    consumed_ids = set()
    
    try:
        while True:
            params = {
                "logGroupName": log_group,
                "logStreamName": log_stream,
                "startFromHead": True,
            }
            
            if last_timestamp:
                params["startTime"] = last_timestamp + 1
            
            response = logs.filter_log_events(**params)
            
            for event in response.get("events", []):
                if event["eventId"] not in consumed_ids:
                    timestamp = datetime.fromtimestamp(
                        event["timestamp"] / 1000, tz=timezone.utc
                    )
                    print(f"[{timestamp.strftime('%H:%M:%S')}] {event['message']}", end="")
                    consumed_ids.add(event["eventId"])
                    last_timestamp = event["timestamp"]
            
            if not follow:
                break
                
            time.sleep(0.2)
            
    except ClientError as e:
        print(f"Error: {e}")