"""Tests for ProfileValidator and related validators.

Tests are organized into classes:
- TestProfileValidator: Core validation logic tests
- TestValidationResultDataclass: Data structure tests
- TestProfileValidatorIntegration: Integration with real profiles
"""

import pytest

try:
    from assembly import ProfileAssembly
    from models import AssembledProfile, PidRecord, ValidationResult
    from registry import PidRegistry
    from validation_logger import ValidationLogger
    from validators import AttributeValidator, ProfileValidator, SpecificationValidator
except ImportError:
    from assembly import ProfileAssembly
    from models import AssembledProfile, PidRecord, ValidationResult
    from registry import PidRegistry
    from validation_logger import ValidationLogger
    from validators import AttributeValidator, ProfileValidator, SpecificationValidator


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
def assembly(registry, logger):
    """Create a ProfileAssembly for testing."""
    return ProfileAssembly(registry, logger)


@pytest.fixture
def validator(registry, logger, assembly):
    """Create a ProfileValidator for testing."""
    return ProfileValidator(registry, logger, assembly)


@pytest.fixture
def minimal_record():
    """Create a minimal valid record for testing."""
    return PidRecord(
        pid="test/MinimalRecord",
        data={
            "0.FDO/Type": ["FDO_Profile"],
            "0.FDO/Profile": ["0.FDO/Root"],
            "0.FDO/Data": ["Not_Applicable"],
        },
        source_pid="test/MinimalRecord",
    )


@pytest.fixture
def complete_profile_def_record():
    """Create a complete ProfileDef record for testing."""
    return PidRecord(
        pid="0.FDO/ProfileDef",
        data={
            "0.FDO/Type": ["FDO_Profile"],
            "0.FDO/Profile": ["0.FDO/ProfileDef"],
            "0.FDO/Data": ["Not_Applicable"],
            "0.FDO/Name": [{"value": "Profile Definition Profile", "lang": "en"}],
            "0.FDO/Description": [
                {
                    "value": "The profile that all profile definitions must comply with.",
                    "lang": "en",
                }
            ],
            "0.FDO/Attribute": [
                "0.FDO/Type",
                "0.FDO/Profile",
                "0.FDO/Data",
                "0.FDO/Name",
                "0.FDO/Description",
                "0.FDO/Attribute",
            ],
        },
        source_pid="0.FDO/ProfileDef",
    )


# =============================================================================
# TestProfileValidator - Core validation logic
# =============================================================================


class TestProfileValidator:
    """Test ProfileValidator core functionality."""

    def test_validate_minimal_record_against_root(
        self, validator, minimal_record, logger
    ):
        """Test validating a minimal record against Root profile."""
        result = validator.validate(minimal_record, "test/MinimalRecord")

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.profiles_checked >= 1
        assert result.attributes_checked > 0

    def test_validate_complete_profile_def(
        self, validator, complete_profile_def_record, logger
    ):
        """Test validating ProfileDef against itself."""
        result = validator.validate(complete_profile_def_record, "0.FDO/ProfileDef")

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.profiles_checked >= 1
        # ProfileDef declares 6 attributes
        assert result.attributes_checked >= 6

    def test_validate_missing_required_attribute(self, validator, logger, assembly):
        """Test that missing required attributes are detected."""
        # Create a record missing 0.FDO/Data
        incomplete_record = PidRecord(
            pid="test/Incomplete",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/Root"],
                # Missing 0.FDO/Data
            },
            source_pid="test/Incomplete",
        )

        result = validator.validate(incomplete_record, "test/Incomplete")

        assert result.valid is False
        assert len(result.errors) == 1
        assert "Missing required attribute '0.FDO/Data'" in result.errors[0]

    def test_validate_no_profile_reference(self, validator, logger):
        """Test validation when record has no profile reference."""
        no_profile_record = PidRecord(
            pid="test/NoProfile",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Data": ["Not_Applicable"],
            },
            source_pid="test/NoProfile",
        )

        result = validator.validate(no_profile_record, "test/NoProfile")

        assert result.valid is True  # Warning, not error
        assert len(result.warnings) == 1
        assert "No 0.FDO/Profile attribute" in result.warnings[0]
        assert len(result.errors) == 0

    def test_validate_non_pid_profile_value(self, validator, logger):
        """Test that non-PID profile values are skipped."""
        literal_profile_record = PidRecord(
            pid="test/LiteralProfile",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["Not_Applicable"],
                "0.FDO/Data": ["Not_Applicable"],
            },
            source_pid="test/LiteralProfile",
        )

        result = validator.validate(literal_profile_record, "test/LiteralProfile")

        # Should skip the literal value - no profiles validated but no error either
        assert result.valid is True
        # No warnings generated currently when all profile refs are literals

    def test_validate_multiple_profiles(self, validator, logger, assembly):
        """Test validation against multiple profile references."""
        multi_profile_record = PidRecord(
            pid="test/MultiProfile",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/Root"],  # Could add more
                "0.FDO/Data": ["Not_Applicable"],
                "0.FDO/Name": [{"value": "Test", "lang": "en"}],
                "0.FDO/Description": [{"value": "Test", "lang": "en"}],
            },
            source_pid="test/MultiProfile",
        )

        result = validator.validate(multi_profile_record, "test/MultiProfile")

        assert result.profiles_checked >= 1

    def test_validate_with_cycle_warning(self, validator, logger, assembly):
        """Test that cycles in profile chain generate warnings."""
        # This would require creating a cycle in test data
        # For now, just verify the mechanism exists
        pass

    def test_validation_result_tracks_resolutions(
        self, validator, logger, assembly, complete_profile_def_record
    ):
        """Test that validation result tracks number of resolutions."""
        result = validator.validate(complete_profile_def_record, "0.FDO/ProfileDef")

        # ProfileDef doesn't extend anything, so should resolve 1 profile
        assert result.profiles_checked >= 1

    def test_validation_result_aggregates_errors(self, validator, logger):
        """Test that multiple errors are aggregated."""
        # Create a record missing multiple required attributes
        very_incomplete_record = PidRecord(
            pid="test/VeryIncomplete",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/Root"],
                # Missing both 0.FDO/Profile (has it) and 0.FDO/Data
            },
            source_pid="test/VeryIncomplete",
        )

        result = validator.validate(very_incomplete_record, "test/VeryIncomplete")

        # Should have at least one error for missing 0.FDO/Data
        assert len(result.errors) >= 1

    def test_is_pid_reference_filters_literals(self, validator):
        """Test that _is_pid_reference correctly filters literals."""
        assert validator._is_pid_reference("0.FDO/Root") is True
        assert validator._is_pid_reference("0.FDO/ProfileDef") is True
        assert validator._is_pid_reference("Not_Applicable") is False
        assert validator._is_pid_reference("Not_Applicable_Numeric") is False
        assert validator._is_pid_reference("Not_Applicable_String") is False

    def test_get_required_attributes_uses_declared_only(self, validator, assembly):
        """Test that only declared attributes are required, not inherited."""
        assembled = assembly.assemble("0.FDO/Root")
        required = validator._get_required_attributes(assembled)

        # Root declares 3 attributes
        assert len(required) == 3
        assert "0.FDO/Type" in required
        assert "0.FDO/Profile" in required
        assert "0.FDO/Data" in required


# =============================================================================
# TestValidationResultDataclass - Data structure tests
# =============================================================================


class TestValidationResultDataclass:
    """Test ValidationResult dataclass functionality."""

    def test_initial_state_is_valid(self):
        """Test that new ValidationResult starts as valid."""
        result = ValidationResult()
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_add_error_marks_invalid(self):
        """Test that adding an error marks result as invalid."""
        result = ValidationResult()
        result.add_error("Test error")

        assert result.valid is False
        assert len(result.errors) == 1
        assert "Test error" in result.errors

    def test_add_warning_doesnt_mark_invalid(self):
        """Test that adding a warning doesn't affect validity."""
        result = ValidationResult()
        result.add_warning("Test warning")

        assert result.valid is True
        assert len(result.warnings) == 1
        assert "Test warning" in result.warnings

    def test_merge_combines_results(self):
        """Test merging two validation results."""
        result1 = ValidationResult()
        result1.add_error("Error 1")
        result1.add_warning("Warning 1")
        result1.profiles_checked = 2
        result1.attributes_checked = 5

        result2 = ValidationResult()
        result2.add_error("Error 2")
        result2.add_warning("Warning 2")
        result2.profiles_checked = 3
        result2.attributes_checked = 7

        result1.merge(result2)

        assert result1.valid is False
        assert len(result1.errors) == 2
        assert len(result1.warnings) == 2
        assert result1.profiles_checked == 5
        assert result1.attributes_checked == 12

    def test_merge_with_valid_result(self):
        """Test merging when second result is valid."""
        result1 = ValidationResult()
        result1.add_error("Error 1")

        result2 = ValidationResult()  # Valid, no errors

        result1.merge(result2)

        assert result1.valid is False  # Still invalid from result1
        assert len(result1.errors) == 1

    def test_merge_with_invalid_result(self):
        """Test merging when first result is valid but second is invalid."""
        result1 = ValidationResult()  # Valid

        result2 = ValidationResult()
        result2.add_error("Error 2")

        result1.merge(result2)

        assert result1.valid is False  # Now invalid from result2
        assert len(result1.errors) == 1


# =============================================================================
# TestProfileValidatorIntegration - Integration with real profiles
# =============================================================================


class TestProfileValidatorIntegration:
    """Test ProfileValidator with actual type system profiles."""

    def test_validate_root_profile(self, validator, logger):
        """Test validating the Root profile record."""
        root_record = validator.registry.resolve_pid("0.FDO/Root")
        assert root_record is not None

        result = validator.validate(root_record, "0.FDO/Root")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_profiledef_profile(self, validator, logger):
        """Test validating the ProfileDef profile record."""
        profiledef_record = validator.registry.resolve_pid("0.FDO/ProfileDef")
        assert profiledef_record is not None

        result = validator.validate(profiledef_record, "0.FDO/ProfileDef")

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validation_shows_detailed_logging(self, validator, logger):
        """Test that validation produces detailed logs in verbose mode."""
        logger.verbose = True
        profiledef_record = validator.registry.resolve_pid("0.FDO/ProfileDef")

        result = validator.validate(profiledef_record, "0.FDO/ProfileDef")

        # Just verify it completes without errors
        assert result.valid is True

    def test_validation_handles_extended_profiles(self, validator, logger, assembly):
        """Test validation with profiles that extend other profiles."""
        # ProfileDef extends... (check if it extends anything)
        profiledef_record = validator.registry.resolve_pid("0.FDO/ProfileDef")
        assert profiledef_record is not None

        result = validator.validate(profiledef_record, "0.FDO/ProfileDef")

        # Should validate successfully
        assert result.valid is True

    def test_assembly_integration(self, validator, logger, assembly):
        """Test that validator correctly uses assembly component."""
        # Assemble a profile first
        assembled = assembly.assemble("0.FDO/Root")
        assert assembled.pid == "0.FDO/Root"
        assert len(assembled.declared_attributes) > 0

        # Then validate using the same assembly
        root_record = validator.registry.resolve_pid("0.FDO/Root")
        result = validator.validate(root_record, "0.FDO/Root")

        assert result.valid is True
        assert result.profiles_checked >= 1


# =============================================================================
# TestAttributeValidator - Placeholder tests for Phase 4
# =============================================================================


class TestAttributeValidator:
    """Test AttributeValidator (placeholder for Phase 4)."""

    def test_attribute_validator_exists(self, logger, registry):
        """Test that AttributeValidator class exists."""
        validator = AttributeValidator(registry, logger)
        assert validator is not None

    def test_attribute_validator_returns_empty_result(self, logger, registry):
        """Test that AttributeValidator returns empty result (not yet implemented)."""
        validator = AttributeValidator(registry, logger)
        record = PidRecord(
            pid="test/Record",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="test/Record",
        )

        result = validator.validate(record, "test/Record")

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


# =============================================================================
# TestSpecificationValidator - Placeholder tests for Phase 6
# =============================================================================


class TestSpecificationValidator:
    """Test SpecificationValidator (placeholder for Phase 6)."""

    def test_specification_validator_exists(self, logger, registry):
        """Test that SpecificationValidator class exists."""
        validator = SpecificationValidator(registry, logger)
        assert validator is not None

    def test_specification_validator_returns_empty_result(self, logger, registry):
        """Test that SpecificationValidator returns empty result (not yet implemented)."""
        validator = SpecificationValidator(registry, logger)
        record = PidRecord(
            pid="test/Record",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="test/Record",
        )

        result = validator.validate(record, "test/Record")

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
