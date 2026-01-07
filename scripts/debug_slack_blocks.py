#!/usr/bin/env python3
"""Debug script to test Slack Block Kit payloads."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any

def get_webhook_url() -> str:
    """Get Slack webhook URL from environment variable."""
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("Error: SLACK_WEBHOOK_URL environment variable not set")
        print("Export it first: export SLACK_WEBHOOK_URL='https://hooks.slack.com/services/...'")
        sys.exit(1)
    return url


def send_payload(payload: dict[str, Any], label: str) -> bool:
    """Send a payload to Slack and report success/failure."""
    print(f"\n{'='*60}")
    print(f"Test: {label}")
    print(f"{'='*60}")
    print(f"Payload:\n{json.dumps(payload, indent=2)}")

    webhook_url = get_webhook_url()
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = response.read().decode("utf-8")
            print(f"Response: {result}")
            return True
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} - {e.read().decode('utf-8')}")
        return False


def test_simple_text():
    """Test 1: Simple text message."""
    return send_payload(
        {"text": "Test 1: Simple text message"},
        "Simple text"
    )


def test_header_block():
    """Test 2: Header block."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "Test 2: Header Block", "emoji": True}
                }
            ]
        },
        "Header block"
    )


def test_section_with_bold():
    """Test 3: Section with bold text."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*Bold Project Name*\nSome description"}
                }
            ]
        },
        "Section with bold text"
    )


def test_section_with_link():
    """Test 4: Section with clickable link."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "• <https://github.com/test/repo/pull/42|#42 Test PR Title> (2d)"}
                }
            ]
        },
        "Section with link"
    )


def test_context_block():
    """Test 5: Context block."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "5/10 merged  •  💰 $1.50"}
                    ]
                }
            ]
        },
        "Context block"
    )


def test_progress_bar():
    """Test 6: Progress bar with percentage."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*my-project*\n████████░░ 80%"}
                }
            ]
        },
        "Progress bar"
    )


def test_complete_project():
    """Test 7: Complete project block (similar to real output)."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "ClaudeChain Statistics", "emoji": True}
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "📅 2026-01-07"}
                    ]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*cleanup* ✅\n██████████ 100%"}
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "9/9 merged  •  💰 $1.66"}
                    ]
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*remove-dead-files*\n█████░░░░░ 52%"}
                },
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": "11/21 merged  •  💰 $2.56"}
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "• <https://github.com/test/repo/pull/35|#35 Some PR Title> (0d)"}
                }
            ]
        },
        "Complete project blocks"
    )


def test_leaderboard():
    """Test 8: Leaderboard with fields."""
    return send_payload(
        {
            "text": "Fallback",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "*🏆 Leaderboard*"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": "🥇 *alice*\n5 merged"},
                        {"type": "mrkdwn", "text": "🥈 *bob*\n3 merged"}
                    ]
                }
            ]
        },
        "Leaderboard"
    )


def test_custom(payload_json: str):
    """Send a custom JSON payload."""
    try:
        payload = json.loads(payload_json)
        return send_payload(payload, "Custom payload")
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        return False


def test_real_formatter():
    """Test 9: Use real SlackBlockKitFormatter to generate payload."""
    import sys
    sys.path.insert(0, "src")

    from claudechain.domain.formatters.slack_block_kit_formatter import SlackBlockKitFormatter
    from datetime import datetime, timezone

    formatter = SlackBlockKitFormatter(repo="gestrich/test-repo")
    blocks = []

    # Header
    blocks.extend(formatter.format_header_blocks(
        title="ClaudeChain Statistics",
        generated_at=datetime.now(timezone.utc),
    ))

    # Complete project (100%)
    blocks.extend(formatter.format_project_blocks(
        project_name="cleanup",
        merged=9,
        total=9,
        cost_usd=1.66,
        open_prs=None,
    ))

    # In-progress project with open PR
    blocks.extend(formatter.format_project_blocks(
        project_name="remove-dead-files",
        merged=11,
        total=21,
        cost_usd=2.56,
        open_prs=[{
            "number": 35,
            "title": "Sources/Pages/Examples/LinkExamples.swift",
            "url": "https://github.com/gestrich/test-repo/pull/35",
            "age_days": 0,
        }],
    ))

    payload = formatter.build_message(blocks)
    return send_payload(payload, "Real formatter output")


def test_real_stats_report():
    """Test 10: Use real StatisticsReport.format_for_slack_blocks() method."""
    import sys
    sys.path.insert(0, "src")

    from datetime import datetime, timezone
    from claudechain.domain.models import StatisticsReport, ProjectStats
    from claudechain.domain.github_models import GitHubPullRequest

    # Create a mock StatisticsReport
    report = StatisticsReport(repo="gestrich/test-repo")
    report.generated_at = datetime.now(timezone.utc)

    # Add a complete project
    complete_stats = ProjectStats(project_name="cleanup", spec_path="specs/cleanup/spec.md")
    complete_stats.total_tasks = 9
    complete_stats.completed_tasks = 9
    complete_stats.total_cost_usd = 1.66
    report.project_stats["cleanup"] = complete_stats

    # Add an in-progress project with open PR
    progress_stats = ProjectStats(project_name="remove-dead-files", spec_path="specs/remove-dead-files/spec.md")
    progress_stats.total_tasks = 21
    progress_stats.completed_tasks = 11
    progress_stats.in_progress_tasks = 1
    progress_stats.total_cost_usd = 2.56

    # Create a mock open PR
    open_pr = GitHubPullRequest(
        number=35,
        title="ClaudeChain: [remove-dead-files] Sources/Pages/Examples/LinkExamples.swift",
        state="open",
        created_at=datetime.now(timezone.utc),
        merged_at=None,
        assignees=[],
        labels=[],
        url="https://github.com/gestrich/test-repo/pull/35",
    )
    progress_stats.open_prs.append(open_pr)
    report.project_stats["remove-dead-files"] = progress_stats

    # Generate Block Kit output using the REAL method
    payload = report.format_for_slack_blocks(show_assignee_stats=False)

    print("\n" + "="*60)
    print("DEBUG: Raw payload from format_for_slack_blocks:")
    print("="*60)
    print(json.dumps(payload, indent=2))

    return send_payload(payload, "Real StatisticsReport.format_for_slack_blocks()")


def main():
    parser = argparse.ArgumentParser(description="Debug Slack Block Kit payloads")
    parser.add_argument(
        "test",
        nargs="?",
        choices=["all", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "custom"],
        default="all",
        help="Which test to run (default: all)"
    )
    parser.add_argument(
        "--payload",
        type=str,
        help="Custom JSON payload (use with 'custom' test)"
    )

    args = parser.parse_args()

    tests = {
        "1": test_simple_text,
        "2": test_header_block,
        "3": test_section_with_bold,
        "4": test_section_with_link,
        "5": test_context_block,
        "6": test_progress_bar,
        "7": test_complete_project,
        "8": test_leaderboard,
        "9": test_real_formatter,
        "10": test_real_stats_report,
    }

    if args.test == "all":
        for test_func in tests.values():
            test_func()
    elif args.test == "custom":
        if not args.payload:
            print("Error: --payload required for custom test")
            return
        test_custom(args.payload)
    else:
        tests[args.test]()


if __name__ == "__main__":
    main()
