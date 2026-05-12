"""Tests for registry.py - PID resolution."""

from pathlib import Path

import pytest

from registry import PidRegistry
from validation_logger import ValidationLogger


class TestPidRegistry:
    """Test PidRegistry functionality."""

    def test_registry_loads_successfully(self):
        """Test that registry.json is loaded on initialization."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        assert registry.registry is not None
        assert len(registry.registry) > 0

    def test_resolve_known_pid(self):
        """Test resolving a PID that exists in registry.json."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        record = registry.resolve_pid("0.FDO/Root")

        assert record is not None
        assert record.pid == "0.FDO/Root"
        assert record.has_attribute("0.FDO/Type")

    def test_resolve_returns_pid_record(self):
        """Test that resolve_pid returns a PidRecord with correct structure."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        record = registry.resolve_pid("0.FDO/ProfileDef")

        assert record.pid == "0.FDO/ProfileDef"
        assert record.source_pid == "0.FDO/ProfileDef"
        assert isinstance(record.data, dict)

    def test_resolve_nonexistent_pid(self):
        """Test resolving a PID that doesn't exist."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        record = registry.resolve_pid("0.FDO/NonExistent_PID_12345")

        assert record is None

    def test_resolve_logs_attempts(self, capsys):
        """Test that resolution attempts are logged in verbose mode."""
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)

        # Try to resolve existing PID
        registry.resolve_pid("0.FDO/Root")

        captured = capsys.readouterr()
        assert "Resolved" in captured.out or "✓" in captured.out

    def test_base_path_is_parent_directory(self):
        """Test that base_path points to typesystem directory (two levels up)."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        # registry.py is in typesystem/scripts/
        # base_path should be typesystem/ (parent of scripts)
        expected_base = Path(__file__).parent.parent.parent

        assert registry.base_path == expected_base

    def test_registry_contains_core_pids(self):
        """Test that registry contains core FDO PIDs."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        # Check for essential PIDs
        assert "0.FDO/Root" in registry.registry
        assert "0.FDO/ProfileDef" in registry.registry
        assert "0.FDO/AttributeDef" in registry.registry
        assert "0.FDO/SyntaxDef" in registry.registry

    def test_multiple_resolutions_same_pid(self):
        """Test that multiple resolutions of same PID work (no caching)."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        record1 = registry.resolve_pid("0.FDO/Root")
        record2 = registry.resolve_pid("0.FDO/Root")

        # Both should succeed
        assert record1 is not None
        assert record2 is not None

        # Should have same content but be separate objects (no caching)
        assert record1.pid == record2.pid
        assert record1.data == record2.data

    def test_resolution_increments_logger_count(self):
        """Test that each resolution increments the logger's counter."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)

        initial_count = logger.get_resolution_count()

        registry.resolve_pid("0.FDO/Root")
        registry.resolve_pid("0.FDO/ProfileDef")
        registry.resolve_pid("0.FDO/NonExistent")

        final_count = logger.get_resolution_count()

        # Should have incremented by 3
        assert final_count == initial_count + 3
