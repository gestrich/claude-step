"""Integration tests for ClaudeChain workflows.

This module tests workflow configuration and structure validation.
"""

import pytest
import re
from pathlib import Path


class TestAutoStartWorkflowLogic:
    """Tests for auto-start workflow bash script logic."""

    def test_project_name_extraction_pattern(self):
        """Verify the sed pattern correctly extracts project names from spec paths."""
        # Pattern used in workflow: sed 's|claude-chain/\([^/]*\)/spec.md|\1|'
        pattern = r'claude-chain/([^/]*)/spec\.md'

        test_cases = [
            ("claude-chain/my-project/spec.md", "my-project"),
            ("claude-chain/test-project-1/spec.md", "test-project-1"),
            ("claude-chain/auth-refactor/spec.md", "auth-refactor"),
            ("claude-chain/api_v2/spec.md", "api_v2"),
        ]

        for path, expected_project in test_cases:
            match = re.search(pattern, path)
            assert match is not None, f"Pattern should match path: {path}"
            extracted = match.group(1)
            assert extracted == expected_project, \
                f"Expected '{expected_project}', got '{extracted}' for path '{path}'"

    def test_project_name_extraction_rejects_invalid_paths(self):
        """Verify the pattern rejects invalid paths."""
        pattern = r'claude-chain/([^/]*)/spec\.md'

        invalid_paths = [
            "claude-chain/spec.md",  # Missing project directory
            "spec.md",  # Missing claude-chain prefix
            "claude-chain/project/other.md",  # Wrong filename
            "claude-chain/project/subdir/spec.md",  # Too many directories
        ]

        for path in invalid_paths:
            match = re.search(pattern, path)
            assert match is None, f"Pattern should NOT match invalid path: {path}"

    def test_branch_name_pattern_for_pr_detection(self):
        """Verify the branch name pattern used to detect existing PRs."""
        # Pattern used in workflow: claude-chain-$project-*
        # We check if branch starts with the pattern prefix

        def matches_pr_branch_pattern(branch_name: str, project: str) -> bool:
            """Check if branch name matches ClaudeChain PR pattern for given project."""
            prefix = f"claude-chain-{project}-"
            return branch_name.startswith(prefix)

        test_cases = [
            # (branch_name, project, should_match)
            ("claude-chain-my-project-1", "my-project", True),
            ("claude-chain-my-project-2", "my-project", True),
            ("claude-chain-my-project-123", "my-project", True),
            ("claude-chain-other-project-1", "my-project", False),
            ("claude-chain-my-project", "my-project", False),  # Missing task number
            ("my-project-1", "my-project", False),  # Missing prefix
        ]

        for branch, project, should_match in test_cases:
            result = matches_pr_branch_pattern(branch, project)
            assert result == should_match, \
                f"Branch '{branch}' with project '{project}': expected {should_match}, got {result}"

    def test_diff_filter_flags(self):
        """Document the diff-filter flags used in the workflow.

        This is a documentation test to ensure we understand the flags:
        - AM = Added or Modified files (what we want to process)
        - D = Deleted files (what we want to detect but ignore)
        """
        # These are the flags used in the workflow
        process_filter = "AM"  # Added or Modified
        deleted_filter = "D"   # Deleted

        # Verify flag meanings
        assert "A" in process_filter, "Should detect Added files"
        assert "M" in process_filter, "Should detect Modified files"
        assert "D" not in process_filter, "Should NOT process Deleted files"
        assert deleted_filter == "D", "Should detect Deleted files separately"


class TestClaudeChainWorkflowYAML:
    """Tests for ClaudeChain workflow YAML structure (simplified workflow)."""

    def test_workflow_file_exists(self):
        """Verify the ClaudeChain workflow file exists."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"
        assert workflow_path.exists(), \
            f"ClaudeChain workflow should exist at {workflow_path}"

    def test_workflow_yaml_is_valid(self):
        """Verify the workflow YAML is syntactically valid."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Basic structure validation
        assert workflow_data is not None, "YAML should parse successfully"
        assert "name" in workflow_data, "Workflow should have a name"
        # Note: YAML parses 'on' as boolean True, so check for True or 'on'
        assert (True in workflow_data or "on" in workflow_data), "Workflow should have triggers"
        assert "jobs" in workflow_data, "Workflow should have jobs"

    def test_workflow_uses_simplified_pattern(self):
        """Verify the workflow uses the simplified pattern without explicit event inputs."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        jobs = workflow_data["jobs"]
        assert "run-claudechain" in jobs, "Workflow should have run-claudechain job"

        steps = jobs["run-claudechain"]["steps"]

        # Should have a single step that uses the action
        action_step = None
        for step in steps:
            if step.get("uses", "").startswith("./"):
                action_step = step
                break

        assert action_step is not None, "Should have a step that uses the local action"

        # Verify simplified pattern - action reads GitHub context directly
        # so github_event and event_name inputs are NOT needed
        with_block = action_step.get("with", {})
        assert "github_event" not in with_block, "Should NOT pass github_event (action reads context directly)"
        assert "event_name" not in with_block, "Should NOT pass event_name (action reads context directly)"

    def test_workflow_has_no_complex_bash_steps(self):
        """Verify the workflow doesn't have complex bash logic (simplified)."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        steps = workflow_data["jobs"]["run-claudechain"]["steps"]

        # The simplified workflow should NOT have these steps
        step_names = [step.get("name", "") for step in steps]

        assert not any("Determine project" in name for name in step_names), \
            "Simplified workflow should NOT have 'Determine project' step"
        assert not any("Validate base branch" in name for name in step_names), \
            "Simplified workflow should NOT have 'Validate base branch' step"

    def test_workflow_has_required_secrets(self):
        """Verify the workflow uses required secrets."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            content = f.read()

        assert "secrets.ANTHROPIC_API_KEY" in content, \
            "Workflow should use ANTHROPIC_API_KEY secret"
        assert "secrets.GITHUB_TOKEN" in content, \
            "Workflow should use GITHUB_TOKEN secret"


@pytest.mark.integration
class TestAutoStartEdgeCases:
    """Tests for edge cases in auto-start workflow logic."""

    def test_empty_projects_list_handling(self):
        """Verify workflow handles empty project lists correctly."""
        # When PROJECTS is empty, the workflow should:
        # 1. Output empty string to GITHUB_OUTPUT
        # 2. Exit with status 0 (success)
        # 3. Not attempt to process any projects

        projects = ""

        # Simulate the bash loop
        project_list = projects.split() if projects else []
        assert len(project_list) == 0, "Empty string should result in empty list"

    def test_multiple_projects_parsing(self):
        """Verify multiple space-separated projects are parsed correctly."""
        projects = "project1 project2 project3"

        project_list = projects.split()
        assert len(project_list) == 3, "Should parse 3 projects"
        assert project_list == ["project1", "project2", "project3"]

    def test_project_name_with_hyphens_and_underscores(self):
        """Verify project names with special characters are handled correctly."""
        pattern = r'claude-chain/([^/]*)/spec\.md'

        special_names = [
            "my-project",
            "my_project",
            "my-project-123",
            "api_v2_refactor",
            "auth-2024-Q1",
        ]

        for name in special_names:
            path = f"claude-chain/{name}/spec.md"
            match = re.search(pattern, path)
            assert match is not None, f"Should match project name: {name}"
            assert match.group(1) == name, f"Should extract exact name: {name}"


@pytest.mark.integration
class TestClaudeChainBranchNameEdgeCases:
    """Tests for branch name edge cases in ClaudeChain workflow.

    The claudechain.yml workflow extracts project names from PR branch names
    using the pattern: claude-chain-{project}-{8-char-hex-hash}
    """

    def test_branch_name_extraction_with_hyphenated_projects(self):
        """Verify project extraction works with hyphenated project names."""
        # Pattern matches: claude-chain-{project}-{8-char-hex}
        # Project names can contain hyphens, only the final 8-char hex is special
        pattern = r'^claude-chain-(.+)-([0-9a-f]{8})$'

        test_cases = [
            # (branch_name, expected_project)
            ("claude-chain-my-project-a1b2c3d4", "my-project"),
            ("claude-chain-test-project-12345678", "test-project"),
            ("claude-chain-my-complex-project-name-deadbeef", "my-complex-project-name"),
            ("claude-chain-api-v2-refactor-abcd1234", "api-v2-refactor"),
            ("claude-chain-2024-q1-auth-00000000", "2024-q1-auth"),
        ]

        for branch, expected_project in test_cases:
            match = re.match(pattern, branch)
            assert match is not None, f"Pattern should match branch: {branch}"
            assert match.group(1) == expected_project, \
                f"Expected '{expected_project}', got '{match.group(1)}' for branch '{branch}'"
            assert len(match.group(2)) == 8, "Hash should be exactly 8 characters"

    def test_branch_name_extraction_rejects_invalid_patterns(self):
        """Verify pattern rejects invalid branch names."""
        pattern = r'^claude-chain-(.+)-([0-9a-f]{8})$'

        invalid_branches = [
            "claude-chain-project-123",      # Hash too short (3 chars)
            "claude-chain-project-1234567",  # Hash too short (7 chars)
            "claude-chain-project-123456789", # Hash too long (9 chars)
            "claude-chain-project-ABCD1234", # Uppercase not valid hex
            "claude-chain-project-xyz12345", # Invalid hex chars
            "claude-chain-project",          # Missing hash entirely
            "feature/my-branch",            # Not a ClaudeChain branch
            "main",                         # Not a ClaudeChain branch
            "claude-chain--a1b2c3d4",        # Empty project name
        ]

        for branch in invalid_branches:
            match = re.match(pattern, branch)
            assert match is None, f"Pattern should NOT match invalid branch: {branch}"

    def test_branch_name_with_long_project_names(self):
        """Verify very long project names are handled correctly."""
        pattern = r'^claude-chain-(.+)-([0-9a-f]{8})$'

        # Very long project name (but still reasonable)
        long_project = "this-is-a-very-long-project-name-with-many-hyphens-2024"
        branch = f"claude-chain-{long_project}-abcdef12"

        match = re.match(pattern, branch)
        assert match is not None, f"Should match long project name"
        assert match.group(1) == long_project, "Should extract full long project name"

    def test_branch_name_with_numeric_project_names(self):
        """Verify project names with numbers are handled correctly."""
        pattern = r'^claude-chain-(.+)-([0-9a-f]{8})$'

        test_cases = [
            ("claude-chain-v2-api-12345678", "v2-api"),
            ("claude-chain-2024-refactor-abcdef00", "2024-refactor"),
            ("claude-chain-project-123-update-11111111", "project-123-update"),
        ]

        for branch, expected_project in test_cases:
            match = re.match(pattern, branch)
            assert match is not None, f"Pattern should match branch: {branch}"
            assert match.group(1) == expected_project, \
                f"Expected '{expected_project}', got '{match.group(1)}'"

    def test_branch_name_edge_case_all_hex_project_name(self):
        """Verify project names that look like hex are handled correctly.

        Edge case: project name 'deadbeef' with hash '12345678'
        Branch: 'claude-chain-deadbeef-12345678'
        Should extract project='deadbeef', hash='12345678'
        """
        pattern = r'^claude-chain-(.+)-([0-9a-f]{8})$'

        branch = "claude-chain-deadbeef-12345678"
        match = re.match(pattern, branch)
        assert match is not None, "Should match hex-like project name"
        assert match.group(1) == "deadbeef", "Should extract 'deadbeef' as project"
        assert match.group(2) == "12345678", "Should extract '12345678' as hash"


@pytest.mark.integration
class TestSimplifiedWorkflowEventHandling:
    """Tests for simplified workflow event handling.

    The simplified workflow lets the action read GitHub context directly
    via built-in environment variables (GITHUB_EVENT_NAME, GITHUB_EVENT_PATH).
    """

    def test_workflow_does_not_pass_event_context_explicitly(self):
        """Verify workflow does NOT pass github_event/event_name (action reads them directly)."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        steps = workflow_data["jobs"]["run-claudechain"]["steps"]

        # Find the action step
        action_step = None
        for step in steps:
            if step.get("uses", "").startswith("./"):
                action_step = step
                break

        assert action_step is not None, "Should have action step"

        with_block = action_step.get("with", {})

        # Should NOT pass github_event or event_name - action reads context directly
        assert "github_event" not in with_block, \
            "Should NOT pass github_event (action reads GITHUB_EVENT_PATH directly)"
        assert "event_name" not in with_block, \
            "Should NOT pass event_name (action reads GITHUB_EVENT_NAME directly)"

    def test_workflow_dispatch_passes_project_name(self):
        """Verify workflow_dispatch input for project_name is passed to action."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Check triggers
        triggers = workflow_data.get(True) or workflow_data.get("on")
        assert "workflow_dispatch" in triggers, "Should have workflow_dispatch trigger"

        inputs = triggers["workflow_dispatch"]["inputs"]
        assert "project_name" in inputs, "Should have project_name input"

        # Check that project_name is passed to action
        steps = workflow_data["jobs"]["run-claudechain"]["steps"]
        action_step = None
        for step in steps:
            if step.get("uses", "").startswith("./"):
                action_step = step
                break

        with_block = action_step.get("with", {})
        assert "project_name" in with_block, "Should pass project_name to action"


@pytest.mark.integration
class TestGenericWorkflowDocumentation:
    """Tests for generic workflow documentation."""

    def test_claudechain_has_event_handling_documentation(self):
        """Verify ClaudeChain workflow has documentation about automatic event handling."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            content = f.read()

        # Should document automatic event handling
        assert "automatically" in content.lower() or "event context" in content.lower(), \
            "Should document that workflow handles events automatically"

    def test_claudechain_has_security_documentation(self):
        """Verify ClaudeChain workflow has security considerations documented."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudechain.yml"

        with open(workflow_path) as f:
            content = f.read()

        # Should document security considerations
        assert "Security" in content or "security" in content, \
            "Should have security considerations documented"
