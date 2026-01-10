# ABOUTME: Natural language processing module for free-text command parsing.
# ABOUTME: Uses rule-based parsing with fuzzy string matching via rapidfuzz.

from terminal_client.nlp.cli_context_adapter import CLIContextAdapter
from terminal_client.nlp.command_parser import CommandParser, ParseResult

__all__ = ["CommandParser", "ParseResult", "CLIContextAdapter"]
