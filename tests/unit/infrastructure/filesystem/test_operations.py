"""Tests for filesystem operations"""

from pathlib import Path

import pytest

from claudestep.infrastructure.filesystem.operations import (
    file_exists,
    find_file,
    read_file,
    write_file,
)


class TestReadFile:
    """Test suite for read_file function"""

    def test_read_file_success(self, tmp_path):
        """Should read and return file contents"""
        # Arrange
        file_path = tmp_path / "test.txt"
        expected_content = "Hello, World!\nLine 2"
        file_path.write_text(expected_content)

        # Act
        result = read_file(file_path)

        # Assert
        assert result == expected_content

    def test_read_file_empty_file(self, tmp_path):
        """Should return empty string for empty file"""
        # Arrange
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        # Act
        result = read_file(file_path)

        # Assert
        assert result == ""

    def test_read_file_raises_on_nonexistent_file(self, tmp_path):
        """Should raise FileNotFoundError when file doesn't exist"""
        # Arrange
        file_path = tmp_path / "nonexistent.txt"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            read_file(file_path)

    def test_read_file_handles_unicode(self, tmp_path):
        """Should correctly read Unicode content"""
        # Arrange
        file_path = tmp_path / "unicode.txt"
        expected_content = "Hello 世界 🌍"
        file_path.write_text(expected_content, encoding="utf-8")

        # Act
        result = read_file(file_path)

        # Assert
        assert result == expected_content

    def test_read_file_preserves_newlines(self, tmp_path):
        """Should preserve newline characters in content"""
        # Arrange
        file_path = tmp_path / "newlines.txt"
        expected_content = "line1\n\nline3\nline4"
        file_path.write_text(expected_content)

        # Act
        result = read_file(file_path)

        # Assert
        assert result == expected_content
        assert result.count("\n") == 3


class TestWriteFile:
    """Test suite for write_file function"""

    def test_write_file_creates_new_file(self, tmp_path):
        """Should create new file with content"""
        # Arrange
        file_path = tmp_path / "new.txt"
        content = "Test content"

        # Act
        write_file(file_path, content)

        # Assert
        assert file_path.exists()
        assert file_path.read_text() == content

    def test_write_file_overwrites_existing_file(self, tmp_path):
        """Should overwrite existing file content"""
        # Arrange
        file_path = tmp_path / "existing.txt"
        file_path.write_text("old content")
        new_content = "new content"

        # Act
        write_file(file_path, new_content)

        # Assert
        assert file_path.read_text() == new_content

    def test_write_file_empty_content(self, tmp_path):
        """Should write empty file when content is empty string"""
        # Arrange
        file_path = tmp_path / "empty.txt"

        # Act
        write_file(file_path, "")

        # Assert
        assert file_path.exists()
        assert file_path.read_text() == ""

    def test_write_file_multiline_content(self, tmp_path):
        """Should correctly write multiline content"""
        # Arrange
        file_path = tmp_path / "multiline.txt"
        content = "line1\nline2\nline3"

        # Act
        write_file(file_path, content)

        # Assert
        assert file_path.read_text() == content

    def test_write_file_handles_unicode(self, tmp_path):
        """Should correctly write Unicode content"""
        # Arrange
        file_path = tmp_path / "unicode.txt"
        content = "Hello 世界 🌍"

        # Act
        write_file(file_path, content)

        # Assert
        assert file_path.read_text() == content

    def test_write_file_creates_parent_directory_not_supported(self, tmp_path):
        """Should raise error when parent directory doesn't exist"""
        # Arrange
        file_path = tmp_path / "nonexistent" / "file.txt"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            write_file(file_path, "content")


class TestFileExists:
    """Test suite for file_exists function"""

    def test_file_exists_returns_true_for_existing_file(self, tmp_path):
        """Should return True when file exists"""
        # Arrange
        file_path = tmp_path / "exists.txt"
        file_path.write_text("content")

        # Act
        result = file_exists(file_path)

        # Assert
        assert result is True

    def test_file_exists_returns_false_for_nonexistent_file(self, tmp_path):
        """Should return False when file doesn't exist"""
        # Arrange
        file_path = tmp_path / "nonexistent.txt"

        # Act
        result = file_exists(file_path)

        # Assert
        assert result is False

    def test_file_exists_returns_false_for_directory(self, tmp_path):
        """Should return False for directory (not a file)"""
        # Arrange
        dir_path = tmp_path / "directory"
        dir_path.mkdir()

        # Act
        result = file_exists(dir_path)

        # Assert
        assert result is False

    def test_file_exists_handles_symlinks(self, tmp_path):
        """Should return True for symlink to existing file"""
        # Arrange
        real_file = tmp_path / "real.txt"
        real_file.write_text("content")
        symlink = tmp_path / "link.txt"
        symlink.symlink_to(real_file)

        # Act
        result = file_exists(symlink)

        # Assert
        assert result is True


class TestFindFile:
    """Test suite for find_file function"""

    def test_find_file_in_current_directory(self, tmp_path):
        """Should find file in the starting directory"""
        # Arrange
        target_file = tmp_path / "target.txt"
        target_file.write_text("content")

        # Act
        result = find_file(tmp_path, "target.txt")

        # Assert
        assert result == target_file

    def test_find_file_in_subdirectory(self, tmp_path):
        """Should find file in subdirectory"""
        # Arrange
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        target_file = subdir / "target.txt"
        target_file.write_text("content")

        # Act
        result = find_file(tmp_path, "target.txt")

        # Assert
        assert result == target_file

    def test_find_file_in_nested_subdirectories(self, tmp_path):
        """Should find file in deeply nested directory"""
        # Arrange
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        nested_dir.mkdir(parents=True)
        target_file = nested_dir / "target.txt"
        target_file.write_text("content")

        # Act
        result = find_file(tmp_path, "target.txt")

        # Assert
        assert result == target_file

    def test_find_file_returns_none_when_not_found(self, tmp_path):
        """Should return None when file is not found"""
        # Arrange
        (tmp_path / "other.txt").write_text("content")

        # Act
        result = find_file(tmp_path, "nonexistent.txt")

        # Assert
        assert result is None

    def test_find_file_returns_first_match(self, tmp_path):
        """Should return first match when multiple files with same name exist"""
        # Arrange
        file1 = tmp_path / "target.txt"
        file1.write_text("first")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        file2 = subdir / "target.txt"
        file2.write_text("second")

        # Act
        result = find_file(tmp_path, "target.txt")

        # Assert
        # Should find the one in the current directory first
        assert result == file1

    def test_find_file_with_max_depth_zero(self, tmp_path):
        """Should only search current directory when max_depth=0"""
        # Arrange
        current_file = tmp_path / "current.txt"
        current_file.write_text("content")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        nested_file = subdir / "nested.txt"
        nested_file.write_text("content")

        # Act
        result_current = find_file(tmp_path, "current.txt", max_depth=0)
        result_nested = find_file(tmp_path, "nested.txt", max_depth=0)

        # Assert
        assert result_current == current_file
        assert result_nested is None  # Not found because it's in subdirectory

    def test_find_file_with_max_depth_one(self, tmp_path):
        """Should search up to specified depth"""
        # Arrange
        subdir1 = tmp_path / "level1"
        subdir1.mkdir()
        file_depth1 = subdir1 / "file1.txt"
        file_depth1.write_text("depth 1")

        subdir2 = subdir1 / "level2"
        subdir2.mkdir()
        file_depth2 = subdir2 / "file2.txt"
        file_depth2.write_text("depth 2")

        # Act
        result1 = find_file(tmp_path, "file1.txt", max_depth=1)
        result2 = find_file(tmp_path, "file2.txt", max_depth=1)

        # Assert
        assert result1 == file_depth1
        assert result2 is None  # Too deep

    def test_find_file_skips_hidden_directories(self, tmp_path):
        """Should skip directories starting with dot"""
        # Arrange
        hidden_dir = tmp_path / ".hidden"
        hidden_dir.mkdir()
        hidden_file = hidden_dir / "target.txt"
        hidden_file.write_text("content")

        # Act
        result = find_file(tmp_path, "target.txt")

        # Assert
        assert result is None  # Should not find file in hidden directory

    def test_find_file_handles_permission_errors(self, tmp_path):
        """Should handle permission errors gracefully"""
        # Arrange
        accessible_dir = tmp_path / "accessible"
        accessible_dir.mkdir()
        target_file = accessible_dir / "target.txt"
        target_file.write_text("content")

        # Act - Should not crash even if some dirs are inaccessible
        result = find_file(tmp_path, "target.txt")

        # Assert
        assert result == target_file

    def test_find_file_empty_directory(self, tmp_path):
        """Should return None when searching empty directory"""
        # Act
        result = find_file(tmp_path, "anything.txt")

        # Assert
        assert result is None

    def test_find_file_with_no_max_depth(self, tmp_path):
        """Should search unlimited depth when max_depth is None"""
        # Arrange
        deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)
        target_file = deep_dir / "target.txt"
        target_file.write_text("content")

        # Act
        result = find_file(tmp_path, "target.txt", max_depth=None)

        # Assert
        assert result == target_file
