# Hash-Based Task Identification

## Background

ClaudeChain uses content-based hashing to identify tasks in spec.md files, replacing the previous positional index system. This approach provides stable task identifiers that remain consistent even when tasks are reordered, inserted, or deleted.

## Problem Solved

**Previous approach** (positional indices):
- Tasks identified by position: task 1, task 2, task 3
- Indices embedded in branch names: `claude-chain-<project>-3`
- Fragile: inserting, deleting, or reordering tasks broke PR/task mapping

**Example of the problem**:
```markdown
<!-- Original spec.md -->
- [ ] Task at position 1
- [ ] Task at position 2  ← PR created: claude-chain-myproject-2
- [ ] Task at position 3

<!-- Someone inserts a new task -->
- [ ] Task at position 1
- [ ] NEW TASK at position 2  ← Inserted!
- [ ] Task at position 3  ← Was position 2, now shifted (PR broken!)
```

## Architecture

### Hash Function

**Algorithm**: SHA-256 truncated to 8 characters
- Hash of normalized task description (whitespace stripped and collapsed)
- 8 hex characters provide ~4 billion combinations (sufficient for task lists)
- Example: `generate_task_hash("Add user authentication")` → `"39b1209d"`

**Implementation**:
```python
# src/claudechain/domain/spec_content.py
def generate_task_hash(description: str) -> str:
    """Generate stable hash from task description."""
    normalized = " ".join(description.split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:8]
```

### Branch Naming Convention

**New format**: `claude-chain-<project>-<task-hash>`
- Example: `claude-chain-auth-refactor-a3f2b891`
- Task hash provides stable identifier regardless of task position

**Format Detection**:
- Old format: `claude-chain-project-3` (all digits → index)
- New format: `claude-chain-project-a3f2b891` (8 hex chars → hash)

### Domain Model

**SpecTask** includes task_hash field:
```python
@dataclass
class SpecTask:
    description: str
    completed: bool
    task_hash: str  # Auto-generated from description
```

- Hash computed automatically during parsing via `SpecTask.from_markdown_line()`
- Stored alongside description for easy access

### Task Finding Logic

**Dual-mode support** (hash and index):
```python
def get_next_available_task(
    self,
    skip_indices: Set[int] = None,
    skip_hashes: Set[str] = None
) -> Optional[Tuple[int, str, str]]:
    """Find next uncompleted task, skipping specified indices and hashes."""
    # Returns: (task_index, task_description, task_hash)
```

Tasks are skipped if they match either:
- `skip_indices` (legacy index-based PRs)
- `skip_hashes` (new hash-based PRs)

### Orphaned PR Detection

**Orphaned PRs** occur when:
- Task description changes while PR is open
- Task is deleted from spec.md
- Task hash no longer matches any current task

**Detection logic**:
```python
def detect_orphaned_prs(project: str) -> List[GitHubPullRequest]:
    """Find PRs whose task hash no longer matches current spec.md."""
    # Compare PR identifiers against current spec task hashes
    # Returns list of orphaned PRs
```

**User guidance**:
- Console warnings show orphaned PRs with PR numbers and links
- GitHub Actions step summary includes clickable PR links
- Clear resolution steps: close orphaned PRs, system will create new ones

## Benefits

1. **Task reordering**: Tasks can be freely reordered without breaking PR mappings
2. **Task insertion**: New tasks can be inserted anywhere without affecting existing PRs
3. **Task deletion**: Deleting tasks is safe (orphaned PRs are detected)
4. **Self-healing**: Closing orphaned PRs triggers new PRs with correct task hashes
5. **No manual ID management**: Hashes computed automatically from task descriptions

## Trade-offs

1. **Task hashes not human-readable**: Branch names include project for context
2. **Changing task description invalidates PRs**: User must close and restart
3. **Orphaned PR handling**: System detects but user must manually close
4. **Backward compatibility**: Dual-mode support during transition period

## Migration from Index-Based System

**Backward compatibility**:
- System supports both old (index) and new (hash) formats
- Branch name parsing auto-detects format
- Deprecation warnings logged when index-based PRs detected
- 6-month transition period before index support removal

**Migration helper command**:
```bash
python -m claudechain migrate-to-hashes --project my-refactor
```

Provides:
- Categorizes open PRs by format (index vs hash)
- Lists PRs needing migration with clickable links
- Guidance on migration steps

## Key Design Principles

1. **Spec.md as single source of truth**: No modification of spec.md required
2. **On-the-fly computation**: Hashes computed during parsing, not stored in spec.md
3. **Whitespace normalization**: Ensures stable hashes regardless of formatting
4. **Graceful degradation**: System continues working with orphaned PRs present
5. **Clear user guidance**: Warnings include actionable resolution steps

## Key Files

| File | Purpose |
|------|---------|
| `src/claudechain/domain/spec_content.py` | Hash generation and SpecTask model |
| `src/claudechain/services/core/task_service.py` | Task finding with hash-based skip lists |
| `src/claudechain/services/core/pr_service.py` | Branch name formatting and parsing |
| `src/claudechain/domain/github_models.py` | GitHubPullRequest with task_hash property |
| `src/claudechain/cli/commands/prepare.py` | Orphaned PR detection and warnings |
| `tests/unit/services/test_task_hashing.py` | Comprehensive hash-based task tests |
