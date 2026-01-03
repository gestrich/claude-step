## Background

ClaudeStep fundamentally assumes tasks are executed synchronously - one PR at a time per project. The current implementation with multiple reviewers and `maxOpenPRs` capacity settings contradicts this core assumption and adds unnecessary complexity:

1. **Multiple reviewers with capacity limits** implies concurrent PR execution, which breaks the sequential task model
2. **Balancing assignment across multiple reviewers** is confusing and the logic for "first available" isn't intuitive
3. **`maxOpenPRs` configuration** exists both per-reviewer and as a project-wide fallback, creating dual complexity

The simplification:
- Only 1 PR can be open at a time per project (enforced, not configurable)
- Only 1 optional assignee per project (not an array of reviewers)
- Remove all capacity-related configuration and inputs

## Phases

- [ ] Phase 1: Simplify domain models

**Files to modify:**
- `src/claudestep/domain/project_configuration.py`

**Changes:**
1. Remove the `Reviewer` dataclass entirely
2. Remove `DEFAULT_PROJECT_PR_LIMIT` constant (no longer configurable)
3. Change `ProjectConfiguration.reviewers: List[Reviewer]` to `ProjectConfiguration.assignee: Optional[str]`
4. Remove methods: `get_reviewer_usernames()`, `get_reviewer()`
5. Update `from_yaml_string()` to parse `assignee: username` instead of `reviewers: [...]`
6. Update `to_dict()` to serialize the new structure

**New configuration format:**
```yaml
# Optional - if omitted, PRs have no assignee
assignee: alice
```

- [ ] Phase 2: Simplify ReviewerService to AssigneeService

**Files to modify:**
- `src/claudestep/services/core/reviewer_service.py` (rename to `assignee_service.py`)
- `src/claudestep/services/__init__.py`

**Changes:**
1. Rename `ReviewerService` to `AssigneeService`
2. Simplify `find_available_reviewer()` to `check_capacity()` that:
   - Checks if project has any open ClaudeStep PRs (count >= 1 means no capacity)
   - Returns `(assignee: Optional[str], has_capacity: bool, open_prs: List)`
   - No per-reviewer capacity checking needed
3. Remove `_check_project_capacity()` method (logic merged into simplified check)
4. Update service exports

- [ ] Phase 3: Simplify capacity result model

**Files to modify:**
- `src/claudestep/domain/models.py`

**Changes:**
1. Simplify `ReviewerCapacityResult` to `CapacityResult`:
   - Remove `reviewers_status` list (no longer tracking multiple reviewers)
   - Remove `selected_reviewer` (replaced by assignee from config)
   - Keep: `has_capacity: bool`, `open_prs: List`, `all_at_capacity: bool`
2. Simplify `format_summary()` to show:
   - Current open PR count (0 or 1)
   - Whether capacity is available
   - List of open PRs if any

- [ ] Phase 4: Update CLI commands

**Files to modify:**
- `src/claudestep/cli/commands/prepare.py`
- `src/claudestep/cli/commands/finalize.py`
- `src/claudestep/cli/commands/discover_ready.py`

**Changes in prepare.py:**
1. Import `AssigneeService` instead of `ReviewerService`
2. Simplify capacity checking logic
3. Get assignee directly from `config.assignee` (no selection logic needed)
4. Update output: keep `has_capacity` and `reviewer` (or rename to `assignee`)
5. Remove `reviewers_json` output (no longer an array)

**Changes in finalize.py:**
1. Simplify summary messaging (no "reviewer capacity" vs "project capacity" distinction)

**Changes in discover_ready.py:**
1. Import `AssigneeService`
2. Simplify capacity check calls

- [ ] Phase 5: Update action.yml outputs

**Files to modify:**
- `action.yml`

**Changes:**
1. Rename `reviewer` output to `assignee`
2. Keep `has_capacity` output
3. Update descriptions to reflect simplified model
4. Remove any mentions of multiple reviewers or maxOpenPRs

- [ ] Phase 6: Update test builders

**Files to modify:**
- `tests/builders/config_builder.py`

**Changes:**
1. Remove `with_reviewer(username, max_prs)` method
2. Add `with_assignee(username)` method
3. Remove `with_no_reviewers()` (now just don't call `with_assignee`)
4. Update `build()` to create simplified config

- [ ] Phase 7: Update unit tests

**Files to modify:**
- `tests/unit/domain/test_project_configuration.py`
- `tests/unit/services/core/test_reviewer_service.py` (rename to `test_assignee_service.py`)

**Changes in test_project_configuration.py:**
1. Remove all `Reviewer` class tests
2. Remove tests for `get_reviewer_usernames()`, `get_reviewer()`
3. Add tests for `assignee` field parsing
4. Update YAML parsing tests for new format

**Changes in test_assignee_service.py:**
1. Drastically simplify - only need to test:
   - Has capacity when 0 open PRs
   - No capacity when 1+ open PRs
   - Returns configured assignee (or None if not configured)
2. Remove all multi-reviewer capacity tests
3. Remove `TestFindAvailableReviewerNoReviewers` class (no longer a separate mode)

- [ ] Phase 8: Update integration tests

**Files to modify:**
- `tests/integration/cli/commands/test_prepare.py`
- Any other integration tests referencing reviewers

**Changes:**
1. Update test configurations to use `assignee` instead of `reviewers`
2. Simplify capacity-related test scenarios

- [ ] Phase 9: Update documentation

**Files to modify:**
- `docs/feature-guides/projects.md`
- `docs/feature-guides/setup.md`
- `docs/feature-guides/troubleshooting.md`
- `docs/feature-guides/notifications.md`
- `docs/feature-guides/how-it-works.md`

**Changes in projects.md:**
1. Replace entire "Reviewer Configuration" section with simpler "Assignee Configuration"
2. Remove examples of multiple reviewers and maxOpenPRs
3. New example:
   ```yaml
   # Optional assignee
   assignee: alice
   ```

**Changes in troubleshooting.md:**
1. Simplify "No Capacity" troubleshooting
2. Remove advice about adding reviewers or increasing maxOpenPRs
3. Solution is simply: merge or close the existing open PR

**Changes in other docs:**
1. Update terminology: "reviewer" -> "assignee" where appropriate
2. Remove references to reviewer capacity and maxOpenPRs

- [ ] Phase 10: Validation

**Tests to run:**
```bash
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v
pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing
```

**Success criteria:**
1. All unit tests pass
2. All integration tests pass
3. Coverage remains at 85%+
4. Configuration parsing works with new `assignee` field
5. Capacity check correctly limits to 1 open PR per project
6. Documentation accurately reflects new simplified model
