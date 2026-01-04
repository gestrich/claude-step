"""Tests for the statistics command"""

import json
from datetime import datetime
from unittest.mock import Mock, patch, call

import pytest

from claudechain.cli.commands.statistics import cmd_statistics
from claudechain.domain.models import StatisticsReport, ProjectStats, TeamMemberStats, PRReference


class TestCmdStatistics:
    """Test suite for cmd_statistics functionality"""

    @pytest.fixture
    def mock_github_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.write_step_summary = Mock()
        mock.set_error = Mock()
        return mock

    @pytest.fixture
    def sample_statistics_report(self):
        """Fixture providing a sample statistics report with data"""
        # Create sample project stats
        project_a = ProjectStats("project-a", "/fake/spec-a.md")
        project_a.total_tasks = 10
        project_a.completed_tasks = 6
        project_a.in_progress_tasks = 2
        project_a.pending_tasks = 2
        project_a.total_cost_usd = 15.50

        project_b = ProjectStats("project-b", "/fake/spec-b.md")
        project_b.total_tasks = 5
        project_b.completed_tasks = 5
        project_b.in_progress_tasks = 0
        project_b.pending_tasks = 0
        project_b.total_cost_usd = 8.25

        # Create sample team stats
        from datetime import datetime, timezone
        alice = TeamMemberStats("alice")
        alice.merged_prs = [
            PRReference(1, "PR 1", "project-a", datetime(2024, 1, 1, tzinfo=timezone.utc)),
            PRReference(2, "PR 2", "project-a", datetime(2024, 1, 2, tzinfo=timezone.utc)),
            PRReference(3, "PR 3", "project-b", datetime(2024, 1, 3, tzinfo=timezone.utc)),
            PRReference(4, "PR 4", "project-b", datetime(2024, 1, 4, tzinfo=timezone.utc)),
        ]
        alice.open_prs = [
            PRReference(5, "PR 5", "project-a", datetime(2024, 1, 5, tzinfo=timezone.utc)),
        ]

        bob = TeamMemberStats("bob")
        bob.merged_prs = [
            PRReference(6, "PR 6", "project-a", datetime(2024, 1, 6, tzinfo=timezone.utc)),
            PRReference(7, "PR 7", "project-a", datetime(2024, 1, 7, tzinfo=timezone.utc)),
            PRReference(8, "PR 8", "project-b", datetime(2024, 1, 8, tzinfo=timezone.utc)),
            PRReference(9, "PR 9", "project-b", datetime(2024, 1, 9, tzinfo=timezone.utc)),
            PRReference(10, "PR 10", "project-a", datetime(2024, 1, 10, tzinfo=timezone.utc)),
            PRReference(11, "PR 11", "project-a", datetime(2024, 1, 11, tzinfo=timezone.utc)),
            PRReference(12, "PR 12", "project-b", datetime(2024, 1, 12, tzinfo=timezone.utc)),
        ]
        bob.open_prs = [
            PRReference(13, "PR 13", "project-a", datetime(2024, 1, 13, tzinfo=timezone.utc)),
        ]

        # Create report and add stats
        report = StatisticsReport()
        report.add_project(project_a)
        report.add_project(project_b)
        report.add_team_member(alice)
        report.add_team_member(bob)

        return report

    @pytest.fixture
    def empty_statistics_report(self):
        """Fixture providing an empty statistics report"""
        return StatisticsReport()

    def test_cmd_statistics_success_with_slack_format(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should generate statistics report in Slack format successfully"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch(
            "claudechain.cli.commands.statistics.ProjectRepository"
        ):
            mock_service = Mock()
            mock_service.collect_all_statistics.return_value = sample_statistics_report
            mock_service_class.return_value = mock_service

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                config_path=None,
                days_back=30,
                format_type="slack",
                slack_webhook_url=""
            )

        # Assert
        assert result == 0
        mock_service.collect_all_statistics.assert_called_once_with(
            config_path=None, days_back=30, show_assignee_stats=False
        )

        # Verify Slack output was written
        slack_output_calls = [
            c for c in mock_github_helper.write_output.call_args_list if c[0][0] == "slack_message"
        ]
        assert len(slack_output_calls) == 1
        assert mock_github_helper.write_output.call_args_list[1] == call(
            "has_statistics", "true"
        )

        # Verify JSON output was written
        json_output_calls = [
            c for c in mock_github_helper.write_output.call_args_list if c[0][0] == "statistics_json"
        ]
        assert len(json_output_calls) == 1

        # Verify step summary was written
        assert mock_github_helper.write_step_summary.call_count > 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("ClaudeChain Statistics Report" in str(c) for c in summary_calls)

    def test_cmd_statistics_success_with_json_format(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should generate statistics report in JSON format successfully"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_service.collect_all_statistics.return_value = sample_statistics_report
            mock_service_class.return_value = mock_service

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                config_path="/path/to/config.yml",
                days_back=7,
                format_type="json",
                slack_webhook_url=""
            )

        # Assert
        assert result == 0
        mock_service.collect_all_statistics.assert_called_once_with(
            config_path="/path/to/config.yml", days_back=7, show_assignee_stats=False
        )

        # Verify JSON output was written
        json_output_calls = [
            c for c in mock_github_helper.write_output.call_args_list if c[0][0] == "statistics_json"
        ]
        assert len(json_output_calls) == 1

        # Verify Slack output was NOT written for json-only format
        slack_output_calls = [
            c for c in mock_github_helper.write_output.call_args_list if c[0][0] == "slack_message"
        ]
        assert len(slack_output_calls) == 0

    def test_cmd_statistics_uses_default_days_back(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should use default value of 30 days when not explicitly provided"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act (using default days_back parameter value)
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack"
            )

        # Assert
        assert result == 0
        mock_collect.assert_called_once_with(config_path=None, days_back=30, show_assignee_stats=False)

    def test_cmd_statistics_writes_leaderboard_when_present(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should write leaderboard to step summary when team stats exist and enabled"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            # Mock format_leaderboard to return content
            sample_statistics_report.format_leaderboard = Mock(
                return_value="## Leaderboard\n1. bob - 7 PRs"
            )
            mock_collect.return_value = sample_statistics_report

            # Act - must enable show_assignee_stats to see leaderboard
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack",
                show_assignee_stats=True
            )

        # Assert
        assert result == 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("Leaderboard" in str(c) for c in summary_calls)

    def test_cmd_statistics_writes_project_progress(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should write project progress summaries in alphabetical order"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack"
            )

        # Assert
        assert result == 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("Project Progress" in str(c) for c in summary_calls)

        # Verify projects are sorted alphabetically
        summary_text = " ".join([str(c) for c in summary_calls])
        project_a_pos = summary_text.find("project-a")
        project_b_pos = summary_text.find("project-b")
        # Both should be present and project-a should come before project-b
        assert project_a_pos > 0
        assert project_b_pos > 0
        assert project_a_pos < project_b_pos

    def test_cmd_statistics_writes_team_member_activity(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should write team member activity sorted by merged count descending when enabled"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act - must enable show_assignee_stats to see team member activity
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack",
                show_assignee_stats=True
            )

        # Assert
        assert result == 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("Team Member Activity" in str(c) for c in summary_calls)

        # Verify members are sorted by merged_count (bob has 7, alice has 4)
        summary_text = " ".join([str(c) for c in summary_calls])
        bob_pos = summary_text.find("bob")
        alice_pos = summary_text.find("alice")
        # Both should be present and bob should come before alice
        assert bob_pos > 0
        assert alice_pos > 0
        assert bob_pos < alice_pos

    def test_cmd_statistics_handles_empty_report(
        self, mock_github_helper, empty_statistics_report
    ):
        """Should handle empty statistics report gracefully"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = empty_statistics_report

            # Act - with show_assignee_stats=True to test team member section
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack",
                show_assignee_stats=True
            )

        # Assert
        assert result == 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("No projects found" in str(c) for c in summary_calls)
        assert any("No team member activity found" in str(c) for c in summary_calls)

    def test_cmd_statistics_handles_exception(
        self, mock_github_helper, capsys
    ):
        """Should handle exceptions and return error code"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.side_effect = Exception("Test error")

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack"
            )

        # Assert
        assert result == 1
        mock_github_helper.set_error.assert_called_once()
        error_call = mock_github_helper.set_error.call_args[0][0]
        assert "Statistics collection failed" in error_call
        assert "Test error" in error_call

        # Verify error output was written
        mock_github_helper.write_output.assert_called_once_with(
            "has_statistics", "false"
        )

        # Verify error step summary was written
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("Error" in str(c) for c in summary_calls)
        assert any("Test error" in str(c) for c in summary_calls)

    def test_cmd_statistics_prints_collection_info(
        self, mock_github_helper, sample_statistics_report, capsys
    ):
        """Should print collection information to console"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                config_path="/path/to/config.yml",
                days_back=15,
                format_type="slack"
            )

        # Assert
        assert result == 0
        captured = capsys.readouterr()
        assert "ClaudeChain Statistics Collection" in captured.out
        assert "Days back: 15" in captured.out
        assert "Config path: /path/to/config.yml" in captured.out
        assert "Collection Complete" in captured.out
        assert "Projects found: 2" in captured.out
        assert "Team members tracked: 2" in captured.out
        assert "Statistics generated successfully" in captured.out

    def test_cmd_statistics_prints_all_projects_mode_when_no_config(
        self, mock_github_helper, sample_statistics_report, capsys
    ):
        """Should print 'All projects' mode when config_path is None"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                config_path=None,
                format_type="slack"
            )

        # Assert
        assert result == 0
        captured = capsys.readouterr()
        assert "Mode: All projects" in captured.out

    def test_cmd_statistics_slack_format_outputs_slack_text(
        self, mock_github_helper, sample_statistics_report, capsys
    ):
        """Should output Slack formatted text to console when format is slack"""
        # Arrange
        slack_output = "Slack formatted report text"
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            sample_statistics_report.format_for_slack = Mock(
                return_value=slack_output
            )
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack"
            )

        # Assert
        assert result == 0
        captured = capsys.readouterr()
        assert "Slack Output" in captured.out
        assert slack_output in captured.out

    def test_cmd_statistics_writes_timestamp_to_summary(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should write current timestamp to step summary"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            with patch(
                "claudechain.cli.commands.statistics.datetime"
            ) as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-01-15T10:30:00"
                )

                # Act
                result = cmd_statistics(
                    gh=mock_github_helper,
                    repo="owner/repo",
                    format_type="slack"
                )

        # Assert
        assert result == 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        assert any("2024-01-15T10:30:00" in str(c) for c in summary_calls)

    def test_cmd_statistics_json_output_is_valid_json(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should output valid JSON data when format is json or slack"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="json"
            )

        # Assert
        assert result == 0
        json_output_calls = [
            c for c in mock_github_helper.write_output.call_args_list if c[0][0] == "statistics_json"
        ]
        assert len(json_output_calls) == 1

        # Verify it's valid JSON by parsing it
        json_data = json_output_calls[0][0][1]
        parsed = json.loads(json_data)
        assert "projects" in parsed or "team_members" in parsed

    def test_cmd_statistics_parses_days_back_as_integer(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should accept days_back as integer parameter"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                days_back=90,
                format_type="json"
            )

        # Assert
        assert result == 0
        mock_collect.assert_called_once_with(config_path=None, days_back=90, show_assignee_stats=False)

    def test_cmd_statistics_no_leaderboard_when_empty(
        self, mock_github_helper, sample_statistics_report
    ):
        """Should not write leaderboard section when format_leaderboard returns empty"""
        # Arrange
        with patch(
            "claudechain.cli.commands.statistics.StatisticsService"
        ) as mock_service_class, patch("claudechain.cli.commands.statistics.ProjectRepository"):
            mock_service = Mock()
            mock_collect = mock_service.collect_all_statistics
            mock_service_class.return_value = mock_service
            # Mock format_leaderboard to return empty string
            sample_statistics_report.format_leaderboard = Mock(return_value="")
            mock_collect.return_value = sample_statistics_report

            # Act
            result = cmd_statistics(
                gh=mock_github_helper,
                repo="owner/repo",
                format_type="slack"
            )

        # Assert
        assert result == 0
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        # Should still have "Project Progress" but no separate leaderboard content
        assert any("Project Progress" in str(c) for c in summary_calls)
