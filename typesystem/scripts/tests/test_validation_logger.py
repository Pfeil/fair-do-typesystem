"""Tests for validation_logger.py."""

import sys
from io import StringIO

import pytest

from validation_logger import ValidationLogger


class TestValidationLogger:
    """Test ValidationLogger functionality."""

    def test_initial_state(self):
        """Test initial logger state."""
        logger = ValidationLogger()

        assert logger.verbose is False
        assert logger.indent_level == 0
        assert logger.resolution_count == 0

    def test_verbose_mode(self):
        """Test verbose mode initialization."""
        logger = ValidationLogger(verbose=True)

        assert logger.verbose is True

    def test_reset_for_record(self):
        """Test that reset clears state for new record."""
        logger = ValidationLogger()
        logger.indent_level = 3
        logger.resolution_count = 5

        logger.reset_for_record("0.FDO/NewRecord")

        assert logger.indent_level == 0
        assert logger.resolution_count == 0

    def test_log_resolution_increments_counter(self):
        """Test that log_resolution increments counter."""
        logger = ValidationLogger()

        assert logger.get_resolution_count() == 0

        logger.log_resolution("0.FDO/Test", success=True)
        assert logger.get_resolution_count() == 1

        logger.log_resolution("0.FDO/Test2", success=False)
        assert logger.get_resolution_count() == 2

    def test_enter_exit_context(self):
        """Test context indentation."""
        logger = ValidationLogger()
        initial = logger.indent_level

        logger.enter_context()
        assert logger.indent_level == initial + 1

        logger.enter_context()
        assert logger.indent_level == initial + 2

        logger.exit_context()
        assert logger.indent_level == initial + 1

        logger.exit_context()
        assert logger.indent_level == initial

    def test_exit_context_does_not_go_negative(self):
        """Test that exit_context doesn't go below zero."""
        logger = ValidationLogger()

        logger.exit_context()  # Should not error
        assert logger.indent_level == 0

    def test_get_resolution_count(self):
        """Test resolution count getter."""
        logger = ValidationLogger()

        logger.log_resolution("PID1", success=True)
        logger.log_resolution("PID2", success=True)
        logger.log_resolution("PID3", success=False)

        assert logger.get_resolution_count() == 3

    def test_log_phase_always_shown(self, capsys):
        """Test that log_phase always outputs."""
        logger = ValidationLogger(verbose=False)

        logger.log_phase("Profile", "0.FDO/Root")

        captured = capsys.readouterr()
        assert "Profile:" in captured.out
        assert "0.FDO/Root" in captured.out

    def test_log_step_only_in_verbose(self, capsys):
        """Test that log_step only outputs in verbose mode."""
        # Non-verbose mode
        logger_quiet = ValidationLogger(verbose=False)
        logger_quiet.log_step("Test", "Message")

        captured = capsys.readouterr()
        assert captured.out == ""

        # Verbose mode
        logger_verbose = ValidationLogger(verbose=True)
        logger_verbose.log_step("Test", "Message")

        captured = capsys.readouterr()
        assert "Test:" in captured.out
        assert "Message" in captured.out

    def test_log_resolution_verbose_output(self, capsys):
        """Test resolution logging with target."""
        logger = ValidationLogger(verbose=True)

        logger.log_resolution("0.FDO/Test", success=True, target="core/test.json")

        captured = capsys.readouterr()
        assert "✓" in captured.out
        assert "0.FDO/Test" in captured.out
        assert "core/test.json" in captured.out

    def test_log_resolution_failure(self, capsys):
        """Test failed resolution logging."""
        logger = ValidationLogger(verbose=True)

        logger.log_resolution("0.FDO/Missing", success=False)

        captured = capsys.readouterr()
        assert "✗" in captured.out
        assert "0.FDO/Missing" in captured.out
