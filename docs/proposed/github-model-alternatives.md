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

## Phase 2: Alternative Model 1 - Separate Spec and Execution

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

**Tasks:**

- Create detailed diagram showing this structure
- Show example JSON for a project with 5 tasks (2 completed, 1 in progress, 2 pending)
- Document how this handles:
  - Not-yet-started tasks (just in spec, no executions)
  - Multiple attempts at same task (multiple executions with same task_index)
  - Refinements (additional operations in same execution)
- List pros and cons vs current model

**Expected Outcome:**

- Visual diagram of separated spec/execution model
- Example JSON demonstrating the structure
- Analysis of whether this feels more natural

## Phase 3: Alternative Model 2 - PR-Centric

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

**Tasks:**
- Create detailed diagram showing this structure
- Show example JSON for same 5-task project
- Document how this handles:
  - Calculating pending tasks (total_tasks - PR count)
  - Showing which tasks are pending (need to track completed indices)
  - Statistics and progress reporting
- List pros and cons vs current model and Alternative 1

**Expected Outcome:**
- Visual diagram of PR-centric model
- Example JSON demonstrating the structure
- Analysis of simplicity vs completeness trade-offs

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
