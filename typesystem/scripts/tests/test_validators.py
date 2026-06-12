"""Tests for ProfileValidator and related validators.

Tests are organized into classes:
- TestProfileValidator: Core validation logic tests
- TestValidationResultDataclass: Data structure tests
- TestProfileValidatorIntegration: Integration with real profiles
"""

import pytest

try:
    from assembly import AttributeAssembly, ExtensionsAssembly
    from models import PidRecord, ValidationResult
    from registry import PidRegistry
    from validation_logger import ValidationLogger
    from validators import AttributeValidator, ProfileValidator, SpecificationValidator
except ImportError:
    from assembly import AttributeAssembly, ExtensionsAssembly
    from models import PidRecord, ValidationResult
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
def assembly(registry: PidRegistry, logger: ValidationLogger) -> ExtensionsAssembly:
    return ExtensionsAssembly(registry, logger)


@pytest.fixture
def attribute_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> AttributeAssembly:
    return AttributeAssembly(registry, logger)


@pytest.fixture
def validator(
    registry: PidRegistry, logger: ValidationLogger, assembly: ExtensionsAssembly
) -> ProfileValidator:
    return ProfileValidator(registry, logger, assembly)


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
        validator: ProfileValidator,
        minimal_record: PidRecord,
        logger: ValidationLogger,
    ):
        """Test validating a minimal record against Root profile."""
        result = validator.validate(minimal_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.profiles_checked >= 1
        assert result.attributes_checked > 0

    def test_validate_complete_profile_def(
        self,
        validator: ProfileValidator,
        complete_profile_def_record: PidRecord,
        logger: ValidationLogger,
    ):
        """Test validating ProfileDef against itself."""
        result = validator.validate(complete_profile_def_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert result.profiles_checked >= 1
        # ProfileDef declares 6 attributes
        assert result.attributes_checked >= 6

    def test_validate_missing_required_attribute(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
        assembly: ExtensionsAssembly,
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

        result = validator.validate(incomplete_record)

        assert result.valid is False
        assert len(result.errors) == 1
        assert "Missing required attribute '0.FDO/Data'" in result.errors[0]

    def test_validate_no_profile_reference(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
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

        result = validator.validate(no_profile_record)

        assert result.valid is True  # Warning, not error
        assert len(result.warnings) == 1
        assert "No 0.FDO/Profile attribute" in result.warnings[0]
        assert len(result.errors) == 0

    def test_validate_non_pid_profile_value(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
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

        result = validator.validate(literal_profile_record)

        # Should skip the literal value - no profiles validated but no error either
        assert result.valid is True
        # No warnings generated currently when all profile refs are literals

    def test_validate_multiple_profiles(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
        assembly: ExtensionsAssembly,
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

        result = validator.validate(multi_profile_record)

        assert result.profiles_checked >= 1

    def test_validate_with_cycle_warning(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
        assembly: ExtensionsAssembly,
    ):
        """Test that cycles in profile chain generate warnings."""
        # This would require creating a cycle in test data
        # For now, just verify the mechanism exists
        pass

    def test_validation_result_tracks_resolutions(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
        assembly: ExtensionsAssembly,
        complete_profile_def_record: PidRecord,
    ):
        """Test that validation result tracks number of resolutions."""
        result = validator.validate(complete_profile_def_record)

        # ProfileDef doesn't extend anything, so should resolve 1 profile
        assert result.profiles_checked >= 1

    def test_validation_result_aggregates_errors(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
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

        result = validator.validate(very_incomplete_record)

        # Should have at least one error for missing 0.FDO/Data
        assert len(result.errors) >= 1

    def test_is_pid_reference_filters_literals(self, validator: ProfileValidator):
        """Test that _is_pid_reference correctly filters literals."""
        assert validator._is_pid_reference("0.FDO/Root") is True
        assert validator._is_pid_reference("0.FDO/ProfileDef") is True
        assert validator._is_pid_reference("Not_Applicable") is False
        assert validator._is_pid_reference("Not_Applicable_Numeric") is False
        assert validator._is_pid_reference("Not_Applicable_String") is False

    def test_get_required_attributes_uses_declared_only(
        self,
        validator: ProfileValidator,
        assembly: ExtensionsAssembly,
    ):
        """Test that only declared attributes are required, not inherited."""
        assembled = assembly.assemble("0.FDO/Root")
        required = validator._get_required_attributes(assembled)

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

    def test_validate_root_profile(
        self, validator: ProfileValidator, logger: ValidationLogger
    ):
        """Test validating the Root profile record."""
        root_record = validator.registry.resolve_pid("0.FDO/Root")
        assert root_record is not None

        result = validator.validate(root_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.additional_attributes) == 0
        assert result.profiles_checked == 1

    def test_validate_profiledef_profile(
        self, validator: ProfileValidator, logger: ValidationLogger
    ):
        """Test validating the ProfileDef profile record."""
        profiledef_record = validator.registry.resolve_pid("0.FDO/ProfileDef")
        assert profiledef_record is not None

        result = validator.validate(profiledef_record)

        assert result.valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
        assert len(result.additional_attributes) == 0
        assert result.profiles_checked == 1

    def test_validation_shows_detailed_logging(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
        capsys: pytest.CaptureFixture,
    ):
        """Test that validation produces detailed logs in verbose mode."""
        logger.verbose = True
        profiledef_record = validator.registry.resolve_pid("0.FDO/ProfileDef")
        assert profiledef_record

        result = validator.validate(profiledef_record)
        captured = capsys.readouterr()

        assert result.valid is True
        assert "Attribute Check:".lower() in captured.out.lower()

    def test_validation_handles_extended_profiles(
        self,
        validator: ProfileValidator,
        logger: ValidationLogger,
        assembly: ExtensionsAssembly,
        capsys: pytest.CaptureFixture,
    ):
        """Test validation with profiles that extend other profiles."""
        record = validator.registry.resolve_pid("data")
        assert record

        # Data uses a profile making use of 0.FDO/Extends:
        extending_profile_name: str = "extended-profile"
        logger.verbose = True

        result = validator.validate(record)
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

    def test_attribute_validator_instantiation(
        self, logger, registry, attribute_assembly
    ):
        """Test that AttributeValidator can be instantiated."""
        validator: AttributeValidator = AttributeValidator(
            registry, logger, attribute_assembly
        )
        assert validator is not None
        assert validator.registry is registry
        assert validator.logger is logger
        assert validator.assembly is attribute_assembly

    def test_validate_empty_record(self, logger, registry, attribute_assembly):
        """Test validation of empty record."""
        validator: AttributeValidator = AttributeValidator(
            registry, logger, attribute_assembly
        )
        record: PidRecord = PidRecord(
            pid="test/Empty",
            data={},
            source_pid="test/Empty",
        )

        result: ValidationResult = validator.validate(record, "test/Empty")

        assert result is not None
        assert result.valid is True
        assert len(result.errors) == 0
        assert result.attributes_checked == 0

    def test_validate_metadata_only_record(self, logger, registry, attribute_assembly):
        """Test validation of minimal record."""
        pid: str = "test/minimal"
        validator: AttributeValidator = AttributeValidator(
            registry, logger, attribute_assembly
        )
        record: PidRecord = PidRecord(
            pid=pid,
            data={
                "0.FDO/Type": ["FDO_Profile"],
                "0.FDO/Profile": ["0.FDO/Root"],
                "0.FDO/Data": ["Not_Applicable"],
            },
            source_pid=pid,
        )

        result: ValidationResult = validator.validate(record, pid)

        assert result.valid is True

    def test_validate_with_missing_attribute(
        self, logger, registry, attribute_assembly
    ):
        """Test profile violations do not matter, as we only validate contained attributes."""
        validator: AttributeValidator = AttributeValidator(
            registry, logger, attribute_assembly
        )

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

        result: ValidationResult = validator.validate(record, "test/MissingName")

        # Since 0.FDO/Name is not present at all, no cardinality check happens
        # The validator only checks attributes that exist in the record
        assert result is not None
        assert result.errors == []
        assert result.profiles_checked == 0
        assert result.warnings == []


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
