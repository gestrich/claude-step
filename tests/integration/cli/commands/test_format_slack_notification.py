"""
Tests for format_slack_notification.py - Slack notification formatting command
"""

import json
from unittest.mock import Mock, patch

import pytest

from claudechain.cli.commands.format_slack_notification import cmd_format_slack_notification, format_pr_notification
from claudechain.domain.cost_breakdown import CostBreakdown, ModelUsage


def make_cost_breakdown_json(
    main_cost: float = 0.0,
    summary_cost: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    models: list | None = None,
) -> str:
    """Helper to create valid CostBreakdown JSON for testing."""
    return json.dumps({
        "main_cost": main_cost,
        "summary_cost": summary_cost,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "models": models or []
    })


class TestFormatPrNotification:
    """Test suite for PR notification formatting functionality"""

    def test_format_pr_notification_creates_slack_message(self):
        """Should format notification as Slack mrkdwn with proper structure"""
        # Arrange
        cost_breakdown = CostBreakdown(
            main_cost=0.123456,
            summary_cost=0.045678,
        )

        # Act
        result = format_pr_notification(
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="my-project",
            task="Refactor authentication system",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert
        assert "🎉 *New PR Created*" in result
        assert "*PR:* <https://github.com/owner/repo/pull/42|#42>" in result
        assert "*Project:* `my-project`" in result
        assert "*Task:* Refactor authentication system" in result

    def test_format_pr_notification_includes_total_cost(self):
        """Should include total cost in concise format"""
        # Arrange
        cost_breakdown = CostBreakdown(
            main_cost=0.123456,
            summary_cost=0.045678,
        )

        # Act
        result = format_pr_notification(
            pr_number="1",
            pr_url="https://example.com",
            project_name="test",
            task="test task",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert
        assert "*💰 Cost:* $0.17" in result  # Total cost only (0.123456 + 0.045678)

    def test_format_pr_notification_uses_two_decimal_places(self):
        """Should display costs with 2 decimal places (cents)"""
        # Arrange
        cost_breakdown = CostBreakdown(
            main_cost=0.001,
            summary_cost=0.002,
        )

        # Act
        result = format_pr_notification(
            pr_number="1",
            pr_url="https://example.com",
            project_name="test",
            task="test",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert
        assert "*💰 Cost:* $0.00" in result

    def test_format_pr_notification_handles_zero_costs(self):
        """Should format zero costs correctly"""
        # Arrange
        cost_breakdown = CostBreakdown(main_cost=0.0, summary_cost=0.0)

        # Act
        result = format_pr_notification(
            pr_number="1",
            pr_url="https://example.com",
            project_name="test",
            task="test",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert
        assert "*💰 Cost:* $0.00" in result

    def test_format_pr_notification_handles_large_costs(self):
        """Should format large cost values correctly"""
        # Arrange
        cost_breakdown = CostBreakdown(
            main_cost=123.456789,
            summary_cost=45.678901,
        )

        # Act
        result = format_pr_notification(
            pr_number="1",
            pr_url="https://example.com",
            project_name="test",
            task="test",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert
        assert "*💰 Cost:* $169.14" in result  # Total only

    def test_format_pr_notification_formats_pr_link_as_slack_mrkdwn(self):
        """Should format PR link using Slack mrkdwn syntax"""
        # Arrange
        cost_breakdown = CostBreakdown(main_cost=0.0, summary_cost=0.0)

        # Act
        result = format_pr_notification(
            pr_number="99",
            pr_url="https://github.com/owner/repo/pull/99",
            project_name="test",
            task="test",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert
        # Slack mrkdwn link format: <URL|Text>
        assert "<https://github.com/owner/repo/pull/99|#99>" in result

    def test_format_pr_notification_is_concise(self):
        """Should be concise without detailed breakdowns (those go in PR comment)"""
        # Arrange
        cost_breakdown = CostBreakdown(main_cost=1.0, summary_cost=2.0)

        # Act
        result = format_pr_notification(
            pr_number="1",
            pr_url="https://example.com",
            project_name="test",
            task="test",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert - should NOT have detailed breakdown
        assert "```" not in result  # No code blocks
        assert "Main task:" not in result  # No line-by-line breakdown
        assert "Per-Model" not in result  # No model details
        # Should have total cost
        assert "*💰 Cost:* $3.00" in result

    def test_format_pr_notification_does_not_include_model_breakdown(self):
        """Should NOT include per-model breakdown (that goes in PR comment)"""
        # Arrange
        cost_breakdown = CostBreakdown(
            main_cost=0.01,
            summary_cost=0.0,
            input_tokens=1000,
            output_tokens=500,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=1000,
                    output_tokens=500,
                )
            ],
        )

        # Act
        result = format_pr_notification(
            pr_number="1",
            pr_url="https://example.com",
            project_name="test",
            task="test",
            cost_breakdown=cost_breakdown,
            repo="owner/repo"
        )

        # Assert - model breakdown should NOT be in Slack message
        assert "*📊 Per-Model Usage:*" not in result
        assert "claude-3-haiku-20240307" not in result
        # Just the total cost
        assert "*💰 Cost:* $0.01" in result


class TestCmdFormatSlackNotification:
    """Test suite for format_slack_notification command functionality"""

    @pytest.fixture
    def mock_gh_actions(self):
        """Fixture providing mocked GitHub Actions helper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.set_error = Mock()
        return mock

    @pytest.fixture
    def default_cost_breakdown_json(self):
        """Fixture providing standard cost breakdown JSON"""
        return make_cost_breakdown_json(
            main_cost=0.123456,
            summary_cost=0.045678,
        )

    @pytest.fixture
    def default_params(self, default_cost_breakdown_json):
        """Fixture providing standard notification parameters"""
        return {
            "pr_number": "42",
            "pr_url": "https://github.com/owner/repo/pull/42",
            "project_name": "my-project",
            "task": "Refactor authentication system",
            "cost_breakdown_json": default_cost_breakdown_json,
            "repo": "owner/repo"
        }

    def test_cmd_format_slack_notification_generates_notification_successfully(self, mock_gh_actions, default_params):
        """Should generate Slack notification when all inputs are valid"""
        # Act
        result = cmd_format_slack_notification(gh=mock_gh_actions, **default_params)

        # Assert
        assert result == 0
        assert mock_gh_actions.write_output.call_count == 2
        mock_gh_actions.write_output.assert_any_call("has_pr", "true")

        # Verify slack_message was written
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        assert len(slack_message_call) == 1
        message = slack_message_call[0][0][1]
        assert "🎉 *New PR Created*" in message
        assert "my-project" in message

    def test_cmd_format_slack_notification_includes_all_required_fields_in_message(self, mock_gh_actions, default_params):
        """Should include PR number, URL, project, task, and total cost in message"""
        # Act
        cmd_format_slack_notification(gh=mock_gh_actions, **default_params)

        # Assert
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]

        assert "#42" in message
        assert "https://github.com/owner/repo/pull/42" in message
        assert "my-project" in message
        assert "Refactor authentication system" in message
        assert "$0.17" in message  # Total cost

    def test_cmd_format_slack_notification_calculates_total_cost_correctly(self, mock_gh_actions):
        """Should calculate total cost as sum of main and summary costs"""
        # Arrange
        cost_breakdown_json = make_cost_breakdown_json(
            main_cost=0.123,
            summary_cost=0.456,
        )

        # Act
        cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="test",
            task="test",
            cost_breakdown_json=cost_breakdown_json,
            repo="owner/repo"
        )

        # Assert
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]

        assert "$0.58" in message  # Total only (0.123 + 0.456)

    def test_cmd_format_slack_notification_skips_when_no_pr_number(self, mock_gh_actions):
        """Should skip notification and return success when pr_number is empty"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="test",
            task="test",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("has_pr", "false")
        mock_gh_actions.set_error.assert_not_called()

    def test_cmd_format_slack_notification_skips_when_no_pr_url(self, mock_gh_actions):
        """Should skip notification when pr_url is empty"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="",
            project_name="test",
            task="test",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("has_pr", "false")

    def test_cmd_format_slack_notification_skips_when_pr_number_is_whitespace(self, mock_gh_actions):
        """Should skip notification when pr_number is whitespace only"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="   ",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="test",
            task="test",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("has_pr", "false")

    def test_cmd_format_slack_notification_skips_when_pr_url_is_whitespace(self, mock_gh_actions):
        """Should skip notification when pr_url is whitespace only"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="   ",
            project_name="test",
            task="test",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("has_pr", "false")

    def test_cmd_format_slack_notification_handles_invalid_json(self, mock_gh_actions):
        """Should return error when cost_breakdown_json is invalid"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="test",
            task="test",
            cost_breakdown_json="not valid json {]}",
            repo="owner/repo"
        )

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once()
        mock_gh_actions.write_output.assert_called_with("has_pr", "false")

    def test_cmd_format_slack_notification_strips_whitespace_from_inputs(self, mock_gh_actions):
        """Should strip whitespace from parameter values"""
        # Arrange
        cost_breakdown_json = make_cost_breakdown_json(
            main_cost=0.123,
            summary_cost=0.456,
        )

        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="  42  ",
            pr_url="  https://github.com/owner/repo/pull/42  ",
            project_name="  my-project  ",
            task="  test task  ",
            cost_breakdown_json=f"  {cost_breakdown_json}  ",
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]

        # Verify trimmed values are used
        assert "#42>" in message  # PR number without spaces
        assert "$0.58" in message  # Total cost

    def test_cmd_format_slack_notification_handles_empty_optional_fields(self, mock_gh_actions):
        """Should handle empty optional fields gracefully"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="",
            task="",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo=""
        )

        # Assert
        assert result == 0
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]

        # Should still contain basic structure
        assert "🎉 *New PR Created*" in message
        assert "#42" in message

    def test_cmd_format_slack_notification_handles_unexpected_exception(self, mock_gh_actions, default_params):
        """Should catch and report unexpected exceptions"""
        # Arrange
        with patch('claudechain.cli.commands.format_slack_notification.format_pr_notification') as mock_format:
            # Simulate unexpected error during formatting
            mock_format.side_effect = RuntimeError("Unexpected error")

            # Act
            result = cmd_format_slack_notification(gh=mock_gh_actions, **default_params)

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once()
        error_message = mock_gh_actions.set_error.call_args[0][0]
        assert "Error generating PR notification" in error_message
        assert "Unexpected error" in error_message
        mock_gh_actions.write_output.assert_called_once_with("has_pr", "false")

    def test_cmd_format_slack_notification_writes_has_pr_false_on_exception(self, mock_gh_actions, default_params):
        """Should write has_pr=false when exception occurs"""
        # Arrange
        with patch('claudechain.cli.commands.format_slack_notification.format_pr_notification') as mock_format:
            mock_format.side_effect = Exception("Test error")

            # Act
            result = cmd_format_slack_notification(gh=mock_gh_actions, **default_params)

        # Assert
        assert result == 1
        mock_gh_actions.write_output.assert_called_with("has_pr", "false")

    def test_cmd_format_slack_notification_handles_empty_task_description(self, mock_gh_actions):
        """Should handle empty task description gracefully"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="test",
            task="",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]
        assert "*Task:*" in message  # Task field should still be present

    def test_cmd_format_slack_notification_handles_empty_project_name(self, mock_gh_actions):
        """Should handle empty project name gracefully"""
        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="",
            task="test task",
            cost_breakdown_json=make_cost_breakdown_json(),
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]
        assert "*Project:*" in message  # Project field should still be present

    def test_cmd_format_slack_notification_outputs_message_to_console(self, mock_gh_actions, default_params, capsys):
        """Should print notification message to console for debugging"""
        # Act
        cmd_format_slack_notification(gh=mock_gh_actions, **default_params)

        # Assert
        captured = capsys.readouterr()
        assert "=== Slack Notification Message ===" in captured.out
        assert "🎉 *New PR Created*" in captured.out

    def test_cmd_format_slack_notification_does_not_include_model_breakdown(self, mock_gh_actions):
        """Should NOT include per-model breakdown (that goes in PR comment)"""
        # Arrange
        cost_breakdown_json = make_cost_breakdown_json(
            main_cost=0.01,
            summary_cost=0.005,
            input_tokens=1000,
            output_tokens=500,
            models=[
                {
                    "model": "claude-3-haiku-20240307",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                }
            ]
        )

        # Act
        result = cmd_format_slack_notification(
            gh=mock_gh_actions,
            pr_number="42",
            pr_url="https://github.com/owner/repo/pull/42",
            project_name="test",
            task="test",
            cost_breakdown_json=cost_breakdown_json,
            repo="owner/repo"
        )

        # Assert
        assert result == 0
        calls = mock_gh_actions.write_output.call_args_list
        slack_message_call = [c for c in calls if c[0][0] == "slack_message"]
        message = slack_message_call[0][0][1]
        # Detailed model breakdown should NOT be in Slack message
        assert "*📊 Per-Model Usage:*" not in message
        assert "claude-3-haiku-20240307" not in message
        # Just total cost
        assert "$0.01" in message or "$0.02" in message  # Total is main + summary
