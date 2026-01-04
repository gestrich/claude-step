"""Domain constants for ClaudeChain application.

Defines application-wide default values and constants that are reusable
across different layers of the application.
"""

# Default GitHub label for ClaudeChain PRs
DEFAULT_PR_LABEL = "claudechain"

# Default base branch
DEFAULT_BASE_BRANCH = "main"

# Default metadata branch
DEFAULT_METADATA_BRANCH = "claudechain-metadata"

# Default statistics lookback period (days)
DEFAULT_STATS_DAYS_BACK = 30

# Default number of days before a PR is considered stale
DEFAULT_STALE_PR_DAYS = 7

# Default allowed tools for Claude Code execution
# Minimal permissions: file operations + git staging/committing (required by ClaudeChain prompt)
# Users can override via CLAUDE_ALLOWED_TOOLS env var or project's allowedTools config
DEFAULT_ALLOWED_TOOLS = "Read,Write,Edit,Bash(git add:*),Bash(git commit:*)"

# PR Summary file path (used by action.yml and commands)
PR_SUMMARY_FILE_PATH = "/tmp/pr-summary.md"
