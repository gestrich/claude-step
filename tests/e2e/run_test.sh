#!/bin/bash

# =============================================================================
# E2E TESTS TEMPORARILY DISABLED
# =============================================================================
# These tests are disabled because they require a specific GitHub Actions
# environment and workflow setup that is not always available. The tests
# interact with real GitHub workflows and can fail due to external factors
# (workflow timeouts, GitHub API issues, etc.).
#
# To re-enable: Remove this exit statement.
# =============================================================================
echo "E2E tests temporarily disabled - see run_test.sh for details"
exit 0

# End-to-End Test Runner for ClaudeChain
#
# This script triggers the E2E integration tests for ClaudeChain remotely on GitHub.
# All test execution happens on GitHub's infrastructure, avoiding local git mutations.
#
# Prerequisites:
# - GitHub CLI (gh) installed and authenticated
# - Repository write access to trigger workflows
# - ANTHROPIC_API_KEY configured as a repository secret
#
# Usage:
#   ./tests/e2e/run_test.sh
#
# The script will:
# 1. Check prerequisites (gh CLI authentication)
# 2. Force push current HEAD to main-e2e branch (ensures fresh test infrastructure)
# 3. Trigger the e2e-test.yml workflow on main-e2e
# 4. Monitor the workflow execution and stream logs to the terminal
# 5. Report success/failure with proper exit codes
#
# Note: Tests run via pytest on GitHub's runners. You do NOT need Python or pytest
# installed locally. All git operations happen remotely on the ephemeral main-e2e branch.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# E2E test branch name
E2E_BRANCH="main-e2e"

echo "========================================"
echo "ClaudeChain E2E Test Runner"
echo "========================================"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}ERROR: GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi
echo -e "${GREEN}✓${NC} GitHub CLI (gh) is installed"

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}ERROR: GitHub CLI is not authenticated${NC}"
    echo "Run: gh auth login"
    exit 1
fi
echo -e "${GREEN}✓${NC} GitHub CLI is authenticated"

# Get current HEAD info
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
CURRENT_SHA=$(git rev-parse --short HEAD)
echo -e "${GREEN}✓${NC} Current branch: ${CURRENT_BRANCH} (${CURRENT_SHA})"

# Force push HEAD to main-e2e
echo ""
echo "========================================"
echo "Pushing to ${E2E_BRANCH}"
echo "========================================"
echo ""
echo "Force pushing HEAD to ${E2E_BRANCH}..."
git push origin HEAD:${E2E_BRANCH} --force

if [ $? -ne 0 ]; then
    echo -e "${RED}✗${NC} Failed to push to ${E2E_BRANCH}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Pushed ${CURRENT_BRANCH} (${CURRENT_SHA}) to ${E2E_BRANCH}"

# Trigger the workflow
echo ""
echo "========================================"
echo "Triggering E2E Tests on GitHub"
echo "========================================"
echo ""
echo "Branch: ${E2E_BRANCH}"
echo "Workflow: e2e-test.yml"
echo ""

# Trigger the e2e-test.yml workflow on main-e2e
echo "Triggering workflow..."
gh workflow run e2e-test.yml --ref "${E2E_BRANCH}"

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}✗${NC} Failed to trigger workflow"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓${NC} Workflow triggered successfully!"
echo ""

# Wait a moment for the workflow run to be created
echo "Waiting for workflow run to start..."
sleep 5

# Get the most recent workflow run ID for this workflow and branch
RUN_ID=$(gh run list --workflow=e2e-test.yml --branch="${E2E_BRANCH}" --limit=1 --json databaseId --jq '.[0].databaseId')

if [ -z "$RUN_ID" ]; then
    echo -e "${YELLOW}Warning: Could not find workflow run ID${NC}"
    echo "The workflow may be queued. You can monitor it manually:"
    echo "  gh run list --workflow=e2e-test.yml"
    echo ""
    echo "Or visit: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/workflows/e2e-test.yml"
    echo ""
    exit 0
fi

echo "Workflow run ID: ${RUN_ID}"
echo ""
echo "========================================"
echo "Monitoring Workflow Execution"
echo "========================================"
echo ""
echo "Streaming logs from GitHub Actions..."
echo "Press Ctrl+C to stop monitoring (workflow will continue running)"
echo ""

# Watch the workflow run and stream logs
# The --exit-status flag makes gh run watch exit with the workflow's exit code
gh run watch "${RUN_ID}" --exit-status

WORKFLOW_EXIT_CODE=$?

echo ""
echo "========================================"
echo "Workflow Execution Complete"
echo "========================================"
echo ""

if [ $WORKFLOW_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ E2E Tests PASSED${NC}"
    echo ""
    echo "View detailed logs:"
    echo "  gh run view ${RUN_ID}"
    echo ""
    exit 0
else
    echo -e "${RED}✗ E2E Tests FAILED${NC}"
    echo ""
    echo "View detailed logs and errors:"
    echo "  gh run view ${RUN_ID}"
    echo ""
    echo "Or visit: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/actions/runs/${RUN_ID}"
    echo ""
    exit 1
fi
