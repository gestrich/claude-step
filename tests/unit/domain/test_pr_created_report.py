"""Tests for PullRequestCreatedReport domain model."""

import pytest
from unittest.mock import Mock

from claudestep.domain.pr_created_report import PullRequestCreatedReport
from claudestep.domain.formatters import (
    Section,
    Header,
    TextBlock,
    LabeledValue,
    Table,
    Divider,
    MarkdownReportFormatter,
)


@pytest.fixture
def mock_cost_breakdown():
    """Create a mock CostBreakdown for testing."""
    mock = Mock()
    mock.main_cost = 0.15
    mock.summary_cost = 0.05
    mock.total_cost = 0.20
    mock.input_tokens = 1000
    mock.output_tokens = 500
    mock.cache_read_tokens = 200
    mock.cache_write_tokens = 100
    mock.get_aggregated_models.return_value = []
    return mock


@pytest.fixture
def mock_cost_breakdown_with_models():
    """Create a mock CostBreakdown with model data."""
    mock = Mock()
    mock.main_cost = 0.15
    mock.summary_cost = 0.05
    mock.total_cost = 0.20
    mock.input_tokens = 1000
    mock.output_tokens = 500
    mock.cache_read_tokens = 200
    mock.cache_write_tokens = 100

    # Create mock model
    model = Mock()
    model.model = "claude-sonnet-4-20250514"
    model.input_tokens = 1000
    model.output_tokens = 500
    model.cache_read_tokens = 200
    model.cache_write_tokens = 100
    model.calculate_cost.return_value = 0.20

    mock.get_aggregated_models.return_value = [model]
    return mock


@pytest.fixture
def report(mock_cost_breakdown):
    """Create a basic PullRequestCreatedReport."""
    return PullRequestCreatedReport(
        pr_number="123",
        pr_url="https://github.com/owner/repo/pull/123",
        project_name="my-project",
        task="Fix the login bug",
        cost_breakdown=mock_cost_breakdown,
        repo="owner/repo",
        run_id="456789",
    )


@pytest.fixture
def report_with_summary(mock_cost_breakdown):
    """Create a report with AI summary content."""
    return PullRequestCreatedReport(
        pr_number="123",
        pr_url="https://github.com/owner/repo/pull/123",
        project_name="my-project",
        task="Fix the login bug",
        cost_breakdown=mock_cost_breakdown,
        repo="owner/repo",
        run_id="456789",
        summary_content="This PR fixes a bug in the login flow by adding proper validation.",
    )


class TestPullRequestCreatedReport:
    """Tests for PullRequestCreatedReport."""

    def test_workflow_url(self, report):
        """Test workflow URL generation."""
        assert report.workflow_url == "https://github.com/owner/repo/actions/runs/456789"


class TestBuildNotificationElements:
    """Tests for build_notification_elements()."""

    def test_returns_string(self, report):
        """Test that build_notification_elements returns a formatted string."""
        result = report.build_notification_elements()
        assert isinstance(result, str)

    def test_contains_header(self, report):
        """Test notification contains header with emoji."""
        result = report.build_notification_elements()
        assert "🎉 *New PR Created*" in result

    def test_contains_pr_link(self, report):
        """Test notification contains PR link in Slack format."""
        result = report.build_notification_elements()
        assert "*PR:*" in result
        assert "<https://github.com/owner/repo/pull/123|#123>" in result

    def test_contains_project_name(self, report):
        """Test notification contains project name in code format."""
        result = report.build_notification_elements()
        assert "*Project:*" in result
        assert "`my-project`" in result

    def test_contains_task(self, report):
        """Test notification contains task."""
        result = report.build_notification_elements()
        assert "*Task:*" in result
        assert "Fix the login bug" in result

    def test_contains_cost(self, report):
        """Test notification contains cost."""
        result = report.build_notification_elements()
        assert "*💰 Cost:*" in result
        assert "$0.20" in result

    def test_matches_expected_format(self, report):
        """Test notification matches the expected Slack mrkdwn format."""
        result = report.build_notification_elements()

        expected = (
            "🎉 *New PR Created*\n"
            "\n"
            "*PR:* <https://github.com/owner/repo/pull/123|#123>\n"
            "*Project:* `my-project`\n"
            "*Task:* Fix the login bug\n"
            "\n"
            "*💰 Cost:* $0.20"
        )
        assert result == expected


class TestBuildCommentElements:
    """Tests for build_comment_elements()."""

    def test_returns_section(self, report):
        """Test that build_comment_elements returns a Section."""
        result = report.build_comment_elements()
        assert isinstance(result, Section)

    def test_contains_cost_header(self, report):
        """Test comment contains cost breakdown header."""
        result = report.build_comment_elements()
        headers = [e for e in result.elements if isinstance(e, Header)]
        cost_header = next((h for h in headers if "Cost" in h.text), None)
        assert cost_header is not None

    def test_contains_cost_table(self, report):
        """Test comment contains cost table."""
        result = report.build_comment_elements()
        tables = [e for e in result.elements if isinstance(e, Table)]
        assert len(tables) >= 1

    def test_contains_footer_with_workflow_link(self, report):
        """Test comment contains footer with workflow link."""
        result = report.build_comment_elements()
        text_blocks = [e for e in result.elements if isinstance(e, TextBlock)]
        footer = next((tb for tb in text_blocks if "workflow" in tb.text.lower()), None)
        assert footer is not None

    def test_includes_summary_when_present(self, report_with_summary):
        """Test comment includes AI summary when provided."""
        result = report_with_summary.build_comment_elements()
        text_blocks = [e for e in result.elements if isinstance(e, TextBlock)]
        summary = next((tb for tb in text_blocks if "login" in tb.text.lower()), None)
        assert summary is not None

    def test_includes_divider_after_summary(self, report_with_summary):
        """Test comment has divider after summary."""
        result = report_with_summary.build_comment_elements()
        dividers = [e for e in result.elements if isinstance(e, Divider)]
        assert len(dividers) >= 1

    def test_formats_correctly_for_markdown(self, report):
        """Test comment renders correctly with MarkdownReportFormatter."""
        elements = report.build_comment_elements()
        formatter = MarkdownReportFormatter()
        result = formatter.format(elements)

        assert "Cost" in result
        assert "$0.15" in result  # main_cost
        assert "$0.05" in result  # summary_cost
        assert "$0.20" in result  # total_cost


class TestBuildWorkflowSummaryElements:
    """Tests for build_workflow_summary_elements()."""

    def test_returns_section(self, report):
        """Test that build_workflow_summary_elements returns a Section."""
        result = report.build_workflow_summary_elements()
        assert isinstance(result, Section)

    def test_contains_complete_header(self, report):
        """Test workflow summary contains completion header."""
        result = report.build_workflow_summary_elements()
        headers = [e for e in result.elements if isinstance(e, Header)]
        complete_header = next((h for h in headers if "Complete" in h.text), None)
        assert complete_header is not None

    def test_contains_pr_link(self, report):
        """Test workflow summary contains PR link."""
        result = report.build_workflow_summary_elements()
        labeled_values = [e for e in result.elements if isinstance(e, LabeledValue)]
        pr_label = next((lv for lv in labeled_values if lv.label == "PR"), None)
        assert pr_label is not None

    def test_contains_task_when_present(self, report):
        """Test workflow summary contains task description."""
        result = report.build_workflow_summary_elements()
        labeled_values = [e for e in result.elements if isinstance(e, LabeledValue)]
        task_label = next((lv for lv in labeled_values if lv.label == "Task"), None)
        assert task_label is not None
        assert "login bug" in str(task_label.value)

    def test_formats_correctly_for_markdown(self, report):
        """Test workflow summary renders correctly with MarkdownReportFormatter."""
        elements = report.build_workflow_summary_elements()
        formatter = MarkdownReportFormatter()
        result = formatter.format(elements)

        assert "ClaudeStep Complete" in result
        assert "#123" in result
        assert "Cost" in result


class TestModelBreakdown:
    """Tests for model breakdown table."""

    def test_no_model_breakdown_when_no_models(self, report):
        """Test no model breakdown section when no models."""
        result = report.build_comment_elements()
        # Should have exactly 1 table (cost summary), not model breakdown
        tables = [e for e in result.elements if isinstance(e, Table)]
        assert len(tables) == 1

    def test_includes_model_breakdown_when_models_present(self, mock_cost_breakdown_with_models):
        """Test model breakdown included when models present."""
        report = PullRequestCreatedReport(
            pr_number="123",
            pr_url="https://github.com/owner/repo/pull/123",
            project_name="my-project",
            task="Fix bug",
            cost_breakdown=mock_cost_breakdown_with_models,
            repo="owner/repo",
            run_id="456789",
        )
        result = report.build_comment_elements()

        # Should have nested section with model breakdown
        sections = [e for e in result.elements if isinstance(e, Section)]
        assert len(sections) >= 1

        # Find model breakdown section
        model_section = sections[0]
        headers = [e for e in model_section.elements if isinstance(e, Header)]
        assert any("Model" in h.text for h in headers)
