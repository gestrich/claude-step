# ClaudeStep Metadata Schema

This document defines the JSON schema used for storing ClaudeStep metadata in the `claudestep-metadata` branch.

## Data Model Overview

ClaudeStep uses a hierarchical structure to track automation progress:

```
Project
  └── Step (one per task in spec.md)
      ├── PR Properties (task_index, description, branch, reviewer, state, etc.)
      └── AITask[] (individual AI operations)
          └── AI Properties (type, model, cost, tokens, duration)
```

**Typical Flow**: Each step in `spec.md` becomes a Pull Request with 2 AI tasks:
1. **PRCreation**: Claude Code generates the code changes
2. **PRSummary**: AI generates the PR description

## Directory Structure

The `claudestep-metadata` branch has the following structure:

```
claudestep-metadata/
├── projects/
│   ├── project-name-1.json
│   ├── project-name-2.json
│   └── project-name-3.json
└── README.md
```

### File Organization

- **`projects/`**: Directory containing one JSON file per project
  - File naming: `{project-name}.json` (matches the project directory name)
  - Each file contains all step metadata for that project
- **`README.md`**: Explains the purpose of the metadata branch

### Design Rationale

- **Flat structure**: Simple and efficient for typical ClaudeStep usage (5-20 projects per repo)
- **One file per project**: Enables atomic updates per project and parallel writes across projects
- **Human-readable JSON**: Easy to inspect and debug using GitHub's web interface or git commands
- **Clear naming**: "Step" represents each task from spec.md, making the model intuitive

## JSON Schema

### Project Metadata File

Each project file (`projects/{project-name}.json`) has the following structure:

```json
{
  "schema_version": "1.0",
  "project": "my-refactor",
  "last_updated": "2025-01-15T10:30:00Z",
  "steps": [
    {
      "step_index": 1,
      "step_description": "Refactor authentication module",
      "branch_name": "claude-step-my-refactor-1",
      "reviewer": "alice",
      "pr_number": 42,
      "pr_state": "merged",
      "created_at": "2025-01-10T14:22:00Z",
      "ai_tasks": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-01-10T14:22:00Z",
          "workflow_run_id": 123456,
          "tokens_input": 8500,
          "tokens_output": 1200,
          "duration_seconds": 12.5
        },
        {
          "type": "PRSummary",
          "model": "claude-sonnet-4",
          "cost_usd": 0.02,
          "created_at": "2025-01-10T14:23:00Z",
          "workflow_run_id": 123456,
          "tokens_input": 1200,
          "tokens_output": 150,
          "duration_seconds": 2.1
        }
      ]
    },
    {
      "step_index": 2,
      "step_description": "Add JWT token validation"
    },
    {
      "step_index": 3,
      "step_description": "Implement OAuth2 integration"
    }
  ]
}
```

**Key Changes from Legacy Format:**
- `tasks` → `steps` (clearer naming: each item is a step from spec.md)
- `task_index` → `step_index` (consistency with "step" terminology)
- `task_description` → `step_description` (consistency with "step" terminology)
- Removed `project` field from step (redundant - already at project level)
- Removed deprecated cost fields from step level
- Cost and model info now **exclusively** in `ai_tasks` array
- `workflow_run_id` moved from step to AITask (a step may have multiple workflow runs)
- **NEW:** Support for not-yet-started steps (only `step_index` and `step_description`)

### Field Definitions

#### Project-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | Schema version for future migrations (currently "1.0") |
| `project` | string | Yes | Project name (matches directory and file name) |
| `last_updated` | string (ISO 8601) | Yes | Timestamp of last metadata update |
| `steps` | array | Yes | List of Step objects (one per task from spec.md) |

#### Step-Level Fields

Each object in the `steps` array represents a single step from spec.md. Steps that haven't started yet will only have `step_index` and `step_description`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step_index` | integer | Yes | Step number from spec.md (1-based) |
| `step_description` | string | Yes | Step description text from spec.md |
| `branch_name` | string | No | PR branch name (e.g., "claude-step-project-1"). Null if step not started. |
| `reviewer` | string | No | Assigned reviewer GitHub username. Null if step not started. |
| `pr_number` | integer | No | Pull request number. Null if step not started. |
| `pr_state` | string | No | PR state: "open", "merged", or "closed". Null if step not started. |
| `created_at` | string (ISO 8601) | No | PR creation timestamp. Null if step not started. |
| `ai_tasks` | array | No | List of AI operations for this step (typically 2: PRCreation + PRSummary). Empty if step not started. |

**Note:**
- Steps not yet started will have `null` for all fields except `step_index` and `step_description`
- Cost and model information is NOT stored at the step level - it lives in the `ai_tasks` array
- `workflow_run_id` is stored in each `AITask`, not at the step level (a step may have multiple workflow runs)

#### AI Task Fields

Each object in the `ai_tasks` array represents a single AI operation:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Task type: "PRCreation", "PRRefinement", "PRSummary", etc. |
| `model` | string | Yes | AI model used (e.g., "claude-sonnet-4", "claude-opus-4") |
| `cost_usd` | float | Yes | Cost in USD for this specific AI operation |
| `created_at` | string (ISO 8601) | Yes | When this AI task was executed |
| `workflow_run_id` | integer | Yes | GitHub Actions workflow run ID that executed this AI task |
| `tokens_input` | integer | No | Input tokens used (default: 0) |
| `tokens_output` | integer | No | Output tokens generated (default: 0) |
| `duration_seconds` | float | No | Time taken for this operation in seconds (default: 0.0) |

**Why workflow_run_id is in AITask:**
- Each AI operation runs in a specific GitHub Actions workflow
- A single step may have multiple workflow runs (e.g., PRCreation in one run, PRRefinement in another)
- This enables precise tracking of which workflow execution performed which AI operation

**AI Task Types:**
- `PRCreation`: Initial code generation for the PR
- `PRRefinement`: Code refinement or iteration based on feedback
- `PRSummary`: AI-generated PR description and summary
- `CodeReview`: AI-assisted code review feedback
- `TestGeneration`: Automated test generation

### Timestamp Format

All timestamps use ISO 8601 format with timezone:

- **Format**: `YYYY-MM-DDTHH:MM:SSZ` (UTC)
- **Example**: `2025-01-15T10:30:00Z`
- Python: Use `datetime.isoformat()` for serialization
- Python: Use `datetime.fromisoformat(s.replace("Z", "+00:00"))` for parsing

## PR State Values

The `pr_state` field tracks the lifecycle of each pull request:

| Value | Description | Usage |
|-------|-------------|-------|
| `open` | PR is currently open | Used for reviewer capacity checking |
| `merged` | PR was merged | Used for statistics and completion tracking |
| `closed` | PR was closed without merging | Tracked but typically excluded from statistics |

## Schema Versioning

The `schema_version` field enables future migrations:

- **Current version**: "1.0"
- **Forward compatibility**: New fields can be added with default values
- **Breaking changes**: Increment schema version and implement migration logic
- **Backward compatibility**: Parsers should handle missing optional fields gracefully

## Example: Complete Project File

```json
{
  "schema_version": "1.0",
  "project": "auth-refactor",
  "last_updated": "2025-01-20T15:45:00Z",
  "steps": [
    {
      "step_index": 1,
      "step_description": "Extract authentication logic to separate module",
      "branch_name": "claude-step-auth-refactor-1",
      "reviewer": "alice",
      "pr_number": 101,
      "pr_state": "merged",
      "created_at": "2025-01-10T09:00:00Z",
      "ai_tasks": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-01-10T09:00:00Z",
          "workflow_run_id": 100001,
          "tokens_input": 7500,
          "tokens_output": 1100,
          "duration_seconds": 10.2
        },
        {
          "type": "PRSummary",
          "model": "claude-sonnet-4",
          "cost_usd": 0.03,
          "created_at": "2025-01-10T09:01:00Z",
          "workflow_run_id": 100001,
          "tokens_input": 1100,
          "tokens_output": 180,
          "duration_seconds": 2.5
        }
      ]
    },
    {
      "step_index": 2,
      "step_description": "Add JWT token validation",
      "branch_name": "claude-step-auth-refactor-2",
      "reviewer": "bob",
      "pr_number": 105,
      "pr_state": "open",
      "created_at": "2025-01-15T14:30:00Z",
      "ai_tasks": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.18,
          "created_at": "2025-01-15T14:30:00Z",
          "workflow_run_id": 100025,
          "tokens_input": 9200,
          "tokens_output": 1350,
          "duration_seconds": 14.8
        },
        {
          "type": "PRSummary",
          "model": "claude-sonnet-4",
          "cost_usd": 0.02,
          "created_at": "2025-01-15T14:32:00Z",
          "workflow_run_id": 100025,
          "tokens_input": 1350,
          "tokens_output": 120,
          "duration_seconds": 1.9
        }
      ]
    },
    {
      "step_index": 3,
      "step_description": "Implement OAuth2 integration",
      "branch_name": "claude-step-auth-refactor-3",
      "reviewer": "alice",
      "pr_number": 108,
      "pr_state": "open",
      "created_at": "2025-01-20T11:15:00Z",
      "ai_tasks": [
        {
          "type": "PRCreation",
          "model": "claude-opus-4",
          "cost_usd": 0.22,
          "created_at": "2025-01-20T11:15:00Z",
          "workflow_run_id": 100050,
          "tokens_input": 12000,
          "tokens_output": 1800,
          "duration_seconds": 18.3
        },
        {
          "type": "PRRefinement",
          "model": "claude-opus-4",
          "cost_usd": 0.03,
          "created_at": "2025-01-20T11:20:00Z",
          "workflow_run_id": 100075,
          "tokens_input": 2500,
          "tokens_output": 200,
          "duration_seconds": 3.2
        },
        {
          "type": "PRSummary",
          "model": "claude-sonnet-4",
          "cost_usd": 0.04,
          "created_at": "2025-01-20T11:22:00Z",
          "workflow_run_id": 100075,
          "tokens_input": 1800,
          "tokens_output": 210,
          "duration_seconds": 2.8
        }
      ]
    },
    {
      "step_index": 4,
      "step_description": "Add rate limiting middleware"
    },
    {
      "step_index": 5,
      "step_description": "Write integration tests for auth flow"
    }
  ]
}
```

**This example demonstrates:**

1. **Typical 2-AI-Task Pattern** (Steps 1 & 2):
   - `PRCreation`: Claude Code generates the code changes
   - `PRSummary`: AI writes the PR description
   - Both run in same workflow (same `workflow_run_id`)
   - Most steps follow this pattern

2. **Complex Step with Refinement** (Step 3):
   - `PRCreation`: Initial code generation with Opus 4 (workflow 100050)
   - `PRRefinement`: Additional iteration in a later workflow (100075)
   - `PRSummary`: PR description in same workflow as refinement (100075)
   - **Note**: Different workflow_run_ids show this step had multiple workflow executions

3. **Not-Yet-Started Steps** (Steps 4 & 5):
   - Only `step_index` and `step_description` fields present
   - All other fields omitted (will be added when PR is created)
   - Shows complete project progress at a glance

4. **Model Flexibility**:
   - Steps 1-2: Use Sonnet 4 throughout (cost-effective)
   - Step 3: Uses Opus 4 for complex work, Sonnet 4 for summary

5. **Clean Structure**:
   - No redundant `project` field at step level
   - No deprecated cost fields at step level
   - `workflow_run_id` in each AI task (enables tracking multiple workflow runs per step)
   - Cost/model info encapsulated in AI tasks
   - Easy to calculate totals: sum `cost_usd` from all `ai_tasks`

## Index Strategy Decision

**Decision**: **No separate index file** for initial implementation.

### Rationale

1. **Simple implementation**: Fewer moving parts, less complexity
2. **Acceptable performance**: Reading 5-20 project files via GitHub API takes <2 seconds
3. **Atomic updates**: Each project file can be updated independently
4. **No synchronization issues**: No need to keep index in sync with project files

### Query Performance

- **List all projects**: Single Git Tree API call + parse filenames (instant)
- **Get project metadata**: 1 API call per project (~100ms each)
- **Filter by date**: Read all files, filter in-memory (<2 seconds for 20 projects)
- **Statistics generation**: Target <5 seconds (vs. 30+ seconds with artifacts)

### Future Optimization

If performance becomes an issue (e.g., 100+ projects):
- Add optional `index.json` with summary data (project names, last_updated, counts)
- Rebuild index on-demand or during writes
- Use index for fast filtering, then read individual project files

## Implementation Notes

### Python Models (Planned)

The schema will be implemented in Python using dataclasses:

- **`AITask`**: Represents a single AI operation (type, model, cost, tokens, duration)
- **`Step`**: Represents a single step from spec.md with its PR info and list of AI tasks
- **`Project`**: Represents a project with all its steps
- All models have `from_dict()` and `to_dict()` methods for JSON serialization

See: `src/claudestep/domain/models.py` (to be refactored)

### Key Improvements Over Legacy Format

**Legacy Format Issues:**
- Mixed concerns: PR info and cost data at same level
- Redundant fields: `project` repeated in each task
- Deprecated fields: `model`, `main_task_cost_usd`, `pr_summary_cost_usd`, `total_cost_usd`
- Unclear naming: "task" could mean spec.md task or AI task

**New Format Benefits:**
- **Clear separation**: PR properties vs. AI operations
- **No redundancy**: `project` only at top level
- **Clean model**: Cost/model info only in `ai_tasks`
- **Clear naming**: "Step" = spec.md task, "AITask" = AI operation
- **Encapsulation**: Each AI task owns its cost, model, and metrics

### Storage Backend

The schema is stored in GitHub using:
- **Branch**: `claudestep-metadata` (created on first write)
- **API**: GitHub Contents API for file operations
- **Encoding**: JSON with UTF-8 encoding
- **Commits**: One commit per project update (atomic writes)

See: `src/claudestep/infrastructure/metadata/` (to be implemented in Phase 4)
