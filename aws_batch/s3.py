"""S3 operations for workdir upload and download."""

import os
import io
import time
from pathlib import Path
from zipfile import ZipFile, ZipInfo
from zlib import crc32
import fsspec
import boto3


# Default exclusion patterns
DEFAULT_EXCLUDES = {
    "env",
    ".git",
    ".snakemake",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "*.egg-info",
    ".pytest_cache",
    ".coverage",
    "*.log",
}

# Snakemake subdirs to preserve
SNAKEMAKE_PRESERVE = {
    "log",
    "metadata",
    "storage",
}


def should_exclude(path, excludes=None):
    """Check if a path should be excluded from upload.

    Args:
        path: Path to check
        excludes: Set of exclusion patterns

    Returns:
        True if path should be excluded
    """
    if excludes is None:
        excludes = DEFAULT_EXCLUDES
    # Check direct matches
    if path.name in excludes:
        return True

    # Check patterns
    for pattern in excludes:
        if pattern.startswith("*") and path.name.endswith(pattern[1:]):
            return True

    # Special handling for .snakemake subdirectories
    parts = path.parts
    if ".snakemake" in parts:
        snakemake_idx = parts.index(".snakemake")
        if snakemake_idx + 1 < len(parts):
            subdir = parts[snakemake_idx + 1]
            if subdir not in SNAKEMAKE_PRESERVE:
                return True

    return False


def upload_workdir(
    workdir,
    bucket,
    run_id,
    excludes=None,
    region="us-east-1",
):
    """Upload working directory to S3 as a ZIP file.

    Streams directly to S3 without creating a local ZIP file.

    Args:
        workdir: Local directory to upload
        bucket: S3 bucket name
        run_id: Unique run identifier
        excludes: Additional exclusion patterns
        region: AWS region

    Returns:
        S3 URL for the uploaded workdir
    """
    if excludes is None:
        excludes = DEFAULT_EXCLUDES
    else:
        excludes = DEFAULT_EXCLUDES.union(excludes)

    s3_key = f"{run_id}.zip"
    s3_url = f"s3://{bucket}/{s3_key}"

    print(f"Uploading workdir to {s3_url}...")
    start_time = time.time()

    # Count files for progress
    total_files = sum(
        1
        for root, dirs, files in os.walk(workdir)
        for f in files
        if not should_exclude(Path(root) / f, excludes)
    )

    uploaded = 0

    # Stream ZIP directly to S3 using fsspec
    with fsspec.open(s3_url, "wb") as remote_file:
        with ZipFile(remote_file, "w") as zipf:
            for root, dirs, files in os.walk(workdir):
                # Filter directories in place
                dirs[:] = [
                    d for d in dirs if not should_exclude(Path(root) / d, excludes)
                ]

                for file in files:
                    file_path = Path(root) / file
                    if should_exclude(file_path, excludes):
                        continue

                    # Add file to ZIP with relative path
                    arcname = file_path.relative_to(workdir)
                    zipf.write(file_path, arcname)

                    uploaded += 1
                    if uploaded % 100 == 0:
                        print(f"  Uploaded {uploaded}/{total_files} files...")

    elapsed = time.time() - start_time
    print(f"Upload complete: {uploaded} files in {elapsed:.1f}s")

    return s3_url


def download_workdir(
    s3_url,
    workdir,
    overwrite=False,
    check_crc=True,
    region="us-east-1",
):
    """Download and extract workdir from S3.

    Only downloads files that have changed (based on CRC32).

    Args:
        s3_url: S3 URL of the workdir ZIP
        workdir: Local directory to extract to
        overwrite: Whether to overwrite without checking
        check_crc: Whether to check CRC32 before overwriting
        region: AWS region

    Returns:
        Number of files extracted
    """
    print(f"Downloading workdir from {s3_url}...")
    start_time = time.time()

    # Ensure workdir exists
    workdir.mkdir(parents=True, exist_ok=True)

    extracted = 0
    skipped = 0

    # Stream ZIP from S3
    with fsspec.open(s3_url, "rb") as remote_file:
        with ZipFile(remote_file, "r") as zipf:
            members = zipf.namelist()
            total_files = len(members)

            for member_name in members:
                member = zipf.getinfo(member_name)
                target_path = workdir / member_name

                # Check if we need to extract
                should_extract = overwrite or not target_path.exists()

                if not should_extract and check_crc and target_path.is_file():
                    # Compare CRC32
                    with open(target_path, "rb") as f:
                        local_crc = crc32(f.read())

                    if local_crc != member.CRC:
                        should_extract = True

                if should_extract:
                    # Ensure parent directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Extract file
                    with zipf.open(member) as source:
                        with open(target_path, "wb") as target:
                            target.write(source.read())

                    # Preserve modification time
                    date_time = time.mktime(member.date_time + (0, 0, -1))
                    os.utime(target_path, (date_time, date_time))

                    extracted += 1
                else:
                    skipped += 1

                if (extracted + skipped) % 100 == 0:
                    print(f"  Processed {extracted + skipped}/{total_files} files...")

    elapsed = time.time() - start_time
    print(
        f"Download complete: {extracted} extracted, {skipped} unchanged ({elapsed:.1f}s)"
    )

    return extracted


def list_bucket_runs(
    bucket,
    prefix=None,
    region="us-east-1",
):
    """List run IDs in an S3 bucket.

    Args:
        bucket: S3 bucket name
        prefix: Optional prefix to filter by
        region: AWS region

    Returns:
        List of run IDs
    """
    s3 = boto3.client("s3", region_name=region)

    params = {"Bucket": bucket}
    if prefix:
        params["Prefix"] = prefix

    run_ids = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(**params):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".zip"):
                run_id = key[:-4]  # Remove .zip extension
                run_ids.append(run_id)

    return run_ids


def delete_run(
    bucket,
    run_id,
    region="us-east-1",
):
    """Delete a run's data from S3.

    Args:
        bucket: S3 bucket name
        run_id: Run ID to delete
        region: AWS region
    """
    s3 = boto3.client("s3", region_name=region)
    s3_key = f"{run_id}.zip"

    try:
        s3.delete_object(Bucket=bucket, Key=s3_key)
        print(f"Deleted {s3_key} from {bucket}")
    except Exception as e:
        print(f"Error deleting {s3_key}: {e}")


def get_run_size(
    bucket,
    run_id,
    region="us-east-1",
):
    """Get the size of a run's ZIP file in S3.

    Args:
        bucket: S3 bucket name
        run_id: Run ID
        region: AWS region

    Returns:
        Size in bytes or None if not found
    """
    s3 = boto3.client("s3", region_name=region)
    s3_key = f"{run_id}.zip"

    try:
        response = s3.head_object(Bucket=bucket, Key=s3_key)
        return response["ContentLength"]
    except Exception:
        return None
