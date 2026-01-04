"""Unit tests for domain exception classes"""

import pytest

from claudechain.domain.exceptions import (
    ContinuousRefactoringError,
    ConfigurationError,
    FileNotFoundError,
    GitError,
    GitHubAPIError,
)


class TestExceptionHierarchy:
    """Test suite for exception class hierarchy and inheritance"""

    def test_base_exception_can_be_raised(self):
        """Should be able to raise and catch ContinuousRefactoringError"""
        # Arrange & Act & Assert
        with pytest.raises(ContinuousRefactoringError):
            raise ContinuousRefactoringError("Test error")

    def test_base_exception_includes_message(self):
        """Should store error message in exception"""
        # Arrange
        message = "Something went wrong"

        # Act
        error = ContinuousRefactoringError(message)

        # Assert
        assert str(error) == message

    def test_configuration_error_inherits_from_base(self):
        """ConfigurationError should inherit from ContinuousRefactoringError"""
        # Act
        error = ConfigurationError("Config issue")

        # Assert
        assert isinstance(error, ContinuousRefactoringError)
        assert isinstance(error, Exception)

    def test_file_not_found_error_inherits_from_base(self):
        """FileNotFoundError should inherit from ContinuousRefactoringError"""
        # Act
        error = FileNotFoundError("File missing")

        # Assert
        assert isinstance(error, ContinuousRefactoringError)
        assert isinstance(error, Exception)

    def test_git_error_inherits_from_base(self):
        """GitError should inherit from ContinuousRefactoringError"""
        # Act
        error = GitError("Git failure")

        # Assert
        assert isinstance(error, ContinuousRefactoringError)
        assert isinstance(error, Exception)

    def test_github_api_error_inherits_from_base(self):
        """GitHubAPIError should inherit from ContinuousRefactoringError"""
        # Act
        error = GitHubAPIError("API failure")

        # Assert
        assert isinstance(error, ContinuousRefactoringError)
        assert isinstance(error, Exception)


class TestConfigurationError:
    """Test suite for ConfigurationError exception"""

    def test_can_catch_configuration_error(self):
        """Should be able to catch ConfigurationError specifically"""
        # Arrange
        message = "Invalid config file"

        # Act & Assert
        with pytest.raises(ConfigurationError, match="Invalid config file"):
            raise ConfigurationError(message)

    def test_can_catch_as_base_exception(self):
        """Should be able to catch ConfigurationError as base type"""
        # Act & Assert
        with pytest.raises(ContinuousRefactoringError):
            raise ConfigurationError("Config problem")


class TestFileNotFoundError:
    """Test suite for FileNotFoundError exception"""

    def test_can_catch_file_not_found_error(self):
        """Should be able to catch FileNotFoundError specifically"""
        # Arrange
        message = "spec.md not found"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="spec.md not found"):
            raise FileNotFoundError(message)

    def test_can_catch_as_base_exception(self):
        """Should be able to catch FileNotFoundError as base type"""
        # Act & Assert
        with pytest.raises(ContinuousRefactoringError):
            raise FileNotFoundError("Missing file")


class TestGitError:
    """Test suite for GitError exception"""

    def test_can_catch_git_error(self):
        """Should be able to catch GitError specifically"""
        # Arrange
        message = "git command failed: exit code 1"

        # Act & Assert
        with pytest.raises(GitError, match="git command failed"):
            raise GitError(message)

    def test_can_catch_as_base_exception(self):
        """Should be able to catch GitError as base type"""
        # Act & Assert
        with pytest.raises(ContinuousRefactoringError):
            raise GitError("Git operation failed")


class TestGitHubAPIError:
    """Test suite for GitHubAPIError exception"""

    def test_can_catch_github_api_error(self):
        """Should be able to catch GitHubAPIError specifically"""
        # Arrange
        message = "GitHub API rate limit exceeded"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="rate limit exceeded"):
            raise GitHubAPIError(message)

    def test_can_catch_as_base_exception(self):
        """Should be able to catch GitHubAPIError as base type"""
        # Act & Assert
        with pytest.raises(ContinuousRefactoringError):
            raise GitHubAPIError("API call failed")


class TestExceptionCatchPatterns:
    """Test suite for common exception catching patterns"""

    def test_can_catch_all_custom_exceptions_with_base(self):
        """Should catch any custom exception using base exception type"""
        # Arrange
        exceptions = [
            ConfigurationError("Config error"),
            FileNotFoundError("File error"),
            GitError("Git error"),
            GitHubAPIError("API error"),
        ]

        # Act & Assert
        for error in exceptions:
            with pytest.raises(ContinuousRefactoringError):
                raise error

    def test_exceptions_preserve_original_message(self):
        """Should preserve error messages across all exception types"""
        # Arrange
        test_cases = [
            (ConfigurationError, "Invalid reviewers configuration"),
            (FileNotFoundError, "Could not find configuration.yml"),
            (GitError, "Failed to create branch"),
            (GitHubAPIError, "Authentication failed"),
        ]

        # Act & Assert
        for exception_class, message in test_cases:
            error = exception_class(message)
            assert str(error) == message
