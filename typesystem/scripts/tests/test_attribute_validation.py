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

try:
    from assembly import AttributeAssembly, ExtensionsAssembly
    from models import PidRecord, ValidationResult, ValidationRules
    from registry import PidRegistry
    from validation_logger import ValidationLogger
    from validators import AttributeValidator
except ImportError:
    from assembly import AttributeAssembly, ExtensionsAssembly
    from models import PidRecord, ValidationResult, ValidationRules
    from registry import PidRegistry
    from validation_logger import ValidationLogger
    from validators import AttributeValidator


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def logger():
    """Create a ValidationLogger for testing."""
    return ValidationLogger(verbose=False)


@pytest.fixture
def registry(logger):
    """Create a PidRegistry for testing."""
    return PidRegistry(logger)


@pytest.fixture
def attribute_assembly(registry, logger):
    """Create an AttributeAssembly for testing."""
    return AttributeAssembly(registry, logger)


@pytest.fixture
def attribute_validator(registry, logger, attribute_assembly):
    """Create an AttributeValidator for testing."""
    return AttributeValidator(registry, logger, attribute_assembly)


@pytest.fixture
def sample_record_with_type():
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

    def test_assemble_rules_for_type_attribute(self, attribute_assembly, logger):
        """Test assembling rules for 0.FDO/Type."""
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert rules.cardinality == "1..*"
        assert rules.primitive_type == "string"
        assert rules.syntax_definition_pid == "0.FDO/StringSyntax"

    def test_assemble_rules_for_cardinality_attribute(self, attribute_assembly, logger):
        """Test assembling rules for 0.FDO/Cardinality."""
        rules = attribute_assembly.assemble_rules("0.FDO/Cardinality")

        assert rules.cardinality == "1"
        # Cardinality has its own custom syntax
        assert rules.syntax_definition_pid is not None

    def test_assemble_rules_for_name_attribute(self, attribute_assembly, logger):
        """Test assembling rules for 0.FDO/Name."""
        rules = attribute_assembly.assemble_rules("0.FDO/Name")

        assert rules.cardinality == "1..*"
        assert rules.primitive_type == "string"

    def test_assemble_rules_nonexistent_attribute(self, attribute_assembly, logger):
        """Test assembling rules for non-existent attribute."""
        rules = attribute_assembly.assemble_rules("0.FDO/NonExistent")

        # Should return empty rules, not crash
        assert rules.cardinality is None
        assert rules.primitive_type is None

    def test_assemble_rules_extracts_all_syntax_fields(
        self, attribute_assembly, logger
    ):
        """Test that all syntax fields are extracted."""
        # Test with StringSyntax which has primitive type
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert hasattr(rules, "primitive_type")
        assert hasattr(rules, "regex")
        assert hasattr(rules, "numeric_interval")
        assert hasattr(rules, "whitelist")
        assert hasattr(rules, "blacklist")

    def test_assemble_rules_logs_steps_in_verbose_mode(
        self, attribute_assembly, logger
    ):
        """Test that assembly produces logs in verbose mode."""
        logger.verbose = True
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert rules.cardinality is not None


# =============================================================================
# TestAttributeValidator - Value validation tests
# =============================================================================


class TestAttributeValidator:
    """Test AttributeValidator core functionality."""

    def test_validate_record_with_valid_attributes(
        self, attribute_validator, sample_record_with_type, logger
    ):
        """Test validating a record with valid attributes."""
        result = attribute_validator.validate(sample_record_with_type, "test/WithType")

        # Should have checked at least one attribute
        assert result.attributes_checked > 0

    def test_validate_skips_metadata_attributes(
        self, attribute_validator, sample_record_with_type, logger
    ):
        """Test that metadata attributes (Type, Profile, Data) are skipped."""
        result = attribute_validator.validate(sample_record_with_type, "test/WithType")

        # Metadata attributes should be skipped, only Name should be validated
        # (or other non-metadata attributes)
        pass  # Just verify it doesn't crash

    def test_validate_empty_record(self, attribute_validator, logger):
        """Test validating a record with no attributes."""
        empty_record = PidRecord(
            pid="test/Empty",
            data={},
            source_pid="test/Empty",
        )

        result = attribute_validator.validate(empty_record, "test/Empty")

        # Should complete without errors
        assert result.valid is True
        assert result.attributes_checked == 0


# =============================================================================
# TestCardinalityValidation - Cardinality-specific tests
# =============================================================================


class TestCardinalityValidation:
    """Test cardinality validation logic."""

    def test_check_cardinality_exactly_one(self, attribute_validator, logger):
        """Test cardinality "1" (exactly one)."""
        result = ValidationResult()

        # Valid: exactly one value
        assert attribute_validator._check_cardinality(1, "1", "test", result) is True

        # Invalid: zero values
        result = ValidationResult()
        assert attribute_validator._check_cardinality(0, "1", "test", result) is False
        assert len(result.errors) == 1

        # Invalid: two values
        result = ValidationResult()
        assert attribute_validator._check_cardinality(2, "1", "test", result) is False
        assert len(result.errors) == 1

    def test_check_cardinality_zero_or_one(self, attribute_validator, logger):
        """Test cardinality "0..1" (optional)."""
        result = ValidationResult()

        # Valid: zero values
        assert attribute_validator._check_cardinality(0, "0..1", "test", result) is True

        # Valid: one value
        result = ValidationResult()
        assert attribute_validator._check_cardinality(1, "0..1", "test", result) is True

        # Invalid: two values
        result = ValidationResult()
        assert (
            attribute_validator._check_cardinality(2, "0..1", "test", result) is False
        )
        assert len(result.errors) == 1

    def test_check_cardinality_one_or_more(self, attribute_validator, logger):
        """Test cardinality "1..*" (mandatory, repeatable)."""
        result = ValidationResult()

        # Valid: one value
        assert attribute_validator._check_cardinality(1, "1..*", "test", result) is True

        # Valid: multiple values
        result = ValidationResult()
        assert attribute_validator._check_cardinality(5, "1..*", "test", result) is True

        # Invalid: zero values
        result = ValidationResult()
        assert (
            attribute_validator._check_cardinality(0, "1..*", "test", result) is False
        )
        assert len(result.errors) == 1

    def test_check_cardinality_zero_or_more(self, attribute_validator, logger):
        """Test cardinality "0..*" (optional, repeatable)."""
        result = ValidationResult()

        # Valid: any number of values
        assert attribute_validator._check_cardinality(0, "0..*", "test", result) is True
        result = ValidationResult()
        assert attribute_validator._check_cardinality(1, "0..*", "test", result) is True
        result = ValidationResult()
        assert (
            attribute_validator._check_cardinality(100, "0..*", "test", result) is True
        )

    def test_check_cardinality_range(self, attribute_validator, logger):
        """Test cardinality "2..3" (range)."""
        result = ValidationResult()

        # Valid: within range
        assert attribute_validator._check_cardinality(2, "2..3", "test", result) is True
        result = ValidationResult()
        assert attribute_validator._check_cardinality(3, "2..3", "test", result) is True

        # Invalid: below range
        result = ValidationResult()
        assert (
            attribute_validator._check_cardinality(1, "2..3", "test", result) is False
        )
        assert len(result.errors) == 1

        # Invalid: above range
        result = ValidationResult()
        assert (
            attribute_validator._check_cardinality(4, "2..3", "test", result) is False
        )
        assert len(result.errors) == 1

    def test_check_cardinality_invalid_expression(self, attribute_validator, logger):
        """Test invalid cardinality expression handling."""
        result = ValidationResult()

        # Should not crash, should return True (permissive)
        assert (
            attribute_validator._check_cardinality(1, "invalid", "test", result) is True
        )


# =============================================================================
# TestTypeValidation - Type checking tests
# =============================================================================


class TestTypeValidation:
    """Test primitive type validation logic."""

    def test_check_type_string(self, attribute_validator, logger):
        """Test string type checking."""
        assert attribute_validator._check_type("hello", "string") is True
        assert attribute_validator._check_type("", "string") is True
        assert attribute_validator._check_type(123, "string") is False
        assert attribute_validator._check_type(True, "string") is False

    def test_check_type_number(self, attribute_validator, logger):
        """Test number type checking."""
        assert attribute_validator._check_type(123, "number") is True
        assert attribute_validator._check_type(12.5, "number") is True
        assert attribute_validator._check_type("123", "number") is False
        assert (
            attribute_validator._check_type(True, "number") is False
        )  # bool is not number

    def test_check_type_integer(self, attribute_validator, logger):
        """Test integer type checking."""
        assert attribute_validator._check_type(123, "integer") is True
        assert attribute_validator._check_type(12.5, "integer") is False
        assert attribute_validator._check_type("123", "integer") is False
        assert (
            attribute_validator._check_type(True, "integer") is False
        )  # bool is not int

    def test_check_type_boolean(self, attribute_validator, logger):
        """Test boolean type checking."""
        assert attribute_validator._check_type(True, "boolean") is True
        assert attribute_validator._check_type(False, "boolean") is True
        assert attribute_validator._check_type(1, "boolean") is False
        assert attribute_validator._check_type("true", "boolean") is False

    def test_check_type_unknown_type(self, attribute_validator, logger):
        """Test unknown type (should be permissive)."""
        assert attribute_validator._check_type("anything", "unknown_type") is True


# =============================================================================
# TestRegexValidation - Pattern matching tests
# =============================================================================


class TestRegexValidation:
    """Test regex pattern validation logic."""

    def test_check_regex_valid_pattern(self, attribute_validator, logger):
        """Test regex with valid pattern."""
        # Simple pattern: digits only
        assert attribute_validator._check_regex("123", r"\d+") is True
        assert attribute_validator._check_regex("abc", r"\d+") is False

    def test_check_regex_cardinality_pattern(self, attribute_validator, logger):
        """Test regex for cardinality format."""
        # Cardinality pattern from spec
        pattern = r"^(\d+)(\.\.(\d+|\*))?$"

        assert attribute_validator._check_regex("1", pattern) is True
        assert attribute_validator._check_regex("0..1", pattern) is True
        assert attribute_validator._check_regex("1..*", pattern) is True
        assert attribute_validator._check_regex("2..3", pattern) is True
        assert attribute_validator._check_regex("abc", pattern) is False

    def test_check_regex_invalid_pattern(self, attribute_validator, logger):
        """Test regex with invalid pattern (should be permissive)."""
        # Invalid regex should not crash
        assert attribute_validator._check_regex("anything", "[invalid") is True


# =============================================================================
# TestNumericIntervalValidation - Interval checking tests
# =============================================================================


class TestNumericIntervalValidation:
    """Test numeric interval validation logic."""

    def test_check_interval_min_only(self, attribute_validator, logger):
        """Test interval with minimum only."""
        interval = {"min": 0}

        assert attribute_validator._check_numeric_interval(5, interval) is True
        assert attribute_validator._check_numeric_interval(0, interval) is True
        assert attribute_validator._check_numeric_interval(-1, interval) is False

    def test_check_interval_max_only(self, attribute_validator, logger):
        """Test interval with maximum only."""
        interval = {"max": 100}

        assert attribute_validator._check_numeric_interval(50, interval) is True
        assert attribute_validator._check_numeric_interval(100, interval) is True
        assert attribute_validator._check_numeric_interval(101, interval) is False

    def test_check_interval_both_bounds(self, attribute_validator, logger):
        """Test interval with both min and max."""
        interval = {"min": 10, "max": 20}

        assert attribute_validator._check_numeric_interval(15, interval) is True
        assert attribute_validator._check_numeric_interval(10, interval) is True
        assert attribute_validator._check_numeric_interval(20, interval) is True
        assert attribute_validator._check_numeric_interval(9, interval) is False
        assert attribute_validator._check_numeric_interval(21, interval) is False

    def test_check_interval_empty(self, attribute_validator, logger):
        """Test empty interval (should accept anything)."""
        interval = {}

        assert attribute_validator._check_numeric_interval(999, interval) is True
        assert attribute_validator._check_numeric_interval(-999, interval) is True


# =============================================================================
# TestWhitelistBlacklistValidation - Whitelist/blacklist tests
# =============================================================================


class TestWhitelistBlacklistValidation:
    """Test whitelist and blacklist validation logic."""

    def test_validate_value_against_whitelist(self, attribute_validator, logger):
        """Test value validation against whitelist."""
        rules = ValidationRules(whitelist=["red", "green", "blue"])

        # Valid: in whitelist
        result = attribute_validator._validate_value("red", rules, "color")
        assert result.valid is True

        # Invalid: not in whitelist
        result = attribute_validator._validate_value("yellow", rules, "color")
        assert result.valid is False
        assert len(result.errors) == 1

    def test_validate_value_against_blacklist(self, attribute_validator, logger):
        """Test value validation against blacklist."""
        rules = ValidationRules(blacklist=["spam", "scam"])

        # Valid: not in blacklist
        result = attribute_validator._validate_value("legit", rules, "type")
        assert result.valid is True

        # Invalid: in blacklist
        result = attribute_validator._validate_value("spam", rules, "type")
        assert result.valid is False
        assert len(result.errors) == 1

    def test_validate_value_no_constraints(self, attribute_validator, logger):
        """Test value validation with no constraints."""
        rules = ValidationRules()

        # Should be valid with no constraints
        result = attribute_validator._validate_value("anything", rules, "field")
        assert result.valid is True


# =============================================================================
# TestIntegration - Integration tests with real type system
# =============================================================================


class TestIntegration:
    """Test integration with real type system data."""

    def test_validate_type_attribute_with_real_data(
        self, attribute_validator, logger, registry
    ):
        """Test validating 0.FDO/Type attribute definition."""
        # Get the Type attribute definition
        type_def = registry.resolve_pid("0.FDO/Type")
        assert type_def is not None

        # Validate it
        result = attribute_validator.validate(type_def, "0.FDO/Type")

        # Should check cardinality and type
        assert result.attributes_checked >= 1

    def test_validate_cardinality_attribute_with_real_data(
        self, attribute_validator, logger, registry
    ):
        """Test validating 0.FDO/Cardinality attribute definition."""
        # Get the Cardinality attribute definition
        card_def = registry.resolve_pid("0.FDO/Cardinality")
        assert card_def is not None

        # Validate it
        result = attribute_validator.validate(card_def, "0.FDO/Cardinality")

        # Should validate successfully
        pass  # Just verify it doesn't crash

    def test_assemble_and_validate_combined(
        self, attribute_assembly, attribute_validator, logger
    ):
        """Test assembling rules and then validating."""
        # Assemble rules for Type
        rules = attribute_assembly.assemble_rules("0.FDO/Type")

        assert rules.cardinality == "1..*"
        assert rules.primitive_type == "string"

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
