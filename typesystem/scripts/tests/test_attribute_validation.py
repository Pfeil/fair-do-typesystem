"""Tests for AttributeAssembly and AttributeValidator (Phase 4).

Tests are organized into classes:
- TestAttributeAssembly: Rule assembly tests
- TestAttributeValidator: Value validation tests
- TestCardinalityValidation: Cardinality-specific tests
- TestTypeValidation: Type checking tests
- TestRegexValidation: Pattern matching tests
- TestIntegration: Integration tests with real type system
"""

import pytest

from assembly import AttributeAssembly
from models import PidRecord, SyntaxRules, ValidationResult
from registry import PidRegistry
from validation_logger import ValidationLogger
from validators import AttributeValidator

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def logger() -> ValidationLogger:
    """Create a ValidationLogger for testing."""
    return ValidationLogger(verbose=True)


@pytest.fixture
def registry(logger) -> PidRegistry:
    """Create a PidRegistry for testing."""
    return PidRegistry(logger)


@pytest.fixture
def attribute_assembly(registry, logger) -> AttributeAssembly:
    """Create an AttributeAssembly for testing."""
    return AttributeAssembly(registry, logger)


@pytest.fixture
def attribute_validator(registry, logger, attribute_assembly) -> AttributeValidator:
    """Create an AttributeValidator for testing."""
    return AttributeValidator(registry, logger, attribute_assembly)


@pytest.fixture
def sample_record_with_type() -> PidRecord:
    """Create a record with 0.FDO/Type attribute for testing."""
    return PidRecord(
        pid="test/WithType",
        data={
            "0.FDO/Type": ["FDO_Profile"],
            "0.FDO/Profile": ["0.FDO/Root"],
            "0.FDO/Data": ["Not_Applicable"],
            "0.FDO/Name": [{"value": "Test Record", "lang": "en"}],
        },
        source_pid="test/WithType",
    )


# =============================================================================
# TestAttributeAssembly - Rule assembly tests
# =============================================================================


class TestAttributeAssembly:
    """Test AttributeAssembly core functionality."""

    def test_assemble_rules_for_type_attribute(
        self, attribute_assembly: AttributeAssembly
    ):
        """Test assembling rules for 0.FDO/Type."""
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert rules.cardinality == "1..*"
        assert rules.syntax_rules[0].primitive_types[0] == "string"
        assert rules.syntax_rules[0].syntax_pid == "0.FDO/StringSyntax"
        assert len(rules.syntax_rules[0].regexes) == 0
        assert len(rules.syntax_rules[0].numeric_intervals) == 0
        assert len(rules.syntax_rules[0].whitelist) == 0
        assert len(rules.syntax_rules[0].blacklist) == 0

    def test_assemble_rules_for_cardinality_attribute(
        self, attribute_assembly: AttributeAssembly
    ):
        """Test assembling rules for 0.FDO/Cardinality."""
        rules = attribute_assembly.assemble_rules("0.FDO/Cardinality")

        assert rules.cardinality == "1"
        assert len(rules.syntax_rules) == 1
        assert rules.syntax_rules[0].syntax_pid == "0.FDO/CardinalitySyntax"
        assert rules.syntax_rules[0].primitive_types[0] == "string"
        assert len(rules.syntax_rules[0].whitelist) == 0
        assert len(rules.syntax_rules[0].blacklist) == 0
        assert len(rules.syntax_rules[0].regexes) == 1

    def test_assemble_rules_for_name_attribute(
        self, attribute_assembly: AttributeAssembly
    ):
        """Test assembling rules for 0.FDO/Name."""
        rules = attribute_assembly.assemble_rules("0.FDO/Name")

        assert rules.cardinality == "1..*"
        assert len(rules.syntax_rules) == 1
        assert rules.syntax_rules[0].syntax_pid == "0.FDO/StringSyntax"
        assert rules.syntax_rules[0].primitive_types[0] == "string"
        assert len(rules.syntax_rules[0].regexes) == 0

    def test_assemble_rules_nonexistent_attribute(
        self, attribute_assembly: AttributeAssembly
    ):
        """Test assembling rules for non-existent attribute."""
        rules = attribute_assembly.assemble_rules("0.FDO/NonExistent")

        # Should return empty rules, not crash
        assert rules.cardinality is None
        assert len(rules.syntax_rules) == 0
        assert len(rules.validation_mechanisms) == 0
        assert not rules.validation_result.valid

    def test_assemble_rules_extracts_all_syntax_fields(
        self, attribute_assembly: AttributeAssembly
    ):
        """Test that all syntax fields are extracted."""
        # Test with StringSyntax which has primitive type
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert rules.cardinality
        assert len(rules.cardinality) > 0
        assert len(rules.syntax_rules) == 1
        assert len(rules.validation_mechanisms) == 2
        syntax = rules.syntax_rules[0]
        assert syntax.primitive_types == ["string"]


# =============================================================================
# TestAttributeValidator - Value validation tests
# =============================================================================


class TestAttributeValidator:
    """Test AttributeValidator core functionality."""

    def test_accepts_correct_value(self, attribute_validator: AttributeValidator):
        """Test if the proper value is accepted."""
        record_with_name_valid = PidRecord(
            pid="test/WithProperName",
            data={"0.FDO/Cardinality": ["1..5"]},
            source_pid="test/WithProperName",
        )
        result = attribute_validator.validate(
            record_with_name_valid, record_with_name_valid.pid
        )

        assert result.attributes_checked > 0
        assert result.valid

    def test_rejects_invalid_value_type_due_to_regex(
        self, attribute_validator: AttributeValidator
    ):
        """Test if the proper value is rejected."""
        record_with_name_invalid = PidRecord(
            pid="test/WithProperName",
            data={"0.FDO/Cardinality": ["1..5..7"]},
            source_pid="test/WithProperName",
        )
        result = attribute_validator.validate(
            record_with_name_invalid, record_with_name_invalid.pid
        )

        # Should have checked at least one attribute
        assert result.attributes_checked > 0
        assert not result.valid
        assert "pattern" in result.errors[0].message().lower()

    def test_validate_validates_basic_attributes(
        self,
        attribute_validator: AttributeValidator,
    ):
        """Test that basic attributes (Type, Profile, Data) are validated."""
        record = PidRecord(
            pid="test/WithProperName",
            data={
                "0.FDO/Type": ["0.FDO/Profile"],
                "0.FDO/Profile": ["Some/Profile"],
                "0.FDO/Data": ["0.FDO/Profile"],
            },
            source_pid="test/WithProperName",
        )
        result = attribute_validator.validate(record, record.pid)

        assert result.attributes_checked == 3
        assert result.valid

    def test_validate_empty_record(
        self,
        attribute_validator: AttributeValidator,
    ):
        """Test validating a record with no attributes."""
        empty_record = PidRecord(
            pid="test/Empty",
            data={},
            source_pid="test/Empty",
        )

        result = attribute_validator.validate(empty_record, "test/Empty")

        # Should complete without errors
        assert result.valid
        assert result.attributes_checked == 0


# =============================================================================
# TestCardinalityValidation - Cardinality-specific tests
# =============================================================================


class TestCardinalityValidation:
    """Test cardinality validation logic."""

    attribute_name = "test"
    owning_record_pid = "owning_record_pid"

    def test_accepts_multiple_values(self, attribute_validator: AttributeValidator):
        """Test type may be repeated."""
        pid = "test/Record"
        record = PidRecord(
            pid=pid,
            data={
                "0.FDO/Type": ["0.FDO/Data", "0.FDO/Data", "0.FDO/Cardinality"],
                "0.FDO/Data": ["0.FDO/Type", "0.FDO/Type", "0.FDO/Cardinality"],
                "0.FDO/Cardinality": ["1..3"],
            },
            source_pid=pid,
        )
        result = attribute_validator.validate(record, pid)
        assert result.errors == []
        assert result.valid

    def test_rejects_multiple_values(self, attribute_validator: AttributeValidator):
        """Test type may be repeated."""
        pid = "test/Record"
        record = PidRecord(
            pid=pid,
            data={"0.FDO/Regex": ["1", "2", "3"]},
            source_pid=pid,
        )
        result = attribute_validator.validate(record, pid)
        assert not result.valid

    def test_check_cardinality_exactly_one(
        self, attribute_validator: AttributeValidator
    ):
        """Test cardinality "1" (exactly one)."""
        result = ValidationResult()

        # Valid: exactly one value
        assert (
            attribute_validator._check_cardinality(
                1, "1", self.attribute_name, self.owning_record_pid, result
            )
            is True
        )

        for actual_count in [0, 2, 3, 9999, -1, -9999]:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    actual_count,
                    "1",
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is False
            ), f"Expected False for actual_count={actual_count}, got True"
            assert len(result.errors) == 1, (
                f"Expected 1 error, got {len(result.errors)} for actual_count={actual_count}"
            )

    def test_check_cardinality_zero_or_one(
        self, attribute_validator: AttributeValidator
    ):
        """Test cardinality "0..1" (optional)."""

        valid_values = [0, 1]
        for actual_count in valid_values:
            result = ValidationResult()

            # Valid: zero values
            assert (
                attribute_validator._check_cardinality(
                    actual_count,
                    "0..1",
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
            ) is True

        invalid_values = [-9999, -1, 2, 5, 9999]
        for actual_count in invalid_values:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    actual_count,
                    "0..1",
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is False
            ), f"Expected False for actual_count={actual_count}, got True"
            assert len(result.errors) == 1, (
                f"Expected 1 error, got {len(result.errors)} for actual_count={actual_count}"
            )

    def test_check_cardinality_one_or_more(
        self, attribute_validator: AttributeValidator
    ):
        """Test cardinality "1..*" (mandatory, repeatable)."""
        valid_values = [1, 5, 10, 9999]
        for actual_count in valid_values:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    actual_count,
                    "1..*",
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is True
            ), f"Expected True for actual_count={actual_count}, got False"
            assert len(result.errors) == 0, (
                f"Expected 0 errors, got {len(result.errors)} for actual_count={actual_count}"
            )

        invalid_values = [0, -1, -5, -9999]
        for actual_count in invalid_values:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    actual_count,
                    "1..*",
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is False
            ), f"Expected False for actual_count={actual_count}, got True"
            assert len(result.errors) == 1, (
                f"Expected 1 error, got {len(result.errors)} for actual_count={actual_count}"
            )

    def test_check_cardinality_zero_or_more(
        self, attribute_validator: AttributeValidator
    ):
        """Test cardinality "0..*" (optional, repeatable)."""
        expression = "0..*"
        valid_values = [0, 1, 5, 9999]
        for actual_value in valid_values:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    actual_value,
                    expression,
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is True
            ), f"Expected True for actual_count={actual_value}, got False"
            assert len(result.errors) == 0, (
                f"Expected no errors for actual_count={actual_value}, got {result.errors}"
            )

        invalid_values = [-1, -10, -9999]
        for actual_value in invalid_values:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    actual_value,
                    expression,
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is False
            ), f"Expected False for actual_count={actual_value}, got True"
            assert len(result.errors) == 1, (
                f"Expected no errors for actual_count={actual_value}, got {result.errors}"
            )

    def test_check_cardinality_range(self, attribute_validator: AttributeValidator):
        """Test cardinality "2..3" (range)."""
        expression = "2..3"
        valid_values = [2, 3]
        for actual_value in valid_values:
            result = ValidationResult()

            assert (
                attribute_validator._check_cardinality(
                    actual_value,
                    expression,
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is True
            ), f"Expected True for actual_count={actual_value}, got {result.errors}"
            assert len(result.errors) == 0, (
                f"Expected no errors, got {result.errors} for actual_count={actual_value}"
            )

        invalid_values = [-9999, -10, -1, 0, 1, 4, 5, 10, 9999]
        for actual_value in invalid_values:
            result = ValidationResult()

            assert (
                attribute_validator._check_cardinality(
                    actual_value,
                    expression,
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
                is False
            ), f"Expected False for actual_count={actual_value}, got {result.errors}"
            assert len(result.errors) == 1, (
                f"Expected 1 error, got {len(result.errors)} for actual_count={actual_value}"
            )

    def test_check_cardinality_invalid_expression(
        self, attribute_validator: AttributeValidator
    ):
        """
        Test if invalid cardinalities lead to an error.
        """
        invalid_cardinality_str = "invalid"
        invalid_amounts = [-9999, -10, -1, 0, 1, 10, 9999]
        for amount in invalid_amounts:
            result = ValidationResult()
            assert (
                attribute_validator._check_cardinality(
                    amount,
                    invalid_cardinality_str,
                    self.attribute_name,
                    self.owning_record_pid,
                    result,
                )
            ) is False, f"Expected False for actual_count={amount}, got {result.errors}"


# =============================================================================
# TestTypeValidation - Type checking tests
# =============================================================================


class TestTypeValidation:
    """Test primitive type validation logic."""

    # TODO the handle system java library returns byte arrays which do not have
    # the notion of a type like json does. Therefore, this test class is
    # questionable. We might need to form our values internally to strings always,
    # so our validator always receives strings / byte arrays to handle.

    def test_check_type_string(self, attribute_validator: AttributeValidator):
        """Test string type checking."""
        assert attribute_validator._check_type("hello", "string") is True
        assert attribute_validator._check_type("", "string") is True
        assert attribute_validator._check_type(123, "string") is False
        assert attribute_validator._check_type(True, "string") is False

    def test_check_type_number(self, attribute_validator: AttributeValidator):
        """Test number type checking."""
        assert attribute_validator._check_type(123, "number") is True
        assert attribute_validator._check_type(12.5, "number") is True
        assert attribute_validator._check_type("123", "number") is False
        assert (
            attribute_validator._check_type(True, "number") is False
        )  # bool is not number

    def test_check_type_integer(self, attribute_validator: AttributeValidator):
        """Test integer type checking."""
        assert attribute_validator._check_type(123, "integer") is True
        assert attribute_validator._check_type(12.5, "integer") is False
        assert attribute_validator._check_type("123", "integer") is False
        assert (
            attribute_validator._check_type(True, "integer") is False
        )  # bool is not int

    def test_check_type_boolean(self, attribute_validator: AttributeValidator):
        """Test boolean type checking."""
        assert attribute_validator._check_type(True, "boolean") is True
        assert attribute_validator._check_type(False, "boolean") is True
        assert attribute_validator._check_type(1, "boolean") is False
        assert attribute_validator._check_type("true", "boolean") is False

    def test_check_type_unknown_type(self, attribute_validator: AttributeValidator):
        """Test unknown type"""
        assert attribute_validator._check_type("anything", "unknown_type") is False


# =============================================================================
# TestRegexValidation - Pattern matching tests
# =============================================================================


class TestRegexValidation:
    """Test regex pattern validation logic."""

    def test_check_regex_valid_pattern(self, attribute_validator: AttributeValidator):
        """Test regex with valid pattern."""
        # Simple pattern: digits only
        assert attribute_validator._check_regex("123", r"\d+") is True
        assert attribute_validator._check_regex("abc", r"\d+") is False

    def test_check_regex_cardinality_pattern(
        self, attribute_validator: AttributeValidator
    ):
        """Test regex for cardinality format."""
        # Cardinality pattern from spec
        pattern = r"^(\d+)(\.\.(\d+|\*))?$"

        assert attribute_validator._check_regex("1", pattern) is True
        assert attribute_validator._check_regex("01..01", pattern) is True
        assert attribute_validator._check_regex("0..1", pattern) is True
        assert attribute_validator._check_regex("1..*", pattern) is True
        assert attribute_validator._check_regex("2..3", pattern) is True
        assert attribute_validator._check_regex("abc", pattern) is False

    def test_check_regex_invalid_pattern(self, attribute_validator: AttributeValidator):
        """Test regex with invalid pattern."""
        assert attribute_validator._check_regex("anything", "[invalid") is False


# =============================================================================
# TestNumericIntervalValidation - Interval checking tests
# =============================================================================


class TestNumericIntervalValidation:
    """Test numeric interval validation logic."""

    def test_check_interval_min_only(self, attribute_validator: AttributeValidator):
        """Test interval with minimum only."""
        interval = "0..*"
        result = ValidationResult()

        assert (
            attribute_validator._check_cardinality_any(
                5, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                0, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                -1, interval, "test", "pid", result
            )
            is False
        )

    def test_check_interval_max_only(self, attribute_validator: AttributeValidator):
        """Test interval with maximum only."""
        interval = "0..100"
        result = ValidationResult()

        assert (
            attribute_validator._check_cardinality_any(
                50, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                100, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                101, interval, "test", "pid", result
            )
            is False
        )

    def test_check_interval_both_bounds(self, attribute_validator: AttributeValidator):
        """Test interval with both min and max."""
        interval = "10..20"
        result = ValidationResult()

        assert (
            attribute_validator._check_cardinality_any(
                15, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                10, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                20, interval, "test", "pid", result
            )
            is True
        )
        assert (
            attribute_validator._check_cardinality_any(
                9, interval, "test", "pid", result
            )
            is False
        )
        assert (
            attribute_validator._check_cardinality_any(
                21, interval, "test", "pid", result
            )
            is False
        )

    def test_check_interval_empty(self, attribute_validator: AttributeValidator):
        """Test empty interval (should accept nothing)."""
        interval = ""
        result = ValidationResult()

        assert (
            attribute_validator._check_cardinality_any(
                999, interval, "test", "pid", result
            )
            is False
        )
        assert (
            attribute_validator._check_cardinality_any(
                -999, interval, "test", "pid", result
            )
            is False
        )


# =============================================================================
# TestWhitelistBlacklistValidation - Whitelist/blacklist tests
# =============================================================================


class TestWhitelistBlacklistValidation:
    """Test whitelist and blacklist validation logic."""

    def test_validate_value_against_whitelist(
        self, attribute_validator: AttributeValidator
    ):
        """Test value validation against whitelist."""
        rules = SyntaxRules(syntax_pid="", whitelist=["red", "green", "blue"])

        # Valid: in whitelist
        result = attribute_validator._validate_syntax(
            "red", rules, "color", "owning_record_pid"
        )
        assert result.valid is True

        # Invalid: not in whitelist
        result = attribute_validator._validate_syntax(
            "yellow", rules, "color", "owning_record_pid"
        )
        assert result.valid is False
        assert len(result.errors) == 1

    def test_validate_value_against_blacklist(
        self, attribute_validator: AttributeValidator
    ):
        """Test value validation against blacklist."""
        rules = SyntaxRules(syntax_pid="", blacklist=["spam", "scam"])

        # Valid: not in blacklist
        result = attribute_validator._validate_syntax(
            "legit", rules, "type", "owning_record_pid"
        )
        assert result.valid is True

        # Invalid: in blacklist
        result = attribute_validator._validate_syntax(
            "spam", rules, "type", "owning_record_pid"
        )
        assert result.valid is False
        assert len(result.errors) == 1

    def test_validate_value_no_constraints(
        self, attribute_validator: AttributeValidator
    ):
        """Test value validation with no constraints."""
        rules = SyntaxRules(syntax_pid="")

        # Should be valid with no constraints
        result = attribute_validator._validate_syntax(
            "anything", rules, "field", "owning_record_pid"
        )
        assert result.valid is True

    def test_blacklist_rules_over_whitelist(
        self, attribute_validator: AttributeValidator
    ):
        """Test whitelist vs blacklist validation."""
        rules = SyntaxRules(
            syntax_pid="test",
            whitelist=["apple", "banana", "fruit"],
            blacklist=["orange", "grape", "fruit"],
        )

        # Whitelisted, not blacklisted -> works
        result = attribute_validator._validate_syntax(
            "apple", rules, "field", "owning_record_pid"
        )
        assert result.valid is True
        assert len(result.errors) == 0

        # Not whitelisted, blacklisted -> fails
        result = attribute_validator._validate_syntax(
            "orange", rules, "field", "owning_record_pid"
        )
        assert result.valid is False
        # not in whitelist, and in blacklist -> 2 errors
        assert len(result.errors) == 2

        # In Whitelist and in blacklist -> fails (blacklist rules)
        result = attribute_validator._validate_syntax(
            "fruit", rules, "field", "owning_record_pid"
        )
        assert result.valid is False
        # Whitelist check is ok, blacklist check fails
        assert len(result.errors) == 1


# =============================================================================
# TestIntegration - Integration tests with real type system
# =============================================================================


class TestIntegration:
    """Test integration with real type system data."""

    def test_validate_type_attribute_with_real_data(
        self, attribute_validator: AttributeValidator, registry: PidRegistry
    ):
        """Test validating 0.FDO/Type attribute definition."""
        # Get the Type attribute definition
        type_def = registry.resolve_pid("0.FDO/Type")
        assert type_def is not None

        # Validate it
        result = attribute_validator.validate(type_def, "0.FDO/Type")

        # Should check cardinality and type
        assert result.attributes_checked >= 1

    def test_validate_cardinality_attribute(
        self, attribute_validator: AttributeValidator, registry: PidRegistry
    ):
        """Test validating 0.FDO/Cardinality attribute definition."""
        # Get the Cardinality attribute definition
        card_def = registry.resolve_pid("0.FDO/Cardinality")
        assert card_def is not None

        # Validate it
        result = attribute_validator.validate(card_def, "0.FDO/Cardinality")

        # Should validate successfully
        assert result.errors == []
        assert result.valid

    def test_assemble_and_validate_combined(
        self,
        attribute_assembly: AttributeAssembly,
        attribute_validator: AttributeValidator,
    ):
        """Test assembling rules and then validating."""
        # Assemble rules for Type
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert rules.cardinality == "1..*"
        assert len(rules.syntax_rules) == 1
        assert rules.syntax_rules[0].primitive_types == ["string"]

        # Create a test record
        test_record = PidRecord(
            pid="test/Test",
            data={"0.FDO/Name": [{"value": "Test", "lang": "en"}]},
            source_pid="test/Test",
        )

        # Validate
        result = attribute_validator.validate(test_record, "test/Test")

        # Should complete without crashing
        assert result is not None
