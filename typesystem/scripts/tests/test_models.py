"""Tests for models.py data classes."""

import pytest

from models import AssembledProfile, PidRecord, ValidationResult, ValidationRules


class TestPidRecord:
    """Test PidRecord data class."""

    def test_basic_attributes(self):
        """Test that basic attributes are set correctly."""
        record = PidRecord(
            pid="0.FDO/Test",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="0.FDO/Test",
        )

        assert record.pid == "0.FDO/Test"
        assert record.source_pid == "0.FDO/Test"
        assert record.data == {"0.FDO/Type": ["FDO_Profile"]}

    def test_has_attribute_present(self):
        """Test has_attribute returns True for existing attributes."""
        record = PidRecord(
            pid="0.FDO/Test",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="0.FDO/Test",
        )

        assert record.has_attribute("0.FDO/Type") is True

    def test_has_attribute_missing(self):
        """Test has_attribute returns False for missing attributes."""
        record = PidRecord(
            pid="0.FDO/Test",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="0.FDO/Test",
        )

        assert record.has_attribute("0.FDO/NonExistent") is False

    def test_get_values_returns_list(self):
        """Test get_values returns a list of values."""
        record = PidRecord(
            pid="0.FDO/Test",
            data={"0.FDO/Type": ["FDO_Profile", "FDO_Record"]},
            source_pid="0.FDO/Test",
        )

        values = record.get_values("0.FDO/Type")
        assert len(values) == 2
        assert values[0] == "FDO_Profile"
        assert values[1] == "FDO_Record"

    def test_get_single_value_exactly_one(self):
        """Test get_single_value returns value when exactly one exists."""
        record = PidRecord(
            pid="0.FDO/Test",
            data={"0.FDO/Name": [{"value": "Test", "lang": "en"}]},
            source_pid="0.FDO/Test",
        )

        value = record.get_single_value("0.FDO/Name")
        assert value["value"] == "Test"

    def test_get_single_value_multiple(self):
        """Test get_single_value returns None when multiple values exist."""
        record = PidRecord(
            pid="0.FDO/Test",
            data={"0.FDO/Type": ["Type1", "Type2"]},
            source_pid="0.FDO/Test",
        )

        assert record.get_single_value("0.FDO/Type") is None

    def test_get_single_value_none(self):
        """Test get_single_value returns None when no values exist."""
        record = PidRecord(pid="0.FDO/Test", data={}, source_pid="0.FDO/Test")

        assert record.get_single_value("0.FDO/Type") is None


class TestAssembledProfile:
    """Test AssembledProfile data class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        profile = AssembledProfile(pid="0.FDO/Test")

        assert profile.pid == "0.FDO/Test"
        assert profile.all_attributes == []
        assert profile.declared_attributes == []
        assert profile.extends_chain == []
        assert profile.profiles_resolved == 0
        assert profile.has_cycle is False

    def test_with_attributes(self):
        """Test profile with attributes from extension chain."""
        profile = AssembledProfile(
            pid="0.FDO/ChildProfile",
            all_attributes=["0.FDO/Type", "0.FDO/Profile", "0.FDO/Data", "0.FDO/Name"],
            declared_attributes=["0.FDO/Type", "0.FDO/Profile"],
            extends_chain=["0.FDO/ChildProfile", "0.FDO/ParentProfile"],
            profiles_resolved=2,
            has_cycle=False,
        )

        assert len(profile.all_attributes) == 4
        assert len(profile.declared_attributes) == 2
        assert profile.profiles_resolved == 2
        assert len(profile.extends_chain) == 2

    def test_cycle_detected(self):
        """Test profile with detected cycle."""
        profile = AssembledProfile(
            pid="0.FDO/CircularProfile",
            all_attributes=["0.FDO/Type"],
            declared_attributes=["0.FDO/Type"],
            extends_chain=["0.FDO/CircularProfile"],
            profiles_resolved=1,
            has_cycle=True,
        )

        assert profile.has_cycle is True


class TestValidationRules:
    """Test ValidationRules data class."""

    def test_default_values(self):
        """Test that all fields default to None."""
        rules = ValidationRules()

        assert rules.cardinality is None
        assert rules.primitive_type is None
        assert rules.regex is None
        assert rules.numeric_interval is None
        assert rules.whitelist is None
        assert rules.blacklist is None
        assert rules.syntax_definition_pid is None

    def test_with_cardinality_and_type(self):
        """Test rules with cardinality and primitive type."""
        rules = ValidationRules(cardinality="1..*", primitive_type="string")

        assert rules.cardinality == "1..*"
        assert rules.primitive_type == "string"

    def test_with_whitelist(self):
        """Test rules with whitelist."""
        rules = ValidationRules(whitelist=["value1", "value2", "value3"])

        assert len(rules.whitelist) == 3
        assert "value1" in rules.whitelist


class TestValidationResult:
    """Test ValidationResult data class."""

    def test_initially_valid(self):
        """Test that new results are valid by default."""
        result = ValidationResult()

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_add_error_marks_invalid(self):
        """Test that adding an error marks result as invalid."""
        result = ValidationResult()
        result.add_error("Missing required attribute")

        assert result.valid is False
        assert len(result.errors) == 1

    def test_add_warning_keeps_valid(self):
        """Test that adding a warning doesn't affect validity."""
        result = ValidationResult()
        result.add_warning("Optional field missing")

        assert result.valid is True
        assert len(result.warnings) == 1

    def test_merge_combines_errors_and_warnings(self):
        """Test that merge combines errors, warnings, and counts."""
        result1 = ValidationResult()
        result1.add_error("Error 1")
        result1.add_warning("Warning 1")
        result1.resolutions_performed = 5

        result2 = ValidationResult()
        result2.add_error("Error 2")
        result2.add_error("Error 3")
        result2.add_warning("Warning 2")
        result2.resolutions_performed = 3

        result1.merge(result2)

        assert result1.valid is False
        assert len(result1.errors) == 3
        assert len(result1.warnings) == 2
        assert result1.resolutions_performed == 8

    def test_merge_with_valid_result(self):
        """Test that merging with valid result doesn't change validity."""
        result1 = ValidationResult()
        result1.add_error("Error 1")

        result2 = ValidationResult()  # Valid, no errors

        result1.merge(result2)

        assert result1.valid is False  # Still invalid from error 1
        assert len(result1.errors) == 1
