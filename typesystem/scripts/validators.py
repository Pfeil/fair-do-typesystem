"""Validation logic for FDO records.

This module contains validators that check if records conform to their profiles
and if attribute values match their definitions.

Validators focus purely on validation logic - they delegate data gathering
to assembly components (ProfileAssembly, AttributeAssembly).
"""

from typing import List, Optional

try:
    # When imported as a package
    from .assembly import ProfileAssembly
    from .models import AssembledProfile, PidRecord, ValidationResult
    from .registry import PidRegistry
    from .validation_logger import ValidationLogger
except ImportError:
    # When run directly
    from assembly import ProfileAssembly
    from models import AssembledProfile, PidRecord, ValidationResult
    from registry import PidRegistry
    from validation_logger import ValidationLogger


class ProfileValidator:
    """Validates that a record conforms to its claimed profile(s).

    Uses ProfileAssembly to resolve complete profile requirements,
    then checks if the record has all required attributes.

    Usage:
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        assembly = ProfileAssembly(registry, logger)
        validator = ProfileValidator(registry, logger, assembly)

        record = registry.resolve_pid("0.FDO/Root")
        result = validator.validate(record, "0.FDO/Root")
        print(f"Valid: {result.valid}")
    """

    def __init__(
        self,
        registry: PidRegistry,
        logger: ValidationLogger,
        assembly: ProfileAssembly,
    ):
        self.registry = registry
        self.logger = logger
        self.assembly = assembly

    def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Validate record against its profile(s).

        For each profile referenced by the record:
        1. Assemble complete profile (including extensions)
        2. Check all required attributes are present
        3. Report missing attributes as errors

        Args:
            record: The record to validate
            record_pid: PID of the record (for logging)

        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()

        profile_refs = record.get_values("0.FDO/Profile")
        if not profile_refs:
            self.logger.log_step(
                "Profile Validation",
                f"⚠ No profile references found in {record_pid}",
                indent=0,
            )
            result.add_warning(f"No 0.FDO/Profile attribute in {record_pid}")
            return result

        self.logger.log_step(
            "Profile Validation",
            f"Checking {len(profile_refs)} profile reference(s)",
            indent=0,
        )

        for profile_ref in profile_refs:
            if not self._is_pid_reference(profile_ref):
                self.logger.log_step(
                    "Profile Validation",
                    f"⊘ Skipping non-PID value: {profile_ref}",
                    indent=1,
                )
                continue

            self.logger.log_step(
                "Profile Validation",
                f"→ Validating against profile {profile_ref}",
                indent=1,
            )

            # ASSEMBLY: Get complete profile info
            assembled = self.assembly.assemble(profile_ref)
            result.profiles_checked += 1

            if assembled.has_cycle:
                self.logger.log_step(
                    "Cycle Detection",
                    f"⚠ Cycle detected in profile chain, using partial info",
                    indent=2,
                )
                result.add_warning(
                    f"Profile {profile_ref} has circular extension chain"
                )

            # VALIDATION: Check required attributes
            required_attrs = self._get_required_attributes(assembled)
            self.logger.log_step(
                "Required Attributes",
                f"Checking {len(required_attrs)} required attribute(s)",
                indent=2,
            )

            for attr_name in required_attrs:
                if not record.has_attribute(attr_name):
                    error_msg = (
                        f"Missing required attribute '{attr_name}' "
                        f"(declared by {profile_ref})"
                    )
                    self.logger.log_step("Attribute Check", f"✗ {error_msg}", indent=3)
                    result.add_error(error_msg)
                else:
                    self.logger.log_step(
                        "Attribute Check", f"✓ {attr_name} present", indent=3
                    )

            result.attributes_checked += len(required_attrs)

        return result

    def _get_required_attributes(self, assembled: AssembledProfile) -> List[str]:
        """
        Get the list of required attributes from an assembled profile.

        For now, all attributes in the profile's declared list are required.
        Future implementations may support optional attributes via cardinality.

        Args:
            assembled: The assembled profile information

        Returns:
            List of required attribute names
        """
        # Filter to only declared attributes (not inherited)
        # This is what the profile itself requires
        return assembled.declared_attributes

    def _is_pid_reference(self, value: str) -> bool:
        """
        Check if a string is a PID reference (not a literal value).

        Uses a blacklist of known non-PID literals.

        Args:
            value: The value to check

        Returns:
            True if value looks like a PID reference
        """
        non_pid_literals = {
            "Not_Applicable",
            "Not_Applicable_Numeric",
            "Not_Applicable_String",
        }
        return value not in non_pid_literals


class AttributeValidator:
    """Validates attribute values against their definitions.

    TODO: Implementation for Phase 4.
    Will use AttributeAssembly to gather validation rules,
    then check values against those rules.
    """

    def __init__(
        self,
        registry: PidRegistry,
        logger: ValidationLogger,
    ):
        self.registry = registry
        self.logger = logger

    def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Validate all attribute values in the record.

        Args:
            record: The record to validate
            record_pid: PID of the record (for logging)

        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()

        # TODO: Implement Phase 4
        self.logger.log_step(
            "Attribute Validation",
            f"⊘ Not yet implemented for {record_pid}",
            indent=0,
        )

        return result


class SpecificationValidator:
    """Validates overall specification compliance (R8-1 through R8-5).

    TODO: Implementation for Phase 6.
    Will check structural requirements like:
    - R8-1: Root profile conformance
    - R8-2: Profile extension validity
    - R8-3: Attribute definition syntax
    - R8-4: Syntax definition completeness
    - R8-5: Circular reference detection
    """

    def __init__(
        self,
        registry: PidRegistry,
        logger: ValidationLogger,
    ):
        self.registry = registry
        self.logger = logger

    def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Validate specification-level requirements.

        Args:
            record: The record to validate
            record_pid: PID of the record (for logging)

        Returns:
            ValidationResult with errors/warnings
        """
        result = ValidationResult()

        # TODO: Implement Phase 6
        self.logger.log_step(
            "Specification Validation",
            f"⊘ Not yet implemented for {record_pid}",
            indent=0,
        )

        return result
