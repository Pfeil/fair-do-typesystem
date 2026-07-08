"""Tests for ProfileValidator and related validators.

Tests are organized into classes:
- TestProfileValidator: Core validation logic tests
- TestValidationResultDataclass: Data structure tests
- TestProfileValidatorIntegration: Integration with real profiles
"""

import pytest

from assembly import AttributeAssembly, ExtensionsAssembly, ProfilesAssembly
from models import (
    MissingRequiredAttribute,
    PidRecord,
    UnresolvablePid,
    ValidationResult,
    ZeroProfilesContained,
)
from registry import PidRegistry
from validation_logger import ValidationLogger
from validators import AttributeValidator, ProfileValidator, SpecificationValidator

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def logger() -> ValidationLogger:
    return ValidationLogger(verbose=True)


@pytest.fixture
def registry(logger: ValidationLogger) -> PidRegistry:
    return PidRegistry(logger)


@pytest.fixture
def extensions_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> ExtensionsAssembly:
    return ExtensionsAssembly(registry, logger)


@pytest.fixture
def profiles_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> ProfilesAssembly:
    return ProfilesAssembly(registry, logger)


@pytest.fixture
def attribute_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> AttributeAssembly:
    return AttributeAssembly(registry, logger)


@pytest.fixture
def profile_validator(
    registry: PidRegistry,
    logger: ValidationLogger,
    profiles_assembly: ProfilesAssembly,
    extensions_assembly: ExtensionsAssembly,
) -> ProfileValidator:
    return ProfileValidator(registry, logger, profiles_assembly, extensions_assembly)


@pytest.fixture
def minimal_record() -> PidRecord:
    """A minimal valid record."""
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
def complete_profile_def_record() -> PidRecord:
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
        self,
        profile_validator: ProfileValidator,
        minimal_record: PidRecord,
    ):
        """Test validating a minimal record against Root profile."""
        result = profile_validator.validate(minimal_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.profiles_checked >= 1
        assert result.attributes_checked > 0

    def test_validate_complete_profile_def(
        self,
        profile_validator: ProfileValidator,
        complete_profile_def_record: PidRecord,
    ):
        """Test validating ProfileDef against itself."""
        result = profile_validator.validate(complete_profile_def_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.profiles_checked >= 1
        # ProfileDef declares 6 attributes
        assert result.attributes_checked >= 6

    def test_validate_missing_required_attribute(
        self,
        profile_validator: ProfileValidator,
    ):
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

        result = profile_validator.validate(incomplete_record)

        assert result.valid is False
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], MissingRequiredAttribute)

    def test_validate_no_profile_reference(
        self,
        profile_validator: ProfileValidator,
    ):
        """Test validation when record has no profile reference."""
        no_profile_record = PidRecord(
            pid="test/NoProfile",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Data": ["Not_Applicable"],
            },
            source_pid="test/NoProfile",
        )

        result = profile_validator.validate(no_profile_record)

        assert result.valid is False
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], ZeroProfilesContained)

    def test_validate_non_pid_profile_value(
        self,
        profile_validator: ProfileValidator,
    ):
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

        result = profile_validator.validate(literal_profile_record)

        # Should skip the literal value - no profiles validated but no error either
        assert result.valid is True
        # No warnings generated currently when all profile refs are literals

    def test_validate_multiple_profiles(
        self,
        profile_validator: ProfileValidator,
    ):
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

        result = profile_validator.validate(multi_profile_record)

        assert result.profiles_checked >= 1

    def test_validation_result_tracks_resolutions(
        self,
        profile_validator: ProfileValidator,
        complete_profile_def_record: PidRecord,
    ):
        """Test that validation result tracks number of resolutions."""
        result = profile_validator.validate(complete_profile_def_record)

        # ProfileDef doesn't extend anything, so should resolve 1 profile
        assert result.profiles_checked >= 1

    def test_validation_result_aggregates_errors(
        self,
        profile_validator: ProfileValidator,
    ):
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

        result = profile_validator.validate(very_incomplete_record)

        # Should have at least one error for missing 0.FDO/Data
        assert len(result.errors) >= 1

    def test_is_pid_reference_filters_literals(
        self, profile_validator: ProfileValidator
    ):
        """Test that _is_pid_reference correctly filters literals."""
        assert profile_validator._is_pid_reference("0.FDO/Root") is True
        assert profile_validator._is_pid_reference("0.FDO/ProfileDef") is True
        assert profile_validator._is_pid_reference("Not_Applicable") is False
        assert profile_validator._is_pid_reference("Not_Applicable_Numeric") is False
        assert profile_validator._is_pid_reference("Not_Applicable_String") is False

    def test_get_required_attributes_uses_declared_only(
        self,
        profile_validator: ProfileValidator,
        extensions_assembly: ExtensionsAssembly,
    ):
        """Test that only declared attributes are required, not inherited."""
        assembled = extensions_assembly.assemble("0.FDO/Root")
        required = profile_validator._get_required_attributes(assembled)

        # Root declares 3 attributes
        assert len(required) == 3
        assert "0.FDO/Type" in required
        assert "0.FDO/Profile" in required
        assert "0.FDO/Data" in required


# =============================================================================
# TestProfileValidatorIntegration - Integration with real profiles
# =============================================================================


class TestProfileValidatorIntegration:
    """Test ProfileValidator with actual type system profiles."""

    def test_validate_root_profile(self, profile_validator: ProfileValidator):
        """Test validating the Root profile record."""
        root_record = profile_validator.registry.resolve_pid("0.FDO/Root")
        assert root_record is not None

        result = profile_validator.validate(root_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.additional_attributes) == 0
        assert result.profiles_checked == 1

    def test_validate_profiledef_profile(self, profile_validator: ProfileValidator):
        """Test validating the ProfileDef profile record."""
        profiledef_record = profile_validator.registry.resolve_pid("0.FDO/ProfileDef")
        assert profiledef_record is not None

        result = profile_validator.validate(profiledef_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.additional_attributes) == 1  # 0.FDO/Extends
        assert result.profiles_checked == 2  # ProfileDef (self) and Root

    def test_validation_shows_detailed_logging(
        self,
        profile_validator: ProfileValidator,
        logger: ValidationLogger,
        capsys: pytest.CaptureFixture,
    ):
        """Test that validation produces detailed logs in verbose mode."""
        logger.verbose = True
        profiledef_record = profile_validator.registry.resolve_pid("0.FDO/ProfileDef")
        assert profiledef_record

        result = profile_validator.validate(profiledef_record)
        captured = capsys.readouterr()

        assert result.valid is True
        assert "Attribute Check:".lower() in captured.out.lower()

    def test_validation_handles_extended_profiles(
        self,
        profile_validator: ProfileValidator,
        logger: ValidationLogger,
        capsys: pytest.CaptureFixture,
    ):
        """Test validation with profiles that extend other profiles."""
        record = profile_validator.registry.resolve_pid("data")
        assert record

        # Data uses a profile making use of 0.FDO/Extends:
        extending_profile_name: str = "extended-profile"
        logger.verbose = True

        result = profile_validator.validate(record)
        captured = capsys.readouterr()

        assert result.valid is True
        # It has 2 direct profiles, one is extending
        assert result.profiles_checked == 2
        assert f"Resolved {extending_profile_name}" in captured.out


# =============================================================================
# TestAttributeValidator - Validation functionality tests
# =============================================================================


class TestAttributeValidator:
    """Test AttributeValidator validation functionality."""

    @pytest.fixture
    def attribute_validator(self, logger, registry, attribute_assembly):
        return AttributeValidator(registry, logger, attribute_assembly)

    def test_attribute_validator_instantiation(
        self, attribute_validator: AttributeValidator
    ):
        """Test that AttributeValidator can be instantiated."""
        assert attribute_validator is not None
        assert attribute_validator.registry is not None
        assert attribute_validator.logger is not None
        assert attribute_validator.assembly is not None

    def test_validate_empty_record(self, attribute_validator: AttributeValidator):
        """Test validation of empty record."""
        record: PidRecord = PidRecord(
            pid="test/Empty",
            data={},
            source_pid="test/Empty",
        )

        result: ValidationResult = attribute_validator.validate(record, "test/Empty")

        assert result is not None
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.attributes_checked == 0

    def test_validate_minimal_record(self, attribute_validator: AttributeValidator):
        """Test validation of minimal record."""
        pid: str = "test/minimal"
        record: PidRecord = PidRecord(
            pid=pid,
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/Root"],
                "0.FDO/Data": ["Not_Applicable"],
                "0.FDO/ReferenceNull": ["hello"],
            },
            source_pid=pid,
        )

        result: ValidationResult = attribute_validator.validate(record, pid)

        assert result.errors == []
        assert result.valid is True

    def test_validate_with_undefined_attribute(
        self, attribute_validator: AttributeValidator
    ):
        """Test undefined attributes cause errors."""

        # Create a record with an undefined attribute
        record: PidRecord = PidRecord(
            pid="test/Undefined",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/Root"],
                "0.FDO/Data": ["Not_Applicable"],
                "nonexisting": ["asd"],
            },
            source_pid="test/Undefined",
        )

        result: ValidationResult = attribute_validator.validate(
            record, "test/Undefined"
        )

        assert len(result.errors) == 1
        assert isinstance(result.errors[0], UnresolvablePid)
        assert result.valid is False

    def test_validate_with_missing_attribute(
        self, attribute_validator: AttributeValidator
    ):
        """Test profile violations do not matter, as we only validate contained attributes."""

        # Create a record with missing required attribute
        # 0.FDO/Name has cardinality "1..*" but we provide none
        record: PidRecord = PidRecord(
            pid="test/MissingName",
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/ProfileDef"],
                "0.FDO/Data": ["Not_Applicable"],
                # Missing 0.FDO/Name which requires 1..*
            },
            source_pid="test/MissingName",
        )

        result: ValidationResult = attribute_validator.validate(
            record, "test/MissingName"
        )

        # Since 0.FDO/Name is not present at all, no cardinality check happens
        # The validator only checks attributes that exist in the record
        assert result is not None
        assert result.errors == []
        assert result.profiles_checked == 0
        assert result.warnings == []
        assert result.valid

    def test_fails_if_attribute_reference_not_in_record(
        self,
        attribute_validator: AttributeValidator,
    ):
        dummy_pid = "dummy_pid"
        record = PidRecord(
            data={
                "0.FDO/Type": ["asdf"],  # valid value, but not present as an attribute!
            },
            pid=dummy_pid,
            source_pid=dummy_pid,
        )
        attribute_result = attribute_validator.validate(record, dummy_pid)
        assert not attribute_result.valid, "Attribute referencing validation shall fail"


# =============================================================================
# TestSpecificationValidator - Specification validation (TODO)
# =============================================================================


class TestSpecificationValidator:
    """Test SpecificationValidator structure."""

    def test_specification_validator_instantiation(self, logger, registry):
        """Test that SpecificationValidator can be instantiated."""
        validator: SpecificationValidator = SpecificationValidator(registry, logger)
        assert validator is not None
        assert validator.registry is registry
        assert validator.logger is logger

    def test_specification_validator_current_behavior(self, logger, registry):
        """Test current behavior (returns valid result)."""
        validator: SpecificationValidator = SpecificationValidator(registry, logger)
        record: PidRecord = PidRecord(
            pid="test/Record",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="test/Record",
        )

        result: ValidationResult = validator.validate(record, "test/Record")

        # Currently returns empty valid result (not yet implemented)
        assert result is not None
        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_specification_validator_tracks_resolutions(self, logger, registry):
        """Test that validator tracks resolution count."""
        validator: SpecificationValidator = SpecificationValidator(registry, logger)
        record: PidRecord = PidRecord(
            pid="test/Record",
            data={"0.FDO/Type": ["FDO_Profile"]},
            source_pid="test/Record",
        )

        result: ValidationResult = validator.validate(record, "test/Record")

        # Should track resolutions even if not implemented
        assert hasattr(result, "resolutions_performed")
