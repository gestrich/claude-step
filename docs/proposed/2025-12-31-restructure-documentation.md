## Background

The ClaudeStep documentation has grown organically and needs reorganization to improve maintainability and discoverability. The current structure mixes:
- User-facing guides with developer architecture docs
- General patterns with feature-specific technical documentation
- Durable documentation with ephemeral implementation specs

### Current Structure Problems
1. `docs/architecture/` contains both general patterns and feature-specific docs (e.g., `e2e-testing.md`)
2. `docs/completed/` has 40+ implementation specs that should be archived or have durable knowledge extracted
3. No clear separation between patterns (how we build) and features (how specific things work)
4. User guides in `user-guides/` should be more clearly named as feature guides

### Target Structure

```
docs/
├── README.md                          # Navigation guide
├── feature-guides/                    # User-facing feature guides
│   └── README.md
├── feature-architecture/              # Feature-specific technical docs & API reference
│   └── README.md
├── general-architecture/              # General architecture & coding patterns
│   └── README.md
└── specs/                             # Ephemeral implementation notes
    ├── README.md
    ├── active/
    └── archive/
```

### Key Principles
1. **Feature-focused organization**: Feature guides for users, feature architecture for developers
2. **General vs Specific**: General patterns separate from feature-specific implementation
3. **Durable vs Ephemeral**: Extract knowledge from specs, then archive with date prefixes
4. **Clear navigation**: Each directory has a README explaining its purpose

## Phases

- [x] Phase 1: Create new directory structure and navigation

Create the new directory structure without moving any existing files yet:
- Create `docs/feature-guides/` directory
- Create `docs/feature-architecture/` directory
- Create `docs/general-architecture/` directory
- Create `docs/specs/active/` directory
- Create `docs/specs/archive/` directory
- Create `docs/README.md` with navigation guide
- Create `docs/feature-guides/README.md` explaining user-facing feature guides
- Create `docs/feature-architecture/README.md` explaining feature technical docs
- Create `docs/general-architecture/README.md` explaining general patterns
- Create `docs/specs/README.md` explaining ephemeral nature and lifecycle

**Files to create:**
- `docs/README.md`
- `docs/feature-guides/README.md`
- `docs/feature-architecture/README.md`
- `docs/general-architecture/README.md`
- `docs/specs/README.md`

**Completion Notes:**
- All directories created successfully
- All README files written with clear navigation and guidance
- Build passes (658/663 tests pass - 4 pre-existing failures unrelated to documentation)
- Documentation structure is ready for content migration in subsequent phases

- [ ] Phase 2: Move user guides to feature-guides

Simple rename/move of user-facing documentation:
- Move `docs/user-guides/getting-started.md` → `docs/feature-guides/getting-started.md`
- Move `docs/user-guides/modifying-tasks.md` → `docs/feature-guides/modifying-tasks.md`
- Delete empty `docs/user-guides/` directory

**Files affected:**
- `docs/user-guides/getting-started.md` → `docs/feature-guides/getting-started.md`
- `docs/user-guides/modifying-tasks.md` → `docs/feature-guides/modifying-tasks.md`

- [ ] Phase 3: Reorganize general architecture patterns

Move general architecture and coding patterns to the new general-architecture directory:
- Move `docs/architecture/python-code-style.md` → `docs/general-architecture/python-style.md`
- Extract service layer content from `docs/architecture/architecture.md` → `docs/general-architecture/service-layer-pattern.md`
- Extract domain model content from relevant completed specs → `docs/general-architecture/domain-model-design.md`
- Extract command dispatcher content from `docs/architecture/architecture.md` → `docs/general-architecture/command-dispatcher.md`
- Merge `docs/architecture/testing-guide.md`, `docs/architecture/tests.md`, and `docs/architecture/local-testing.md` → `docs/general-architecture/testing-philosophy.md`
- Extract GitHub Actions conventions from `docs/architecture/architecture.md` → `docs/general-architecture/github-actions.md`

**Files to create:**
- `docs/general-architecture/python-style.md` (moved)
- `docs/general-architecture/service-layer-pattern.md` (extracted)
- `docs/general-architecture/domain-model-design.md` (extracted)
- `docs/general-architecture/command-dispatcher.md` (extracted)
- `docs/general-architecture/testing-philosophy.md` (merged)
- `docs/general-architecture/github-actions.md` (extracted)

**Files to delete:**
- `docs/architecture/testing-guide.md`
- `docs/architecture/tests.md`
- `docs/architecture/local-testing.md`
- Original `docs/architecture/architecture.md` (after extraction)

- [ ] Phase 4: Extract feature architecture from completed specs

Identify completed specs with durable architecture knowledge and extract to feature architecture docs:
- Extract from `docs/completed/pr-summary-feature-plan.md` → `docs/feature-architecture/pr-summarization.md`
  - Keep: Architecture Decision, Technical Details, Trade-offs
  - Remove: Implementation checklists, verification logs, file change lists
- Extract from `docs/completed/hash-based-task-identification.md` → `docs/feature-architecture/task-identification.md`
- Extract from `docs/completed/formalize-service-layer-pattern.md` → merge into `docs/general-architecture/service-layer-pattern.md`
- Extract from `docs/completed/github-pr-service-abstraction.md` → `docs/feature-architecture/github-integration.md`
- Move `docs/architecture/e2e-testing.md` → `docs/feature-architecture/e2e-testing.md`

**Files to create:**
- `docs/feature-architecture/pr-summarization.md`
- `docs/feature-architecture/task-identification.md`
- `docs/feature-architecture/github-integration.md`
- `docs/feature-architecture/e2e-testing.md` (moved)

**Extraction criteria:**
- ✅ Include: Architecture decisions, technical design, algorithms, data structures, integration points, trade-offs
- ❌ Exclude: Implementation checklists, verification logs, file change lists, temporary notes

- [ ] Phase 5: Move API reference to feature-architecture

Move API documentation to feature-architecture directory (treating it as technical feature docs):
- Move `docs/api.md` → `docs/feature-architecture/api-reference.md`
- Move `docs/metadata-branch-README.md` → `docs/feature-architecture/metadata-branch.md` (or delete if obsolete)

**Files affected:**
- `docs/api.md` → `docs/feature-architecture/api-reference.md`
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
- Update `CLAUDE.md` to reference new structure (feature-guides/, feature-architecture/, general-architecture/)
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
- Delete empty `docs/user-guides/`, `docs/proposed/`, `docs/completed/`, `docs/architecture/`
- Remove any remaining old architecture files that were fully extracted/merged
- Final verification that no broken links exist

**Directories to delete:**
- `docs/user-guides/`
- `docs/proposed/`
- `docs/completed/`
- `docs/architecture/`

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
