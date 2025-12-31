## Background

The ClaudeStep documentation has grown organically and needs reorganization to improve maintainability and discoverability. The current structure mixes:
- User-facing guides with developer architecture docs
- General patterns with feature-specific technical documentation
- Durable documentation with ephemeral implementation specs

### Current Structure Problems
1. `docs/architecture/` contains both general patterns and feature-specific docs (e.g., `e2e-testing.md`)
2. `docs/completed/` has 40+ implementation specs that should be archived or have durable knowledge extracted
3. No clear separation between patterns (how we build) and features (how specific things work)
4. User guides in `user-guides/` should be in `guides/` for consistency

### Target Structure

```
docs/
├── README.md                          # Navigation guide
├── guides/                            # User-facing feature guides
├── architecture/
│   ├── README.md
│   ├── patterns/                      # Architecture & coding patterns
│   └── features/                      # Feature-specific technical docs
├── reference/                         # API reference
└── specs/                             # Ephemeral implementation notes
    ├── README.md
    ├── active/
    └── archive/
```

### Key Principles
1. **Three-tier documentation**: guides (users), architecture (developers), specs (ephemeral)
2. **Patterns vs Features**: General patterns in `patterns/`, feature-specific in `features/`
3. **Durable vs Ephemeral**: Extract knowledge from specs, then archive with date prefixes
4. **Clear navigation**: Each directory has a README explaining its purpose

## Phases

- [ ] Phase 1: Create new directory structure and navigation

Create the new directory structure without moving any existing files yet:
- Create `docs/guides/` directory
- Create `docs/architecture/patterns/` directory
- Create `docs/architecture/features/` directory
- Create `docs/reference/` directory
- Create `docs/specs/active/` directory
- Create `docs/specs/archive/` directory
- Create `docs/README.md` with navigation guide
- Create `docs/architecture/README.md` with overview and index
- Create `docs/architecture/patterns/README.md` explaining patterns
- Create `docs/architecture/features/README.md` explaining feature docs
- Create `docs/specs/README.md` explaining ephemeral nature and lifecycle

**Files to create:**
- `docs/README.md`
- `docs/architecture/README.md`
- `docs/architecture/patterns/README.md`
- `docs/architecture/features/README.md`
- `docs/specs/README.md`

- [ ] Phase 2: Move user guides

Simple rename/move of user-facing documentation:
- Move `docs/user-guides/getting-started.md` → `docs/guides/getting-started.md`
- Move `docs/user-guides/modifying-tasks.md` → `docs/guides/modifying-tasks.md`
- Delete empty `docs/user-guides/` directory

**Files affected:**
- `docs/user-guides/getting-started.md` → `docs/guides/getting-started.md`
- `docs/user-guides/modifying-tasks.md` → `docs/guides/modifying-tasks.md`

- [ ] Phase 3: Reorganize architecture patterns

Move general architecture and coding patterns to the new patterns directory:
- Move `docs/architecture/python-code-style.md` → `docs/architecture/patterns/python-style.md`
- Extract service layer content from `docs/architecture/architecture.md` → `docs/architecture/patterns/service-layer-pattern.md`
- Extract domain model content from relevant completed specs → `docs/architecture/patterns/domain-model-design.md`
- Extract command dispatcher content from `docs/architecture/architecture.md` → `docs/architecture/patterns/command-dispatcher.md`
- Merge `docs/architecture/testing-guide.md`, `docs/architecture/tests.md`, and `docs/architecture/local-testing.md` → `docs/architecture/patterns/testing-philosophy.md`
- Extract GitHub Actions conventions from `docs/architecture/architecture.md` → `docs/architecture/patterns/github-actions.md`

**Files to create:**
- `docs/architecture/patterns/python-style.md` (moved)
- `docs/architecture/patterns/service-layer-pattern.md` (extracted)
- `docs/architecture/patterns/domain-model-design.md` (extracted)
- `docs/architecture/patterns/command-dispatcher.md` (extracted)
- `docs/architecture/patterns/testing-philosophy.md` (merged)
- `docs/architecture/patterns/github-actions.md` (extracted)

**Files to delete:**
- `docs/architecture/testing-guide.md`
- `docs/architecture/tests.md`
- `docs/architecture/local-testing.md`
- Original `docs/architecture/architecture.md` (after extraction)

- [ ] Phase 4: Extract feature architecture from completed specs

Identify completed specs with durable architecture knowledge and extract to feature docs:
- Extract from `docs/completed/pr-summary-feature-plan.md` → `docs/architecture/features/pr-summarization.md`
  - Keep: Architecture Decision, Technical Details, Trade-offs
  - Remove: Implementation checklists, verification logs, file change lists
- Extract from `docs/completed/hash-based-task-identification.md` → `docs/architecture/features/task-identification.md`
- Extract from `docs/completed/formalize-service-layer-pattern.md` → merge into `docs/architecture/patterns/service-layer-pattern.md`
- Extract from `docs/completed/github-pr-service-abstraction.md` → `docs/architecture/features/github-integration.md`
- Move `docs/architecture/e2e-testing.md` → `docs/architecture/features/e2e-testing.md` (already good)

**Files to create:**
- `docs/architecture/features/pr-summarization.md`
- `docs/architecture/features/task-identification.md`
- `docs/architecture/features/github-integration.md`
- `docs/architecture/features/e2e-testing.md` (moved)

**Extraction criteria:**
- ✅ Include: Architecture decisions, technical design, algorithms, data structures, integration points, trade-offs
- ❌ Exclude: Implementation checklists, verification logs, file change lists, temporary notes

- [ ] Phase 5: Move API reference

Move API documentation to reference directory:
- Move `docs/api.md` → `docs/reference/api.md`
- Move `docs/metadata-branch-README.md` → `docs/reference/metadata-branch.md` (or delete if obsolete)

**Files affected:**
- `docs/api.md` → `docs/reference/api.md`
- `docs/metadata-branch-README.md` → evaluate and move/delete

- [ ] Phase 6: Archive implementation specs

Move ephemeral specs to appropriate locations:
- Move `docs/proposed/*.md` → `docs/specs/active/*.md`
- Move `docs/completed/*.md` → `docs/specs/archive/*.md` with date prefixes
  - Extract year/month from git commit history for each file
  - Rename with format: `YYYY-MM-description.md` (e.g., `2024-12-formalize-service-layer.md`)
- Delete empty `docs/proposed/` and `docs/completed/` directories

**Files affected:**
- All files in `docs/proposed/` → `docs/specs/active/`
- All files in `docs/completed/` → `docs/specs/archive/` with date prefixes

- [ ] Phase 7: Update cross-references

Update references between documents and from CLAUDE.md:
- Update `CLAUDE.md` to reference new structure (guides/, architecture/)
- Update any internal cross-references in moved documents
- Update README navigation links to point to new locations
- Check for any broken links in architecture docs

**Files to check/update:**
- `CLAUDE.md`
- All newly created README files
- Any documents with cross-references

- [ ] Phase 8: Clean up old structure

Remove old directories and update any remaining references:
- Verify all content has been moved from old directories
- Delete empty `docs/user-guides/`, `docs/proposed/`, `docs/completed/`
- Remove any remaining old architecture files that were fully extracted/merged
- Final verification that no broken links exist

**Directories to delete:**
- `docs/user-guides/`
- `docs/proposed/`
- `docs/completed/`

- [ ] Phase 9: Validation

Verify the restructuring is complete and functional:
- **Directory structure check**: Confirm all new directories exist with READMEs
- **Content migration check**: Verify all user guides, architecture docs, and specs have been moved
- **Cross-reference check**: Test that all internal links work correctly
- **CLAUDE.md check**: Verify the project instructions reference the correct new paths
- **Git status check**: Review all changes before committing
- **Manual review**: Read through main navigation READMEs to ensure clarity

**Success criteria:**
- All documentation is in the new structure
- No broken cross-references
- Clear navigation through README files
- CLAUDE.md points to correct locations
- Old directories are removed
