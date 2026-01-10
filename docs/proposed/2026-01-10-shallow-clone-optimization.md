# Shallow Clone with On-Demand Ref Fetching

## Background

ClaudeChain currently uses `fetch-depth: 0` in the GitHub Actions checkout, which downloads the entire git history. For large repositories, this is slow and inefficient. Analysis of our git operations revealed that only a few operations actually require historical commits:

**Operations requiring history access:**
1. `git diff <ref_before> <ref_after>` - Used in auto-start to detect changed spec.md files between push refs
2. `git rev-list --count origin/{base}..HEAD` - Used in finalize to check if there are commits to push
3. `git push` - Needs ancestry information for the push

**Key insight:** The `ref_before` and `ref_after` in auto-start come from the push event payload - these are commits immediately before and after the push, not arbitrary historical refs. We can fetch these specific refs on-demand rather than downloading all history.

This approach is similar to how ForeFlight's `code-owner-status.yml` workflow handles large repo checkouts efficiently.

## Phases

- [x] Phase 1: Update action.yml to shallow clone

Change the checkout step in `action.yml` from `fetch-depth: 0` to `fetch-depth: 1`:

```yaml
- name: Checkout repository
  uses: actions/checkout@v4
  with:
    ref: ${{ steps.parse.outputs.checkout_ref }}
    fetch-depth: 1  # Shallow clone for performance
```

This alone will break the auto-start diff detection, which we fix in Phase 2.

- [x] Phase 2: Add on-demand ref fetching in git operations

Modify `src/claudechain/infrastructure/git/operations.py` to fetch refs before diffing:

In `detect_changed_files()` and `detect_deleted_files()`:
- Before running `git diff`, fetch the required refs with `git fetch --depth=1 origin <ref>`
- Handle the case where ref is already available (no-op)
- Handle fetch failures gracefully (log warning, possibly fall back to GitHub API)

Example implementation approach:
```python
def _ensure_ref_available(ref: str) -> None:
    """Fetch a ref if not already available locally."""
    try:
        # Check if ref exists locally
        run_git_command(["cat-file", "-t", ref])
    except GitError:
        # Ref not available, fetch it
        run_git_command(["fetch", "--depth=1", "origin", ref])
```

- [x] Phase 3: Update rev-list operation in finalize

The `git rev-list --count origin/{base}..HEAD` in `finalize.py:157` needs the base branch ref.

Options:
1. Fetch the base branch ref before the rev-list: `git fetch --depth=1 origin {base_branch}`
2. Alternative: Use `git cherry` or compare with remote tracking ref

Recommend option 1 for simplicity - add fetch before the rev-list check.

- [x] Phase 4: Verify push still works with shallow clone

Git push with shallow clones should work because:
- We're pushing a new branch (force push)
- The remote has full history
- Only the local side is shallow

Verify this works correctly in testing. If issues arise, may need to unshallow before push:
`git fetch --unshallow` (fallback, defeats purpose for large repos)

- [x] Phase 5: Validation

**Unit tests:**
- Add tests for the new `_ensure_ref_available()` helper
- Test `detect_changed_files()` behavior when ref needs fetching vs already available

**Integration tests:**
- Test auto-start workflow with shallow clone
- Test finalize workflow with shallow clone

**E2E tests:**
- Verify PRs are created successfully with shallow clone

**Manual verification:**
- Test on a large repository to confirm performance improvement
- Monitor GitHub Actions logs for fetch operations
