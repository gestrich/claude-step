# README Improvements - Feedback Implementation

## ✅ Step 1: Update Overview and Features Sections (COMPLETED)

**Technical Notes:**
- Updated Overview to explain "ClaudeStep" name and PR chain mechanism (README.md:3-7)
- Replaced "Define once, run forever" with "Incremental automation" (README.md:11)
- Changed "Set and forget" to "Continuous flow" to better explain merge-triggered automation (README.md:13)
- Maintained emoji bullets and key messaging while improving clarity

### Overview
- Clarify why it's called "ClaudeStep": It runs Claude Code on individual steps that you define for your project, creating pull requests for each step one at a time
- Explain the chain: Allows you to integrate those pull requests when you have time and automatically stages the next pull request afterwards, creating a chain of steps

### Features
- Remove "Define once, run forever" tagline (confusing)
- Keep mention of automated PRs but use different phrasing
- Update feature list to be clearer

## ✅ Step 2: Fix Prerequisites and Installation Sections (COMPLETED)

**Technical Notes:**
- Removed "GitHub CLI (gh) installed and authenticated" from Prerequisites (README.md:19-22)
- Clarified that Claude Code GitHub App installation is remote GitHub configuration, not local (README.md:24-34)
- Added explanation of what the app is used for: "allows the action to interact with your repository" and "grants necessary permissions for Claude to read your spec and create pull requests"
- Improved wording to indicate the command is run locally but configures remotely

### Prerequisites
- Removed "GitHub CLI (gh) installed and authenticated" - this is a workflow thing, not a user prerequisite

### Install Claude Code GitHub App
- Made clearer that installation is at the repository level (GitHub repo level remotely)
- Clarified: "In your local repository directory, run this command in Claude Code"
- Explained what the GitHub app is used for in this project (kept concise)
- This is GitHub configuration happening remotely, not local installation

## ✅ Step 3: Reorganize GitHub Configuration (COMPLETED)

**Technical Notes:**
- Moved "Configure GitHub" section from Step 1 to Step 4 (after Workflow and Slack) (README.md:111-138)
- Renamed subsequent steps: Step 2→Add Workflow, Step 3→Slack Notifications, Step 4→Configure GitHub, Step 5→Run & Test, Step 6→Review & Iterate
- Consolidated all three GitHub configuration tasks under Step 4 as substeps:
  1. Add API Key (README.md:113-119)
  2. Enable PR Creation (README.md:121-126)
  3. Install Claude Code GitHub App (README.md:128-138)
- GitHub configuration now appears just before "Run & Test" section as planned

### Move and Consolidate
- Move "Configure GitHub" section to AFTER workflow setup and Slack notifications
- Place just before "Run & Test" section
- GitHub configuration is "inside baseball" - don't lead with it

### Configure GitHub should include (as substeps):
1. Add API Key
2. Enable PR Creation
3. Install Claude Code GitHub App

All three are GitHub configuration tasks and should be together.

## ✅ Step 4: Update Workflow and Run & Test Sections (COMPLETED)

**Technical Notes:**
- Renamed workflow file reference from `ai-refactor.yml` to `claude-step.yml` (README.md:66)
- Moved PR trigger note up to workflow creation section as YAML comment (README.md:76-78)
- Added "Push Changes to Main" subsection before "Trigger Initial Workflow" (README.md:146-152)
- Renamed "Manual Test" to "Trigger Initial Workflow" with updated explanation (README.md:154-164)
- Removed "If you fix issues, update spec.md in the same PR" sentence from Review the PR section (previously line 166)
- Removed entire "Improve" subsection (previously lines 173-180)
- Removed "Add Schedule Triggers" section and redundant PR trigger note (previously lines 216-226)

### Workflow File
- Rename from `ai-refactor.yml` to `claude-step.yml`

### Move PR Trigger Note
- Move note about "workflow triggers on both merged and closed-without-merging PRs" UP to the section where we create the workflow file with the merge/close trigger

### Run & Test Section
- Add new step before manual test: "Push your changes to your main branch"
- Clarify that your project (configuration, spec) needs to be merged into main branch before anything starts
- Change "Manual Test" to "Trigger Initial Workflow"
- Explain: Workflow will run automatically upon merge of each new PR, but for the first one, you need to trigger it manually to get the workflow going
- Mention: Assuming you set up the merge/close trigger, future PRs will be staged automatically

### Remove Sections
- Remove "If you fix issues, update spec.md in the same PR" sentence from Review the PR section
- Remove entire "Improve" subsection (about updating spec.md)
- Remove "Add Schedule Triggers" section

## ✅ Step 5: Create Project Name Refactor Implementation Plan (COMPLETED)

**Technical Notes:**
- Created comprehensive implementation plan at docs/proposed/projectrefactor.md
- Plan includes 4 phases: Update Action Trigger Logic, Manual Workflow Runs, Error Handling, and Update README
- Documented problem: current project_name input parameter doesn't work with PR merge/close triggers
- Solution design focuses on automatic project name derivation from PR events with fallback to manual input
- Included testing strategy for each phase
- Plan provides detailed implementation steps, technical considerations, and success criteria for each phase

**Created document: `docs/proposed/projectrefactor.md`**

This is a multi-phase implementation plan with the following requirements:

### Problem
Current implementation uses `project_name` as a required input parameter. This doesn't work well with PR merge/close triggers.

### Solution Design

#### Phase 1: Update Action Trigger Logic
- When action is triggered via PR that was closed or merged:
  - Pass PR number to the action
  - Action receives PR number and derives associated project name
  - Derive project from artifacts (last run check) - we may already have code for this
  - Use derived project name to run action

#### Phase 2: Manual Workflow Runs
- When action is NOT triggered by PR (manual workflow_dispatch):
  - User enters project name as input via GitHub UI
  - If no project name provided: throw error
  - Must always have project name from one of two sources:
    1. Derived from closed PR (via artifacts)
    2. Manually entered during workflow dispatch

#### Phase 3: Error Handling
- Validate that project name is always available
- Error if neither PR-derived nor manually-provided project name exists
- Clear error messages for debugging

#### Phase 4: Update README
- Last step of implementation
- Update README with this new information
- Document both trigger methods (PR-based and manual)
- Explain project name derivation

## Step 6: Update Input/Output Sections and Configuration

### Input Section Changes
- `add_pr_summary`: Clarify that summary is created right after PR is created (not on every change to PR)
- `pr_label`: Keep in input section, add default value if not specified
- Remove `pr_label` from `configuration.yml` - it should only be in inputs
- Remove note "All PRs are automatically labeled with `claudestep` for tracking purposes" (not true since label can be overridden)

### Configuration Section
- Move `label` field out of configuration.yml (moving to input)
- Keep `branchPrefix` and `reviewers` in configuration.yml

## Step 7: Reorganize Spec.md Section and Terminology

### Move Spec Section
- Section currently on line 360+ needs to move WAY UP
- Should be part of getting started flow
- This is core setup, not reference material

### Terminology Changes
- Replace all instances of "checklist" with "steps"
- Phrase as "Add your steps" not "Add checklist"
- Make clear each item is a step

### Remove Subsections
- Remove "Be specific with step descriptions" section
- Remove "Iterative Improvement" section
- Remove "Common Patterns for Organizing Steps" section

## Step 8: Consolidate Document Structure

### Goal
Make entire document one cohesive "0 to 100" setup guide. No scattered sections.

### Reorganization
- Everything is "getting started" - don't need separate Getting Started section
- Walk through setting everything up in one linear flow
- Include PR template section in main flow (not as separate "Advanced" section)
- Include Per-User PR Assignment with configuration section (only need one configuration section)

### Flow Should Be
1. Overview/Features
2. Prerequisites
3. Step-by-step setup (all in order):
   - Create project structure
   - Create spec with steps
   - Create configuration (include per-user assignment here)
   - Optional: PR template
   - Create workflow file (include trigger notes here)
   - Optional: Slack notifications
   - Configure GitHub (API key, permissions, app install)
   - Push to main
   - Trigger initial workflow
4. Reference sections (inputs/outputs, etc.)
5. Development, Support, Credits

## Step 9: Remove Redundant Sections

### Delete These Sections
- Trigger Modes (scheduled stuff already covered, manual dispatch covered in getting started, automatic PR merge is redundant)
- Validation section (don't need)
- Extra spec.md section (already moved up)
- "How It Works" section (redundant)
- Security section
- Limitations section
- Any duplicate "Quick Start" sections

### Consolidate
- Per-User PR Assignment should be with configuration section (not separate)
- Only one configuration reference section needed

## Step 10: Final Cleanup and Length Reduction

### Target
- Reduce document to approximately 2/3 of current length (from 658 lines to ~440 lines)

### Cleanup Tasks
- Remove all redundancy
- Tighten language throughout
- Ensure no repeated concepts
- Verify linear flow from start to finish
- Remove verbose explanations where concise ones suffice
- Ensure every section adds unique value

### Final Review
- Verify all feedback items addressed
- Check that document flows logically
- Confirm terminology is consistent (steps not tasks/checklist)
- Validate that it's a single cohesive guide
