"""
Create TaskMetadata artifact with cost data for statistics.

This command creates a JSON artifact containing task metadata and cost information
that can be downloaded later by the statistics command to aggregate costs.
"""

import json
import os
import tempfile
from datetime import datetime, timezone

from claudechain.domain.cost_breakdown import CostBreakdown
from claudechain.domain.formatting import format_usd
from claudechain.domain.models import AITask, TaskMetadata
from claudechain.infrastructure.github.actions import GitHubActionsHelper


def cmd_create_artifact(
    gh: GitHubActionsHelper,
    cost_breakdown_json: str,
    pr_number: str,
    task: str,
    task_index: str,
    task_hash: str,
    project: str,
    branch_name: str,
    assignee: str,
    run_id: str,
) -> int:
    """
    Create TaskMetadata artifact with cost data for statistics.

    All parameters passed explicitly, no environment variable access.

    Args:
        gh: GitHub Actions helper for outputs and errors
        cost_breakdown_json: JSON string from CostBreakdown.to_json()
        pr_number: Pull request number
        task: Task description
        task_index: Task index
        task_hash: Task hash (for artifact naming)
        project: Project name
        branch_name: Branch name
        assignee: Assignee username
        run_id: Workflow run ID

    Outputs:
        artifact_path: Path to the created artifact file (if created)
        artifact_name: Name for the artifact (if created)

    Returns:
        0 on success, 1 on error
    """
    # Check if we have required metadata for artifact creation
    if not all([task_hash, project, task_index, pr_number]):
        print("::notice::Missing metadata for artifact creation, skipping")
        gh.write_output("artifact_path", "")
        gh.write_output("artifact_name", "")
        return 0

    if not cost_breakdown_json:
        print("::notice::No cost breakdown provided, skipping artifact creation")
        gh.write_output("artifact_path", "")
        gh.write_output("artifact_name", "")
        return 0

    try:
        # Parse cost breakdown from JSON
        cost_breakdown = CostBreakdown.from_json(cost_breakdown_json)
        now = datetime.now(timezone.utc)

        # Create AITask entries from cost breakdown
        ai_tasks = []

        # Main task cost
        if cost_breakdown.main_cost > 0:
            # Get the primary model from main execution
            main_model = "claude-sonnet-4"  # default
            if cost_breakdown.main_models:
                main_model = cost_breakdown.main_models[0].model

            # Sum tokens from main execution models
            main_input_tokens = sum(m.input_tokens for m in cost_breakdown.main_models)
            main_output_tokens = sum(m.output_tokens for m in cost_breakdown.main_models)

            ai_tasks.append(AITask(
                type="PRCreation",
                model=main_model,
                cost_usd=cost_breakdown.main_cost,
                created_at=now,
                tokens_input=main_input_tokens,
                tokens_output=main_output_tokens,
            ))

        # Summary task cost
        if cost_breakdown.summary_cost > 0:
            # Get the primary model from summary execution
            summary_model = "claude-sonnet-4"  # default
            if cost_breakdown.summary_models:
                summary_model = cost_breakdown.summary_models[0].model

            # Sum tokens from summary execution models
            summary_input_tokens = sum(m.input_tokens for m in cost_breakdown.summary_models)
            summary_output_tokens = sum(m.output_tokens for m in cost_breakdown.summary_models)

            ai_tasks.append(AITask(
                type="PRSummary",
                model=summary_model,
                cost_usd=cost_breakdown.summary_cost,
                created_at=now,
                tokens_input=summary_input_tokens,
                tokens_output=summary_output_tokens,
            ))

        # Create TaskMetadata
        metadata = TaskMetadata(
            task_index=int(task_index),
            task_description=task,
            project=project,
            branch_name=branch_name,
            assignee=assignee or "",
            created_at=now,
            workflow_run_id=int(run_id) if run_id else 0,
            pr_number=int(pr_number),
            pr_state="open",
            ai_tasks=ai_tasks,
        )

        # Write to temp file
        artifact_name = f"task-metadata-{project}-{task_hash}"
        artifact_filename = f"{artifact_name}.json"
        artifact_path = os.path.join(tempfile.gettempdir(), artifact_filename)

        with open(artifact_path, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)

        print(f"✅ Created task metadata artifact: {artifact_filename}")
        print(f"   - Total cost: {format_usd(metadata.get_total_cost())}")
        print(f"   - AI tasks: {len(ai_tasks)}")

        gh.write_output("artifact_path", artifact_path)
        gh.write_output("artifact_name", artifact_name)
        return 0

    except Exception as e:
        print(f"::warning::Failed to create task metadata artifact: {e}")
        gh.write_output("artifact_path", "")
        gh.write_output("artifact_name", "")
        return 1
