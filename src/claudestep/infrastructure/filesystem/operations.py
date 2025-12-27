"""Filesystem operations"""

from pathlib import Path
from typing import Optional


def read_file(path: Path) -> str:
    """Read file contents as string

    Args:
        path: Path to file to read

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read
    """
    return path.read_text()


def write_file(path: Path, content: str) -> None:
    """Write string content to file

    Args:
        path: Path to file to write
        content: Content to write

    Raises:
        IOError: If file cannot be written
    """
    path.write_text(content)


def file_exists(path: Path) -> bool:
    """Check if file exists

    Args:
        path: Path to check

    Returns:
        True if file exists, False otherwise
    """
    return path.exists() and path.is_file()


def find_file(start_dir: Path, filename: str, max_depth: Optional[int] = None) -> Optional[Path]:
    """Find a file by name starting from a directory

    Args:
        start_dir: Directory to start searching from
        filename: Name of file to find
        max_depth: Maximum directory depth to search (None for unlimited)

    Returns:
        Path to file if found, None otherwise
    """
    def search(directory: Path, current_depth: int = 0) -> Optional[Path]:
        if max_depth is not None and current_depth > max_depth:
            return None

        # Check current directory
        candidate = directory / filename
        if candidate.is_file():
            return candidate

        # Search subdirectories
        try:
            for subdir in directory.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    result = search(subdir, current_depth + 1)
                    if result:
                        return result
        except PermissionError:
            pass

        return None

    return search(start_dir)
