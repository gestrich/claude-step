"""Parse Claude Code execution result.

Reads the JSON execution file from claude-code-action and extracts
the structured output to determine success/failure and error messages.
"""

import json
import os
from typing import Any

from claudechain.infrastructure.github.actions import GitHubActionsHelper


def cmd_parse_claude_result(
    gh: GitHubActionsHelper,
    execution_file: str,
    result_type: str = "main",
) -> int:
    """Parse Claude Code execution result from JSON file.

    Reads the execution file and extracts structured_output to determine
    if the task completed successfully.

    Args:
        gh: GitHub Actions helper instance
        execution_file: Path to the Claude Code execution JSON file
        result_type: Type of result being parsed ("main" or "summary")

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if not execution_file:
        print(f"No execution file provided for {result_type} task")
        gh.write_output("success", "false")
        gh.write_output("error_message", "No execution file provided")
        return 0  # Not an error in the parsing itself

    if not os.path.exists(execution_file):
        print(f"Execution file not found: {execution_file}")
        gh.write_output("success", "false")
        gh.write_output("error_message", f"Execution file not found: {execution_file}")
        return 0  # Not an error in the parsing itself

    try:
        with open(execution_file, "r") as f:
            execution_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Failed to parse execution file as JSON: {e}")
        gh.write_output("success", "false")
        gh.write_output("error_message", f"Invalid JSON in execution file: {e}")
        return 0

    # Extract structured output from the execution data
    structured_output = _extract_structured_output(execution_data)

    if structured_output is None:
        # No structured output found - this might happen if Claude didn't
        # produce the expected JSON format
        print("No structured output found in execution file")
        # Default to success if Claude ran but didn't produce structured output
        # This maintains backward compatibility
        gh.write_output("success", "true")
        gh.write_output("error_message", "")
        gh.write_output("summary", "")
        return 0

    # Extract fields from structured output
    success = structured_output.get("success", True)
    error_message = structured_output.get("error_message", "")

    # Main task has "summary", summary task has "summary_content"
    summary = structured_output.get("summary", "") or structured_output.get("summary_content", "")

    # Write outputs
    gh.write_output("success", "true" if success else "false")
    gh.write_output("error_message", error_message)
    gh.write_output("summary", summary)

    if success:
        print(f"✅ Claude Code {result_type} task completed successfully")
        if summary:
            print(f"   Summary: {summary[:100]}..." if len(summary) > 100 else f"   Summary: {summary}")
        return 0
    else:
        print(f"❌ Claude Code {result_type} task failed")
        if error_message:
            print(f"   Error: {error_message}")
        return 1


def _extract_structured_output(execution_data: Any) -> dict[str, Any] | None:
    """Extract structured_output from Claude Code execution data.

    The execution file format when using --verbose contains a list of events.
    The structured output is in the last element's result.structured_output field.

    When not using --verbose, the execution_data may be the direct result object.

    Args:
        execution_data: Parsed JSON from execution file

    Returns:
        The structured output dict, or None if not found
    """
    # Handle case where execution_data is a list (verbose mode)
    if isinstance(execution_data, list) and execution_data:
        # Look for the last element with structured_output
        for item in reversed(execution_data):
            if isinstance(item, dict):
                # Check for result.structured_output pattern
                result = item.get("result", {})
                if isinstance(result, dict) and "structured_output" in result:
                    return result["structured_output"]
                # Check for direct structured_output
                if "structured_output" in item:
                    return item["structured_output"]

    # Handle case where execution_data is a dict
    if isinstance(execution_data, dict):
        # Direct structured_output
        if "structured_output" in execution_data:
            return execution_data["structured_output"]
        # Nested in result
        result = execution_data.get("result", {})
        if isinstance(result, dict) and "structured_output" in result:
            return result["structured_output"]

    return None
