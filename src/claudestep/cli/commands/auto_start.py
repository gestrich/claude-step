"""CLI command for auto-start workflow.

Orchestrates Service Layer classes to detect new projects and make
auto-trigger decisions. This command instantiates services and coordinates
their operations but does not implement business logic directly.
"""

import os
from typing import List

from claudestep.domain.auto_start import AutoStartProject
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.services.composite.auto_start_service import AutoStartService
from claudestep.services.composite.workflow_service import WorkflowService
from claudestep.services.core.pr_service import PRService


def cmd_auto_start(
    gh: GitHubActionsHelper,
    repo: str,
    base_branch: str,
    ref_before: str,
    ref_after: str,
    auto_start_enabled: bool = True
) -> int:
    """Detect new projects and trigger ClaudeStep workflows for them.

    This command orchestrates the auto-start workflow:
    1. Detect changed spec.md files
    2. Determine which projects are new (no existing PRs)
    3. Make auto-trigger decisions based on business logic
    4. Trigger ClaudeStep workflows for approved projects

    GitHub Actions outputs:
        triggered_projects: Space-separated list of successfully triggered projects
        trigger_count: Number of successful triggers
        failed_projects: Space-separated list of projects that failed to trigger
        projects_to_trigger: (legacy) Space-separated list of projects identified for triggering
        project_count: (legacy) Number of projects identified for triggering

    Args:
        gh: GitHub Actions helper instance
        repo: GitHub repository (owner/name)
        base_branch: Base branch name (e.g., "main")
        ref_before: Git reference before the push (commit SHA)
        ref_after: Git reference after the push (commit SHA)
        auto_start_enabled: Whether auto-start is enabled (default: True)

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        print("=== ClaudeStep Auto-Start Detection ===\n")
        print(f"Repository: {repo}")
        print(f"Base branch: {base_branch}")
        print(f"Checking changes: {ref_before[:8]}...{ref_after[:8]}\n")

        # === Initialize services ===
        pr_service = PRService(repo)
        auto_start_service = AutoStartService(repo, pr_service, auto_start_enabled)

        # === Step 1: Detect changed projects ===
        print("=== Step 1/3: Detecting changed projects ===")
        changed_projects = auto_start_service.detect_changed_projects(
            ref_before=ref_before,
            ref_after=ref_after,
            spec_pattern="claude-step/*/spec.md"
        )

        if not changed_projects:
            print("No spec.md changes detected\n")
            gh.write_output("projects_to_trigger", "")
            gh.write_output("project_count", "0")
            return 0

        print(f"Found {len(changed_projects)} changed project(s):")
        for project in changed_projects:
            print(f"  - {project.name} ({project.change_type.value})")
        print()

        # === Step 2: Determine new projects ===
        print("=== Step 2/3: Determining new projects ===")
        new_projects = auto_start_service.determine_new_projects(changed_projects)

        if not new_projects:
            print("\nNo new projects to trigger (all have existing PRs)\n")
            gh.write_output("projects_to_trigger", "")
            gh.write_output("project_count", "0")
            return 0

        print(f"\nFound {len(new_projects)} new project(s) to trigger\n")

        # === Step 3: Make auto-trigger decisions ===
        print("=== Step 3/4: Making auto-trigger decisions ===")
        projects_to_trigger: List[str] = []

        for project in new_projects:
            decision = auto_start_service.should_auto_trigger(project)

            if decision.should_trigger:
                projects_to_trigger.append(project.name)
                print(f"  ✓ {project.name}: TRIGGER - {decision.reason}")
            else:
                print(f"  ✗ {project.name}: SKIP - {decision.reason}")

        print()

        # === Step 4: Trigger workflows ===
        triggered_projects: List[str] = []
        failed_projects: List[str] = []

        if projects_to_trigger:
            print("=== Step 4/4: Triggering workflows ===")
            workflow_service = WorkflowService()
            triggered_projects, failed_projects = workflow_service.batch_trigger_claudestep_workflows(
                projects=projects_to_trigger,
                base_branch=base_branch,
                checkout_ref=ref_after
            )
            print()

        # === Write outputs ===
        # Write list of successfully triggered projects
        triggered_output = " ".join(triggered_projects) if triggered_projects else ""
        gh.write_output("triggered_projects", triggered_output)
        gh.write_output("trigger_count", str(len(triggered_projects)))

        # Write list of failed projects
        failed_output = " ".join(failed_projects) if failed_projects else ""
        gh.write_output("failed_projects", failed_output)

        # Also write legacy projects_to_trigger for backward compatibility
        projects_output = " ".join(projects_to_trigger) if projects_to_trigger else ""
        gh.write_output("projects_to_trigger", projects_output)
        gh.write_output("project_count", str(len(projects_to_trigger)))

        # === Summary ===
        if triggered_projects:
            print(f"✅ Auto-start complete")
            print(f"   Successfully triggered: {len(triggered_projects)} project(s)")
            print(f"   Projects: {triggered_output}")
            if failed_projects:
                print(f"   ⚠️  Failed triggers: {len(failed_projects)} project(s)")
                print(f"   Failed projects: {failed_output}")
        elif projects_to_trigger:
            # Some projects were identified but all triggers failed
            print(f"❌ Auto-start failed - all triggers failed")
            print(f"   Failed projects: {failed_output}")
        else:
            print("✅ Auto-start complete (no projects to trigger)")

        return 0

    except Exception as e:
        gh.set_error(f"Auto-start detection failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


def cmd_auto_start_summary(
    gh: GitHubActionsHelper,
    triggered_projects: str,
    failed_projects: str
) -> int:
    """Generate GitHub Actions step summary for auto-start workflow.

    This command reads the outputs from the auto-start command and generates
    a formatted markdown summary showing:
    - Projects that were successfully triggered
    - Projects that failed to trigger
    - Overall status

    Args:
        gh: GitHub Actions helper instance
        triggered_projects: Space-separated list of successfully triggered projects
        failed_projects: Space-separated list of projects that failed to trigger

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Parse project lists
        triggered_list = [p for p in triggered_projects.split() if p]
        failed_list = [p for p in failed_projects.split() if p]

        # Write step summary header
        gh.write_step_summary("# ClaudeStep Auto-Start Summary")
        gh.write_step_summary("")

        # Determine overall status
        if triggered_list and not failed_list:
            # All succeeded
            gh.write_step_summary("✅ **Status**: All workflows triggered successfully")
            gh.write_step_summary("")
            gh.write_step_summary(f"**Triggered Projects** ({len(triggered_list)}):")
            gh.write_step_summary("")
            for project in triggered_list:
                gh.write_step_summary(f"- `{project}` - Workflow started")
            gh.write_step_summary("")

        elif triggered_list and failed_list:
            # Partial success
            gh.write_step_summary("⚠️ **Status**: Partial success - some workflows failed to trigger")
            gh.write_step_summary("")
            gh.write_step_summary(f"**Successfully Triggered** ({len(triggered_list)}):")
            gh.write_step_summary("")
            for project in triggered_list:
                gh.write_step_summary(f"- `{project}` ✓")
            gh.write_step_summary("")
            gh.write_step_summary(f"**Failed to Trigger** ({len(failed_list)}):")
            gh.write_step_summary("")
            for project in failed_list:
                gh.write_step_summary(f"- `{project}` ✗")
            gh.write_step_summary("")

        elif failed_list and not triggered_list:
            # All failed
            gh.write_step_summary("❌ **Status**: All workflow triggers failed")
            gh.write_step_summary("")
            gh.write_step_summary(f"**Failed Projects** ({len(failed_list)}):")
            gh.write_step_summary("")
            for project in failed_list:
                gh.write_step_summary(f"- `{project}` ✗")
            gh.write_step_summary("")

        else:
            # No projects detected
            gh.write_step_summary("ℹ️ **Status**: No new projects detected")
            gh.write_step_summary("")
            gh.write_step_summary("No spec.md changes found that require auto-start.")
            gh.write_step_summary("")

        # Add helpful information
        gh.write_step_summary("---")
        gh.write_step_summary("")
        gh.write_step_summary("**What happens next?**")
        gh.write_step_summary("")
        if triggered_list:
            gh.write_step_summary("- Triggered workflows will process the first task from each project's spec.md")
            gh.write_step_summary("- Pull requests will be created automatically for each task")
            gh.write_step_summary("- Check the Actions tab to monitor workflow progress")
        else:
            gh.write_step_summary("- Auto-start only triggers for new projects (projects with no existing PRs)")
            gh.write_step_summary("- Existing projects must be triggered manually or via scheduled workflows")
        gh.write_step_summary("")

        print("✅ Auto-start summary generated successfully")
        return 0

    except Exception as e:
        gh.set_error(f"Auto-start summary generation failed: {str(e)}")
        gh.write_step_summary("# ClaudeStep Auto-Start Summary")
        gh.write_step_summary("")
        gh.write_step_summary(f"❌ **Error**: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
