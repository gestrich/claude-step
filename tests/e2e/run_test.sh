#!/bin/bash

# End-to-End Test Runner for ClaudeStep
#
# This script runs the E2E integration tests for ClaudeStep.
# It verifies prerequisites and executes the test suite.
#
# Prerequisites:
# - GitHub CLI (gh) installed and authenticated
# - Python 3.11+ with pytest installed
# - Repository write access
# - ANTHROPIC_API_KEY environment variable set (for workflow runs)
#
# Usage:
#   ./tests/e2e/run_test.sh [pytest-args]
#
# Examples:
#   ./tests/e2e/run_test.sh                    # Run all E2E tests
#   ./tests/e2e/run_test.sh -v                 # Verbose output
#   ./tests/e2e/run_test.sh -k statistics      # Run only statistics tests
#   ./tests/e2e/run_test.sh --pdb              # Drop into debugger on failure

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "ClaudeStep E2E Test Runner"
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

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}ERROR: pytest is not installed${NC}"
    echo "Install it with: pip install pytest"
    exit 1
fi
echo -e "${GREEN}✓${NC} pytest is installed"

# Check if Python 3.11+ is available
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.11"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo -e "${RED}ERROR: Python 3.11+ is required (found: ${PYTHON_VERSION})${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python ${PYTHON_VERSION} is installed"

# Check if git is configured
if ! git config user.name &> /dev/null || ! git config user.email &> /dev/null; then
    echo -e "${RED}ERROR: Git is not configured${NC}"
    echo "Run:"
    echo "  git config --global user.name 'Your Name'"
    echo "  git config --global user.email 'your.email@example.com'"
    exit 1
fi
echo -e "${GREEN}✓${NC} Git is configured"

# Check if we're in the correct directory
if [ ! -f "tests/e2e/test_workflow_e2e.py" ]; then
    echo -e "${RED}ERROR: Must run from repository root${NC}"
    echo "Current directory: $(pwd)"
    echo "Expected to find: tests/e2e/test_workflow_e2e.py"
    exit 1
fi
echo -e "${GREEN}✓${NC} Running from repository root"

# Check for required dependencies
echo ""
echo "Checking Python dependencies..."
if ! python3 -c "import yaml" 2>/dev/null; then
    echo -e "${YELLOW}WARNING: PyYAML is not installed${NC}"
    echo "Installing PyYAML..."
    pip install pyyaml
fi
echo -e "${GREEN}✓${NC} Python dependencies are available"

# Optional: Check if ANTHROPIC_API_KEY is set
echo ""
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo -e "${YELLOW}WARNING: ANTHROPIC_API_KEY environment variable is not set${NC}"
    echo "The E2E tests will trigger workflows that require this API key."
    echo "Tests may fail if the repository secret is not configured."
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborting."
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} ANTHROPIC_API_KEY is set"
fi

# Run the tests
echo ""
echo "========================================"
echo "Running E2E Tests"
echo "========================================"
echo ""

# Change to repository root (in case script is called from elsewhere)
cd "$(git rev-parse --show-toplevel)"

# Run pytest with E2E tests
# Pass through any additional arguments (e.g., -v, -k, --pdb)
# Note: --no-cov disables coverage checks since E2E tests run code in remote workflows
pytest tests/e2e/ --no-cov "$@"

# Capture exit code
EXIT_CODE=$?

echo ""
echo "========================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}E2E Tests Passed${NC}"
else
    echo -e "${RED}E2E Tests Failed${NC}"
fi
echo "========================================"

exit $EXIT_CODE
