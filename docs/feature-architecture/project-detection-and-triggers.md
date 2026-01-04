# Project Detection and Triggers

## Overview

ClaudeChain automatically detects projects from changed files and validates base branches before execution. This document describes the trigger system, project detection, and base branch validation.

## Trigger Architecture

### Workflow Triggers

ClaudeChain supports two trigger modes:

| Mode | Trigger | Project Detection | Base Branch |
|------|---------|-------------------|-------------|
| PR Merge | `pull_request: types: [closed]` with `paths: ['claude-chain/**']` | Auto-detect from changed spec.md files | Validated against config |
| Manual | `workflow_dispatch` | Explicit `project_name` input | Explicit `base_branch` input |

### PR Merge Trigger Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PR Merged to Any Branch                          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Did files in claude-chain/   │
                    │ directory change?            │
                    └──────────────────────────────┘
                         │                    │
                        YES                   NO
                         │                    │
                         ▼                    ▼
          ┌─────────────────────────┐    ┌──────────┐
          │ Detect project(s) from  │    │   SKIP   │
          │ changed spec.md files   │    └──────────┘
          └─────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────┐
          │ Load local config file  │
          │ (claude-chain/{project}/│
          │  configuration.yml)     │
          └─────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────┐
          │ Resolve base_branch:    │
          │ 1. config.baseBranch    │
          │ 2. default_base_branch  │
          │ 3. "main" (fallback)    │
          └─────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────┐
          │ Does resolved base      │
          │ branch == merge target? │
          └─────────────────────────┘
                │               │
               YES              NO
                │               │
                ▼               ▼
     ┌──────────────────┐  ┌──────────────┐
     │ EXECUTE workflow │  │ SKIP (branch │
     │ - Add label      │  │  mismatch)   │
     │ - Find next task │  └──────────────┘
     │ - Create new PR  │
     └──────────────────┘
```

## Project Detection

### detect_projects_from_merge()

Detects projects from changed spec.md files in a merge:

```python
# src/claudechain/services/core/project_service.py
@staticmethod
def detect_projects_from_merge(changed_files: List[str]) -> List[Project]:
    """Detect projects from changed spec.md files in a merge.

    Args:
        changed_files: List of file paths that changed in the merge

    Returns:
        List of Project objects for projects with changed spec.md files.
        Empty list if no spec files were changed.
    """
```

**Pattern matched**: `claude-chain/*/spec.md`

**Examples**:
```python
>>> files = ["claude-chain/my-project/spec.md", "README.md"]
>>> projects = ProjectService.detect_projects_from_merge(files)
>>> [p.name for p in projects]
['my-project']

>>> files = ["claude-chain/project-a/spec.md", "claude-chain/project-b/spec.md"]
>>> projects = ProjectService.detect_projects_from_merge(files)
>>> sorted([p.name for p in projects])
['project-a', 'project-b']
```

### Multiple Project Detection

When multiple projects are detected:
1. All projects are detected and logged
2. First project (alphabetically) is processed
3. Warning issued about additional projects
4. `detected_projects` output provides JSON for advanced matrix workflows

## Configuration Loading

### Local vs API Fetch

| Scenario | Config Source |
|----------|---------------|
| After checkout (PR merge, workflow_dispatch) | Local filesystem |
| Statistics gathering | GitHub API (via `get_file_from_branch()`) |

**Local loading** (post-checkout):
```python
# src/claudechain/infrastructure/repositories/project_repository.py
def load_local_configuration(self, project: Project) -> ProjectConfiguration:
    """Load project configuration from local filesystem."""
    config_path = project.config_path
    if os.path.exists(config_path):
        with open(config_path) as f:
            return ProjectConfiguration.from_yaml_string(project, f.read())
    return ProjectConfiguration.default(project)
```

## Base Branch Validation

### Resolution Order

Base branch is resolved in this order:
1. Project's `configuration.yml` → `baseBranch` field
2. Workflow's `default_base_branch` input
3. Hardcoded fallback: `"main"`

### Validation Behavior

| Event Type | Mismatch Behavior |
|------------|-------------------|
| PR merge | SKIP silently (PR merged to different branch) |
| workflow_dispatch | ERROR (user explicitly chose wrong branch) |

**PR merge skip message**:
```
Skipping project 'my-project': expected base branch 'develop' but PR merged into 'main'
```

**workflow_dispatch error message**:
```
Error: Base branch mismatch for project 'my-project': config expects 'develop' but workflow was triggered on 'main'
```

### Configuration Example

```yaml
# claude-chain/my-project/configuration.yml
baseBranch: develop  # PRs must target 'develop'
assignee: alice
```

## Label Management

### Automatic Labeling

When ClaudeChain executes successfully:
1. The merged PR receives the `claudechain` label
2. The newly created task PR receives the `claudechain` label

This enables:
- Statistics queries (find all ClaudeChain-related PRs)
- Visual indicator of processed PRs
- Discovery of projects for multi-project statistics

### Label vs Changed-Files Triggering

| Initial Trigger | Subsequent Triggers |
|-----------------|---------------------|
| Changed files detection (no label needed) | Changed files detection (label present) |

Labels are **not required** for triggering. They're added after execution for tracking purposes.

## Key Files

| File | Purpose |
|------|---------|
| `src/claudechain/services/core/project_service.py` | `detect_projects_from_merge()` |
| `src/claudechain/infrastructure/repositories/project_repository.py` | `load_local_configuration()` |
| `src/claudechain/cli/commands/prepare.py` | Base branch validation |
| `src/claudechain/cli/commands/parse_event.py` | Changed files detection |
| `src/claudechain/domain/github_event.py` | `should_skip()` with label bypass |
| `.github/workflows/claudechain.yml` | Workflow trigger configuration |

## Testing

### Unit Tests

```python
def test_detect_projects_from_merge_single_project():
    files = ["claude-chain/auth/spec.md", "README.md"]
    projects = ProjectService.detect_projects_from_merge(files)
    assert len(projects) == 1
    assert projects[0].name == "auth"

def test_detect_projects_from_merge_multiple_projects():
    files = ["claude-chain/a/spec.md", "claude-chain/b/spec.md"]
    projects = ProjectService.detect_projects_from_merge(files)
    assert len(projects) == 2
    assert sorted([p.name for p in projects]) == ["a", "b"]

def test_base_branch_validation_mismatch():
    # Config expects 'develop', PR merged to 'main'
    # Should skip for PR merge events
    ...
```

### Integration Tests

- PR merge with changed spec.md → project detection → base branch validation → execution
- workflow_dispatch with project + base_branch inputs
- Skip cases: base branch mismatch, no spec changes
