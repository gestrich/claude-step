# Cost Data Passing and Command Naming Cleanup

## Background

After completing the token-based cost calculation feature (Phase 4 in `2026-01-02-2-token-based-cost-calculation.md`), there are inconsistencies in how cost data is passed between commands and how commands are named:

**Issues identified:**

1. **Unclear command naming**: `notify_pr.py` generates Slack notification messages but the name doesn't clearly indicate it's Slack-specific. It could mean email, webhook, or any notification.

2. **Fragmented cost data passing**: `cmd_notify_pr` receives three separate cost-related parameters as strings:
   ```python
   main_cost: str,
   summary_cost: str,
   model_breakdown_json: str,
   ```
   This should be a single structured model that contains all cost information.

3. **Dictionary string access instead of typed model fields**: In `format_pr_notification()`, model breakdown data is accessed via string keys:
   ```python
   model_name = model.get("model", "unknown")
   cost = model.get("cost", 0.0)
   ```
   This violates the project's domain model design principle of "parse once into well-formed models."

4. **`CostBreakdown` already exists**: The domain layer has a comprehensive `CostBreakdown` model that holds all cost information, including per-model data via `ModelUsage`. This should be the single structure passed between commands.

5. **Data flow inefficiency**: `post_pr_comment` creates a `CostBreakdown`, extracts values, serializes to JSON, then `notify_pr` parses the JSON back into dicts. This is wasteful when both commands run in sequence.

## Phases

- [x] Phase 1: Rename `notify_pr` to `format_slack_notification`

Rename the command to clearly indicate its purpose:
- Rename `src/claudechain/cli/commands/notify_pr.py` → `src/claudechain/cli/commands/format_slack_notification.py`
- Rename function `cmd_notify_pr` → `cmd_format_slack_notification`
- Update CLI command from `notify-pr` → `format-slack-notification`
- Update imports in `__main__.py`
- Update `action.yml` step names and command invocations
- Update tests: rename test file and update references

**Files to modify:**
- `src/claudechain/cli/commands/notify_pr.py` (rename to `format_slack_notification.py`)
- `src/claudechain/__main__.py`
- `src/claudechain/cli/parser.py` (if command is registered there)
- `action.yml`
- `tests/unit/cli/commands/test_notify_pr.py` (rename)

- [x] Phase 2: Use `CostBreakdown` model in Slack formatting

Instead of passing three separate cost parameters, pass a serialized `CostBreakdown` and deserialize it:

1. Add `to_json()` and `from_json()` methods to `CostBreakdown`:
   ```python
   def to_json(self) -> str:
       """Serialize to JSON for passing between workflow steps."""
       return json.dumps({
           "main_cost": self.main_cost,
           "summary_cost": self.summary_cost,
           "input_tokens": self.input_tokens,
           "output_tokens": self.output_tokens,
           "cache_read_tokens": self.cache_read_tokens,
           "cache_write_tokens": self.cache_write_tokens,
           "models": [
               {
                   "model": m.model,
                   "input_tokens": m.input_tokens,
                   "output_tokens": m.output_tokens,
                   "cache_read_tokens": m.cache_read_tokens,
                   "cache_write_tokens": m.cache_write_tokens,
               }
               for m in self.get_aggregated_models()
           ]
       })

   @classmethod
   def from_json(cls, json_str: str) -> 'CostBreakdown':
       """Deserialize from JSON."""
       data = json.loads(json_str)
       # Parse back into CostBreakdown with ModelUsage instances
       ...
   ```

2. Update `post_pr_comment` to output a single `cost_breakdown_json` instead of three separate outputs:
   ```python
   gh.write_output("cost_breakdown", cost_breakdown.to_json())
   ```

3. Update `format_slack_notification` to receive single `cost_breakdown_json` parameter:
   ```python
   def cmd_format_slack_notification(
       gh: GitHubActionsHelper,
       pr_number: str,
       pr_url: str,
       project_name: str,
       task: str,
       cost_breakdown_json: str,  # Single structured parameter
       repo: str,
   ) -> int:
       cost_breakdown = CostBreakdown.from_json(cost_breakdown_json)
       # Use typed model fields directly
   ```

4. Update `action.yml` to pass single `COST_BREAKDOWN` env var

5. Remove string `.get()` access - use typed `ModelUsage` fields directly:
   ```python
   # Before (bad)
   model_name = model.get("model", "unknown")

   # After (good)
   model_name = model.model
   ```

**Files to modify:**
- `src/claudechain/domain/cost_breakdown.py` (add `to_json`/`from_json`)
- `src/claudechain/cli/commands/format_slack_notification.py`
- `src/claudechain/cli/commands/post_pr_comment.py`
- `src/claudechain/__main__.py`
- `action.yml`

- [x] Phase 3: Update tests

Update all tests to use new command name and single cost model:
- Rename `test_notify_pr.py` → `test_format_slack_notification.py`
- Update test function names and imports
- Add tests for `CostBreakdown.to_json()` and `from_json()` round-trip
- Update integration tests if any reference the old command

**Files to modify:**
- `tests/unit/cli/commands/test_notify_pr.py` (rename and update)
- `tests/unit/domain/test_cost_breakdown.py` (add serialization tests)
- Any integration tests referencing `notify-pr`

- [x] Phase 4: Validation

Run full test suite to verify changes:
```bash
python3 -m pytest tests/unit/ tests/integration/ -v
```

Specific validations:
- `CostBreakdown` serialization round-trip preserves all data
- `format-slack-notification` command works with new parameter
- `post-pr-comment` outputs correct JSON format
- All renamed imports resolve correctly
- `action.yml` workflow steps execute in correct order

Success criteria:
- All tests pass
- No references to old `notify-pr` command remain
- No string `.get()` access on model data
- Single `cost_breakdown` parameter replaces three separate cost parameters
