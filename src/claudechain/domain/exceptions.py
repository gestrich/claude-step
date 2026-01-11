"""Custom exceptions for ClaudeChain operations"""


class ContinuousRefactoringError(Exception):
    """Base exception for continuous refactoring operations"""
    pass


class ConfigurationError(ContinuousRefactoringError):
    """Configuration file issues"""
    pass


class FileNotFoundError(ContinuousRefactoringError):
    """Missing required files"""
    pass


class GitError(ContinuousRefactoringError):
    """Git operation failures"""
    pass


class GitHubAPIError(ContinuousRefactoringError):
    """GitHub API call failures"""
    pass


class ActionScriptError(ContinuousRefactoringError):
    """Action script execution failures"""

    def __init__(self, script_path: str, exit_code: int, stdout: str = "", stderr: str = ""):
        self.script_path = script_path
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        message = f"Action script '{script_path}' failed with exit code {exit_code}"
        if stderr:
            message += f": {stderr[:500]}"
        super().__init__(message)
