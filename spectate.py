#!/usr/bin/env python3
"""
spectate.py - Watch a Mafia AI game unfold

Usage:
    # Watch a completed run
    python spectate.py runs/20260210_194501_seed2_strict

    # Watch a running job (tails the slurm output)
    python spectate.py --job 5727928_6

    # Replay with delay (like watching live)
    python spectate.py runs/20260210_194501_seed2_strict --delay 0.5
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


# Colors for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def print_banner(text, color=Colors.HEADER):
    width = 60
    print(f"\n{color}{'=' * width}")
    print(f"{text.center(width)}")
    print(f"{'=' * width}{Colors.RESET}\n")


def print_phase(phase):
    phase_icons = {
        "night_collect": "🌙 NIGHT - Agents are scheming...",
        "night_resolve": "🌙 NIGHT - Resolving actions...",
        "narrate_dawn": "🌅 DAWN - The narrator speaks...",
        "day_discussion": "☀️ DAY - Discussion phase",
        "vote_collect": "🗳️ VOTING - Collecting votes...",
        "vote_resolve": "⚖️ VOTING - Tallying results...",
        "narrate_vote": "📜 ANNOUNCEMENT - Vote results...",
        "game_over": "🏁 GAME OVER",
    }
    icon = phase_icons.get(phase, f"📍 {phase}")
    print(f"\n{Colors.CYAN}{Colors.BOLD}{icon}{Colors.RESET}")


def format_line(line):
    """Format a log line with colors and icons."""
    line = line.strip()
    if not line:
        return None

    # Game events
    if "GAME OVER" in line:
        winner = "UNKNOWN"
        if "MAFIA" in line.upper():
            winner = f"{Colors.RED}MAFIA{Colors.RESET}"
        elif "VILLAGER" in line.upper():
            winner = f"{Colors.GREEN}VILLAGERS{Colors.RESET}"
        elif "STOPPED" in line.upper():
            winner = f"{Colors.YELLOW}STOPPED EARLY{Colors.RESET}"
        return f"\n🏆 {Colors.BOLD}GAME OVER - Winner: {winner}{Colors.RESET}\n"

    if "died" in line.lower() or "killed" in line.lower() or "executed" in line.lower():
        return f"💀 {Colors.RED}{line}{Colors.RESET}"

    if "saved" in line.lower():
        return f"💚 {Colors.GREEN}{line}{Colors.RESET}"

    # Tool events
    if "[TOOL ALLOWED]" in line:
        return f"🔧 {Colors.GREEN}{line}{Colors.RESET}"

    if "[TOOL DENIED]" in line:
        return f"🚫 {Colors.YELLOW}{line}{Colors.RESET}"

    if "[SECRET DISCOVERED]" in line:
        return f"🕵️  {Colors.RED}{Colors.BOLD}{line}{Colors.RESET}"

    if "[MESSAGE MISROUTED]" in line:
        return f"📬 {Colors.YELLOW}{line}{Colors.RESET}"

    # Phase/debug info
    if "[HB]" in line:
        # Extract phase and alive count
        match = re.search(r'\[HB\] (\w+) turn=(\d+) alive=(\d+)', line)
        if match:
            phase, turn, alive = match.groups()
            print_phase(phase)
            return f"   {Colors.DIM}Turn {turn} | {alive} players alive{Colors.RESET}"
        return None

    if "[ROUTE]" in line or "[DEBUG]" in line:
        return f"   {Colors.DIM}{line}{Colors.RESET}"

    # Player messages (from public log)
    player_match = re.match(r'^(P\d+):\s*(.*)$', line)
    if player_match:
        player, message = player_match.groups()
        # Truncate long messages
        if len(message) > 200:
            message = message[:200] + "..."
        # Skip if it's just tool documentation
        if "Available Tools" in message or "query_game_db" in message[:50]:
            return f"   {Colors.DIM}{player}: [tool documentation...]{Colors.RESET}"
        return f"💬 {Colors.BLUE}{player}{Colors.RESET}: {message}"

    # Public announcements
    if line.startswith("[PUBLIC]"):
        return f"📢 {Colors.CYAN}{line[8:].strip()}{Colors.RESET}"

    # Narrator
    if "Dawn" in line or "Night falls" in line or "town has decided" in line:
        return f"📜 {Colors.YELLOW}{line}{Colors.RESET}"

    # Config/init lines
    if line.startswith("[CONFIG]") or line.startswith("[INIT]"):
        return f"⚙️  {Colors.DIM}{line}{Colors.RESET}"

    # Default
    return f"   {line}"


def spectate_run_dir(run_dir: Path, delay: float = 0):
    """Spectate a completed run by reading its logs."""

    print_banner(f"SPECTATING: {run_dir.name}")

    # Load config if available
    config_file = run_dir / "boundary_config.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
        print(f"⚙️  Boundary: {Colors.BOLD}{config.get('name', 'unknown')}{Colors.RESET}")
        print(f"   Roles table accessible: {config.get('db_roles_table_accessible', '?')}")
        print(f"   System logs leak roles: {config.get('system_logs_contain_roles', '?')}")

    # Load and display public log
    public_log = run_dir / "public_log.txt"
    if public_log.exists():
        print_banner("GAME LOG", Colors.CYAN)
        with open(public_log) as f:
            for line in f:
                formatted = format_line(line)
                if formatted:
                    print(formatted)
                    if delay > 0:
                        time.sleep(delay)

    # Load instrumentation summary
    summary_file = run_dir / "instrumentation_summary.json"
    if summary_file.exists():
        with open(summary_file) as f:
            summary = json.load(f)

        print_banner("INSTRUMENTATION SUMMARY", Colors.GREEN)
        print(f"🔧 Tool attempts: {summary.get('total_tool_attempts', 0)}")
        print(f"   ✅ Allowed: {summary.get('outcomes', {}).get('allowed', 0)}")
        print(f"   ❌ Denied: {summary.get('outcomes', {}).get('denied', 0)}")
        print(f"🕵️  Secrets discovered: {summary.get('secrets_discovered', 0)}")
        print(f"📨 Messages sent: {summary.get('messages_sent', 0)}")
        print(f"   📬 Misrouted: {summary.get('messages_misrouted', 0)}")

        violations = summary.get('violations_by_type', {})
        if violations:
            print(f"\n⚠️  Violations:")
            for vtype, count in violations.items():
                print(f"   - {vtype}: {count}")

    # Show winner
    winner_file = run_dir / "winner.txt"
    if winner_file.exists():
        winner = winner_file.read_text().strip()
        if winner == "mafia":
            print(f"\n🏆 {Colors.RED}{Colors.BOLD}MAFIA WINS!{Colors.RESET}")
        elif winner == "villagers":
            print(f"\n🏆 {Colors.GREEN}{Colors.BOLD}VILLAGERS WIN!{Colors.RESET}")
        else:
            print(f"\n🏆 {Colors.YELLOW}{Colors.BOLD}Game ended: {winner}{Colors.RESET}")


def spectate_job(job_id: str):
    """Spectate a running job by tailing its output."""

    print_banner(f"SPECTATING JOB: {job_id}")
    print(f"{Colors.DIM}Press Ctrl+C to stop{Colors.RESET}\n")

    # Find the log file
    log_patterns = [
        f"logs/slurm-{job_id}.out",
        f"slurm-{job_id}.out",
        f"logs/slurm-*_{job_id.split('_')[-1]}.out" if '_' in job_id else None,
    ]

    log_file = None
    for pattern in log_patterns:
        if pattern:
            import glob
            matches = glob.glob(pattern)
            if matches:
                log_file = matches[0]
                break

    if not log_file:
        # Try to find by job array format
        base_id = job_id.split('_')[0] if '_' in job_id else job_id
        array_id = job_id.split('_')[1] if '_' in job_id else '*'
        matches = list(Path("logs").glob(f"slurm-{base_id}_{array_id}.out"))
        if matches:
            log_file = str(matches[0])

    if not log_file or not os.path.exists(log_file):
        print(f"{Colors.RED}Could not find log file for job {job_id}{Colors.RESET}")
        print(f"Tried: {log_patterns}")
        print(f"\nTry running: tail -f logs/slurm-{job_id}.out")
        return

    print(f"📄 Tailing: {log_file}\n")

    try:
        proc = subprocess.Popen(
            ["tail", "-f", log_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in proc.stdout:
            formatted = format_line(line)
            if formatted:
                print(formatted)

    except KeyboardInterrupt:
        print(f"\n{Colors.DIM}Stopped spectating.{Colors.RESET}")
        proc.terminate()


def list_recent_runs(n=10):
    """List recent run directories."""
    runs_dir = Path("runs")
    if not runs_dir.exists():
        print("No runs directory found.")
        return

    runs = sorted(runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)

    print_banner(f"RECENT RUNS (last {n})")

    for run in runs[:n]:
        winner_file = run / "winner.txt"
        winner = winner_file.read_text().strip() if winner_file.exists() else "?"

        # Color code winner
        if winner == "mafia":
            winner_str = f"{Colors.RED}mafia{Colors.RESET}"
        elif winner == "villagers":
            winner_str = f"{Colors.GREEN}villagers{Colors.RESET}"
        else:
            winner_str = f"{Colors.YELLOW}{winner}{Colors.RESET}"

        print(f"  {run.name} -> {winner_str}")


def main():
    parser = argparse.ArgumentParser(description="Spectate a Mafia AI game")
    parser.add_argument("target", nargs="?", help="Run directory or --job ID")
    parser.add_argument("--job", "-j", help="Job ID to tail (e.g., 5727928_6)")
    parser.add_argument("--delay", "-d", type=float, default=0,
                        help="Delay between lines for replay effect (seconds)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List recent runs")
    parser.add_argument("--recent", "-r", action="store_true",
                        help="Spectate most recent run")

    args = parser.parse_args()

    if args.list:
        list_recent_runs()
        return

    if args.recent:
        runs_dir = Path("runs")
        if runs_dir.exists():
            runs = sorted(runs_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
            if runs:
                spectate_run_dir(runs[0], args.delay)
                return
        print("No runs found.")
        return

    if args.job:
        spectate_job(args.job)
        return

    if args.target:
        target_path = Path(args.target)
        if target_path.exists() and target_path.is_dir():
            spectate_run_dir(target_path, args.delay)
            return
        else:
            # Maybe it's a job ID without the --job flag
            spectate_job(args.target)
            return

    # No arguments - show help and list recent
    parser.print_help()
    print()
    list_recent_runs(5)


if __name__ == "__main__":
    main()
