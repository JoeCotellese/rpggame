# ABOUTME: Tests for the MCPBridge thread-safe command queue.
# ABOUTME: Verifies queue operations and cross-thread communication.

"""Tests for MCPBridge command queue.

These tests verify:
- Command request creation and structure
- Queue put/get operations
- Future-based response handling
- Thread safety basics
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError

import pytest
from client_2d.mcp_bridge import CommandRequest, CommandType, MCPBridge


class TestCommandType:
    """Tests for CommandType enum."""

    def test_command_types_exist(self) -> None:
        """All expected command types are defined."""
        assert CommandType.GET_STATE is not None
        assert CommandType.MOVE is not None
        assert CommandType.ATTACK is not None
        assert CommandType.WAIT is not None

    def test_command_types_unique(self) -> None:
        """Each command type has a unique value."""
        types = [
            CommandType.GET_STATE,
            CommandType.MOVE,
            CommandType.ATTACK,
            CommandType.WAIT,
        ]
        assert len(types) == len(set(types))


class TestCommandRequest:
    """Tests for CommandRequest dataclass."""

    def test_create_simple_request(self) -> None:
        """Create a basic command request."""
        request = CommandRequest(command_type=CommandType.GET_STATE)

        assert request.command_type == CommandType.GET_STATE
        assert request.args == {}
        assert request.response_future is not None

    def test_create_request_with_args(self) -> None:
        """Create a command request with arguments."""
        request = CommandRequest(
            command_type=CommandType.MOVE,
            args={"direction": "north"},
        )

        assert request.command_type == CommandType.MOVE
        assert request.args == {"direction": "north"}

    def test_future_set_result(self) -> None:
        """Response future can be set and retrieved."""
        request = CommandRequest(command_type=CommandType.GET_STATE)

        request.response_future.set_result("test result")

        assert request.response_future.result() == "test result"

    def test_future_set_exception(self) -> None:
        """Response future can hold exceptions."""
        request = CommandRequest(command_type=CommandType.GET_STATE)

        request.response_future.set_exception(ValueError("test error"))

        with pytest.raises(ValueError, match="test error"):
            request.response_future.result()


class TestMCPBridge:
    """Tests for MCPBridge queue operations."""

    def test_init_empty_queue(self) -> None:
        """New bridge has empty queue."""
        bridge = MCPBridge()

        assert bridge.queue_size() == 0
        assert bridge.game_window is None

    def test_set_game_window(self) -> None:
        """Can set game window reference."""
        bridge = MCPBridge()

        # Use a mock object
        mock_window = object()
        bridge.set_game_window(mock_window)

        assert bridge.game_window is mock_window

    def test_poll_empty_queue(self) -> None:
        """Polling empty queue returns None."""
        bridge = MCPBridge()

        result = bridge.poll_commands()

        assert result is None

    def test_submit_and_poll(self) -> None:
        """Submitted command can be polled."""
        bridge = MCPBridge()
        request = CommandRequest(command_type=CommandType.GET_STATE)

        # Submit in a way that won't block (we'll set result before timeout)
        def submit_thread():
            try:
                bridge.submit_command(request, timeout=1.0)
            except FutureTimeoutError:
                pass  # Expected if we don't set result

        thread = threading.Thread(target=submit_thread)
        thread.start()

        # Give thread time to submit
        time.sleep(0.1)

        # Poll should get the command
        polled = bridge.poll_commands()
        assert polled is request

        # Set result so submit thread can complete
        request.response_future.set_result("done")
        thread.join()

    def test_queue_size_increases(self) -> None:
        """Queue size increases when commands are submitted."""
        bridge = MCPBridge()

        def submit_thread(cmd):
            try:
                bridge.submit_command(cmd, timeout=0.5)
            except FutureTimeoutError:
                pass

        # Submit multiple commands
        threads = []
        for _ in range(3):
            cmd = CommandRequest(command_type=CommandType.GET_STATE)
            t = threading.Thread(target=submit_thread, args=(cmd,))
            threads.append(t)
            t.start()

        # Wait for submissions
        time.sleep(0.1)

        assert bridge.queue_size() == 3

        # Cleanup
        for _ in range(3):
            cmd = bridge.poll_commands()
            if cmd:
                cmd.response_future.set_result("done")

        for t in threads:
            t.join()


class TestMCPBridgeThreadSafety:
    """Tests for thread-safe behavior."""

    def test_concurrent_submit_and_poll(self) -> None:
        """Multiple threads can submit while main thread polls."""
        bridge = MCPBridge()
        results = []

        def producer(index):
            cmd = CommandRequest(
                command_type=CommandType.MOVE,
                args={"index": index},
            )
            try:
                result = bridge.submit_command(cmd, timeout=2.0)
                results.append((index, result))
            except FutureTimeoutError:
                results.append((index, "timeout"))

        # Start producer threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=producer, args=(i,))
            threads.append(t)
            t.start()

        # Consumer loop - process commands
        processed = 0
        start = time.time()
        while processed < 5 and (time.time() - start) < 3.0:
            cmd = bridge.poll_commands()
            if cmd:
                cmd.response_future.set_result(f"processed_{cmd.args['index']}")
                processed += 1
            else:
                time.sleep(0.05)

        # Wait for all producers
        for t in threads:
            t.join()

        # Verify all commands were processed
        assert len(results) == 5
        for index, result in results:
            assert result == f"processed_{index}"

    def test_submit_timeout(self) -> None:
        """Submit times out if result not set."""
        bridge = MCPBridge()
        request = CommandRequest(command_type=CommandType.GET_STATE)

        def submit_thread():
            with pytest.raises(FutureTimeoutError):
                bridge.submit_command(request, timeout=0.1)

        thread = threading.Thread(target=submit_thread)
        thread.start()
        thread.join()

        # Command should still be in queue
        assert bridge.queue_size() == 1
