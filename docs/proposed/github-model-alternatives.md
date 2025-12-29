# GitHub Metadata Model - Alternative Designs

## Background

The current data model for ClaudeStep metadata storage feels awkward and may not be the most intuitive way to represent the relationships between projects, steps, PRs, and AI operations.

### Current Model Issues

The current implementation uses:
```
Project
  └── Step
      ├── PR info (branch_name, reviewer, pr_number, pr_state, created_at)
      └── ai_tasks: List[AITask]
          └── workflow_run_id, type, model, cost, tokens, duration
```

**Potential Issues:**
1. **Mixed responsibilities**: Step combines both spec.md metadata AND PR execution details
2. **Unclear ownership**: Is a Step a "task from spec.md" or a "PR"? It's trying to be both
3. **Optional fields**: Most Step fields are optional, making the model hard to reason about
4. **Not-yet-started steps**: Minimal steps (just index + description) feel like a special case
5. **Naming confusion**: "Step" is better than "Task" but still unclear what it represents

### Goals

1. **Clear separation of concerns**: Separate spec.md structure from PR execution tracking
2. **Explicit relationships**: Make relationships between entities obvious
3. **Minimal special cases**: Avoid "not started" vs "started" being fundamentally different
4. **Easy to reason about**: Model should match mental model of how ClaudeStep works
5. **Visual clarity**: Diagrams should make relationships immediately obvious

## Phase 1: Document Current Model ✅

**Tasks:**
- Create detailed diagram of current `Project → Step → AITask` structure
- Document all fields and their purposes
- Show example JSON for different states (not started, in progress, merged)
- Identify pain points and awkward aspects
- Document what queries we need to support (capacity checking, statistics, progress)

**Expected Outcome:**
- Clear understanding of current model's strengths and weaknesses
- Visual representation showing current structure
- List of specific issues to address in alternatives

### Current Model Structure

```
Project
├── schema_version: str                  # Metadata format version (e.g., "1.0")
├── project: str                         # Project name/identifier
├── last_updated: datetime               # Last modification timestamp
└── steps: List[Step]                   # All steps from spec.md
    └── Step
        ├── step_index: int              # Required: Position in spec.md (1-based)
        ├── step_description: str        # Required: Task description from spec.md
        ├── branch_name: Optional[str]   # PR branch (None if not started)
        ├── reviewer: Optional[str]      # Assigned reviewer (None if not started)
        ├── pr_number: Optional[int]     # GitHub PR number (None if not started)
        ├── pr_state: Optional[str]      # "open", "merged", "closed" (None if not started)
        ├── created_at: Optional[datetime] # PR creation timestamp (None if not started)
        └── ai_tasks: List[AITask]       # All AI operations for this PR
            └── AITask
                ├── type: str                # "PRCreation", "PRRefinement", "PRSummary"
                ├── model: str              # AI model used (e.g., "claude-sonnet-4")
                ├── cost_usd: float         # Cost for this operation
                ├── created_at: datetime    # When this AI task was executed
                ├── workflow_run_id: int    # GitHub Actions run that executed this
                ├── tokens_input: int       # Input tokens (default: 0)
                ├── tokens_output: int      # Output tokens (default: 0)
                └── duration_seconds: float # Execution time (default: 0.0)
```

### Field Purposes and Semantics

#### Project Fields
- **schema_version**: Enables future schema evolution and migration
- **project**: Identifies which spec.md file this metadata tracks
- **last_updated**: Cache invalidation and audit trail
- **steps**: Contains ALL steps from spec.md, both started and not-yet-started

#### Step Fields
- **step_index**: Links to spec.md position (permanent identifier)
- **step_description**: Human-readable task from spec.md
- **branch_name**: Git branch created for the PR
- **reviewer**: Team member assigned to review this PR
- **pr_number**: GitHub PR identifier for linking/querying
- **pr_state**: Tracks PR lifecycle (open → merged/closed)
- **created_at**: Timestamp for progress tracking and statistics
- **ai_tasks**: Complete history of all AI operations on this step

#### AITask Fields
- **type**: Distinguishes different AI operation purposes
- **model**: Tracks which AI model was used (cost/capability tracking)
- **cost_usd**: Per-operation cost tracking
- **created_at**: Timeline reconstruction
- **workflow_run_id**: Links to GitHub Actions logs for debugging
- **tokens_input/output**: Detailed usage metrics
- **duration_seconds**: Performance tracking

### Example JSON for Different States

#### Not Started Step
```json
{
  "step_index": 3,
  "step_description": "Add email validation to user registration form"
}
```

#### In Progress Step (PR Created)
```json
{
  "step_index": 2,
  "step_description": "Implement OAuth2 authentication flow",
  "branch_name": "claudestep/auth-refactor/step-2",
  "reviewer": "alice",
  "pr_number": 42,
  "pr_state": "open",
  "created_at": "2025-12-29T10:30:00Z",
  "ai_tasks": [
    {
      "type": "PRCreation",
      "model": "claude-sonnet-4",
      "cost_usd": 0.15,
      "created_at": "2025-12-29T10:30:00Z",
      "workflow_run_id": 123456,
      "tokens_input": 5000,
      "tokens_output": 2000,
      "duration_seconds": 45.2
    }
  ]
}
```

#### Merged Step with Refinement
```json
{
  "step_index": 1,
  "step_description": "Set up authentication middleware",
  "branch_name": "claudestep/auth-refactor/step-1",
  "reviewer": "bob",
  "pr_number": 41,
  "pr_state": "merged",
  "created_at": "2025-12-28T14:20:00Z",
  "ai_tasks": [
    {
      "type": "PRCreation",
      "model": "claude-sonnet-4",
      "cost_usd": 0.12,
      "created_at": "2025-12-28T14:20:00Z",
      "workflow_run_id": 123450,
      "tokens_input": 4500,
      "tokens_output": 1800,
      "duration_seconds": 42.1
    },
    {
      "type": "PRRefinement",
      "model": "claude-sonnet-4",
      "cost_usd": 0.08,
      "created_at": "2025-12-28T16:45:00Z",
      "workflow_run_id": 123451,
      "tokens_input": 3000,
      "tokens_output": 1200,
      "duration_seconds": 28.5
    }
  ]
}
```

#### Complete Project Example
```json
{
  "schema_version": "1.0",
  "project": "auth-refactor",
  "last_updated": "2025-12-29T10:30:00Z",
  "steps": [
    {
      "step_index": 1,
      "step_description": "Set up authentication middleware",
      "branch_name": "claudestep/auth-refactor/step-1",
      "reviewer": "bob",
      "pr_number": 41,
      "pr_state": "merged",
      "created_at": "2025-12-28T14:20:00Z",
      "ai_tasks": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-12-28T14:20:00Z",
          "workflow_run_id": 123450,
          "tokens_input": 4500,
          "tokens_output": 1800,
          "duration_seconds": 42.1
        }
      ]
    },
    {
      "step_index": 2,
      "step_description": "Implement OAuth2 authentication flow",
      "branch_name": "claudestep/auth-refactor/step-2",
      "reviewer": "alice",
      "pr_number": 42,
      "pr_state": "open",
      "created_at": "2025-12-29T10:30:00Z",
      "ai_tasks": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-12-29T10:30:00Z",
          "workflow_run_id": 123456,
          "tokens_input": 5000,
          "tokens_output": 2000,
          "duration_seconds": 45.2
        }
      ]
    },
    {
      "step_index": 3,
      "step_description": "Add email validation to user registration form"
    },
    {
      "step_index": 4,
      "step_description": "Implement password reset functionality"
    },
    {
      "step_index": 5,
      "step_description": "Add two-factor authentication support"
    }
  ]
}
```

### Pain Points and Awkward Aspects

#### 1. **Mixed Responsibilities in Step**
The `Step` dataclass tries to represent two distinct concepts:
- A task definition from spec.md (immutable, semantic content)
- A PR execution (mutable, runtime state)

This creates confusion: Is a Step a "plan" or an "execution"?

#### 2. **Optional Field Explosion**
Most Step fields are Optional, creating two distinct "modes":
- **Minimal Step**: Just `step_index` + `step_description` (not started)
- **Full Step**: All fields populated (PR created)

This makes the model hard to reason about:
```python
# Which fields can I safely access?
if step.pr_number:  # Have to check before using
    print(f"PR: {step.pr_number}")
```

#### 3. **Unclear Entity Boundaries**
The model doesn't clearly separate:
- **Spec content** (what needs to be done) vs **Execution state** (what was done)
- **PR metadata** (GitHub state) vs **AI operations** (ClaudeStep internals)

#### 4. **Special Case Handling**
Not-yet-started steps feel like a special case rather than a natural part of the model. Code frequently needs to check `step.is_started()` to determine which fields are valid.

#### 5. **Naming Ambiguity**
"Step" is better than the old "Task" name, but still unclear:
- Is it a "step in the plan" (spec.md)?
- Is it a "step in execution" (PR)?
- It's trying to be both, which creates cognitive overhead

#### 6. **Implicit Relationships**
The relationship between Steps and PRs is implicit (same object). If we ever need to support multiple PR attempts for the same step, the model breaks down.

#### 7. **Denormalized Data**
`step_description` is duplicated from spec.md into metadata storage. If spec.md changes, metadata becomes stale. However, this may be intentional for historical accuracy.

#### 8. **No Direct Status Field**
PR state must be inferred from multiple fields:
- Not started: `pr_number is None`
- In progress: `pr_number is not None and pr_state == "open"`
- Complete: `pr_state == "merged"`

This logic is scattered across the codebase.

### Required Query Patterns

Based on the codebase analysis, the model must efficiently support:

#### 1. **Reviewer Capacity Checking**
```python
# For each reviewer, count open PRs across all projects
# to determine if they have capacity for new assignments
open_prs_by_reviewer = {}
for project in all_projects:
    for step in project.steps:
        if step.pr_state == "open":
            open_prs_by_reviewer[step.reviewer].append(...)
```

#### 2. **Project Statistics**
```python
# Calculate completion percentage, costs, progress
total_steps = len(project.steps)
completed = sum(1 for s in project.steps if s.pr_state == "merged")
in_progress = sum(1 for s in project.steps if s.pr_state == "open")
pending = sum(1 for s in project.steps if not s.is_started())
total_cost = sum(step.get_total_cost() for step in project.steps)
```

#### 3. **Next Step Selection**
```python
# Find the next pending step to work on
next_step = next(s for s in project.steps if not s.is_started())
```

#### 4. **Team Leaderboard**
```python
# Aggregate PR counts by team member across all projects
for project in all_projects:
    for step in project.steps:
        if step.pr_state == "merged":
            team_stats[step.reviewer].merged_count += 1
```

#### 5. **Cost Analysis**
```python
# Sum costs by project, by model, by time period
for step in project.steps:
    for ai_task in step.ai_tasks:
        cost_by_model[ai_task.model] += ai_task.cost_usd
```

#### 6. **Progress Tracking**
```python
# Determine if project is complete, blocked, or active
all_merged = all(s.pr_state == "merged" for s in project.steps if s.is_started())
has_open = any(s.pr_state == "open" for s in project.steps)
```

### Model Strengths

Despite the pain points, the current model has several strengths:

#### 1. **Complete Historical Record**
Every step from spec.md is preserved, including not-yet-started ones. This provides a complete view of the project plan.

#### 2. **Simple Hierarchy**
The three-level hierarchy (Project → Step → AITask) is straightforward and easy to understand at a high level.

#### 3. **Self-Contained Steps**
Each Step contains all information about its PR and AI operations. No need to join across multiple data structures.

#### 4. **Minimal JSON for Pending Steps**
Not-yet-started steps serialize to just two fields, keeping the JSON compact.

#### 5. **Backward Compatibility Support**
The model gracefully handles migration from old field names (task_index → step_index).

### Conclusion

The current model works but has conceptual awkwardness stemming from Steps trying to be both "plan definition" and "execution record". The optional field pattern creates two distinct Step "modes" that require careful handling throughout the codebase.

Alternative models should explore:
1. Separating spec definition from execution tracking
2. Making entity boundaries more explicit
3. Reducing optional fields and special cases
4. Clarifying the relationship between tasks and PRs

**Technical Notes:**
- Current implementation: `src/claudestep/domain/models.py:502-809`
- Uses Python dataclasses with `from_dict`/`to_dict` for JSON serialization
- Backward compatibility handled via field name aliasing
- All datetime fields use ISO 8601 format in JSON

## Phase 2: Alternative Model 1 - Separate Spec and Execution ✅

**Concept:**
```
Project
  ├── spec: ProjectSpec
  │   └── tasks: List[TaskDefinition]
  │       └── index, description
  └── executions: List[Execution]
      └── task_index, pr_number, branch, reviewer, state, created_at
          └── ai_operations: List[AIOperation]
              └── workflow_run_id, type, model, cost, tokens
```

**Key Ideas:**
- **ProjectSpec**: Immutable definition from spec.md (what needs to be done)
- **TaskDefinition**: Just index + description from spec.md
- **Execution**: One attempt to implement a task (may fail, may be refined)
- **AIOperation**: Individual AI work (replaces AITask)

### Detailed Structure Diagram

```
Project
├── schema_version: str                   # Metadata format version (e.g., "1.0")
├── project: str                          # Project name/identifier
├── last_updated: datetime                # Last modification timestamp
├── spec: ProjectSpec                     # IMMUTABLE: Definition from spec.md
│   └── tasks: List[TaskDefinition]       # All tasks defined in spec.md
│       └── TaskDefinition
│           ├── index: int                # Position in spec.md (1-based)
│           └── description: str          # Task description from spec.md
└── executions: List[Execution]           # MUTABLE: PR execution history
    └── Execution
        ├── execution_id: str             # Unique identifier for this execution attempt
        ├── task_index: int               # References TaskDefinition.index
        ├── pr_number: int                # GitHub PR number
        ├── branch_name: str              # Git branch for this execution
        ├── reviewer: str                 # Assigned reviewer username
        ├── pr_state: str                 # "open", "merged", "closed"
        ├── created_at: datetime          # When execution started
        └── ai_operations: List[AIOperation]  # All AI work for this execution
            └── AIOperation
                ├── operation_id: str         # Unique identifier for this operation
                ├── type: str                 # "PRCreation", "PRRefinement", "PRSummary"
                ├── model: str                # AI model used (e.g., "claude-sonnet-4")
                ├── cost_usd: float           # Cost for this operation
                ├── created_at: datetime      # When this operation was executed
                ├── workflow_run_id: int      # GitHub Actions run that executed this
                ├── tokens_input: int         # Input tokens (default: 0)
                ├── tokens_output: int        # Output tokens (default: 0)
                └── duration_seconds: float   # Execution time (default: 0.0)
```

### Key Relationships

1. **Spec → Execution**: One-to-many relationship via `task_index`
   - One `TaskDefinition` can have zero or more `Execution` records
   - Zero executions = task not yet started
   - One execution = normal case (single PR attempt)
   - Multiple executions = task was attempted multiple times (e.g., PR closed and retried)

2. **Execution → AIOperation**: One-to-many relationship
   - Each `Execution` has one or more `AIOperation` records
   - First operation is typically "PRCreation"
   - Additional operations are "PRRefinement" or other modifications
   - All operations belong to the same PR/execution

3. **Task Identification**: Tasks are identified by `index` (permanent) rather than PR state
   - Spec defines what needs to be done (static)
   - Executions track what was done (dynamic)

### Example JSON: Auth Refactor Project

This example shows a project with 5 tasks:
- Task 1: Merged (one execution with one operation)
- Task 2: In progress (one execution with one operation)
- Task 3: Not started (no executions)
- Task 4: Not started (no executions)
- Task 5: Not started (no executions)

```json
{
  "schema_version": "1.0",
  "project": "auth-refactor",
  "last_updated": "2025-12-29T10:30:00Z",
  "spec": {
    "tasks": [
      {
        "index": 1,
        "description": "Set up authentication middleware"
      },
      {
        "index": 2,
        "description": "Implement OAuth2 authentication flow"
      },
      {
        "index": 3,
        "description": "Add email validation to user registration form"
      },
      {
        "index": 4,
        "description": "Implement password reset functionality"
      },
      {
        "index": 5,
        "description": "Add two-factor authentication support"
      }
    ]
  },
  "executions": [
    {
      "execution_id": "exec-001-task-1",
      "task_index": 1,
      "pr_number": 41,
      "branch_name": "claudestep/auth-refactor/step-1",
      "reviewer": "bob",
      "pr_state": "merged",
      "created_at": "2025-12-28T14:20:00Z",
      "ai_operations": [
        {
          "operation_id": "op-001",
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-12-28T14:20:00Z",
          "workflow_run_id": 123450,
          "tokens_input": 4500,
          "tokens_output": 1800,
          "duration_seconds": 42.1
        }
      ]
    },
    {
      "execution_id": "exec-002-task-2",
      "task_index": 2,
      "pr_number": 42,
      "branch_name": "claudestep/auth-refactor/step-2",
      "reviewer": "alice",
      "pr_state": "open",
      "created_at": "2025-12-29T10:30:00Z",
      "ai_operations": [
        {
          "operation_id": "op-002",
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-12-29T10:30:00Z",
          "workflow_run_id": 123456,
          "tokens_input": 5000,
          "tokens_output": 2000,
          "duration_seconds": 45.2
        }
      ]
    }
  ]
}
```

### Example: Task with Multiple Executions (Failed Then Succeeded)

This shows Task 1 with two execution attempts: first was closed without merging, second succeeded.

```json
{
  "schema_version": "1.0",
  "project": "auth-refactor",
  "last_updated": "2025-12-29T16:00:00Z",
  "spec": {
    "tasks": [
      {
        "index": 1,
        "description": "Set up authentication middleware"
      }
    ]
  },
  "executions": [
    {
      "execution_id": "exec-001-task-1-attempt-1",
      "task_index": 1,
      "pr_number": 40,
      "branch_name": "claudestep/auth-refactor/step-1-attempt-1",
      "reviewer": "bob",
      "pr_state": "closed",
      "created_at": "2025-12-27T09:00:00Z",
      "ai_operations": [
        {
          "operation_id": "op-001",
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-12-27T09:00:00Z",
          "workflow_run_id": 123440,
          "tokens_input": 4500,
          "tokens_output": 1800,
          "duration_seconds": 42.1
        }
      ]
    },
    {
      "execution_id": "exec-001-task-1-attempt-2",
      "task_index": 1,
      "pr_number": 41,
      "branch_name": "claudestep/auth-refactor/step-1",
      "reviewer": "bob",
      "pr_state": "merged",
      "created_at": "2025-12-28T14:20:00Z",
      "ai_operations": [
        {
          "operation_id": "op-005",
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-12-28T14:20:00Z",
          "workflow_run_id": 123450,
          "tokens_input": 4500,
          "tokens_output": 1800,
          "duration_seconds": 42.1
        }
      ]
    }
  ]
}
```

### Example: Execution with Multiple AI Operations (Refinements)

This shows an execution with initial creation plus two refinement operations.

```json
{
  "execution_id": "exec-001-task-1",
  "task_index": 1,
  "pr_number": 41,
  "branch_name": "claudestep/auth-refactor/step-1",
  "reviewer": "bob",
  "pr_state": "merged",
  "created_at": "2025-12-28T14:20:00Z",
  "ai_operations": [
    {
      "operation_id": "op-001",
      "type": "PRCreation",
      "model": "claude-sonnet-4",
      "cost_usd": 0.12,
      "created_at": "2025-12-28T14:20:00Z",
      "workflow_run_id": 123450,
      "tokens_input": 4500,
      "tokens_output": 1800,
      "duration_seconds": 42.1
    },
    {
      "operation_id": "op-002",
      "type": "PRRefinement",
      "model": "claude-sonnet-4",
      "cost_usd": 0.08,
      "created_at": "2025-12-28T16:45:00Z",
      "workflow_run_id": 123451,
      "tokens_input": 3000,
      "tokens_output": 1200,
      "duration_seconds": 28.5
    },
    {
      "operation_id": "op-003",
      "type": "PRRefinement",
      "model": "claude-sonnet-4",
      "cost_usd": 0.06,
      "created_at": "2025-12-28T18:15:00Z",
      "workflow_run_id": 123452,
      "tokens_input": 2500,
      "tokens_output": 1000,
      "duration_seconds": 22.3
    }
  ]
}
```

### How This Model Handles Different Scenarios

#### 1. Not-Yet-Started Tasks

**Current Model:**
```json
{
  "step_index": 3,
  "step_description": "Add email validation"
}
```

**Alternative Model 1:**
```json
// Task appears only in spec
{
  "spec": {
    "tasks": [
      {"index": 3, "description": "Add email validation"}
    ]
  },
  "executions": []  // No executions yet
}
```

**Key Difference:**
- Current: Minimal Step object with optional fields
- Alternative 1: Task definition exists in spec, absence from executions indicates "not started"
- **Benefit:** No special case handling - a task either has executions or it doesn't

#### 2. Multiple Attempts at Same Task

**Current Model:**
Not directly supported. Would need to either:
- Overwrite the Step record (losing history)
- Add array of attempts (major schema change)

**Alternative Model 1:**
```json
{
  "spec": {
    "tasks": [{"index": 1, "description": "Set up auth middleware"}]
  },
  "executions": [
    {
      "execution_id": "exec-001-attempt-1",
      "task_index": 1,
      "pr_number": 40,
      "pr_state": "closed",
      "created_at": "2025-12-27T09:00:00Z",
      "ai_operations": [...]
    },
    {
      "execution_id": "exec-001-attempt-2",
      "task_index": 1,
      "pr_number": 41,
      "pr_state": "merged",
      "created_at": "2025-12-28T14:20:00Z",
      "ai_operations": [...]
    }
  ]
}
```

**Benefit:** Multiple executions with same `task_index` naturally represent retry attempts. Complete history preserved.

#### 3. PR Refinements

**Current Model:**
```json
{
  "step_index": 1,
  "step_description": "Set up auth middleware",
  "pr_number": 41,
  "ai_tasks": [
    {"type": "PRCreation", "cost_usd": 0.12, ...},
    {"type": "PRRefinement", "cost_usd": 0.08, ...}
  ]
}
```

**Alternative Model 1:**
```json
{
  "executions": [
    {
      "execution_id": "exec-001",
      "task_index": 1,
      "pr_number": 41,
      "ai_operations": [
        {"type": "PRCreation", "cost_usd": 0.12, ...},
        {"type": "PRRefinement", "cost_usd": 0.08, ...}
      ]
    }
  ]
}
```

**Similarity:** Both models handle this similarly with an array of operations/tasks
**Difference:** Alternative 1 makes the execution boundary more explicit

### Pros and Cons vs Current Model

#### Pros ✅

1. **Clear Separation of Concerns**
   - Spec defines "what needs to be done" (immutable)
   - Executions track "what was done" (mutable)
   - No confusion about whether a field represents plan vs execution

2. **Explicit Entity Boundaries**
   - `TaskDefinition` is always lightweight (just index + description)
   - `Execution` is always fully-formed (never has optional PR fields)
   - No "two modes" of the same entity type

3. **Natural Support for Retries**
   - Multiple executions for same `task_index` naturally represent retry attempts
   - Complete history of all attempts preserved
   - Current model would require major restructuring to support this

4. **Reduced Optional Fields**
   - `TaskDefinition` has no optional fields
   - `Execution` has no optional fields (every execution is a PR)
   - Easier to reason about: "Does this task have executions? If yes, check their states"

5. **Better Mental Model Alignment**
   - Users think: "Here's my plan (spec.md)" + "Here's what happened (PRs)"
   - Model directly reflects this mental model
   - Current model conflates these concepts into "Step"

6. **Clearer Queries**
   ```python
   # Find not-yet-started tasks
   started_indices = {e.task_index for e in project.executions}
   not_started = [t for t in project.spec.tasks if t.index not in started_indices]

   # Find task with multiple attempts
   from collections import Counter
   attempts = Counter(e.task_index for e in project.executions)
   retried_tasks = [idx for idx, count in attempts.items() if count > 1]
   ```

7. **Spec.md as Source of Truth**
   - Spec explicitly stored, making it clear that task descriptions come from spec.md
   - If spec.md changes, we can compare against stored spec to detect drift
   - Current model's implicit spec makes this harder to reason about

#### Cons ❌

1. **More Complex Structure**
   - Three-level hierarchy (Project → Spec/Executions → Tasks/Operations) vs two-level
   - Requires understanding the Spec vs Execution distinction
   - More conceptual overhead for developers

2. **Increased JSON Verbosity**
   - Task descriptions duplicated in both spec and execution references
   - Not-yet-started tasks still appear in spec (current model is minimal)
   - Actually, this is debatable - current model also stores all tasks

3. **More Complex Queries for Common Cases**
   ```python
   # Current: Get task status
   if step.pr_state == "merged": ...

   # Alternative 1: Get task status (requires joining spec + executions)
   task_executions = [e for e in project.executions if e.task_index == task.index]
   if task_executions:
       latest = max(task_executions, key=lambda e: e.created_at)
       if latest.pr_state == "merged": ...
   ```

4. **Data Consistency Risks**
   - Must ensure `task_index` in executions always references valid spec task
   - Must ensure execution IDs are unique
   - More relationships to validate

5. **Migration Effort**
   - Existing metadata needs transformation from Step → Spec + Execution
   - All code that reads/writes metadata needs updates
   - Testing burden to ensure migration correctness

6. **Not Addressing All Current Pain Points**
   - Still has denormalized data (task descriptions in spec)
   - Still needs to check PR state for status
   - Doesn't add explicit status enum (pending/in_progress/completed)

#### Neutral Observations 🤔

1. **Spec Mutability**
   - Spec is labeled "immutable" but must be updated when spec.md changes
   - Question: Should spec be regenerated from spec.md on every run? Or cached?
   - If regenerated, storing it seems redundant
   - If cached, what happens when spec.md changes?

2. **Execution ID Purpose**
   - What's the use case for `execution_id`?
   - PRs already have unique `pr_number`
   - Seems like over-engineering unless we need to support PRs outside GitHub

3. **Task Index Fragility**
   - Both models use task index as permanent identifier
   - Both break if tasks are reordered in spec.md
   - This isn't a Pro/Con difference, just a shared limitation

### Analysis Summary

**Does this feel more natural?**

**Yes, conceptually:** The separation of "plan" (spec) and "execution" (PRs) matches how users think about ClaudeStep. It's intellectually cleaner.

**No, pragmatically:** For the current ClaudeStep use case (single execution per task, no retries), the added complexity doesn't provide much benefit. The current model's main pain point (optional fields) could be addressed with simpler changes (like adding explicit status enums).

**Sweet spot:** This model would be valuable if ClaudeStep plans to support:
- Retry logic (PR closed, try again)
- Multiple implementation strategies (try approach A, if it fails try approach B)
- Execution history tracking (show all attempts over time)

**Recommendation for ClaudeStep:** Unless retry/multi-attempt support is planned, this model may be over-engineered. Alternative 3 (Hybrid) might offer a better balance.

**Technical Notes:**
- Implementation would require new dataclasses: `ProjectSpec`, `TaskDefinition`, `Execution`, `AIOperation`
- Migration script needed to transform existing `Step` records into `spec.tasks` + `executions`
- Query patterns would need adjustment to join spec and executions
- Backward compatibility would be challenging due to structural differences

## Phase 3: Alternative Model 2 - PR-Centric ✅

**Concept:**
```
Project
  ├── total_tasks: int (from spec.md)
  └── pull_requests: List[PullRequest]
      ├── task_index, task_description (copied from spec.md)
      ├── pr_number, branch, reviewer, state, created_at
      └── ai_operations: List[AIOperation]
          └── workflow_run_id, type, model, cost, tokens
```

**Key Ideas:**
- **PR is the primary entity**: Everything centers around PRs
- **No separate "not started" representation**: PRs that don't exist yet simply aren't in the list
- **Spec.md info copied into PR**: Task index/description duplicated (denormalized)
- **Progress calculated**: Compare PR count to total_tasks

### Detailed Structure Diagram

```
Project
├── schema_version: str                   # Metadata format version (e.g., "1.0")
├── project: str                          # Project name/identifier
├── last_updated: datetime                # Last modification timestamp
├── total_tasks: int                      # Total number of tasks in spec.md
└── pull_requests: List[PullRequest]      # All PRs (started tasks only)
    └── PullRequest
        ├── task_index: int               # Position in spec.md (1-based)
        ├── task_description: str         # Task description from spec.md (denormalized)
        ├── pr_number: int                # GitHub PR number
        ├── branch_name: str              # Git branch for this PR
        ├── reviewer: str                 # Assigned reviewer username
        ├── pr_state: str                 # "open", "merged", "closed"
        ├── created_at: datetime          # When PR was created
        └── ai_operations: List[AIOperation]  # All AI work for this PR
            └── AIOperation
                ├── type: str                 # "PRCreation", "PRRefinement", "PRSummary"
                ├── model: str                # AI model used (e.g., "claude-sonnet-4")
                ├── cost_usd: float           # Cost for this operation
                ├── created_at: datetime      # When this operation was executed
                ├── workflow_run_id: int      # GitHub Actions run that executed this
                ├── tokens_input: int         # Input tokens (default: 0)
                ├── tokens_output: int        # Output tokens (default: 0)
                └── duration_seconds: float   # Execution time (default: 0.0)
```

### Key Characteristics

1. **PR as Primary Entity**: The model is organized around PRs. If a PR doesn't exist, the task is simply not in the list.

2. **Denormalized Data**: Task index and description are copied from spec.md into each PullRequest record. This means:
   - No need to join with spec.md to get task info
   - Historical record preserved even if spec.md changes
   - Some data duplication

3. **Progress Tracking**: Progress is calculated by comparing the count of PRs to `total_tasks`:
   - Pending tasks = `total_tasks - len(pull_requests)`
   - Which tasks are pending requires tracking completed indices

4. **Minimal Schema**: Simplest possible structure - just project metadata + flat list of PRs

### Example JSON: Auth Refactor Project

This example shows the same 5-task project as previous alternatives:
- Task 1: Merged
- Task 2: In progress
- Tasks 3-5: Not started (not in PR list)

```json
{
  "schema_version": "1.0",
  "project": "auth-refactor",
  "last_updated": "2025-12-29T10:30:00Z",
  "total_tasks": 5,
  "pull_requests": [
    {
      "task_index": 1,
      "task_description": "Set up authentication middleware",
      "pr_number": 41,
      "branch_name": "claudestep/auth-refactor/step-1",
      "reviewer": "bob",
      "pr_state": "merged",
      "created_at": "2025-12-28T14:20:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-12-28T14:20:00Z",
          "workflow_run_id": 123450,
          "tokens_input": 4500,
          "tokens_output": 1800,
          "duration_seconds": 42.1
        }
      ]
    },
    {
      "task_index": 2,
      "task_description": "Implement OAuth2 authentication flow",
      "pr_number": 42,
      "branch_name": "claudestep/auth-refactor/step-2",
      "reviewer": "alice",
      "pr_state": "open",
      "created_at": "2025-12-29T10:30:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-12-29T10:30:00Z",
          "workflow_run_id": 123456,
          "tokens_input": 5000,
          "tokens_output": 2000,
          "duration_seconds": 45.2
        }
      ]
    }
  ]
}
```

**Note:** Tasks 3, 4, and 5 are not represented in the JSON at all - their absence indicates they haven't been started yet.

### Example: PR with Multiple AI Operations (Refinements)

This shows a PR with initial creation plus two refinement operations:

```json
{
  "task_index": 1,
  "task_description": "Set up authentication middleware",
  "pr_number": 41,
  "branch_name": "claudestep/auth-refactor/step-1",
  "reviewer": "bob",
  "pr_state": "merged",
  "created_at": "2025-12-28T14:20:00Z",
  "ai_operations": [
    {
      "type": "PRCreation",
      "model": "claude-sonnet-4",
      "cost_usd": 0.12,
      "created_at": "2025-12-28T14:20:00Z",
      "workflow_run_id": 123450,
      "tokens_input": 4500,
      "tokens_output": 1800,
      "duration_seconds": 42.1
    },
    {
      "type": "PRRefinement",
      "model": "claude-sonnet-4",
      "cost_usd": 0.08,
      "created_at": "2025-12-28T16:45:00Z",
      "workflow_run_id": 123451,
      "tokens_input": 3000,
      "tokens_output": 1200,
      "duration_seconds": 28.5
    },
    {
      "type": "PRRefinement",
      "model": "claude-sonnet-4",
      "cost_usd": 0.06,
      "created_at": "2025-12-28T18:15:00Z",
      "workflow_run_id": 123452,
      "tokens_input": 2500,
      "tokens_output": 1000,
      "duration_seconds": 22.3
    }
  ]
}
```

### How This Model Handles Different Scenarios

#### 1. Not-Yet-Started Tasks

**Current Model:**
```json
{
  "step_index": 3,
  "step_description": "Add email validation"
}
```

**Alternative Model 1 (Spec/Exec):**
```json
{
  "spec": {
    "tasks": [
      {"index": 3, "description": "Add email validation"}
    ]
  },
  "executions": []
}
```

**Alternative Model 2 (PR-Centric):**
```json
{
  "total_tasks": 5,
  "pull_requests": []  // Task 3 is simply not in the list
}
```

**Key Difference:**
- **Current Model**: Minimal Step object with optional fields
- **Alternative 1**: Task exists in spec, no executions
- **Alternative 2**: Task doesn't appear at all - must infer from `total_tasks` and missing indices
- **Trade-off**: Most compact JSON but loses explicit task listing

#### 2. Calculating Pending Tasks

```python
# Get count of pending tasks
pending_count = project.total_tasks - len(project.pull_requests)

# Determine which specific tasks are pending (requires tracking)
completed_indices = {pr.task_index for pr in project.pull_requests}
pending_indices = [i for i in range(1, project.total_tasks + 1)
                   if i not in completed_indices]
```

**Issue**: To show *which* tasks are pending, you need to:
1. Know the total task count
2. Collect all task indices from PRs
3. Infer missing indices
4. Go back to spec.md to get task descriptions

This is more complex than current model where all tasks are always present.

#### 3. Progress Statistics

```python
# Project completion percentage
total = project.total_tasks
started = len(project.pull_requests)
completed = sum(1 for pr in project.pull_requests if pr.pr_state == "merged")
in_progress = sum(1 for pr in project.pull_requests if pr.pr_state == "open")
pending = total - started

completion_pct = (completed / total) * 100 if total > 0 else 0
```

**Comparison to Current Model:**
```python
# Current model - all tasks always present
total = len(project.steps)
completed = sum(1 for s in project.steps if s.pr_state == "merged")
in_progress = sum(1 for s in project.steps if s.pr_state == "open")
pending = sum(1 for s in project.steps if not s.is_started())
```

**Key Difference**: Current model is clearer because you can iterate over all steps. PR-Centric requires maintaining `total_tasks` separately.

#### 4. Reviewer Capacity Checking

```python
# Count open PRs per reviewer
open_prs_by_reviewer = {}
for pr in project.pull_requests:
    if pr.pr_state == "open":
        open_prs_by_reviewer.setdefault(pr.reviewer, []).append(pr)
```

**Same as current model** - straightforward iteration.

#### 5. Cost Analysis

```python
# Sum costs by project, model, time period
total_cost = 0
cost_by_model = {}

for pr in project.pull_requests:
    for op in pr.ai_operations:
        total_cost += op.cost_usd
        cost_by_model.setdefault(op.model, 0)
        cost_by_model[op.model] += op.cost_usd
```

**Same as current model** - straightforward nested iteration.

#### 6. Next Step Selection

```python
# Find the next pending task to work on
completed_indices = {pr.task_index for pr in project.pull_requests}

for task_index in range(1, project.total_tasks + 1):
    if task_index not in completed_indices:
        # This is the next pending task
        # But we don't have the description!
        # Must read from spec.md
        next_task_index = task_index
        break
```

**Problem**: Unlike current model where task descriptions are always present, this model requires reading spec.md to get task descriptions for pending tasks.

### Pros and Cons vs Current Model and Alternative 1

#### Pros ✅

1. **Simplest Possible Structure**
   - No optional fields on PullRequest (every PR has all fields)
   - No nested hierarchy beyond Project → PR → Operation
   - Flat list of PRs is easy to understand

2. **Minimal JSON for Early Projects**
   - Project with no started tasks: just `{"total_tasks": 5, "pull_requests": []}`
   - Most compact representation for projects with few PRs

3. **PR-Centric Mental Model**
   - Aligns with "ClaudeStep creates PRs" framing
   - Natural for developers who think in terms of PRs
   - No confusion about "what is a Step?"

4. **No Special Cases**
   - A PR either exists or it doesn't
   - No "minimal step" vs "full step" distinction
   - All PRs have the same structure

5. **Easy Capacity Checking**
   - Just iterate over PRs and count by state/reviewer
   - No need to filter out not-started items

6. **Clean History**
   - Only tracks what actually happened (PRs created)
   - No placeholder entries for future work

#### Cons ❌

1. **Loses Explicit Task Listing**
   - Not-yet-started tasks don't appear anywhere in metadata
   - Must infer pending tasks from missing indices
   - To show task descriptions, must re-read spec.md every time

   **Example:**
   ```python
   # Current model - task descriptions always available
   for step in project.steps:
       print(f"{step.step_index}: {step.step_description}")

   # PR-Centric - must join with spec.md
   tasks_from_spec = parse_spec_md("spec.md")  # Must re-read file
   completed_indices = {pr.task_index for pr in project.pull_requests}
   for task in tasks_from_spec:
       if task.index not in completed_indices:
           print(f"{task.index}: {task.description}")
   ```

2. **Requires Maintaining total_tasks**
   - Must update `total_tasks` whenever spec.md changes
   - If spec.md adds/removes tasks, `total_tasks` becomes stale
   - No way to detect this inconsistency

3. **More Complex "Next Task" Selection**
   ```python
   # Current model
   next_step = next(s for s in project.steps if not s.is_started())

   # PR-Centric model
   completed_indices = {pr.task_index for pr in project.pull_requests}
   next_index = next(i for i in range(1, total_tasks + 1)
                     if i not in completed_indices)
   # But we still don't have the description! Must read spec.md
   ```

4. **Denormalized Data Risks**
   - Task descriptions copied from spec.md into each PR
   - If spec.md is updated, metadata has stale descriptions
   - No single source of truth for task definitions

5. **Cannot Show Complete Project View**
   - "Show me all tasks and their statuses" requires joining with spec.md
   - Current model always has complete view in metadata
   - PR-Centric requires file I/O to answer this question

6. **Index Gaps Are Ambiguous**
   ```python
   # If PRs have task_index [1, 2, 4, 5] and total_tasks = 5
   # Is task 3 pending? Or was it deleted from spec.md?
   # No way to tell from metadata alone
   ```

7. **Spec.md Dependency**
   - Many operations require reading spec.md in addition to metadata
   - Current model: metadata is self-contained for most queries
   - PR-Centric: metadata + spec.md needed for full picture

8. **Not Addressing Current Pain Points**
   - Still has optional fields issue (total_tasks can be stale)
   - Still has denormalized data (task descriptions)
   - Doesn't add explicit status enum
   - Actually makes some queries harder

#### Neutral Observations 🤔

1. **total_tasks Semantics**
   - Is this "tasks at time of last update" or "current task count in spec.md"?
   - If spec.md is the source of truth, why cache the count?
   - If metadata is the source of truth, why not store task definitions?

2. **Multiple Attempts at Same Task**
   - Model doesn't explicitly support retry attempts
   - Would need to track multiple PRs with same `task_index`
   - Could work but feels awkward (same as current model)

3. **Spec.md vs Metadata Relationship**
   - Model assumes spec.md is always available and authoritative
   - But then why store `task_description` in PR metadata?
   - Seems to want to be both dependent on and independent from spec.md

### Analysis Summary

**Does this feel more natural?**

**For PR-focused workflows:** Yes, if you primarily think about "PRs we've created" rather than "tasks we planned". The model is simpler and more compact.

**For planning-focused workflows:** No, because you lose the explicit task list. Every query about pending work requires re-reading spec.md.

**Trade-offs:**
- ✅ **Simplicity**: Simplest possible structure, no optional fields on PRs
- ❌ **Completeness**: Cannot answer "what are all tasks?" from metadata alone
- ❌ **Spec.md dependency**: Many operations require spec.md file reads

**When This Model Works Well:**
- Small projects where re-reading spec.md is fast
- Workflows focused on PR status (open/merged) rather than task planning
- Cases where spec.md never changes after initial creation

**When This Model Struggles:**
- Showing comprehensive project status (pending/in-progress/completed tasks)
- Determining next task to work on (requires spec.md read)
- Detecting spec.md changes (no stored baseline to compare against)
- Large projects where re-parsing spec.md is expensive

**Comparison to Alternative 1 (Spec/Exec):**
- Alternative 1 is more complex but more complete
- Alternative 1 stores full spec, Alternative 2 loses it
- Alternative 1 better separates concerns
- Alternative 2 is simpler but requires more spec.md reads

**Comparison to Current Model:**
- Current model is more complete (all tasks always visible)
- PR-Centric is simpler (no optional fields on PRs)
- Current model is self-contained, PR-Centric requires spec.md
- Current model's pain point (optional fields on Step) is solved here, but at the cost of losing not-yet-started task visibility

**Recommendation for ClaudeStep:** This model is too minimal for ClaudeStep's needs. The project needs to show complete task lists, calculate progress, and select next tasks efficiently. Requiring spec.md reads for these common operations adds complexity rather than reducing it.

**Technical Notes:**
- Implementation would require new dataclasses: `Project`, `PullRequest`, `AIOperation`
- Migration would need to filter out not-yet-started Steps and set `total_tasks`
- Many query patterns would need to add spec.md reading logic
- Risk of `total_tasks` becoming stale if spec.md changes

## Phase 4: Alternative Model 3 - Hybrid Approach

**Concept:**
```
Project
  ├── tasks: List[Task]
  │   └── index, description, status (pending/in_progress/completed)
  └── pull_requests: List[PullRequest]
      ├── task_index (reference)
      ├── pr_number, branch, reviewer, state, created_at
      └── ai_operations: List[AIOperation]
          └── workflow_run_id, type, model, cost, tokens
```

**Key Ideas:**
- **Task**: Lightweight reference to spec.md (always present)
- **Status enum**: Explicit state machine (pending → in_progress → completed)
- **PullRequest**: Execution details, references task by index
- **Clear separation**: Task is "what" (spec), PR is "how" (execution)

**Tasks:**

- Create detailed diagram showing this structure
- Show example JSON for same 5-task project
- Document how this handles:
  - Task status transitions
  - Linking PRs to tasks (by task_index)
  - Multiple PRs for same task (if needed)
  - Statistics queries
- List pros and cons vs all previous models

**Expected Outcome:**
- Visual diagram of hybrid model
- Example JSON demonstrating the structure
- Analysis of balance between simplicity and explicitness

## Phase 5: Comparison Matrix

**Tasks:**
- Create comparison table for all models:
  - **Columns**: Current Model, Alt 1 (Spec/Exec), Alt 2 (PR-Centric), Alt 3 (Hybrid)
  - **Rows**:
    - Clarity of relationships
    - Ease of querying for statistics
    - Handling not-yet-started tasks
    - Handling refinements
    - JSON verbosity
    - Code complexity
    - Migration effort from current
- Rate each aspect (👍 Good, 👌 OK, 👎 Poor)
- Identify recommended approach with rationale

**Expected Outcome:**
- Clear comparison showing trade-offs
- Recommendation for which model to pursue
- Migration path from current model

## Phase 6: Detailed Design for Recommended Model

**Tasks:**
- Create comprehensive diagram for recommended model
- Define complete JSON schema with all fields
- Show 3-5 realistic examples:
  - Empty project (no PRs yet)
  - Project with mix of states
  - Complex project with refinements and multiple workflows
- Document Python dataclass structure
- Document serialization methods (from_dict, to_dict)
- Show how to query for common operations:
  - Get reviewer capacity (open PRs per reviewer)
  - Calculate project completion percentage
  - Sum costs across project
  - List pending tasks

**Expected Outcome:**
- Complete specification ready for implementation
- All edge cases considered
- Clear migration strategy

## Phase 8: User Review and Decision

**Tasks:**
- Present all alternatives with diagrams
- Get user feedback on preferred approach
- Refine based on feedback
- Get final approval before implementation

**Expected Outcome:**
- Clear decision on which model to implement
- User buy-in on approach
- Ready to proceed with implementation

## Notes

- **Diagrams**: Use ASCII art or mermaid-style notation for clarity in markdown
- **Examples**: Use the same 5-task auth-refactor project across all alternatives for consistency
- **Verbosity**: Balance between thorough analysis and decision paralysis - 3-4 alternatives is enough
- **User input**: Pause after each alternative for user feedback before proceeding
