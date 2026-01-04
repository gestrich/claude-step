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
