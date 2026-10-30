#!/usr/bin/env python3
"""Antigravity on GCP Manager.

Manage GCP Always Free e2-micro VM, Antigravity CLI, and GitHub Actions Self-Hosted Runners.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add scripts directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from scripts.host import gcp_provision, gcp_ssh


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Parse a simple KEY=VALUE .env file without external dependencies."""
    config: Dict[str, str] = {}
    if not env_path.is_file():
        return config

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                config[key] = val
    return config


def fetch_runner_token(repo: str) -> Optional[str]:
    """Attempt to fetch GitHub Actions runner registration token via GitHub CLI (gh)."""
    gh_bin = shutil.which("gh")
    if not gh_bin:
        return None
    try:
        cmd = [gh_bin, "api", "--method", "POST", f"repos/{repo}/actions/runners/registration-token", "--jq", ".token"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        token = res.stdout.strip()
        if token and len(token) > 10:
            return token
    except Exception:
        pass
    return None


def get_config() -> Dict[str, str]:
    """Load configuration from .env or fallback to .env.example / defaults."""
    env_file = BASE_DIR / ".env"
    example_file = BASE_DIR / ".env.example"

    if not env_file.exists():
        if example_file.exists():
            print(f"[!] .env file not found. Copying from {example_file.name}...")
            shutil.copy(example_file, env_file)
        else:
            print("[!] Neither .env nor .env.example found. Creating minimal .env...")
            env_file.write_text("GCP_PROJECT_ID=cloud-execution-environment\n", encoding="utf-8")

    cfg = load_env_file(env_file)

    # Defaults
    defaults = {
        "GCP_PROJECT_ID": "cloud-execution-environment",
        "GCP_REGION": "us-west1",
        "GCP_ZONE": "us-west1-b",
        "GCP_INSTANCE_NAME": "agy-runner-vm",
        "GCP_MACHINE_TYPE": "e2-micro",
        "GCP_BOOT_DISK_SIZE": "30GB",
        "GCP_BOOT_DISK_TYPE": "pd-standard",
        "GCP_IMAGE_FAMILY": "ubuntu-2404-lts-amd64",
        "GCP_IMAGE_PROJECT": "ubuntu-os-cloud",
        "RUNNER_USER": "runner",
        "SWAP_SIZE_GB": "2",
        "AGY_VERSION": "1.4.10",
        "AGY_CLI_DISABLE_AUTO_UPDATE": "true",
        "TARGET_REPOS": "aegisfleet/tool-survey-report,aegisfleet/amazon-product-article",
    }
    for k, v in defaults.items():
        if k not in cfg or not cfg[k]:
            cfg[k] = v

    return cfg


def cmd_provision(cfg: Dict[str, str]) -> None:
    """Create the GCP Compute Engine e2-micro instance."""
    print("=== [Provision] Creating GCP Compute Engine VM ===")
    gcp_provision.create_instance(
        instance_name=cfg["GCP_INSTANCE_NAME"],
        project_id=cfg["GCP_PROJECT_ID"],
        zone=cfg["GCP_ZONE"],
        machine_type=cfg["GCP_MACHINE_TYPE"],
        boot_disk_size=cfg["GCP_BOOT_DISK_SIZE"],
        boot_disk_type=cfg["GCP_BOOT_DISK_TYPE"],
        image_family=cfg["GCP_IMAGE_FAMILY"],
        image_project=cfg["GCP_IMAGE_PROJECT"],
    )


def cmd_status(cfg: Dict[str, str]) -> None:
    """Check instance status and self-hosted runner status."""
    print("=== [Status] Checking VM & Services ===")
    info = gcp_provision.get_instance_info(
        cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"]
    )
    if not info:
        print(f"[-] Instance '{cfg['GCP_INSTANCE_NAME']}' does not exist.")
        return

    status = info.get("status", "UNKNOWN")
    print(f"[*] Instance: {cfg['GCP_INSTANCE_NAME']} ({status})")
    print(f"    - Machine Type: {info.get('machineType', '').split('/')[-1]}")
    print(f"    - Zone:         {cfg['GCP_ZONE']}")
    print(f"    - Project:      {cfg['GCP_PROJECT_ID']}")

    if status == "RUNNING":
        print("\n[*] Querying service statuses on VM...")
        cmd = (
            "echo '--- Memory & Swap ---'; free -h; "
            "echo '--- actions.runner Services ---'; systemctl list-units --type=service 'actions.runner.*' --no-pager || true; "
            "echo '--- agy Version ---'; agy --version 2>/dev/null || echo 'agy not yet installed'; "
            "echo '--- gh Version ---'; gh --version 2>/dev/null | head -n 1 || echo 'gh not yet installed'"
        )
        try:
            gcp_ssh.ssh_command(
                cfg["GCP_INSTANCE_NAME"],
                cfg["GCP_PROJECT_ID"],
                cfg["GCP_ZONE"],
                command=cmd,
                check=False,
            )
        except Exception as e:
            print(f"[!] Could not query VM services: {e}")


def cmd_setup(cfg: Dict[str, str]) -> None:
    """Upload setup scripts and configure the VM, agy, and runners."""
    print("=== [Setup] Full VM & Runner Configuration ===")

    # 1. Verify instance status
    info = gcp_provision.get_instance_info(
        cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"]
    )
    if not info:
        print(f"[!] Instance '{cfg['GCP_INSTANCE_NAME']}' not found. Please run provision first.")
        return
    if info.get("status") != "RUNNING":
        print(f"[!] Instance status is {info.get('status')}. Starting instance...")
        gcp_provision.start_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])
        print("[*] Waiting 15s for instance to initialize...")
        time.sleep(15)

    instance = cfg["GCP_INSTANCE_NAME"]
    project = cfg["GCP_PROJECT_ID"]
    zone = cfg["GCP_ZONE"]

    # 2. Upload scripts and templates
    print("\n[*] Transferring setup scripts to VM...")
    vm_scripts_dir = BASE_DIR / "scripts" / "vm"
    settings_template = BASE_DIR / "templates" / "settings.json"

    gcp_ssh.ssh_command(instance, project, zone, command="rm -rf /tmp/vm-scripts && mkdir -p /tmp/vm-scripts")
    gcp_ssh.scp_to_vm(str(vm_scripts_dir), "/tmp/vm-scripts", instance, project, zone)
    if settings_template.exists():
        gcp_ssh.scp_to_vm(str(settings_template), "/tmp/settings.json", instance, project, zone, recurse=False)

    gcp_ssh.ssh_command(instance, project, zone, command="chmod +x /tmp/vm-scripts/*.sh /tmp/vm-scripts/vm/*.sh 2>/dev/null || true")

    # Helper script locator on remote VM
    find_script = 'f="/tmp/vm-scripts/$1"; [ -f "$f" ] && echo "$f" || echo "/tmp/vm-scripts/vm/$1"'

    # 3. Phase 0 Gate Check: CPU instructions
    print("\n[*] Executing [00] CPU Gate Check (PCLMULQDQ)...")
    res = gcp_ssh.ssh_command(instance, project, zone, command='script=$(f="/tmp/vm-scripts/00-check-cpu.sh"; [ -f "$f" ] && echo "$f" || echo "/tmp/vm-scripts/vm/00-check-cpu.sh"); bash "$script"', check=False)
    if res.returncode != 0:
        print("[RED] CPU instruction check failed! Antigravity CLI may crash on this CPU.")
        print("Please check output above. Setup aborted.")
        return

    # 4. OS & Swap setup
    print("\n[*] Executing [01] OS setup & swap...")
    env_vars = f"SWAP_SIZE_GB={cfg.get('SWAP_SIZE_GB', '2')}"
    gcp_ssh.ssh_command(instance, project, zone, command=f'{env_vars} sudo -E bash $(f="/tmp/vm-scripts/01-setup-os.sh"; [ -f "$f" ] && echo "$f" || echo "/tmp/vm-scripts/vm/01-setup-os.sh")')

    # 5. Node.js & agy setup
    print(f"\n[*] Executing [02] Node.js & Antigravity CLI ({cfg.get('AGY_VERSION', '1.4.10')})...")
    agy_env = (
        f"RUNNER_USER={cfg.get('RUNNER_USER', 'runner')} "
        f"AGY_VERSION={cfg.get('AGY_VERSION', '1.4.10')} "
        f"AGY_CLI_DISABLE_AUTO_UPDATE={cfg.get('AGY_CLI_DISABLE_AUTO_UPDATE', 'true')}"
    )
    gcp_ssh.ssh_command(instance, project, zone, command=f'{agy_env} sudo -E bash $(f="/tmp/vm-scripts/02-setup-node-agy.sh"; [ -f "$f" ] && echo "$f" || echo "/tmp/vm-scripts/vm/02-setup-node-agy.sh")')

    # 6. GitHub CLI setup
    print("\n[*] Executing [03] GitHub CLI installation...")
    gcp_ssh.ssh_command(instance, project, zone, command='sudo -E bash $(f="/tmp/vm-scripts/03-setup-gh.sh"; [ -f "$f" ] && echo "$f" || echo "/tmp/vm-scripts/vm/03-setup-gh.sh")')

    # 7. Maintenance cron setup
    print("\n[*] Executing [05] Automated maintenance cleanup cron...")
    maint_env = f"RUNNER_USER={cfg.get('RUNNER_USER', 'runner')}"
    gcp_ssh.ssh_command(instance, project, zone, command=f'{maint_env} sudo -E bash $(f="/tmp/vm-scripts/05-setup-maintenance.sh"; [ -f "$f" ] && echo "$f" || echo "/tmp/vm-scripts/vm/05-setup-maintenance.sh")')

    # 8. GitHub Actions Runner setup (Interactive token input per repo)
    print("\n=== [04] GitHub Actions Runner Setup ===")
    target_repos = [r.strip() for r in cfg.get("TARGET_REPOS", "").split(",") if r.strip()]
    if not target_repos:
        print("[!] No TARGET_REPOS configured in .env.")
    else:
        print(f"Target repositories ({len(target_repos)}):")
        for repo in target_repos:
            print(f"  - {repo}")

        for repo in target_repos:
            print("\n------------------------------------------------------------")
            print(f"Setting up runner for: {repo}")
            token = fetch_runner_token(repo)
            if token:
                print(f"[OK] Automatically fetched registration token via GitHub CLI (gh).")
            else:
                print("[!] Could not fetch token automatically via gh CLI.")
                print("Please retrieve a runner registration token from:")
                print(f"  https://github.com/{repo}/settings/actions/runners/new")
                token = input(f"Enter registration token for {repo} (leave blank to skip): ").strip()

            if not token:
                print(f"[!] Skipped runner registration for {repo}.")
                continue

            runner_cmd = f"sudo bash $(f='/tmp/vm-scripts/04-setup-runner.sh'; [ -f \"$f\" ] && echo \"$f\" || echo '/tmp/vm-scripts/vm/04-setup-runner.sh') '{repo}' '{token}'"
            gcp_ssh.ssh_command(instance, project, zone, command=runner_cmd)

    # 9. Prompt for agy initial login
    print("\n============================================================")
    print("Base setup completed successfully!")
    print("Next step is Antigravity CLI (agy) OAuth authentication.")
    print("============================================================")
    ans = input("Do you want to start 'agy login' interactive session now? [Y/n]: ").strip().lower()
    if ans in ("", "y", "yes"):
        cmd_login_agy(cfg)


def cmd_login_agy(cfg: Dict[str, str]) -> None:
    """Launch interactive agy session on the VM for sign in."""
    print("=== Launching agy on VM for sign-in ===")
    print("Notice: Antigravity CLI does not use a 'login' subcommand.")
    print("Launching 'agy' without arguments triggers the Google OAuth sign-in flow.")
    print("Open the URL shown in your browser, approve, and paste the code if prompted.\n")
    instance = cfg["GCP_INSTANCE_NAME"]
    project = cfg["GCP_PROJECT_ID"]
    zone = cfg["GCP_ZONE"]
    runner_user = cfg.get("RUNNER_USER", "runner")

    # Launch agy without arguments as runner user with pseudo-terminal (-t)
    login_cmd = f"sudo -i -u {runner_user} agy"
    try:
        gcp_ssh.ssh_command(instance, project, zone, command=login_cmd, interactive=True, check=False)
    except Exception as e:
        print(f"[!] Session ended or interrupted: {e}")

    print("\n[*] Checking authentication status with 'agy models'...")
    check_cmd = f"sudo -i -u {runner_user} agy models"
    gcp_ssh.ssh_command(instance, project, zone, command=check_cmd, check=False)


def cmd_ssh(cfg: Dict[str, str]) -> None:
    """Connect to VM via interactive SSH through Cloud IAP."""
    print(f"=== Connecting to {cfg['GCP_INSTANCE_NAME']} via IAP Tunnel ===")
    gcp_ssh.ssh_command(
        cfg["GCP_INSTANCE_NAME"],
        cfg["GCP_PROJECT_ID"],
        cfg["GCP_ZONE"],
        interactive=True,
    )


def interactive_menu(cfg: Dict[str, str]) -> None:
    """Show interactive CLI menu."""
    while True:
        print("\n==================================================")
        print("    Antigravity on GCP Management Console        ")
        print("==================================================")
        print(f"Project:  {cfg['GCP_PROJECT_ID']}")
        print(f"Instance: {cfg['GCP_INSTANCE_NAME']} ({cfg['GCP_ZONE']})")
        print("--------------------------------------------------")
        print("1) Provision VM (e2-micro Always Free)")
        print("2) Run Full Setup (OS, Swap, Node, agy, Runners)")
        print("3) Authenticate agy (Interactive OAuth Login)")
        print("4) Connect via SSH (IAP Tunnel)")
        print("5) Check Status (VM & runner services)")
        print("6) Start VM")
        print("7) Stop VM")
        print("8) Delete VM")
        print("q) Exit")
        print("--------------------------------------------------")
        choice = input("Select an option [1-8 / q]: ").strip().lower()

        if choice == "1":
            cmd_provision(cfg)
        elif choice == "2":
            cmd_setup(cfg)
        elif choice == "3":
            cmd_login_agy(cfg)
        elif choice == "4":
            cmd_ssh(cfg)
        elif choice == "5":
            cmd_status(cfg)
        elif choice == "6":
            gcp_provision.start_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])
        elif choice == "7":
            gcp_provision.stop_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])
        elif choice == "8":
            confirm = input(f"Are you sure you want to delete {cfg['GCP_INSTANCE_NAME']}? [y/N]: ").strip().lower()
            if confirm in ("y", "yes"):
                gcp_provision.delete_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])
        elif choice in ("q", "quit", "exit"):
            print("Exiting.")
            break
        else:
            print("[!] Invalid option. Please try again.")


def main() -> None:
    """Main CLI entrypoint."""
    if not gcp_provision.check_gcloud_installed():
        print("[ERROR] 'gcloud' CLI is not installed or not in PATH.")
        print("Please install Google Cloud SDK: https://cloud.google.com/sdk/docs/install")
        sys.exit(1)

    cfg = get_config()

    parser = argparse.ArgumentParser(description="Antigravity on GCP e2-micro Self-Hosted Runner Manager")
    subparsers = parser.add_subparsers(dest="subcommand", help="Available commands")

    subparsers.add_parser("provision", help="Create Compute Engine e2-micro instance")
    subparsers.add_parser("setup", help="Run full VM provisioning (swap, agy, runners)")
    subparsers.add_parser("login-agy", help="Run interactive agy OAuth login")
    subparsers.add_parser("ssh", help="Connect to VM via Cloud IAP SSH")
    subparsers.add_parser("status", help="Check status of VM and runner services")
    subparsers.add_parser("start", help="Start the GCP instance")
    subparsers.add_parser("stop", help="Stop the GCP instance")
    subparsers.add_parser("delete", help="Delete the GCP instance")

    args = parser.parse_args()

    if not args.subcommand:
        interactive_menu(cfg)
    elif args.subcommand == "provision":
        cmd_provision(cfg)
    elif args.subcommand == "setup":
        cmd_setup(cfg)
    elif args.subcommand == "login-agy":
        cmd_login_agy(cfg)
    elif args.subcommand == "ssh":
        cmd_ssh(cfg)
    elif args.subcommand == "status":
        cmd_status(cfg)
    elif args.subcommand == "start":
        gcp_provision.start_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])
    elif args.subcommand == "stop":
        gcp_provision.stop_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])
    elif args.subcommand == "delete":
        gcp_provision.delete_instance(cfg["GCP_INSTANCE_NAME"], cfg["GCP_PROJECT_ID"], cfg["GCP_ZONE"])


if __name__ == "__main__":
    main()
