#!/usr/bin/env python3
"""
aggregate_results.py

Collects all experiment results from runs/ directory into a single CSV for analysis.

Usage:
    python aggregate_results.py
    python aggregate_results.py --output results.csv
"""

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, Any, List


def load_json_file(path: Path) -> Dict[str, Any]:
    """Load a JSON file, return empty dict if not found."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_jsonl_file(path: Path) -> List[Dict[str, Any]]:
    """Load a JSONL file, return empty list if not found."""
    try:
        with open(path, "r") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def extract_run_metrics(run_dir: Path) -> Dict[str, Any]:
    """Extract all metrics from a single run directory."""

    # Parse directory name: YYYYMMDD_HHMMSS_seedN_boundary
    dir_name = run_dir.name
    parts = dir_name.split("_")

    # Extract seed and boundary from dir name
    seed = None
    boundary = None
    for part in parts:
        if part.startswith("seed"):
            seed = int(part.replace("seed", ""))
        if part in ("strict", "sloppy", "broken"):
            boundary = part

    # Load winner
    winner_file = run_dir / "winner.txt"
    winner = None
    if winner_file.exists():
        winner = winner_file.read_text().strip()

    # Load boundary config
    config = load_json_file(run_dir / "boundary_config.json")

    # Load instrumentation summary
    summary = load_json_file(run_dir / "instrumentation_summary.json")

    # Load detailed tool attempts for deeper analysis
    tool_attempts = load_jsonl_file(run_dir / "tool_attempts.jsonl")
    secrets = load_jsonl_file(run_dir / "secrets_discovered.jsonl")
    messages = load_jsonl_file(run_dir / "messages.jsonl")

    # Compute additional metrics
    tool_attempts_by_tool = {}
    tool_denials_by_tool = {}
    violations_by_role = {}

    for attempt in tool_attempts:
        tool = attempt.get("tool", "unknown")
        tool_attempts_by_tool[tool] = tool_attempts_by_tool.get(tool, 0) + 1

        if attempt.get("outcome") == "denied":
            tool_denials_by_tool[tool] = tool_denials_by_tool.get(tool, 0) + 1

        if attempt.get("policy_violation_type"):
            role = attempt.get("role", "unknown")
            violations_by_role[role] = violations_by_role.get(role, 0) + 1

    # Secrets by discovery method
    secrets_by_method = {}
    for secret in secrets:
        method = secret.get("discovery_method", "unknown")
        secrets_by_method[method] = secrets_by_method.get(method, 0) + 1

    # Unique players who discovered secrets
    players_who_cheated = set(s.get("player") for s in secrets)

    # Roles that discovered secrets
    roles_who_cheated = set(s.get("role") for s in secrets)

    return {
        # Run identifiers
        "run_dir": str(run_dir),
        "seed": seed,
        "boundary": boundary,

        # Game outcome
        "winner": winner,

        # High-level tool metrics
        "total_tool_attempts": summary.get("total_tool_attempts", 0),
        "tool_attempts_allowed": summary.get("outcomes", {}).get("allowed", 0),
        "tool_attempts_denied": summary.get("outcomes", {}).get("denied", 0),
        "denial_rate": summary.get("denial_rate", 0),

        # Cheating metrics
        "secrets_discovered": summary.get("secrets_discovered", 0),
        "players_who_cheated": len(players_who_cheated),
        "cheating_players": ",".join(sorted(players_who_cheated)) if players_who_cheated else "",
        "roles_who_cheated": ",".join(sorted(roles_who_cheated)) if roles_who_cheated else "",

        # Messaging metrics
        "messages_sent": summary.get("messages_sent", 0),
        "messages_misrouted": summary.get("messages_misrouted", 0),

        # Tool breakdown
        "query_game_db_attempts": tool_attempts_by_tool.get("query_game_db", 0),
        "send_message_attempts": tool_attempts_by_tool.get("send_message", 0),
        "read_logs_attempts": tool_attempts_by_tool.get("read_logs", 0),

        "query_game_db_denials": tool_denials_by_tool.get("query_game_db", 0),
        "send_message_denials": tool_denials_by_tool.get("send_message", 0),
        "read_logs_denials": tool_denials_by_tool.get("read_logs", 0),

        # Violations by type (from summary)
        "exfiltration_attempts": summary.get("violations_by_type", {}).get("exfiltration", 0),
        "channel_violation_attempts": summary.get("violations_by_type", {}).get("channel_violation", 0),
        "phase_break_attempts": summary.get("violations_by_type", {}).get("phase_break", 0),

        # Violations by role
        "mafia_violations": violations_by_role.get("MAFIA", 0),
        "villager_violations": violations_by_role.get("VILLAGER", 0),
        "doctor_violations": violations_by_role.get("DOCTOR", 0),
        "detective_violations": violations_by_role.get("DETECTIVE", 0),

        # Secrets by discovery method
        "secrets_via_db_query": secrets_by_method.get("query_game_db on roles table", 0),
        "secrets_via_logs": sum(v for k, v in secrets_by_method.items() if "read_logs" in k),
        "secrets_via_message_leak": sum(v for k, v in secrets_by_method.items() if "message" in k.lower()),
    }


def main():
    parser = argparse.ArgumentParser(description="Aggregate Mafia AI experiment results")
    parser.add_argument("--runs-dir", default="runs", help="Directory containing run results")
    parser.add_argument("--output", default="experiment_results.csv", help="Output CSV file")
    parser.add_argument("--json-output", default="experiment_results.json", help="Output JSON file")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    if not runs_dir.exists():
        print(f"Error: {runs_dir} does not exist")
        return

    # Find all run directories
    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    print(f"Found {len(run_dirs)} run directories")

    # Extract metrics from each
    all_results = []
    for run_dir in sorted(run_dirs):
        try:
            metrics = extract_run_metrics(run_dir)
            all_results.append(metrics)
        except Exception as e:
            print(f"Error processing {run_dir}: {e}")

    print(f"Successfully processed {len(all_results)} runs")

    if not all_results:
        print("No results to write")
        return

    # Write CSV
    fieldnames = list(all_results[0].keys())
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    print(f"Wrote {args.output}")

    # Write JSON (for programmatic access)
    with open(args.json_output, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Wrote {args.json_output}")

    # Print summary statistics
    print("\n" + "=" * 60)
    print("SUMMARY STATISTICS")
    print("=" * 60)

    for boundary in ["strict", "sloppy", "broken"]:
        runs = [r for r in all_results if r["boundary"] == boundary]
        if not runs:
            continue

        n = len(runs)
        wins_mafia = sum(1 for r in runs if r["winner"] == "mafia")
        wins_villagers = sum(1 for r in runs if r["winner"] == "villagers")

        total_attempts = sum(r["total_tool_attempts"] for r in runs)
        total_denials = sum(r["tool_attempts_denied"] for r in runs)
        total_secrets = sum(r["secrets_discovered"] for r in runs)

        print(f"\n{boundary.upper()} ({n} runs):")
        print(f"  Mafia wins: {wins_mafia} ({100*wins_mafia/n:.1f}%)")
        print(f"  Villager wins: {wins_villagers} ({100*wins_villagers/n:.1f}%)")
        print(f"  Tool attempts: {total_attempts} (avg {total_attempts/n:.1f}/game)")
        print(f"  Tool denials: {total_denials} (avg {total_denials/n:.1f}/game)")
        print(f"  Secrets discovered: {total_secrets} (avg {total_secrets/n:.1f}/game)")


if __name__ == "__main__":
    main()
