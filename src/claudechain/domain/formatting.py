"""Domain formatting utilities.

Provides consistent formatting functions for domain values like currency,
following project conventions for display across different outputs
(PR comments, Slack messages, statistics, etc.).
"""


def format_usd(amount: float) -> str:
    """Format a USD amount for display.

    Formats to standard US currency convention with dollar sign prefix
    and exactly 2 decimal places (cents).

    Args:
        amount: Amount in USD (e.g., 0.123456)

    Returns:
        Formatted string (e.g., "$0.12")

    Examples:
        >>> format_usd(0.123456)
        '$0.12'
        >>> format_usd(1.5)
        '$1.50'
        >>> format_usd(0.0)
        '$0.00'
        >>> format_usd(123.456)
        '$123.46'
    """
    return f"${amount:.2f}"
