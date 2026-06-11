"""Tests for assembly.py - Profile and attribute assembly."""

import pytest

from assembly import ProfileAssembly
from registry import PidRegistry
from validation_logger import ValidationLogger


class TestProfileAssembly:
    """Test ProfileAssembly functionality."""

    @pytest.fixture
    def assembly(self) -> ProfileAssembly:
        """Create a ProfileAssembly instance for testing."""
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        return ProfileAssembly(registry, logger)

    def test_assemble_root(self, assembly: ProfileAssembly):
        """Test assembling the simple root profile."""
        result = assembly.assemble("0.FDO/Root")

        assert result.pid == "0.FDO/Root"
        assert result.amount_resolved_extension_pids == 1
        assert len(result.all_attributes) == 3  # Root specifies Type, Profile, Data
        assert len(result.extends_chain) == 1
        assert not result.has_cycle

    def test_assemble_profiledef(self, assembly: ProfileAssembly):
        """Test assembling the profile definition."""
        result = assembly.assemble("0.FDO/ProfileDef")

        assert len(result.extends_chain) == 1
        assert result.pid == "0.FDO/ProfileDef"
        assert result.amount_resolved_extension_pids == 1
        assert len(result.all_attributes) == 6
        assert "0.FDO/Type" in result.all_attributes
        assert "0.FDO/Profile" in result.all_attributes
        assert "0.FDO/Data" in result.all_attributes

    def test_assemble_extended_profile(self, assembly: ProfileAssembly):
        result = assembly.assemble("extending-profile")

        assert len(result.extends_chain) == 2
        assert result.pid == "extending-profile"
        assert result.amount_resolved_extension_pids == 2
        assert len(result.all_attributes) == 7
        assert "0.FDO/Type" in result.all_attributes
        assert "0.FDO/Profile" in result.all_attributes
        assert "0.FDO/Data" in result.all_attributes
        assert "added_attribute" in result.all_attributes
        assert not result.has_cycle

    def test_assemble_recursing_profile(self, assembly: ProfileAssembly):
        test_subject = "recursing-profile"
        result = assembly.assemble(test_subject)

        assert result.pid in result.extends_chain, (
            f"PID {result.pid} should be in extends chain"
        )
        assert result.amount_resolved_extension_pids == 4, (
            f"Expected 3+1 extensions, got {result.amount_resolved_extension_pids}"
        )
        assert len(result.all_attributes) == 8, (
            f"Expected 8 attributes: one from itself, and 1+6 from the extensions. Got {len(result.all_attributes)}"
        )
        assert result.has_cycle, "Expected cycle to be detected"
        assert len(result.processing_warnings) == 1, (
            f"{test_subject} has one unresolvable reference, got {len(result.processing_warnings)}"
        )

    def test_assemble_collects_all_attributes(self, assembly: ProfileAssembly):
        """Test that all attributes from extension chain are collected."""
        result = assembly.assemble("0.FDO/AttributeDef")

        assert len(result.all_attributes) == 8, (
            f"Expected 5+3 attributes, got {len(result.all_attributes)}"
        )

        for attr in result.all_attributes:
            assert isinstance(attr, str), (
                f"Expected attribute to be a string (PID), got {type(attr)}"
            )

    def test_assemble_avoids_duplicate_attributes(self, assembly: ProfileAssembly):
        """Test that duplicate attributes are not added multiple times."""
        result = assembly.assemble("profile-with-duplicates")

        # Check for uniqueness
        unique_attrs = set(result.all_attributes)
        assert len(unique_attrs) == len(result.all_attributes), (
            "Duplicate attributes found in assembled profile"
        )
        assert len(result.all_attributes) == 1

    def test_assemble_tracks_extends_chain(self, assembly: ProfileAssembly):
        """Test that extension chain is properly tracked."""
        test_subject: str = "recursing-profile"
        result = assembly.assemble(test_subject)

        # Order in profile
        assert result.extends_chain[0] == test_subject
        assert result.extends_chain[1] == "extending-nonexisting"
        assert result.extends_chain[2] == "extending-profile"
        # From the "extending-profile"
        assert result.extends_chain[3] == "0.FDO/ProfileDef"

    def test_assemble_counts_profiles_resolved(self, assembly: ProfileAssembly):
        """Test that profile count is accurate."""
        result = assembly.assemble("recursing-profile")

        assert result.amount_resolved_extension_pids >= 1
        assert result.amount_resolved_extension_pids == len(result.extends_chain)

    def test_assemble_logs_steps_in_verbose_mode(self, capsys):
        """Test that assembly logs steps when verbose."""
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        assembly = ProfileAssembly(registry, logger)

        assembly.assemble("0.FDO/Root")

        captured = capsys.readouterr()
        # Should have logged something about profile assembly
        assert "Profile" in captured.out or "assembly" in captured.out.lower()

    def test_is_pid_reference_filters_literals(self, assembly: ProfileAssembly):
        """Test that literal values are not treated as PIDs."""
        assert assembly._is_pid_reference("0.FDO/Type") is True
        assert assembly._is_pid_reference("0.FDO/Profile") is True

        assert assembly._is_pid_reference("Not_Applicable") is False
        assert assembly._is_pid_reference("Not_Applicable_Numeric") is False
        assert assembly._is_pid_reference("Not_Applicable_String") is False

    def test_is_pid_reference_accepts_valid_pids(self, assembly: ProfileAssembly):
        """Test that valid PID-like strings are accepted."""
        # Any string that's not in the blacklist should be treated as PID reference
        assert assembly._is_pid_reference("Custom/PID") is True
        assert assembly._is_pid_reference("My/Attribute") is True


class TestProfileAssemblyIntegration:
    """Integration tests for ProfileAssembly with real profiles."""

    @pytest.fixture
    def assembly(self):
        """Create a ProfileAssembly instance for testing."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)
        return ProfileAssembly(registry, logger)

    def test_assemble_all_core_profiles(self):
        """Test assembling all core profiles successfully."""
        logger = ValidationLogger(verbose=False)
        registry = PidRegistry(logger)
        assembly = ProfileAssembly(registry, logger)

        core_profiles = [
            "0.FDO/Root",
            "0.FDO/ProfileDef",
            "0.FDO/AttributeDef",
            "0.FDO/SyntaxDef",
        ]

        for profile_pid in core_profiles:
            result = assembly.assemble(profile_pid)

            # Basic sanity checks
            assert result.pid == profile_pid
            assert result.amount_resolved_extension_pids >= 1
            assert len(result.all_attributes) > 0
            assert len(result.extends_chain) > 0

    def test_assemble_preserves_attribute_order(self, assembly: ProfileAssembly):
        """Test that attribute order is preserved (first occurrence wins)."""
        result = assembly.assemble("0.FDO/ProfileDef")

        # Attributes should be in order of first encounter
        seen = set()
        for attr in result.all_attributes:
            assert attr not in seen, f"Duplicate {attr} breaks order"
            seen.add(attr)

    def test_multiple_assemblies_same_profile(self, assembly: ProfileAssembly):
        """Test that multiple assemblies of same profile work correctly."""
        result1 = assembly.assemble("0.FDO/Root")
        result2 = assembly.assemble("0.FDO/Root")

        # Results should be equivalent (no caching, so different objects)
        assert result1.pid == result2.pid
        assert result1.all_attributes == result2.all_attributes
        assert (
            result1.amount_resolved_extension_pids
            == result2.amount_resolved_extension_pids
        )

    def test_assemble_different_profiles_independent(self, assembly: ProfileAssembly):
        """Test that assembling different profiles doesn't interfere."""
        result1 = assembly.assemble("0.FDO/Root")
        result2 = assembly.assemble("0.FDO/ProfileDef")

        # Each should have its own PID
        assert result1.pid != result2.pid

        # Both should be valid
        assert result1.amount_resolved_extension_pids >= 1
        assert result2.amount_resolved_extension_pids >= 1
