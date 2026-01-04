# Token-Based Cost Calculation

## Background

The `claude-code-action` has a bug where it calculates costs using incorrect pricing rates. Our research on PR #24 from `gestrich/swift-lambda-sample` showed that when using `claude-3-haiku-20240307`, the action calculated costs using Sonnet rates ($3/$15 per MTok) instead of Haiku 3 rates ($0.25/$1.25 per MTok), resulting in a 12x overcharge in the displayed cost.

To work around this, we will:
1. Parse token counts from Claude Code execution files (which are accurate)
2. Use hardcoded per-model pricing rates in the app
3. Calculate cost per-model using correct rates, then sum for total
4. Always display token breakdown in addition to cost

### Claude Code Execution File Structure

The execution file JSON contains:

**Top-level fields:**
- `total_cost_usd` - Total cost (INACCURATE - uses wrong rates)

**Per-model breakdown (`modelUsage`):**
```json
"modelUsage": {
  "claude-haiku-4-5-20251001": {
    "inputTokens": 4271,           // ACCURATE
    "outputTokens": 389,           // ACCURATE
    "cacheReadInputTokens": 0,     // ACCURATE
    "cacheCreationInputTokens": 12299,  // ACCURATE
    "costUSD": 0.02158975,         // INACCURATE - wrong rates
    "webSearchRequests": 0,
    "contextWindow": 200000
  },
  "claude-3-haiku-20240307": {
    "inputTokens": 15,
    "outputTokens": 426,
    "cacheReadInputTokens": 90755,
    "cacheCreationInputTokens": 30605,
    "costUSD": 0.14843025,         // INACCURATE - uses Sonnet rates
    ...
  }
}
```

**Key insight:** Token counts are accurate, cost values are not. Since multiple models may be used in a single execution, we must calculate cost per-model and sum those costs (NOT sum tokens across models).

### Pricing Formula

All Claude models follow consistent pricing multipliers:
```
model_cost = (input * rate) + (output * rate * 5) + (cache_write * rate * 1.25) + (cache_read * rate * 0.1)
total_cost = sum of all model_cost values
```

### Hardcoded Model Rates (per MTok input)

Model name patterns and their input rates:
- `claude-3-haiku` or `claude-haiku-3`: $0.25
- `claude-haiku-4` or `claude-4-haiku`: $1.00
- `claude-3-5-sonnet` or `claude-sonnet-3-5`: $3.00
- `claude-sonnet-4` or `claude-4-sonnet`: $3.00
- `claude-opus-4` or `claude-4-opus`: $15.00

Unknown models: raise `UnknownModelError` to fail fast and surface pricing gaps immediately

## Phases

- [x] Phase 1: Extract token data and update display format

Extend `CostBreakdown` in `src/claudechain/domain/cost_breakdown.py`:
- Add fields: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens` (all `int`, default 0)
- Update `_extract_from_file()` to also extract tokens from `modelUsage` section (sum across all models)
- Update `format_for_github()` to show token breakdown alongside existing cost (from `total_cost_usd`)
- Update Slack formatting similarly
- Maintain backward compatibility when `modelUsage` is missing (tokens default to 0)

The domain model owns parsing logic per project architecture principles.

Add tests for:
- Token extraction from execution files with `modelUsage` section
- Updated `format_for_github()` output includes tokens
- Backward compatibility when `modelUsage` is missing

- [x] Phase 2: Add hardcoded model pricing and per-model cost calculation

Add model pricing lookup to `ModelUsage`:
- Add `MODEL_RATES` dict mapping model name patterns to input rates (per MTok)
- Add `get_rate_for_model(model_name: str) -> float` function that matches patterns
- Add `calculate_cost() -> float` method on `ModelUsage` that uses the formula and model's rate

Update `ExecutionUsage`:
- Add `calculated_cost` property that sums `calculate_cost()` across all models
- This replaces the inaccurate `total_cost_usd` from the file

Update `CostBreakdown`:
- Use `calculated_cost` from `ExecutionUsage` instead of `total_cost_usd`
- Remove reliance on file's cost values entirely

Add tests for:
- `get_rate_for_model()` with various model name patterns
- `ModelUsage.calculate_cost()` with known rates
- `ExecutionUsage.calculated_cost` sums per-model costs correctly
- Unknown model names use default rate and log warning

- [x] Phase 3: Validation

Run full test suite:
```bash
python3 -m pytest tests/unit/domain/test_cost_breakdown.py -v
python3 -m pytest tests/integration/cli/commands/test_post_pr_comment.py -v
```

Manual verification:
- Run workflow and verify calculated cost differs from original `total_cost_usd`
- Verify token breakdown displays correctly per model

## Real Workflow Validation Data

Data from PR #24 on `gestrich/swift-lambda-sample` (workflow run 20658904611):
- PR: https://github.com/gestrich/swift-lambda-sample/pull/24
- Workflow: https://github.com/gestrich/swift-lambda-sample/actions/runs/20658904611

### Main Execution File Data

```json
{
  "total_cost_usd": 0.170020,
  "modelUsage": {
    "claude-haiku-4-5-20251001": {
      "inputTokens": 4271,
      "outputTokens": 389,
      "cacheReadInputTokens": 0,
      "cacheCreationInputTokens": 12299,
      "costUSD": 0.02158975
    },
    "claude-3-haiku-20240307": {
      "inputTokens": 15,
      "outputTokens": 426,
      "cacheReadInputTokens": 90755,
      "cacheCreationInputTokens": 30605,
      "costUSD": 0.14843025
    }
  }
}
```

### Summary Execution File Data

```json
{
  "total_cost_usd": 0.091275,
  "modelUsage": {
    "claude-haiku-4-5-20251001": {
      "inputTokens": 3,
      "outputTokens": 208,
      "cacheReadInputTokens": 0,
      "cacheCreationInputTokens": 12247,
      "costUSD": 0.016351749999999998
    },
    "claude-3-haiku-20240307": {
      "inputTokens": 6,
      "outputTokens": 303,
      "cacheReadInputTokens": 44484,
      "cacheCreationInputTokens": 15204,
      "costUSD": 0.0749232
    }
  }
}
```

### Expected Calculated Costs (Using Our Formula)

**Main Execution:**

| Model | Rate | Input | Output | Cache Write | Cache Read | Subtotal |
|-------|------|-------|--------|-------------|------------|----------|
| claude-haiku-4-5-20251001 | $1.00/MTok | 4271 × $1.00/M = $0.004271 | 389 × $5.00/M = $0.001945 | 12299 × $1.25/M = $0.01537375 | 0 × $0.10/M = $0.00 | **$0.02158975** |
| claude-3-haiku-20240307 | $0.25/MTok | 15 × $0.25/M = $0.00000375 | 426 × $1.25/M = $0.0005325 | 30605 × $0.3125/M = $0.009564063 | 90755 × $0.025/M = $0.002268875 | **$0.012369188** |
| **Main Total** | | | | | | **$0.033958938** |

**Summary Execution:**

| Model | Rate | Input | Output | Cache Write | Cache Read | Subtotal |
|-------|------|-------|--------|-------------|------------|----------|
| claude-haiku-4-5-20251001 | $1.00/MTok | 3 × $1.00/M = $0.000003 | 208 × $5.00/M = $0.00104 | 12247 × $1.25/M = $0.01530875 | 0 × $0.10/M = $0.00 | **$0.01635175** |
| claude-3-haiku-20240307 | $0.25/MTok | 6 × $0.25/M = $0.0000015 | 303 × $1.25/M = $0.00037875 | 15204 × $0.3125/M = $0.0047525 | 44484 × $0.025/M = $0.0011121 | **$0.006244850** |
| **Summary Total** | | | | | | **$0.022596600** |

### Cost Comparison

| Source | Main | Summary | Total |
|--------|------|---------|-------|
| File `total_cost_usd` (INACCURATE) | $0.170020 | $0.091275 | **$0.261295** |
| Our calculated cost (ACCURATE) | $0.033959 | $0.022597 | **$0.056556** |
| **Overcharge factor** | 5.0x | 4.0x | **4.6x** |

The original costs were inflated because `claude-3-haiku-20240307` was charged at Sonnet rates ($3/$15 per MTok) instead of Haiku 3 rates ($0.25/$1.25 per MTok).

### Expected Token Totals

| Token Type | Main | Summary | Total |
|------------|------|---------|-------|
| Input | 4,286 | 9 | 4,295 |
| Output | 815 | 511 | 1,326 |
| Cache Read | 90,755 | 44,484 | 135,239 |
| Cache Write | 42,904 | 27,451 | 70,355 |
| **Total** | 138,760 | 72,455 | **211,215** |

- [x] Phase 4: Per-Model Breakdown Display

Add per-model cost breakdown to all outputs (PR comment, Slack, workflow summary).

**Current State:**
- PR comment shows aggregate cost + token totals via `CostBreakdown.format_for_github()`
- Slack receives only `MAIN_COST`/`SUMMARY_COST` floats via environment variables
- Workflow summary has no cost information

**Changes Required:**

1. **Extend `CostBreakdown` domain model:**
   - Add `main_models: list[ModelUsage]` and `summary_models: list[ModelUsage]` fields
   - Update `from_execution_files()` to preserve per-model data
   - Add `format_model_breakdown()` method returning markdown table

2. **Update `format_for_github()` in `CostBreakdown`:**
   - Add per-model breakdown section after token usage:
   ```markdown
   ### Per-Model Breakdown

   | Model | Input | Output | Cache R | Cache W | Cost |
   |-------|-------|--------|---------|---------|------|
   | claude-haiku-4-5-20251001 | 4,274 | 597 | 0 | 24,546 | $0.037942 |
   | claude-3-haiku-20240307 | 21 | 729 | 135,239 | 45,809 | $0.018614 |
   | **Total** | 4,295 | 1,326 | 135,239 | 70,355 | **$0.056556** |
   ```

3. **Update `post_pr_comment.py`:**
   - Write model breakdown JSON as output for Slack to consume
   - Add `gh.write_output("model_breakdown", json.dumps(breakdown_data))`

4. **Update `notify_pr.py`:**
   - Parse `MODEL_BREAKDOWN` environment variable (JSON)
   - Update `format_pr_notification()` to include per-model table in Slack mrkdwn format

5. **Update `action.yml`:**
   - Pass `MODEL_BREAKDOWN` to notify step
   - Add step to write cost summary to `$GITHUB_STEP_SUMMARY` after `post_pr_comment`

6. **Add workflow summary output:**
   - Update `post_pr_comment.py` to write summary to `GITHUB_STEP_SUMMARY`
   - Include: task completed, PR link, cost breakdown, per-model table

**Tests:**
- `CostBreakdown.format_model_breakdown()` output format
- Updated `format_for_github()` includes model table
- `notify_pr.py` parses and formats model breakdown
- Integration test for full workflow output
