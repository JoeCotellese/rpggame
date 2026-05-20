# ABOUTME: Debug logging configuration for dual console/file output
# ABOUTME: Manages log file rotation, timestamps, and Rich console integration

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

# Maximum console width for readable output. Kept here for backwards
# compatibility with UI clients that import it; the engine itself no longer
# builds consoles.
MAX_CONSOLE_WIDTH = 100

# A console factory is given the active log-file handle (or None when debug is
# off) and returns whatever console object the UI client wants to use.
ConsoleFactory = Callable[[TextIO | None], Any]


class TeeFile:
    """
    File-like object that writes to both stdout and a log file.

    This allows Rich console output to be simultaneously displayed
    in the terminal and captured to a log file.
    """

    def __init__(self, file: TextIO, stdout: TextIO):
        """
        Initialize TeeFile.

        Args:
            file: Log file to write to
            stdout: Standard output stream
        """
        self.file = file
        self.stdout = stdout

    def write(self, text: str) -> int:
        """
        Write text to both file and stdout.

        Args:
            text: Text to write

        Returns:
            Number of characters written
        """
        # Write to stdout
        self.stdout.write(text)

        # Write to file (will be plain text without ANSI codes
        # because the console was created with force_terminal=False)
        self.file.write(text)

        return len(text)

    def flush(self) -> None:
        """Flush both streams."""
        self.stdout.flush()
        self.file.flush()

    def isatty(self) -> bool:
        """Return whether stdout is a TTY."""
        return self.stdout.isatty()


class LoggingConfig:
    """
    Manages debug logging configuration for the game.

    Responsibilities:
    - Create log directory
    - Generate timestamped log files
    - Rotate old log files (keep last 10)
    - Set up Python logging
    - Create dual-output Rich console
    """

    def __init__(
        self,
        debug_enabled: bool = False,
        console_factory: ConsoleFactory | None = None,
    ):
        """
        Initialize logging configuration.

        Args:
            debug_enabled: Whether debug mode is enabled
            console_factory: Optional callable that builds a UI console. It is
                invoked by ``create_console()`` and receives the active log
                file handle when debug mode is on, ``None`` otherwise. Keeps
                this module free of any UI-toolkit dependency; clients (e.g.
                the Rich-based terminal UI) inject their own factory.
        """
        self.debug_enabled = debug_enabled
        self.console_factory = console_factory
        self.log_file_path: Path | None = None
        self.log_file: TextIO | None = None
        self._event_counter = 0

        if debug_enabled:
            self._setup_logging()

    def _setup_logging(self) -> None:
        """Set up logging infrastructure."""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Generate log file name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = log_dir / f"dnd_game_{timestamp}.log"

        # Rotate old log files
        self._rotate_logs(log_dir)

        # Open log file with UTF-8 encoding
        self.log_file = open(self.log_file_path, "w", encoding="utf-8", buffering=1)

        # Set up Python logging
        self._setup_python_logging()

    def _rotate_logs(self, log_dir: Path, keep_count: int = 10) -> None:
        """
        Rotate log files, keeping only the most recent ones.

        Args:
            log_dir: Directory containing log files
            keep_count: Number of log files to keep
        """
        # Get all log files sorted by modification time (newest first)
        log_files = sorted(
            log_dir.glob("dnd_game_*.log"), key=lambda p: p.stat().st_mtime, reverse=True
        )

        # Delete old log files (keep only the most recent keep_count-1,
        # since we're about to create a new one)
        for old_log in log_files[keep_count - 1 :]:
            try:
                old_log.unlink()
            except OSError as e:
                # Log error but don't crash
                logging.error(f"Failed to delete old log file {old_log}: {e}")

    def _setup_python_logging(self) -> None:
        """Set up Python logging with file handler."""
        # Create logger
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG if self.debug_enabled else logging.INFO)

        # Create file handler
        if self.log_file_path:
            file_handler = logging.FileHandler(self.log_file_path, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)

            # Create formatter with timestamp
            formatter = logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)

            # Add handler to logger
            logger.addHandler(file_handler)

    def create_console(self) -> Any:
        """
        Build a UI console via the injected factory.

        The active log file is passed to the factory when debug mode is on
        (so the factory can wrap it for dual stdout/file output), and ``None``
        otherwise. When no factory was injected the engine has no UI to build,
        and this returns ``None`` — appropriate for headless callers.

        Returns:
            Whatever the factory returns, or ``None`` if no factory was given.
        """
        if self.console_factory is None:
            return None
        log_file = self.log_file if self.debug_enabled else None
        return self.console_factory(log_file)

    def log_event(self, event_type: str, data: dict) -> None:
        """
        Log a game event with metadata.

        Args:
            event_type: Type of event (e.g., "COMBAT_START")
            data: Event data dictionary
        """
        if not self.debug_enabled:
            return

        self._event_counter += 1
        logger = logging.getLogger("dnd_engine.events")

        # Format event data
        data_str = ", ".join(f"{k}={v}" for k, v in data.items())

        logger.info(f"[EVENT #{self._event_counter:03d}] {event_type}: {{{data_str}}}")

    def log_dice_roll(
        self,
        notation: str,
        rolls: list,
        modifier: int,
        total: int,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> None:
        """
        Log a dice roll with full details.

        Args:
            notation: Dice notation (e.g., "1d20+5")
            rolls: Individual die results
            modifier: Modifier applied
            total: Final total
            advantage: Whether roll had advantage
            disadvantage: Whether roll had disadvantage
        """
        if not self.debug_enabled:
            return

        logger = logging.getLogger("dnd_engine.dice")

        adv_status = ""
        if advantage:
            adv_status = " (advantage)"
        elif disadvantage:
            adv_status = " (disadvantage)"

        logger.info(f"[DICE] {notation}{adv_status} → {rolls} + {modifier} = {total}")

    def log_llm_call(
        self, prompt_type: str, latency_ms: float, response_length: int, success: bool = True
    ) -> None:
        """
        Log an LLM API call.

        Args:
            prompt_type: Type of prompt (e.g., "room_description")
            latency_ms: API call latency in milliseconds
            response_length: Length of response in characters
            success: Whether the call succeeded
        """
        if not self.debug_enabled:
            return

        logger = logging.getLogger("dnd_engine.llm")

        status = "SUCCESS" if success else "FAILED"
        logger.info(
            f"[LLM] {prompt_type} - {status} - {latency_ms:.0f}ms - {response_length} chars"
        )

    def log_combat_event(self, message: str) -> None:
        """
        Log a combat event.

        Args:
            message: Combat event message
        """
        if not self.debug_enabled:
            return

        logger = logging.getLogger("dnd_engine.combat")
        logger.info(f"[COMBAT] {message}")

    def log_player_action(self, character: str, action: str, details: str = "") -> None:
        """
        Log a player action.

        Args:
            character: Character name
            action: Action taken
            details: Optional action details
        """
        if not self.debug_enabled:
            return

        logger = logging.getLogger("dnd_engine.player")

        msg = f"[PLAYER] {character}: {action}"
        if details:
            msg += f" ({details})"

        logger.info(msg)

    def get_log_file_path(self) -> Path | None:
        """
        Get the path to the current log file.

        Returns:
            Path to log file, or None if debug mode not enabled
        """
        return self.log_file_path

    def close(self) -> None:
        """Close log file and clean up resources."""
        if self.log_file:
            self.log_file.close()
            self.log_file = None


# Global logging config instance
_logging_config: LoggingConfig | None = None


def init_logging(
    debug_enabled: bool = False,
    console_factory: ConsoleFactory | None = None,
) -> LoggingConfig:
    """
    Initialize global logging configuration.

    Args:
        debug_enabled: Whether debug mode is enabled
        console_factory: Optional UI console factory; see ``LoggingConfig``.

    Returns:
        LoggingConfig instance
    """
    global _logging_config
    _logging_config = LoggingConfig(debug_enabled, console_factory=console_factory)
    return _logging_config


def get_logging_config() -> LoggingConfig | None:
    """
    Get the global logging configuration.

    Returns:
        LoggingConfig instance or None if not initialized
    """
    return _logging_config
