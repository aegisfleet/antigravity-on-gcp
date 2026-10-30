#!/usr/bin/env python3
"""GCP SSH and SCP helper using gcloud CLI with IAP tunneling."""

import os
import subprocess
import sys
from typing import List, Optional

from scripts.host.gcp_provision import get_gcloud_bin


def ssh_command(
    instance_name: str,
    project_id: str,
    zone: str,
    command: Optional[str] = None,
    interactive: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a command on the GCP VM via gcloud compute ssh through IAP tunnel."""
    bin_path = get_gcloud_bin()
    args = [
        bin_path,
        "compute",
        "ssh",
        instance_name,
        f"--project={project_id}",
        f"--zone={zone}",
        "--tunnel-through-iap",
        "--strict-host-key-checking=no",
    ]
    if command:
        args.extend(["--command", command])

    if interactive:
        # Pass stdin/stdout directly to allow interactive sessions (like agy login)
        return subprocess.run(args, check=check)
    else:
        return subprocess.run(args, check=check, text=True, encoding="utf-8")


def scp_to_vm(
    local_path: str,
    remote_path: str,
    instance_name: str,
    project_id: str,
    zone: str,
    recurse: bool = True,
) -> subprocess.CompletedProcess:
    """Transfer local files/directories to GCP VM via gcloud compute scp."""
    bin_path = get_gcloud_bin()
    args = [
        bin_path,
        "compute",
        "scp",
    ]
    if recurse:
        args.append("--recurse")

    args.extend([
        local_path,
        f"{instance_name}:{remote_path}",
        f"--project={project_id}",
        f"--zone={zone}",
        "--tunnel-through-iap",
        "--strict-host-key-checking=no",
    ])
    return subprocess.run(args, check=True, text=True, encoding="utf-8")
