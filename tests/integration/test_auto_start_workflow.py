"""Integration tests for ClaudeStep Auto-Start workflow.

This module tests the bash script logic used in the auto-start workflow without
requiring actual GitHub Actions to run. It validates:
- Project name extraction from spec file paths
- Detection of added/modified vs deleted spec files
- YAML syntax and structure validation

Note: Full E2E testing of the auto-start workflow requires manual testing
since it involves GitHub Actions triggers and workflow_dispatch calls.
"""

import pytest
import re
from pathlib import Path


class TestAutoStartWorkflowLogic:
    """Tests for auto-start workflow bash script logic."""

    def test_project_name_extraction_pattern(self):
        """Verify the sed pattern correctly extracts project names from spec paths."""
        # Pattern used in workflow: sed 's|claude-step/\([^/]*\)/spec.md|\1|'
        pattern = r'claude-step/([^/]*)/spec\.md'

        test_cases = [
            ("claude-step/my-project/spec.md", "my-project"),
            ("claude-step/test-project-1/spec.md", "test-project-1"),
            ("claude-step/auth-refactor/spec.md", "auth-refactor"),
            ("claude-step/api_v2/spec.md", "api_v2"),
        ]

        for path, expected_project in test_cases:
            match = re.search(pattern, path)
            assert match is not None, f"Pattern should match path: {path}"
            extracted = match.group(1)
            assert extracted == expected_project, \
                f"Expected '{expected_project}', got '{extracted}' for path '{path}'"

    def test_project_name_extraction_rejects_invalid_paths(self):
        """Verify the pattern rejects invalid paths."""
        pattern = r'claude-step/([^/]*)/spec\.md'

        invalid_paths = [
            "claude-step/spec.md",  # Missing project directory
            "spec.md",  # Missing claude-step prefix
            "claude-step/project/other.md",  # Wrong filename
            "claude-step/project/subdir/spec.md",  # Too many directories
        ]

        for path in invalid_paths:
            match = re.search(pattern, path)
            assert match is None, f"Pattern should NOT match invalid path: {path}"

    def test_branch_name_pattern_for_pr_detection(self):
        """Verify the branch name pattern used to detect existing PRs."""
        # Pattern used in workflow: claude-step-$project-*
        # We check if branch starts with the pattern prefix

        def matches_pr_branch_pattern(branch_name: str, project: str) -> bool:
            """Check if branch name matches ClaudeStep PR pattern for given project."""
            prefix = f"claude-step-{project}-"
            return branch_name.startswith(prefix)

        test_cases = [
            # (branch_name, project, should_match)
            ("claude-step-my-project-1", "my-project", True),
            ("claude-step-my-project-2", "my-project", True),
            ("claude-step-my-project-123", "my-project", True),
            ("claude-step-other-project-1", "my-project", False),
            ("claude-step-my-project", "my-project", False),  # Missing task number
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


class TestAutoStartWorkflowYAML:
    """Tests for auto-start workflow YAML structure."""

    def test_workflow_file_exists(self):
        """Verify the auto-start workflow file exists."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"
        assert workflow_path.exists(), \
            f"Auto-start workflow should exist at {workflow_path}"

    def test_workflow_yaml_is_valid(self):
        """Verify the workflow YAML is syntactically valid."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Basic structure validation
        assert workflow_data is not None, "YAML should parse successfully"
        assert "name" in workflow_data, "Workflow should have a name"
        # Note: YAML parses 'on' as boolean True, so check for True or 'on'
        assert (True in workflow_data or "on" in workflow_data), "Workflow should have triggers"
        assert "jobs" in workflow_data, "Workflow should have jobs"

    def test_workflow_has_required_triggers(self):
        """Verify the workflow has the correct triggers configured."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # YAML parses 'on:' as boolean True
        triggers = workflow_data.get(True) or workflow_data.get("on")
        assert triggers is not None, "Workflow should have triggers section"

        # Should trigger on push to any branch (generic workflow)
        assert "push" in triggers, "Workflow should trigger on push"
        assert "**" in triggers["push"]["branches"], \
            "Workflow should trigger on push to any branch"

        # Should filter by spec.md paths
        assert "paths" in triggers["push"], "Workflow should have path filters"
        assert "claude-step/*/spec.md" in triggers["push"]["paths"], \
            "Workflow should filter for spec.md files"

    def test_workflow_has_concurrency_control(self):
        """Verify the workflow has concurrency control to prevent race conditions."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        assert "concurrency" in workflow_data, "Workflow should have concurrency control"
        concurrency = workflow_data["concurrency"]

        assert "group" in concurrency, "Concurrency should have a group"
        assert "${{ github.ref }}" in concurrency["group"], \
            "Concurrency group should use github.ref"

        # cancel-in-progress should be false to allow both runs to execute
        # (they'll detect existing PRs and handle appropriately)
        assert concurrency.get("cancel-in-progress") is False, \
            "cancel-in-progress should be false to prevent race conditions"

    def test_workflow_has_required_steps(self):
        """Verify the workflow has all required steps."""
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        jobs = workflow_data["jobs"]
        assert "auto-start" in jobs, "Workflow should have auto-start job"

        steps = jobs["auto-start"]["steps"]
        step_names = [step.get("name", "") for step in steps]

        required_steps = [
            "Checkout repository",
            "Setup Python",
            "Install ClaudeStep",
            "Detect and trigger auto-start",
            "Generate summary",
        ]

        for required_step in required_steps:
            assert any(required_step in name for name in step_names), \
                f"Workflow should have step: {required_step}"


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
        pattern = r'claude-step/([^/]*)/spec\.md'

        special_names = [
            "my-project",
            "my_project",
            "my-project-123",
            "api_v2_refactor",
            "auth-2024-Q1",
        ]

        for name in special_names:
            path = f"claude-step/{name}/spec.md"
            match = re.search(pattern, path)
            assert match is not None, f"Should match project name: {name}"
            assert match.group(1) == name, f"Should extract exact name: {name}"


@pytest.mark.integration
class TestClaudeStepBranchNameEdgeCases:
    """Tests for branch name edge cases in ClaudeStep workflow.

    The claudestep.yml workflow extracts project names from PR branch names
    using the pattern: claude-step-{project}-{8-char-hex-hash}
    """

    def test_branch_name_extraction_with_hyphenated_projects(self):
        """Verify project extraction works with hyphenated project names."""
        # Pattern matches: claude-step-{project}-{8-char-hex}
        # Project names can contain hyphens, only the final 8-char hex is special
        pattern = r'^claude-step-(.+)-([0-9a-f]{8})$'

        test_cases = [
            # (branch_name, expected_project)
            ("claude-step-my-project-a1b2c3d4", "my-project"),
            ("claude-step-test-project-12345678", "test-project"),
            ("claude-step-my-complex-project-name-deadbeef", "my-complex-project-name"),
            ("claude-step-api-v2-refactor-abcd1234", "api-v2-refactor"),
            ("claude-step-2024-q1-auth-00000000", "2024-q1-auth"),
        ]

        for branch, expected_project in test_cases:
            match = re.match(pattern, branch)
            assert match is not None, f"Pattern should match branch: {branch}"
            assert match.group(1) == expected_project, \
                f"Expected '{expected_project}', got '{match.group(1)}' for branch '{branch}'"
            assert len(match.group(2)) == 8, "Hash should be exactly 8 characters"

    def test_branch_name_extraction_rejects_invalid_patterns(self):
        """Verify pattern rejects invalid branch names."""
        pattern = r'^claude-step-(.+)-([0-9a-f]{8})$'

        invalid_branches = [
            "claude-step-project-123",      # Hash too short (3 chars)
            "claude-step-project-1234567",  # Hash too short (7 chars)
            "claude-step-project-123456789", # Hash too long (9 chars)
            "claude-step-project-ABCD1234", # Uppercase not valid hex
            "claude-step-project-xyz12345", # Invalid hex chars
            "claude-step-project",          # Missing hash entirely
            "feature/my-branch",            # Not a ClaudeStep branch
            "main",                         # Not a ClaudeStep branch
            "claude-step--a1b2c3d4",        # Empty project name
        ]

        for branch in invalid_branches:
            match = re.match(pattern, branch)
            assert match is None, f"Pattern should NOT match invalid branch: {branch}"

    def test_branch_name_with_long_project_names(self):
        """Verify very long project names are handled correctly."""
        pattern = r'^claude-step-(.+)-([0-9a-f]{8})$'

        # Very long project name (but still reasonable)
        long_project = "this-is-a-very-long-project-name-with-many-hyphens-2024"
        branch = f"claude-step-{long_project}-abcdef12"

        match = re.match(pattern, branch)
        assert match is not None, f"Should match long project name"
        assert match.group(1) == long_project, "Should extract full long project name"

    def test_branch_name_with_numeric_project_names(self):
        """Verify project names with numbers are handled correctly."""
        pattern = r'^claude-step-(.+)-([0-9a-f]{8})$'

        test_cases = [
            ("claude-step-v2-api-12345678", "v2-api"),
            ("claude-step-2024-refactor-abcdef00", "2024-refactor"),
            ("claude-step-project-123-update-11111111", "project-123-update"),
        ]

        for branch, expected_project in test_cases:
            match = re.match(pattern, branch)
            assert match is not None, f"Pattern should match branch: {branch}"
            assert match.group(1) == expected_project, \
                f"Expected '{expected_project}', got '{match.group(1)}'"

    def test_branch_name_edge_case_all_hex_project_name(self):
        """Verify project names that look like hex are handled correctly.

        Edge case: project name 'deadbeef' with hash '12345678'
        Branch: 'claude-step-deadbeef-12345678'
        Should extract project='deadbeef', hash='12345678'
        """
        pattern = r'^claude-step-(.+)-([0-9a-f]{8})$'

        branch = "claude-step-deadbeef-12345678"
        match = re.match(pattern, branch)
        assert match is not None, "Should match hex-like project name"
        assert match.group(1) == "deadbeef", "Should extract 'deadbeef' as project"
        assert match.group(2) == "12345678", "Should extract '12345678' as hash"


@pytest.mark.integration
class TestGenericWorkflowBaseBranchInference:
    """Tests for generic workflow base branch inference.

    Phase 8 validation: Ensure generic workflows correctly infer base branch
    from event context for all trigger types.
    """

    def test_auto_start_uses_github_ref_name_for_base_branch(self):
        """Verify auto-start workflow derives base branch from github.ref_name.

        The auto-start workflow should:
        - Push to 'main' → BASE_BRANCH='main'
        - Push to 'main-e2e' → BASE_BRANCH='main-e2e'
        - Push to 'feature/test' → BASE_BRANCH='feature/test'
        """
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Find the auto-start step
        steps = workflow_data["jobs"]["auto-start"]["steps"]
        auto_start_step = None
        for step in steps:
            if step.get("name") == "Detect and trigger auto-start":
                auto_start_step = step
                break

        assert auto_start_step is not None, "Should have 'Detect and trigger auto-start' step"

        # Verify BASE_BRANCH uses github.ref_name
        env = auto_start_step.get("env", {})
        assert "BASE_BRANCH" in env, "Should have BASE_BRANCH env var"
        assert env["BASE_BRANCH"] == "${{ github.ref_name }}", \
            "BASE_BRANCH should derive from github.ref_name (the branch that was pushed to)"

    def test_claudestep_workflow_infers_base_from_checkout_ref(self):
        """Verify ClaudeStep workflow infers base branch from checkout_ref.

        For workflow_dispatch events:
        - If base_branch input provided → use it (explicit override)
        - Else use checkout_ref (inferred base branch)

        This ensures manual triggers work correctly:
        - Trigger with checkout_ref='main-e2e' → BASE_BRANCH='main-e2e'
        - Trigger with checkout_ref='feature/test' → BASE_BRANCH='feature/test'
        """
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Find the "Determine project and base branch" step
        steps = workflow_data["jobs"]["run-claudestep"]["steps"]
        determine_step = None
        for step in steps:
            if "Determine project and base branch" in step.get("name", ""):
                determine_step = step
                break

        assert determine_step is not None, "Should have 'Determine project and base branch' step"

        # Verify the run script contains inference logic
        run_script = determine_step.get("run", "")

        # Should check for explicit base_branch input first
        assert "github.event.inputs.base_branch" in run_script, \
            "Should check for explicit base_branch input"

        # Should fall back to checkout_ref
        assert "github.event.inputs.checkout_ref" in run_script, \
            "Should fall back to checkout_ref for base branch inference"

        # Should have logging for inference path taken
        assert "Inferring base_branch from checkout_ref" in run_script or \
               "Using explicit base_branch input" in run_script, \
            "Should log which inference path was taken"

    def test_claudestep_workflow_uses_github_base_ref_for_pr_merge(self):
        """Verify ClaudeStep workflow uses github.base_ref for PR merge events.

        For pull_request events:
        - BASE_BRANCH = github.base_ref (the branch the PR was merged INTO)

        This ensures merge triggers work correctly:
        - PR merged into 'main' → BASE_BRANCH='main'
        - PR merged into 'main-e2e' → BASE_BRANCH='main-e2e'
        """
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # Find the "Determine project and base branch" step
        steps = workflow_data["jobs"]["run-claudestep"]["steps"]
        determine_step = None
        for step in steps:
            if "Determine project and base branch" in step.get("name", ""):
                determine_step = step
                break

        assert determine_step is not None, "Should have 'Determine project and base branch' step"

        # Verify the run script uses github.base_ref for PR events
        run_script = determine_step.get("run", "")

        # Should handle pull_request event type
        assert "github.event_name" in run_script and "pull_request" in run_script, \
            "Should handle pull_request event type"

        # Should use github.base_ref for base branch
        assert "github.base_ref" in run_script, \
            "Should use github.base_ref for PR merge base branch"

    def test_claudestep_workflow_has_base_branch_validation(self):
        """Verify ClaudeStep workflow validates that base branch is set.

        The workflow should fail fast with clear error if base branch
        cannot be determined.
        """
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        steps = workflow_data["jobs"]["run-claudestep"]["steps"]

        # Find the validation step
        validation_step = None
        for step in steps:
            if "Validate base branch" in step.get("name", ""):
                validation_step = step
                break

        assert validation_step is not None, "Should have 'Validate base branch' step"

        # Verify validation checks for empty base_branch
        run_script = validation_step.get("run", "")
        assert "steps.project.outputs.base_branch" in run_script, \
            "Should check project step output for base_branch"
        assert "exit 1" in run_script, \
            "Should exit with error if base branch not determined"

        # Verify helpful error message
        assert "ERROR" in run_script or "error" in run_script.lower(), \
            "Should have clear error message"

    def test_claudestep_workflow_base_branch_has_no_default(self):
        """Verify base_branch input has no default value.

        The base_branch input should NOT have a default so it can be
        properly inferred from checkout_ref when not provided.
        """
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # YAML parses 'on:' as boolean True
        triggers = workflow_data.get(True) or workflow_data.get("on")
        inputs = triggers["workflow_dispatch"]["inputs"]

        # base_branch should exist but have no default
        assert "base_branch" in inputs, "Should have base_branch input"
        assert "default" not in inputs["base_branch"], \
            "base_branch should NOT have a default value (allows inference from checkout_ref)"

        # checkout_ref should have a default for backwards compatibility
        assert "checkout_ref" in inputs, "Should have checkout_ref input"
        assert "default" in inputs["checkout_ref"], \
            "checkout_ref SHOULD have a default for backwards compatibility"

    def test_auto_start_workflow_triggers_on_any_branch(self):
        """Verify auto-start workflow triggers on any branch.

        The workflow should use '**' to trigger on pushes to ANY branch,
        not just specific hardcoded branches like main and main-e2e.
        """
        import yaml

        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            workflow_data = yaml.safe_load(f)

        # YAML parses 'on:' as boolean True
        triggers = workflow_data.get(True) or workflow_data.get("on")

        # Should trigger on push
        assert "push" in triggers, "Should trigger on push"

        # Should use '**' for any branch
        assert "**" in triggers["push"]["branches"], \
            "Should trigger on ANY branch using '**' pattern"

        # Should NOT have hardcoded specific branches
        branches = triggers["push"]["branches"]
        assert "main" not in branches or "**" in branches, \
            "Should not have hardcoded 'main' branch (use '**' instead)"
        assert "main-e2e" not in branches or "**" in branches, \
            "Should not have hardcoded 'main-e2e' branch (use '**' instead)"


@pytest.mark.integration
class TestGenericWorkflowDocumentation:
    """Tests for generic workflow documentation.

    Phase 8 validation: Ensure workflows have proper documentation
    explaining their branch-agnostic behavior.
    """

    def test_auto_start_has_generic_workflow_documentation(self):
        """Verify auto-start workflow has documentation about generic behavior."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            content = f.read()

        # Should document generic behavior
        assert "generic" in content.lower() or "ANY branch" in content, \
            "Should document that workflow works on any branch"

        # Should explain base branch derivation
        assert "github.ref_name" in content, \
            "Should explain that base branch comes from github.ref_name"

    def test_claudestep_has_generic_workflow_documentation(self):
        """Verify ClaudeStep workflow has documentation about generic behavior."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep.yml"

        with open(workflow_path) as f:
            content = f.read()

        # Should document generic behavior
        assert "generic" in content.lower() or "branch-agnostic" in content.lower(), \
            "Should document that workflow is branch-agnostic"

        # Should document base branch inference rules
        assert "PR merge" in content or "pull_request" in content.lower(), \
            "Should document PR merge base branch inference"
        assert "workflow_dispatch" in content, \
            "Should document workflow_dispatch base branch inference"

    def test_claudestep_has_security_documentation(self):
        """Verify ClaudeStep workflow has security considerations documented."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep.yml"

        with open(workflow_path) as f:
            content = f.read()

        # Should document security considerations
        assert "Security" in content or "security" in content, \
            "Should have security considerations documented"

    def test_auto_start_has_security_documentation(self):
        """Verify auto-start workflow has security considerations documented."""
        workflow_path = Path(__file__).parent.parent.parent / ".github/workflows/claudestep-auto-start.yml"

        with open(workflow_path) as f:
            content = f.read()

        # Should document security considerations
        assert "Security" in content or "security" in content, \
            "Should have security considerations documented"
