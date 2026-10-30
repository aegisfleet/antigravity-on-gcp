#!/usr/bin/env python3
"""GCP Compute Engine provisioning helper using gcloud CLI."""

import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional


def get_gcloud_bin() -> str:
    """Find gcloud executable across Windows and Unix platforms."""
    # Check standard PATH
    candidate = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if candidate:
        return candidate

    # Common Windows default path check
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        win_sdk_cmd = os.path.join(local_app_data, "Google", "Cloud SDK", "google-cloud-sdk", "bin", "gcloud.cmd")
        if os.path.isfile(win_sdk_cmd):
            return win_sdk_cmd

    return "gcloud"


def check_gcloud_installed() -> bool:
    """Verify that gcloud CLI is available."""
    bin_path = get_gcloud_bin()
    try:
        res = subprocess.run([bin_path, "--version"], capture_output=True, text=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def run_gcloud(args: List[str], check: bool = True, capture_output: bool = False) -> subprocess.CompletedProcess:
    """Execute a gcloud command."""
    bin_path = get_gcloud_bin()
    return subprocess.run([bin_path] + args, check=check, capture_output=capture_output, text=True, encoding="utf-8")


def ensure_iap_firewall_rule(project_id: str) -> None:
    """Ensure firewall rule exists to allow SSH ingress through Cloud IAP."""
    rule_name = "allow-ssh-ingress-from-iap"
    print(f"[*] Checking firewall rule '{rule_name}' for Cloud IAP...")
    check_cmd = [
        "compute", "firewall-rules", "describe", rule_name,
        f"--project={project_id}",
        "--format=json",
    ]
    res = run_gcloud(check_cmd, check=False, capture_output=True)
    if res.returncode == 0:
        print(f"[OK] Firewall rule '{rule_name}' already exists.")
        return

    print(f"[*] Creating firewall rule '{rule_name}' (source: 35.235.240.0/20, port: 22)...")
    create_cmd = [
        "compute", "firewall-rules", "create", rule_name,
        f"--project={project_id}",
        "--direction=INGRESS",
        "--action=ALLOW",
        "--rules=tcp:22",
        "--source-ranges=35.235.240.0/20",
        "--description=Allow incoming SSH connections from Cloud IAP tunnel",
    ]
    run_gcloud(create_cmd, check=True)
    print(f"[OK] Firewall rule '{rule_name}' created successfully.")


def get_instance_info(instance_name: str, project_id: str, zone: str) -> Optional[Dict[str, Any]]:
    """Get instance description in JSON format."""
    cmd = [
        "compute", "instances", "describe", instance_name,
        f"--project={project_id}",
        f"--zone={zone}",
        "--format=json",
    ]
    res = run_gcloud(cmd, check=False, capture_output=True)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def create_instance(
    instance_name: str,
    project_id: str,
    zone: str,
    machine_type: str = "e2-micro",
    boot_disk_size: str = "30GB",
    boot_disk_type: str = "pd-standard",
    image_family: str = "ubuntu-2404-lts-amd64",
    image_project: str = "ubuntu-os-cloud",
) -> None:
    """Create an e2-micro Compute Engine instance."""
    existing = get_instance_info(instance_name, project_id, zone)
    if existing:
        status = existing.get("status", "UNKNOWN")
        print(f"[!] Instance '{instance_name}' already exists (Status: {status}).")
        return

    ensure_iap_firewall_rule(project_id)

    print(f"[*] Provisioning GCP Compute Engine instance '{instance_name}'...")
    print(f"    - Project:      {project_id}")
    print(f"    - Zone:         {zone}")
    print(f"    - Machine Type: {machine_type} (Always Free eligible)")
    print(f"    - Boot Disk:    {boot_disk_size} ({boot_disk_type})")
    print(f"    - OS Image:     {image_family} ({image_project})")

    cmd = [
        "compute", "instances", "create", instance_name,
        f"--project={project_id}",
        f"--zone={zone}",
        f"--machine-type={machine_type}",
        f"--boot-disk-size={boot_disk_size}",
        f"--boot-disk-type={boot_disk_type}",
        f"--image-family={image_family}",
        f"--image-project={image_project}",
        "--tags=iap-ssh",
        "--metadata=enable-oslogin=TRUE",
    ]
    run_gcloud(cmd, check=True)
    print(f"[OK] Instance '{instance_name}' created successfully.")


def start_instance(instance_name: str, project_id: str, zone: str) -> None:
    """Start the GCP instance."""
    cmd = ["compute", "instances", "start", instance_name, f"--project={project_id}", f"--zone={zone}"]
    run_gcloud(cmd, check=True)
    print(f"[OK] Instance '{instance_name}' started.")


def stop_instance(instance_name: str, project_id: str, zone: str) -> None:
    """Stop the GCP instance."""
    cmd = ["compute", "instances", "stop", instance_name, f"--project={project_id}", f"--zone={zone}"]
    run_gcloud(cmd, check=True)
    print(f"[OK] Instance '{instance_name}' stopped.")


def delete_instance(instance_name: str, project_id: str, zone: str) -> None:
    """Delete the GCP instance."""
    cmd = ["compute", "instances", "delete", instance_name, f"--project={project_id}", f"--zone={zone}", "--quiet"]
    run_gcloud(cmd, check=True)
    print(f"[OK] Instance '{instance_name}' deleted.")
