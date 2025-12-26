"""
Extract cost information from Claude Code action execution file.
"""

import json
import os
from typing import Optional


def cmd_extract_cost(args, gh):
    """
    Extract cost from a Claude Code action execution file.

    Reads from environment:
    - EXECUTION_FILE: Path to the Claude Code execution output file

    Outputs:
    - cost_usd: The total cost in USD (or "0" if not found)
    """
    # Get required environment variable
    execution_file = os.environ.get("EXECUTION_FILE", "").strip()

    if not execution_file:
        gh.set_error("EXECUTION_FILE environment variable is required")
        return 1

    try:
        # Read and parse the execution file
        print(f"Reading execution file: {execution_file}")

        if not os.path.exists(execution_file):
            print(f"::warning::Execution file not found: {execution_file}")
            gh.write_output("cost_usd", "0")
            return 0

        with open(execution_file, 'r') as f:
            data = json.load(f)

        # Debug: Check if data is a list or dict
        if isinstance(data, list):
            print(f"Execution file contains a list with {len(data)} items")
            # If it's a list, get the last item (most recent execution)
            if data:
                data = data[-1]
                print("Using the last item in the list")

        if isinstance(data, dict):
            print(f"Execution file top-level keys: {list(data.keys())[:20]}")
            if 'total_cost_usd' in data:
                print(f"Found total_cost_usd at top level: {data['total_cost_usd']}")

        # Extract cost from the execution data
        cost = extract_cost_from_execution(data)

        if cost is None:
            print("::warning::Could not find cost information in execution file")
            print("::debug::Execution file structure (first 500 chars):")
            print(f"::debug::{json.dumps(data, indent=2)[:500]}")
            gh.write_output("cost_usd", "0")
            return 0

        # Output the cost
        gh.write_output("cost_usd", f"{cost:.6f}")
        print(f"✅ Extracted cost: ${cost:.6f} USD")

        return 0

    except json.JSONDecodeError as e:
        gh.set_error(f"Failed to parse execution file as JSON: {str(e)}")
        gh.write_output("cost_usd", "0")
        return 0  # Don't fail the workflow, just default to 0
    except Exception as e:
        gh.set_error(f"Error extracting cost: {str(e)}")
        gh.write_output("cost_usd", "0")
        return 0  # Don't fail the workflow, just default to 0


def extract_cost_from_execution(data: dict) -> Optional[float]:
    """
    Extract total_cost_usd from Claude Code execution data.

    Args:
        data: Parsed JSON data from the execution file

    Returns:
        Cost in USD as float, or None if not found
    """
    # Try to get total_cost_usd from the top level
    if 'total_cost_usd' in data:
        try:
            return float(data['total_cost_usd'])
        except (ValueError, TypeError):
            pass

    # Try to get it from a nested structure if needed
    if 'usage' in data and 'total_cost_usd' in data['usage']:
        try:
            return float(data['usage']['total_cost_usd'])
        except (ValueError, TypeError):
            pass

    return None
