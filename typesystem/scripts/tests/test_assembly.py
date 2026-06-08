"""Tests for assembly.py - Profile and attribute assembly."""

import pytest

from assembly import ProfileAssembly
from models import AssembledProfile
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
        assert result.profiles_resolved == 1
        assert len(result.all_attributes) == 3  # Root specifies Type, Profile, Data
        assert len(result.extends_chain) == 1
        assert not result.has_cycle

    def test_assemble_profiledef(self, assembly: ProfileAssembly):
        """Test assembling the profile definition."""
        result = assembly.assemble("0.FDO/ProfileDef")

        assert len(result.extends_chain) == 1
        assert result.pid == "0.FDO/ProfileDef"
        assert result.profiles_resolved == 1
        assert len(result.all_attributes) == 6
        assert "0.FDO/Type" in result.all_attributes
        assert "0.FDO/Profile" in result.all_attributes
        assert "0.FDO/Data" in result.all_attributes

    def test_assemble_extended_profile(self, assembly: ProfileAssembly):
        result = assembly.assemble("extending-profile")

        assert len(result.extends_chain) == 2
        assert result.pid == "extending-profile"
        assert result.profiles_resolved == 2
        assert len(result.all_attributes) == 7
        assert "0.FDO/Type" in result.all_attributes
        assert "0.FDO/Profile" in result.all_attributes
        assert "0.FDO/Data" in result.all_attributes
        assert "added_attribute" in result.all_attributes
        assert not result.has_cycle

    def test_assemble_recursing_profile(self, assembly: ProfileAssembly):
        result = assembly.assemble("recursing-profile")

        assert len(result.extends_chain) == 1
        assert result.pid == "recursing-profile"
        assert result.profiles_resolved == 1
        assert len(result.all_attributes) == 1
        assert result.has_cycle

    def test_assemble_collects_all_attributes(self, assembly):
        """Test that all attributes from extension chain are collected."""
        result = assembly.assemble("0.FDO/AttributeDef")

        # Should have attributes from AttributeDef itself
        assert len(result.all_attributes) > 0

        # All attributes should be strings (PIDs)
        for attr in result.all_attributes:
            assert isinstance(attr, str)

    def test_assemble_avoids_duplicate_attributes(self, assembly):
        """Test that duplicate attributes are not added multiple times."""
        result = assembly.assemble("0.FDO/SyntaxDef")

        # Check for uniqueness
        unique_attrs = set(result.all_attributes)
        assert len(unique_attrs) == len(result.all_attributes), (
            "Duplicate attributes found in assembled profile"
        )

    def test_assemble_tracks_extends_chain(self, assembly):
        """Test that extension chain is properly tracked."""
        result = assembly.assemble("0.FDO/ProfileDef")

        assert len(result.extends_chain) > 0
        assert "0.FDO/ProfileDef" in result.extends_chain
        # Chain should be in resolution order
        assert result.extends_chain[0] == "0.FDO/ProfileDef"

    def test_assemble_counts_profiles_resolved(self, assembly):
        """Test that profile count is accurate."""
        result = assembly.assemble("0.FDO/Root")

        assert result.profiles_resolved >= 1
        assert result.profiles_resolved == len(result.extends_chain)

    def test_assemble_handles_non_pid_extends(self, assembly):
        """Test that non-PID extends values (like Not_Applicable) are filtered."""
        # Many profiles have Extends: ["Not_Applicable"]
        result = assembly.assemble("0.FDO/Root")

        # Should not try to resolve "Not_Applicable" as a PID
        # Should complete successfully without errors
        assert result.profiles_resolved >= 1

    def test_assemble_logs_steps_in_verbose_mode(self, capsys):
        """Test that assembly logs steps when verbose."""
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        assembly = ProfileAssembly(registry, logger)

        assembly.assemble("0.FDO/Root")

        captured = capsys.readouterr()
        # Should have logged something about profile assembly
        assert "Profile" in captured.out or "assembly" in captured.out.lower()

    def test_get_declared_attributes(self, assembly):
        """Test getting only declared (not inherited) attributes."""
        declared = assembly._get_declared_attributes("0.FDO/Root")

        assert len(declared) > 0
        assert "0.FDO/Type" in declared
        assert "0.FDO/Profile" in declared
        assert "0.FDO/Data" in declared

    def test_get_declared_attributes_missing_profile(self, assembly):
        """Test getting declared attributes from non-existent profile."""
        declared = assembly._get_declared_attributes("0.FDO/NonExistent")

        assert declared == []

    def test_is_pid_reference_filters_literals(self, assembly):
        """Test that literal values are not treated as PIDs."""
        assert assembly._is_pid_reference("0.FDO/Type") is True
        assert assembly._is_pid_reference("0.FDO/Profile") is True

        assert assembly._is_pid_reference("Not_Applicable") is False
        assert assembly._is_pid_reference("Not_Applicable_Numeric") is False
        assert assembly._is_pid_reference("Not_Applicable_String") is False

    def test_is_pid_reference_accepts_valid_pids(self, assembly):
        """Test that valid PID-like strings are accepted."""
        # Any string that's not in the blacklist should be treated as PID reference
        assert assembly._is_pid_reference("Custom/PID") is True
        assert assembly._is_pid_reference("My/Attribute") is True


class TestAssembledProfileDataclass:
    """Test AssembledProfile dataclass usage in assembly context."""

    def test_complete_assembly_result(self):
        """Test a fully populated AssembledProfile."""
        profile = AssembledProfile(
            pid="0.FDO/TestProfile",
            all_attributes=["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data", "0.FDO/Name"],
            declared_attributes=["0.FDO/Type", "0.FDO/Profile"],
            extends_chain=["0.FDO/TestProfile", "0.FDO/ParentProfile"],
            profiles_resolved=2,
            has_cycle=False,
        )

        assert profile.pid == "0.FDO/TestProfile"
        assert len(profile.all_attributes) == 4
        assert len(profile.declared_attributes) == 2
        assert len(profile.extends_chain) == 2
        assert profile.profiles_resolved == 2
        assert not profile.has_cycle

    def test_cycle_detection_result(self):
        """Test AssembledProfile with cycle detected."""
        profile = AssembledProfile(
            pid="0.FDO/Circular",
            all_attributes=["0.FDO/Type"],
            declared_attributes=["0.FDO/Type"],
            extends_chain=["0.FDO/Circular"],
            profiles_resolved=1,
            has_cycle=True,
        )

        assert profile.has_cycle is True
        assert profile.profiles_resolved == 1


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
            assert result.profiles_resolved >= 1
            assert len(result.all_attributes) > 0
            assert len(result.extends_chain) > 0

    def test_assemble_preserves_attribute_order(self, assembly):
        """Test that attribute order is preserved (first occurrence wins)."""
        result = assembly.assemble("0.FDO/ProfileDef")

        # Attributes should be in order of first encounter
        seen = set()
        for attr in result.all_attributes:
            assert attr not in seen, f"Duplicate {attr} breaks order"
            seen.add(attr)

    def test_multiple_assemblies_same_profile(self, assembly):
        """Test that multiple assemblies of same profile work correctly."""
        result1 = assembly.assemble("0.FDO/Root")
        result2 = assembly.assemble("0.FDO/Root")

        # Results should be equivalent (no caching, so different objects)
        assert result1.pid == result2.pid
        assert result1.all_attributes == result2.all_attributes
        assert result1.profiles_resolved == result2.profiles_resolved

    def test_assemble_different_profiles_independent(self, assembly):
        """Test that assembling different profiles doesn't interfere."""
        result1 = assembly.assemble("0.FDO/Root")
        result2 = assembly.assemble("0.FDO/ProfileDef")

        # Each should have its own PID
        assert result1.pid != result2.pid

        # Both should be valid
        assert result1.profiles_resolved >= 1
        assert result2.profiles_resolved >= 1
