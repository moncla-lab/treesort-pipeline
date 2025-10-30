#!/usr/bin/env python3
"""
AWS Batch MWE - Simple orchestrator for testing the full loop
"""
import argparse
import os
import sys
import uuid
from pathlib import Path

from aws_batch.s3 import upload_workdir, download_workdir
from aws_batch.jobs import JobManager, format_job_status
from aws_batch.logs import stream_job_logs


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Run MWE job on AWS Batch",
    )
    parser.add_argument(
        "directory",
        type=str,
        nargs="?",
        default=".",
        help="Directory containing data to process (default: current directory)"
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default=os.environ.get("AWS_BATCH_S3_BUCKET", "nextstrain-ml"),
        help="S3 bucket for job data (default: nextstrain-ml)"
    )
    parser.add_argument(
        "--job-definition",
        type=str,
        default=os.environ.get("AWS_BATCH_JOB_DEFINITION"),
        help="AWS Batch job definition name"
    )
    parser.add_argument(
        "--job-queue",
        type=str,
        default=os.environ.get("AWS_BATCH_JOB_QUEUE"),
        help="AWS Batch job queue name"
    )
    parser.add_argument(
        "--region",
        type=str,
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--attach",
        type=str,
        metavar="JOB_ID",
        help="Attach to an existing job (skips upload and submission)"
    )

    args = parser.parse_args()

    job_manager = JobManager(region=args.region)

    # Handle attach mode
    if args.attach:
        job_id = args.attach
        print(f"Attaching to job: {job_id}")
        print(f"Region: {args.region}")
        print()

        # Get job details
        try:
            job = job_manager.lookup_job(job_id)
            job_name = job["jobName"]
            status = job["status"]

            print(f"Job name: {job_name}")
            print(f"Current status: {status}")

            # Extract run_id from job if possible
            run_id = None
            if "container" in job and "environment" in job["container"]:
                for env_var in job["container"]["environment"]:
                    if env_var["name"] == "RUN_ID":
                        run_id = env_var["value"]
                        break

            if not run_id:
                # Try to extract from job name (format: mwe-run-xxx)
                if job_name.startswith("mwe-"):
                    run_id = job_name[4:]  # Remove "mwe-" prefix

            workdir = Path(args.directory).resolve()

        except Exception as e:
            print(f"Error looking up job: {e}", file=sys.stderr)
            return 1
    else:
        # Normal mode - validate required arguments
        if not args.job_definition:
            print("Error: --job-definition is required", file=sys.stderr)
            print("\nSet AWS_BATCH_JOB_DEFINITION environment variable or pass --job-definition", file=sys.stderr)
            return 1

        if not args.job_queue:
            print("Error: --job-queue is required", file=sys.stderr)
            print("\nSet AWS_BATCH_JOB_QUEUE environment variable or pass --job-queue", file=sys.stderr)
            return 1

        # Resolve workdir
        workdir = Path(args.directory).resolve()
        if not workdir.exists():
            print(f"Error: Directory '{workdir}' does not exist", file=sys.stderr)
            return 1

        # Check for input data
        input_file = workdir / "data" / "input.txt"
        if not input_file.exists():
            print(f"Warning: {input_file} does not exist", file=sys.stderr)
            print("Creating sample input.txt...", file=sys.stderr)
            input_file.parent.mkdir(exist_ok=True)
            input_file.write_text("Hello from local machine!\nThis was processed on AWS Batch.\n")

        # Generate unique run ID
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        print(f"Starting job: {run_id}")
        print(f"Workdir: {workdir}")
        print(f"Bucket: {args.bucket}")
        print(f"Region: {args.region}")
        print()

        # Upload workdir to S3
        print("=" * 60)
        print("UPLOADING TO S3")
        print("=" * 60)
        try:
            s3_url = upload_workdir(workdir, args.bucket, run_id, region=args.region)
        except Exception as e:
            print(f"Error uploading to S3: {e}", file=sys.stderr)
            return 1

        # Submit job to AWS Batch
        print()
        print("=" * 60)
        print("SUBMITTING JOB")
        print("=" * 60)

        try:
            job_id = job_manager.submit_job(
                job_name=f"mwe-{run_id}",
                job_definition=args.job_definition,
                job_queue=args.job_queue,
                workdir_url=s3_url,
                environment={"RUN_ID": run_id}
            )
            print(f"Job ID: {job_id}")

            # Save job ID to file for easy reattachment
            job_file = workdir / ".last-job-id"
            job_file.write_text(job_id)

        except Exception as e:
            print(f"Error submitting job: {e}", file=sys.stderr)
            return 1

        job_name = f"mwe-{run_id}"

    # Start log streaming
    print()
    print("=" * 60)
    print("MONITORING JOB (Ctrl-C to detach)")
    print("=" * 60)
    log_watcher = stream_job_logs(job_name, job_id, region=args.region)

    try:
        # Wait for job to complete
        final_job = job_manager.wait_for_job(
            job_id,
            callback=lambda job: print(format_job_status(job))
        )

        # Stop log streaming
        log_watcher.stop()

        print()
        print("=" * 60)

        # Check if job succeeded
        if final_job["status"] == "SUCCEEDED":
            print("JOB SUCCEEDED - DOWNLOADING RESULTS")
            print("=" * 60)

            # Download results (matches entrypoint naming: run-xxx-results.zip)
            results_url = f"s3://{args.bucket}/{run_id}-results.zip"
            try:
                download_workdir(results_url, workdir, region=args.region)
                print()
                print("=" * 60)
                print("SUCCESS!")
                print("=" * 60)

                # Show output if it exists
                output_file = workdir / "data" / "output.txt"
                if output_file.exists():
                    print("\nOutput file contents:")
                    print("-" * 40)
                    print(output_file.read_text())
                    print("-" * 40)

                return 0

            except Exception as e:
                print(f"Error downloading results: {e}", file=sys.stderr)
                return 1
        else:
            print("JOB FAILED")
            print("=" * 60)
            reason = final_job.get("statusReason", "Unknown error")
            print(f"Reason: {reason}")
            return 1

    except KeyboardInterrupt:
        print("\n\nDetaching from job...")
        print(f"Job is still running: {job_id}")
        print(f"\nTo reattach, run:")
        print(f"  python main.py --attach {job_id}")
        log_watcher.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
