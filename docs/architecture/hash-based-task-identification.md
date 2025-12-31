# Hash-Based Task Identification

## Overview

ClaudeStep uses a **hash-based task identification** system where tasks are identified by content hash rather than position in the spec file. This enables flexible task management without breaking PR tracking.

## Why Hash-Based Identification?

**Benefits**:
1. **Flexible Task Management** - Insert, delete, or reorder tasks without breaking PR tracking
2. **No Manual ID Management** - Hashes generated automatically from task descriptions
3. **Self-Healing** - Orphaned PRs detected automatically, new PRs created when old ones closed
4. **Stable Identifiers** - Task hash remains constant as long as description unchanged
5. **Collision Resistant** - SHA-256 provides ~4 billion combinations (sufficient for task lists)

**Trade-offs**:
- Task hashes are not human-readable (but branch names include project for context)
- Changing task description invalidates existing PRs (user must close and restart)
- Need to handle orphaned PRs when descriptions change

## Hash Algorithm

**Implementation** (`src/claudestep/domain/spec_content.py`):
```python
def generate_task_hash(description: str) -> str:
    """Generate stable 8-character hash from task description"""
    # Normalize whitespace (strip and collapse)
    normalized = " ".join(description.strip().split())

    # SHA-256 hash
    hash_object = hashlib.sha256(normalized.encode('utf-8'))

    # Truncate to 8 hex characters (32 bits)
    return hash_object.hexdigest()[:8]
```

**Examples**:
- `generate_task_hash("Add user authentication")` → `"39b1209d"`
- `generate_task_hash("  Add user   authentication  ")` → `"39b1209d"` (whitespace normalized)
- `generate_task_hash("Add user authorization")` → `"f7c4d3e2"` (different description = different hash)

## Branch Naming Convention

**Format**:
```
claude-step-{project}-{task-hash}
```

**Examples**:
- `claude-step-auth-refactor-39b1209d`
- `claude-step-api-cleanup-f7c4d3e2`

## Branch Name Parsing

**Format Detection** (`src/claudestep/services/core/pr_service.py`):
```python
def parse_branch_name(branch_name: str) -> tuple[str, str]:
    """Parse branch name to extract project and task hash"""
    # Returns: (project, task_hash)

    # Extract identifier from: claude-step-{project}-{identifier}
    parts = branch_name.split('-')
    identifier = parts[-1]

    # Validate hash format
    if len(identifier) == 8 and all(c in '0123456789abcdef' for c in identifier):
        project = '-'.join(parts[2:-1])  # Everything between 'claude-step-' and hash
        return (project, identifier)
    else:
        raise ValueError(f"Invalid branch name format: {branch_name}")
```

## Orphaned PR Detection

**What are Orphaned PRs?**

Orphaned PRs are pull requests whose task description has changed or been removed from spec.md:

**Example Scenario**:
```markdown
<!-- Original spec.md -->
- [ ] Add user authentication  ← PR created with hash 39b1209d

<!-- User modifies task description -->
- [ ] Add OAuth authentication  ← Hash changes to a8f3c2d1

<!-- Now PR with hash 39b1209d is "orphaned" -->
```

**Detection** (`src/claudestep/services/core/task_service.py`):
```python
def detect_orphaned_prs(self, spec_content: str, project: str) -> List[GitHubPullRequest]:
    """Find PRs whose task hash no longer matches any task in spec"""
    # Get all current task hashes from spec
    valid_hashes = {task.task_hash for task in parse_spec(spec_content)}

    # Get all open PRs for project
    open_prs = self.pr_service.get_open_prs_for_project(project)

    # Find PRs with task_hash not in valid_hashes
    orphaned = [pr for pr in open_prs if pr.task_hash not in valid_hashes]

    return orphaned
```

**User Guidance** (shown in console and GitHub Actions summary):
```
⚠️  Warning: Found 2 orphaned PR(s):
  - PR #123 (claude-step-auth-39b1209d) - task hash 39b1209d no longer matches any task
  - PR #125 (claude-step-auth-f7c4d3e2) - task hash f7c4d3e2 no longer matches any task

To resolve:
  1. Review these PRs and verify if they should be closed
  2. Close any PRs for modified/removed tasks
  3. ClaudeStep will automatically create new PRs for current tasks
```

## Related Files

**Core Implementation**:
- `src/claudestep/domain/spec_content.py` - Hash generation and task parsing
- `src/claudestep/services/core/task_service.py` - Task finding with hash-based identification
- `src/claudestep/services/core/pr_service.py` - Branch name parsing and formatting

**CLI Integration**:
- `src/claudestep/cli/commands/prepare.py` - Orphaned PR detection and warnings
- `src/claudestep/cli/commands/discover_ready.py` - Hash-based task filtering

**Tests**:
- `tests/unit/domain/test_spec_content.py` - Hash generation and task parsing tests
- `tests/unit/services/core/test_pr_service.py` - Branch name parsing tests
- `tests/unit/services/core/test_task_service.py` - Task finding with hash-based identification
