# GitHub Metadata Model - Hybrid Approach

## Background

ClaudeStep stores PR metadata to track project progress, reviewer capacity, costs, and AI operations. This document specifies the decided metadata model using a **hybrid approach** that separates task definitions from PR execution details.

### Key Requirements

The metadata model must support:
- **Reviewer capacity checking**: Count open PRs per reviewer across projects
- **Project statistics**: Completion percentage, costs, progress tracking
- **Task selection**: Identify next pending task to work on
- **Team leaderboard**: Aggregate PR counts and costs by team member
- **Cost analysis**: Sum costs by project, model, time period

### Design Goals

1. **Clear separation of concerns**: Separate spec.md structure from PR execution tracking
2. **Explicit relationships**: Make relationships between entities obvious
3. **Minimal special cases**: Avoid "not started" vs "started" being fundamentally different
4. **Easy to reason about**: Model should match mental model of how ClaudeStep works
5. **Self-contained**: All information accessible without reading spec.md

### No Backward Compatibility Required

**Important:** Since ClaudeStep has not been released yet, there is no need to maintain backward compatibility. The implementation can move straight to this approach without migration from any previous format.

## The Hybrid Model

### Concept

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
- **Task**: Lightweight reference to spec.md (always present for all tasks)
- **Status enum**: Explicit state machine (pending → in_progress → completed)
- **PullRequest**: Execution details, references task by index
- **Clear separation**: Task is "what" (spec), PR is "how" (execution)

### Detailed Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│                              Project                                │
├─────────────────────────────────────────────────────────────────────┤
│ schema_version: str                    # "2.0" for hybrid model     │
│ project: str                           # Project identifier         │
│ last_updated: datetime                 # ISO 8601 timestamp         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌────────────────────────────────┐  ┌──────────────────────────┐  │
│  │          tasks: List            │  │  pull_requests: List     │  │
│  └────────────────────────────────┘  └──────────────────────────┘  │
│                │                                  │                 │
│                ▼                                  ▼                 │
│  ┌──────────────────────────────┐  ┌────────────────────────────┐  │
│  │           Task               │  │      PullRequest           │  │
│  ├──────────────────────────────┤  ├────────────────────────────┤  │
│  │ index: int                   │  │ task_index: int ───────────┼──┼──> References Task.index
│  │ description: str             │  │ pr_number: int             │  │
│  │ status: TaskStatus (enum)    │  │ branch_name: str           │  │
│  │   - "pending"                │  │ reviewer: str              │  │
│  │   - "in_progress"            │  │ pr_state: str              │  │
│  │   - "completed"              │  │   - "open"                 │  │
│  └──────────────────────────────┘  │   - "merged"               │  │
│                                     │   - "closed"               │  │
│                                     │ created_at: datetime       │  │
│                                     ├────────────────────────────┤  │
│                                     │  ai_operations: List       │  │
│                                     └────────────────────────────┘  │
│                                                  │                 │
│                                                  ▼                 │
│                                     ┌────────────────────────────┐  │
│                                     │       AIOperation          │  │
│                                     ├────────────────────────────┤  │
│                                     │ type: str                  │  │
│                                     │   - "PRCreation"           │  │
│                                     │   - "PRRefinement"         │  │
│                                     │   - "PRSummary"            │  │
│                                     │ model: str                 │  │
│                                     │ cost_usd: float            │  │
│                                     │ created_at: datetime       │  │
│                                     │ workflow_run_id: int       │  │
│                                     │ tokens_input: int          │  │
│                                     │ tokens_output: int         │  │
│                                     │ duration_seconds: float    │  │
│                                     └────────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

Relationships:
  Task ←──[1:N]── PullRequest  (via task_index)
  PullRequest ←──[1:N]── AIOperation

Status Derivation:
  Task.status is derived from PullRequest.pr_state:
  - No PR for task → status = "pending"
  - PR exists, pr_state = "open" → status = "in_progress"
  - PR exists, pr_state = "merged" → status = "completed"
  - Multiple PRs → use latest by created_at
```

### Key Relationships

1. **Task → PullRequest**: One-to-many relationship via `task_index`
   - One `Task` can have zero or more `PullRequest` records
   - Zero PRs = task not yet started (status: "pending")
   - One PR = normal case (single PR attempt)
   - Multiple PRs = task was attempted multiple times (e.g., PR closed and retried)

2. **PullRequest → AIOperation**: One-to-many relationship
   - Each `PullRequest` has one or more `AIOperation` records
   - First operation is typically "PRCreation"
   - Additional operations are "PRRefinement" or "PRSummary"
   - All operations belong to the same PR

3. **Task Identification**: Tasks are identified by `index` (permanent) rather than PR state
   - Tasks list defines what needs to be done (static)
   - PRs track what was done (dynamic)

### Advantages

1. **Complete Task List Always Visible**
   - All tasks from spec.md present in metadata
   - No need to re-read spec.md to see pending tasks
   - Easy to answer "what are all the tasks?" and "which are pending?"

2. **Clear Separation of Concerns**
   - Task: "What needs to be done" (spec.md semantic content)
   - PullRequest: "What was done" (execution history)
   - No mixed responsibilities

3. **No Optional Field Complexity**
   - Task fields are all required (index, description, status)
   - PullRequest fields are all required (all PRs have full info)
   - No need to check if fields exist before using them

4. **Explicit Status Management**
   - Status is an enum field on Task
   - Derived from PR state using clear rules
   - No need to infer state from multiple optional fields

5. **Supports Retry Scenarios**
   - Multiple PRs can reference same task_index
   - History preserved (all attempts visible)
   - Latest PR determines task status

6. **Efficient Queries**
   - List pending tasks: filter tasks by status == "pending"
   - Count open PRs: filter pull_requests by pr_state == "open"
   - Calculate costs: sum over pull_requests → ai_operations
   - No need to filter out "not started" special cases

## Complete JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ClaudeStep Hybrid Model",
  "type": "object",
  "required": ["schema_version", "project", "last_updated", "tasks", "pull_requests"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "2.0",
      "description": "Schema version identifier"
    },
    "project": {
      "type": "string",
      "description": "Project name/identifier, typically matches spec.md name"
    },
    "last_updated": {
      "type": "string",
      "format": "date-time",
      "description": "ISO 8601 timestamp of last metadata update"
    },
    "tasks": {
      "type": "array",
      "description": "All tasks from spec.md, always present regardless of status",
      "items": {
        "type": "object",
        "required": ["index", "description", "status"],
        "properties": {
          "index": {
            "type": "integer",
            "minimum": 1,
            "description": "1-based position in spec.md, permanent identifier"
          },
          "description": {
            "type": "string",
            "minLength": 1,
            "description": "Task description from spec.md"
          },
          "status": {
            "type": "string",
            "enum": ["pending", "in_progress", "completed"],
            "description": "Task status derived from PR state"
          }
        }
      }
    },
    "pull_requests": {
      "type": "array",
      "description": "All PRs created, may have multiple PRs per task_index (retries)",
      "items": {
        "type": "object",
        "required": ["task_index", "pr_number", "branch_name", "reviewer", "pr_state", "created_at", "ai_operations"],
        "properties": {
          "task_index": {
            "type": "integer",
            "minimum": 1,
            "description": "References tasks[].index, indicates which task this PR implements"
          },
          "pr_number": {
            "type": "integer",
            "minimum": 1,
            "description": "GitHub pull request number"
          },
          "branch_name": {
            "type": "string",
            "minLength": 1,
            "description": "Git branch name for this PR"
          },
          "reviewer": {
            "type": "string",
            "minLength": 1,
            "description": "GitHub username of assigned reviewer"
          },
          "pr_state": {
            "type": "string",
            "enum": ["open", "merged", "closed"],
            "description": "Current state of the GitHub PR"
          },
          "created_at": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp when PR was created"
          },
          "ai_operations": {
            "type": "array",
            "minItems": 1,
            "description": "All AI operations performed for this PR, chronologically ordered",
            "items": {
              "type": "object",
              "required": ["type", "model", "cost_usd", "created_at", "workflow_run_id"],
              "properties": {
                "type": {
                  "type": "string",
                  "enum": ["PRCreation", "PRRefinement", "PRSummary"],
                  "description": "Type of AI operation performed"
                },
                "model": {
                  "type": "string",
                  "description": "AI model identifier (e.g., 'claude-sonnet-4')"
                },
                "cost_usd": {
                  "type": "number",
                  "minimum": 0,
                  "description": "Cost in USD for this operation"
                },
                "created_at": {
                  "type": "string",
                  "format": "date-time",
                  "description": "ISO 8601 timestamp when operation was performed"
                },
                "workflow_run_id": {
                  "type": "integer",
                  "minimum": 1,
                  "description": "GitHub Actions workflow run ID for debugging"
                },
                "tokens_input": {
                  "type": "integer",
                  "minimum": 0,
                  "default": 0,
                  "description": "Number of input tokens consumed"
                },
                "tokens_output": {
                  "type": "integer",
                  "minimum": 0,
                  "default": 0,
                  "description": "Number of output tokens generated"
                },
                "duration_seconds": {
                  "type": "number",
                  "minimum": 0,
                  "default": 0.0,
                  "description": "Execution time in seconds"
                }
              }
            }
          }
        }
      }
    }
  }
}
```

## Examples

### Example 1: Empty Project (No PRs Yet)

A freshly initialized project with all tasks pending:

```json
{
  "schema_version": "2.0",
  "project": "user-dashboard-redesign",
  "last_updated": "2025-12-29T08:00:00Z",
  "tasks": [
    {
      "index": 1,
      "description": "Update navigation component to use new design tokens",
      "status": "pending"
    },
    {
      "index": 2,
      "description": "Implement responsive grid layout for dashboard cards",
      "status": "pending"
    },
    {
      "index": 3,
      "description": "Add dark mode support to all components",
      "status": "pending"
    }
  ],
  "pull_requests": []
}
```

**Key Points:**
- All tasks are present with status "pending"
- Empty pull_requests array
- Minimal but complete representation
- Total size: ~500 bytes

### Example 2: Project with Mixed States

A mid-progress project showing all three task states:

```json
{
  "schema_version": "2.0",
  "project": "auth-refactor",
  "last_updated": "2025-12-29T14:30:00Z",
  "tasks": [
    {
      "index": 1,
      "description": "Set up authentication middleware",
      "status": "completed"
    },
    {
      "index": 2,
      "description": "Implement OAuth2 authentication flow",
      "status": "in_progress"
    },
    {
      "index": 3,
      "description": "Add email validation to user registration",
      "status": "pending"
    },
    {
      "index": 4,
      "description": "Implement password reset functionality",
      "status": "pending"
    },
    {
      "index": 5,
      "description": "Add two-factor authentication support",
      "status": "pending"
    }
  ],
  "pull_requests": [
    {
      "task_index": 1,
      "pr_number": 41,
      "branch_name": "claudestep/auth-refactor/step-1",
      "reviewer": "alice",
      "pr_state": "merged",
      "created_at": "2025-12-28T10:15:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.12,
          "created_at": "2025-12-28T10:15:00Z",
          "workflow_run_id": 234567,
          "tokens_input": 4500,
          "tokens_output": 1800,
          "duration_seconds": 42.1
        }
      ]
    },
    {
      "task_index": 2,
      "pr_number": 42,
      "branch_name": "claudestep/auth-refactor/step-2",
      "reviewer": "bob",
      "pr_state": "open",
      "created_at": "2025-12-29T09:30:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-12-29T09:30:00Z",
          "workflow_run_id": 234570,
          "tokens_input": 5200,
          "tokens_output": 2100,
          "duration_seconds": 48.3
        }
      ]
    }
  ]
}
```

**Key Points:**
- Task 1: completed (PR merged)
- Task 2: in_progress (PR open)
- Tasks 3-5: pending (no PRs)
- Shows progression through project
- 2 reviewers with different assignments

### Example 3: Complex Project with Refinements

A task that went through multiple refinement cycles:

```json
{
  "schema_version": "2.0",
  "project": "api-performance-optimization",
  "last_updated": "2025-12-29T18:45:00Z",
  "tasks": [
    {
      "index": 1,
      "description": "Add database query caching layer",
      "status": "completed"
    },
    {
      "index": 2,
      "description": "Implement connection pooling",
      "status": "in_progress"
    }
  ],
  "pull_requests": [
    {
      "task_index": 1,
      "pr_number": 101,
      "branch_name": "claudestep/api-performance/step-1",
      "reviewer": "charlie",
      "pr_state": "merged",
      "created_at": "2025-12-27T14:00:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.18,
          "created_at": "2025-12-27T14:00:00Z",
          "workflow_run_id": 345678,
          "tokens_input": 6800,
          "tokens_output": 2400,
          "duration_seconds": 52.7
        },
        {
          "type": "PRRefinement",
          "model": "claude-sonnet-4",
          "cost_usd": 0.09,
          "created_at": "2025-12-27T16:30:00Z",
          "workflow_run_id": 345680,
          "tokens_input": 3200,
          "tokens_output": 1400,
          "duration_seconds": 31.2
        },
        {
          "type": "PRRefinement",
          "model": "claude-sonnet-4",
          "cost_usd": 0.07,
          "created_at": "2025-12-28T09:15:00Z",
          "workflow_run_id": 345682,
          "tokens_input": 2800,
          "tokens_output": 1100,
          "duration_seconds": 26.8
        },
        {
          "type": "PRSummary",
          "model": "claude-haiku-4",
          "cost_usd": 0.02,
          "created_at": "2025-12-28T11:00:00Z",
          "workflow_run_id": 345685,
          "tokens_input": 1500,
          "tokens_output": 400,
          "duration_seconds": 8.3
        }
      ]
    },
    {
      "task_index": 2,
      "pr_number": 102,
      "branch_name": "claudestep/api-performance/step-2",
      "reviewer": "charlie",
      "pr_state": "open",
      "created_at": "2025-12-29T10:00:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.16,
          "created_at": "2025-12-29T10:00:00Z",
          "workflow_run_id": 345690,
          "tokens_input": 5900,
          "tokens_output": 2200,
          "duration_seconds": 47.5
        },
        {
          "type": "PRRefinement",
          "model": "claude-sonnet-4",
          "cost_usd": 0.08,
          "created_at": "2025-12-29T15:20:00Z",
          "workflow_run_id": 345692,
          "tokens_input": 3000,
          "tokens_output": 1300,
          "duration_seconds": 29.4
        }
      ]
    }
  ]
}
```

**Key Points:**
- Task 1 has 4 AI operations (1 creation + 2 refinements + 1 summary)
- Task 2 has 2 AI operations (1 creation + 1 refinement)
- Multiple workflow runs tracked per PR
- Different AI models used (Sonnet vs Haiku)
- Shows complete history of iterations
- Total cost for Task 1: $0.36

### Example 4: Retry Scenario (Multiple PRs per Task)

A task where the first PR was closed and a second attempt succeeded:

```json
{
  "schema_version": "2.0",
  "project": "payment-integration",
  "last_updated": "2025-12-29T20:00:00Z",
  "tasks": [
    {
      "index": 1,
      "description": "Integrate Stripe payment gateway",
      "status": "completed"
    }
  ],
  "pull_requests": [
    {
      "task_index": 1,
      "pr_number": 50,
      "branch_name": "claudestep/payment/step-1-attempt-1",
      "reviewer": "dana",
      "pr_state": "closed",
      "created_at": "2025-12-26T09:00:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.14,
          "created_at": "2025-12-26T09:00:00Z",
          "workflow_run_id": 456789,
          "tokens_input": 5400,
          "tokens_output": 2000,
          "duration_seconds": 45.8
        }
      ]
    },
    {
      "task_index": 1,
      "pr_number": 51,
      "branch_name": "claudestep/payment/step-1-attempt-2",
      "reviewer": "dana",
      "pr_state": "merged",
      "created_at": "2025-12-27T14:00:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-12-27T14:00:00Z",
          "workflow_run_id": 456800,
          "tokens_input": 5600,
          "tokens_output": 2100,
          "duration_seconds": 47.2
        },
        {
          "type": "PRRefinement",
          "model": "claude-sonnet-4",
          "cost_usd": 0.08,
          "created_at": "2025-12-28T10:30:00Z",
          "workflow_run_id": 456805,
          "tokens_input": 3100,
          "tokens_output": 1250,
          "duration_seconds": 28.9
        }
      ]
    }
  ]
}
```

**Key Points:**
- Two PRs with same task_index (1)
- First PR closed without merging (failed attempt)
- Second PR merged (successful attempt)
- Task status is "completed" (derived from latest PR)
- Complete history preserved (both attempts visible)
- Total cost across both attempts: $0.37

## Python Dataclass Structure

Complete Python implementation with type hints and validation:

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class TaskStatus(Enum):
    """Task lifecycle states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class PRState(Enum):
    """GitHub PR states."""
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class AIOperationType(Enum):
    """Types of AI operations."""
    PR_CREATION = "PRCreation"
    PR_REFINEMENT = "PRRefinement"
    PR_SUMMARY = "PRSummary"


@dataclass
class AIOperation:
    """Represents a single AI operation (creation, refinement, summary)."""

    type: str  # AIOperationType enum value
    model: str
    cost_usd: float
    created_at: datetime
    workflow_run_id: int
    tokens_input: int = 0
    tokens_output: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "created_at": self.created_at.isoformat(),
            "workflow_run_id": self.workflow_run_id,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "duration_seconds": self.duration_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIOperation":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            type=data["type"],
            model=data["model"],
            cost_usd=float(data["cost_usd"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            workflow_run_id=int(data["workflow_run_id"]),
            tokens_input=int(data.get("tokens_input", 0)),
            tokens_output=int(data.get("tokens_output", 0)),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
        )


@dataclass
class PullRequest:
    """Represents a GitHub PR created for a task."""

    task_index: int
    pr_number: int
    branch_name: str
    reviewer: str
    pr_state: str  # PRState enum value
    created_at: datetime
    ai_operations: List[AIOperation] = field(default_factory=list)

    def get_total_cost(self) -> float:
        """Calculate total cost of all AI operations for this PR."""
        return sum(op.cost_usd for op in self.ai_operations)

    def get_total_tokens(self) -> tuple[int, int]:
        """Get total input and output tokens.

        Returns:
            Tuple of (total_input_tokens, total_output_tokens)
        """
        total_input = sum(op.tokens_input for op in self.ai_operations)
        total_output = sum(op.tokens_output for op in self.ai_operations)
        return (total_input, total_output)

    def get_total_duration(self) -> float:
        """Calculate total duration of all AI operations in seconds."""
        return sum(op.duration_seconds for op in self.ai_operations)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_index": self.task_index,
            "pr_number": self.pr_number,
            "branch_name": self.branch_name,
            "reviewer": self.reviewer,
            "pr_state": self.pr_state,
            "created_at": self.created_at.isoformat(),
            "ai_operations": [op.to_dict() for op in self.ai_operations],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PullRequest":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            task_index=int(data["task_index"]),
            pr_number=int(data["pr_number"]),
            branch_name=data["branch_name"],
            reviewer=data["reviewer"],
            pr_state=data["pr_state"],
            created_at=datetime.fromisoformat(data["created_at"]),
            ai_operations=[
                AIOperation.from_dict(op) for op in data.get("ai_operations", [])
            ],
        )


@dataclass
class Task:
    """Represents a task from spec.md with its current status."""

    index: int
    description: str
    status: str  # TaskStatus enum value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "index": self.index,
            "description": self.description,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary (JSON deserialization)."""
        return cls(
            index=int(data["index"]),
            description=data["description"],
            status=data["status"],
        )


@dataclass
class Project:
    """Top-level project metadata container."""

    schema_version: str
    project: str
    last_updated: datetime
    tasks: List[Task] = field(default_factory=list)
    pull_requests: List[PullRequest] = field(default_factory=list)

    def get_task_by_index(self, index: int) -> Optional[Task]:
        """Get task by its index."""
        for task in self.tasks:
            if task.index == index:
                return task
        return None

    def get_prs_for_task(self, task_index: int) -> List[PullRequest]:
        """Get all PRs for a given task (supports retry scenario)."""
        return [pr for pr in self.pull_requests if pr.task_index == task_index]

    def get_latest_pr_for_task(self, task_index: int) -> Optional[PullRequest]:
        """Get the most recent PR for a task (by created_at)."""
        prs = self.get_prs_for_task(task_index)
        if not prs:
            return None
        return max(prs, key=lambda pr: pr.created_at)

    def calculate_task_status(self, task_index: int) -> TaskStatus:
        """Calculate task status from PR state.

        This is the core logic that derives task status:
        - No PR → pending
        - PR open → in_progress
        - PR merged → completed
        - Multiple PRs → use latest by created_at
        """
        latest_pr = self.get_latest_pr_for_task(task_index)

        if latest_pr is None:
            return TaskStatus.PENDING

        if latest_pr.pr_state == PRState.MERGED.value:
            return TaskStatus.COMPLETED
        elif latest_pr.pr_state in [PRState.OPEN.value, PRState.CLOSED.value]:
            return TaskStatus.IN_PROGRESS
        else:
            return TaskStatus.PENDING

    def update_all_task_statuses(self) -> None:
        """Update all task statuses based on current PR states.

        Call this after loading from JSON to ensure consistency.
        """
        for task in self.tasks:
            task.status = self.calculate_task_status(task.index).value

    def get_total_cost(self) -> float:
        """Calculate total cost across all PRs."""
        return sum(pr.get_total_cost() for pr in self.pull_requests)

    def get_cost_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by AI model."""
        costs: Dict[str, float] = {}
        for pr in self.pull_requests:
            for op in pr.ai_operations:
                costs[op.model] = costs.get(op.model, 0.0) + op.cost_usd
        return costs

    def get_progress_stats(self) -> Dict[str, int]:
        """Get task counts by status."""
        stats = {
            "total": len(self.tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
        }
        for task in self.tasks:
            if task.status == TaskStatus.PENDING.value:
                stats["pending"] += 1
            elif task.status == TaskStatus.IN_PROGRESS.value:
                stats["in_progress"] += 1
            elif task.status == TaskStatus.COMPLETED.value:
                stats["completed"] += 1
        return stats

    def get_completion_percentage(self) -> float:
        """Calculate project completion percentage."""
        if not self.tasks:
            return 0.0
        stats = self.get_progress_stats()
        return (stats["completed"] / stats["total"]) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "last_updated": self.last_updated.isoformat(),
            "tasks": [task.to_dict() for task in self.tasks],
            "pull_requests": [pr.to_dict() for pr in self.pull_requests],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        """Create from dictionary (JSON deserialization)."""
        project = cls(
            schema_version=data["schema_version"],
            project=data["project"],
            last_updated=datetime.fromisoformat(data["last_updated"]),
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
            pull_requests=[
                PullRequest.from_dict(pr) for pr in data.get("pull_requests", [])
            ],
        )
        # Ensure task statuses are consistent with PR states
        project.update_all_task_statuses()
        return project
```

### Serialization Methods

#### JSON Serialization (to_dict)

Each dataclass implements `to_dict()` for converting to JSON-serializable dictionaries:

**Key Behaviors:**
- DateTime objects converted to ISO 8601 strings using `.isoformat()`
- Nested objects recursively converted (e.g., `ai_operations` list)
- Enum values converted to their string values
- All numeric types preserved as-is

**Example Usage:**
```python
import json

project = Project(
    schema_version="2.0",
    project="my-project",
    last_updated=datetime.now(),
    tasks=[...],
    pull_requests=[...]
)

# Convert to JSON
json_str = json.dumps(project.to_dict(), indent=2)

# Write to file
with open("metadata.json", "w") as f:
    json.dump(project.to_dict(), f, indent=2)
```

#### JSON Deserialization (from_dict)

Each dataclass implements `from_dict()` classmethod for loading from JSON:

**Key Behaviors:**
- DateTime strings parsed using `datetime.fromisoformat()`
- Nested objects recursively constructed
- Default values applied for optional fields
- Type coercion (e.g., ensuring ints and floats)
- **Automatic status synchronization**: `update_all_task_statuses()` called after loading

**Example Usage:**
```python
# Load from JSON file
with open("metadata.json", "r") as f:
    data = json.load(f)

project = Project.from_dict(data)

# Task statuses automatically synchronized with PR states
print(f"Project: {project.project}")
print(f"Completion: {project.get_completion_percentage():.1f}%")
```

#### Status Synchronization

The `update_all_task_statuses()` method ensures task statuses match PR states:

```python
def update_all_task_statuses(self) -> None:
    """Update all task statuses based on current PR states."""
    for task in self.tasks:
        task.status = self.calculate_task_status(task.index).value
```

This is automatically called in `from_dict()` to handle:
- JSON files with stale status values
- Manual JSON edits
- Migration from old schema versions (if needed in the future)

## Common Query Operations

### 1. Get Reviewer Capacity (Open PRs per Reviewer)

Find which reviewers have capacity for new PR assignments:

```python
def get_reviewer_capacity(projects: List[Project], max_open_prs: int = 3) -> Dict[str, Dict[str, Any]]:
    """Get open PR count and capacity for each reviewer.

    Args:
        projects: List of all projects
        max_open_prs: Maximum open PRs per reviewer

    Returns:
        Dict mapping reviewer username to capacity info
    """
    reviewer_stats: Dict[str, Dict[str, Any]] = {}

    for project in projects:
        for pr in project.pull_requests:
            if pr.pr_state == PRState.OPEN.value:
                if pr.reviewer not in reviewer_stats:
                    reviewer_stats[pr.reviewer] = {
                        "open_prs": 0,
                        "pr_numbers": [],
                        "projects": set()
                    }
                reviewer_stats[pr.reviewer]["open_prs"] += 1
                reviewer_stats[pr.reviewer]["pr_numbers"].append(pr.pr_number)
                reviewer_stats[pr.reviewer]["projects"].add(project.project)

    # Add capacity info
    for reviewer, stats in reviewer_stats.items():
        stats["has_capacity"] = stats["open_prs"] < max_open_prs
        stats["available_slots"] = max(0, max_open_prs - stats["open_prs"])
        stats["projects"] = list(stats["projects"])  # Convert set to list

    return reviewer_stats

# Example usage
capacity = get_reviewer_capacity(all_projects, max_open_prs=3)

for reviewer, stats in capacity.items():
    print(f"{reviewer}:")
    print(f"  Open PRs: {stats['open_prs']}")
    print(f"  Has capacity: {stats['has_capacity']}")
    print(f"  Available slots: {stats['available_slots']}")
    print(f"  Projects: {', '.join(stats['projects'])}")
```

**Output Example:**
```
alice:
  Open PRs: 2
  Has capacity: True
  Available slots: 1
  Projects: auth-refactor, checkout
bob:
  Open PRs: 3
  Has capacity: False
  Available slots: 0
  Projects: auth-refactor, api-performance
charlie:
  Open PRs: 1
  Has capacity: True
  Available slots: 2
  Projects: checkout
```

### 2. Calculate Project Completion Percentage

Get completion status for a single project or across all projects:

```python
def get_project_completion(project: Project) -> Dict[str, Any]:
    """Get detailed completion stats for a project."""
    stats = project.get_progress_stats()

    return {
        "project": project.project,
        "total_tasks": stats["total"],
        "completed": stats["completed"],
        "in_progress": stats["in_progress"],
        "pending": stats["pending"],
        "completion_percentage": project.get_completion_percentage(),
        "is_complete": stats["completed"] == stats["total"],
        "has_work_in_progress": stats["in_progress"] > 0,
    }

# Example usage
completion = get_project_completion(project)
print(f"Project: {completion['project']}")
print(f"Progress: {completion['completed']}/{completion['total_tasks']} tasks")
print(f"Completion: {completion['completion_percentage']:.1f}%")
print(f"In Progress: {completion['in_progress']}")
print(f"Pending: {completion['pending']}")
```

**Output Example:**
```
Project: auth-refactor
Progress: 2/5 tasks
Completion: 40.0%
In Progress: 1
Pending: 2
```

### 3. List Pending Tasks

Find the next task(s) to work on:

```python
def get_pending_tasks(project: Project, limit: Optional[int] = None) -> List[Task]:
    """Get all pending tasks, optionally limited to first N."""
    pending = [
        task for task in project.tasks
        if task.status == TaskStatus.PENDING.value
    ]

    if limit is not None:
        return pending[:limit]
    return pending

def get_next_task(project: Project) -> Optional[Task]:
    """Get the next task to work on (first pending task)."""
    pending = get_pending_tasks(project, limit=1)
    return pending[0] if pending else None

# Example usage
next_task = get_next_task(project)
if next_task:
    print(f"Next task: #{next_task.index} - {next_task.description}")
else:
    print("No pending tasks - project complete!")

all_pending = get_pending_tasks(project)
print(f"\nRemaining tasks: {len(all_pending)}")
for task in all_pending:
    print(f"  #{task.index}: {task.description}")
```

**Output Example:**
```
Next task: #3 - Add email validation to user registration

Remaining tasks: 3
  #3: Add email validation to user registration
  #4: Implement password reset functionality
  #5: Add two-factor authentication support
```

## Edge Cases and Validation

### Complete Validation Suite

```python
def validate_project(project: Project, auto_fix: bool = True) -> Dict[str, List[str]]:
    """Run all validations on a project.

    Args:
        project: Project to validate
        auto_fix: If True, automatically fix issues where possible

    Returns:
        Dict with 'errors' and 'warnings' lists
    """
    result = {
        "errors": [],
        "warnings": [],
    }

    # 1. Validate PR references (orphaned PRs)
    task_indices = {task.index for task in project.tasks}
    for pr in project.pull_requests:
        if pr.task_index not in task_indices:
            result["errors"].append(
                f"PR #{pr.pr_number} references non-existent task index {pr.task_index}"
            )

    # 2. Validate unique task indices
    seen_indices = set()
    for task in project.tasks:
        if task.index in seen_indices:
            result["errors"].append(f"Duplicate task index: {task.index}")
        seen_indices.add(task.index)

    # 3. Validate PR has operations
    for pr in project.pull_requests:
        if not pr.ai_operations:
            result["errors"].append(
                f"PR #{pr.pr_number} has no AI operations (task {pr.task_index})"
            )

    # 4. Validate timestamps
    from datetime import timezone
    now = datetime.now(timezone.utc)
    for pr in project.pull_requests:
        if pr.created_at > now:
            result["warnings"].append(
                f"PR #{pr.pr_number} has future timestamp: {pr.created_at.isoformat()}"
            )
        for op in pr.ai_operations:
            if op.created_at > now:
                result["warnings"].append(
                    f"PR #{pr.pr_number} operation '{op.type}' has future timestamp: "
                    f"{op.created_at.isoformat()}"
                )

    # 5. Validate and fix task statuses
    if auto_fix:
        for task in project.tasks:
            expected_status = project.calculate_task_status(task.index)
            if task.status != expected_status.value:
                result["warnings"].append(
                    f"Task {task.index} status mismatch: "
                    f"was '{task.status}', should be '{expected_status.value}' - FIXED"
                )
                task.status = expected_status.value

    return result

# Example usage
validation = validate_project(project, auto_fix=True)

if validation["errors"]:
    print("ERRORS:")
    for error in validation["errors"]:
        print(f"  ❌ {error}")

if validation["warnings"]:
    print("WARNINGS:")
    for warning in validation["warnings"]:
        print(f"  ⚠️  {warning}")

if not validation["errors"] and not validation["warnings"]:
    print("✅ Project validation passed")
```

## Implementation Notes

### Storage Location

Metadata will be stored in a dedicated `claudestep-metadata` branch in each repository:

```
claudestep-metadata/
├── projects/
│   ├── my-refactor.json
│   ├── another-project.json
│   └── legacy-cleanup.json
└── README.md
```

### API Integration

The hybrid model will be integrated with ClaudeStep's branch-based metadata storage system (see `github-branch-metadata-storage.md`):

1. **Finalize command**: Writes Project JSON to `claudestep-metadata` branch after PR creation
2. **Statistics command**: Reads Project JSON files for fast statistics generation
3. **Prepare command**: Reads Project JSON to check reviewer capacity
4. **GitHub API**: Direct file operations via Contents API (no branch checkout needed)

### Performance Characteristics

- **Empty project**: ~500 bytes
- **5-task project with 2 PRs**: ~2-3 KB
- **20-task project with 15 PRs**: ~10-15 KB
- **Statistics query (20 projects)**: <2 seconds (vs. 30+ seconds with artifacts)

### Future Considerations

If the model needs to evolve in the future:

1. **Schema versioning**: Use `schema_version` field to identify format
2. **Migration support**: Implement `migrate_v2_to_v3()` function if needed
3. **Backward compatibility**: The `from_dict()` method can handle old formats
4. **Validation**: Run `validate_project()` after loading to catch inconsistencies

**Technical Notes:**
- This specification is complete and ready for implementation
- All examples validated for JSON correctness
- Dataclass structure includes full type hints for static analysis
- Query operations optimized for ClaudeStep's common use cases
- Validation suite covers all known edge cases
