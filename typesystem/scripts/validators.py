"""Validation logic for FDO records.

This module contains validators that check if records conform to their profiles
and if attribute values match their definitions.

Validators focus purely on validation logic - they delegate data gathering
to assembly components.
"""

import re
from typing import Any, Dict, List, Optional, Set

from assembly import ProfilesAssembly
from models import (
    CardinalityViolation,
    MissingRequiredAttribute,
    ProfilesInfo,
    ValueViolation,
    ZeroProfilesContained,
)

try:
    # When imported as a package
    from .assembly import AttributeAssembly, ExtensionsAssembly
    from .models import ExtensionsInfo, PidRecord, ValidationResult, ValidationRules
    from .registry import PidRegistry
    from .validation_logger import ValidationLogger
except ImportError:
    # When run directly
    from assembly import AttributeAssembly, ExtensionsAssembly
    from models import ExtensionsInfo, PidRecord, ValidationResult, ValidationRules
    from registry import PidRegistry
    from validation_logger import ValidationLogger


class ProfileValidator:
    """Validates that a record conforms to its claimed profile(s).

    Checks if the record has all required attributes.
    """

    def __init__(
        self,
        registry: PidRegistry,
        logger: ValidationLogger,
        profiles_assembly: ProfilesAssembly,
        extensions_assembly: ExtensionsAssembly,
    ) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger
        self.profiles_assembly: ProfilesAssembly = profiles_assembly
        self.extensions_assembly: ExtensionsAssembly = extensions_assembly

    def validate(self, record: PidRecord) -> ValidationResult:
        """
        Validate record against its profile(s).

        This means to check that all required attributes are present,
        as specified in the profiles given in the record.

        Args:
            record: The record to validate

        Returns:
            ValidationResult with errors/warnings
        """
        result: ValidationResult = ValidationResult()
        profiles_info: ProfilesInfo = self.profiles_assembly.assemble_record(record)

        for error in profiles_info.process_warnings:
            if isinstance(error, ZeroProfilesContained):
                result.add_error(error)
            else:
                result.add_warning(error)

        if not result.valid:
            return result

        self.logger.log_step(
            "Profile Validation",
            f"Checking {len(profiles_info.profiles)} profile(s)",
            indent=0,
        )

        for profile in profiles_info.profiles:
            self.logger.log_step(
                "Profile Validation",
                f"→ Validating against profile {profile.pid}",
                indent=1,
            )
            result.profiles_checked += 1

            if profile.has_cycle:
                self.logger.log_step(
                    "Cycle Detection",
                    "⚠ Cycle detected in profile chain",
                    indent=2,
                )
                # we added the warnings already above

            # VALIDATION: Check required attributes
            required_attrs: List[str] = self._get_required_attributes(profile)
            self.logger.log_step(
                "Required Attributes",
                f"Checking {len(required_attrs)} required attribute(s)",
                indent=2,
            )

            for attr_name in required_attrs:
                if not record.has_attribute(attr_name):
                    error_msg: str = (
                        f"Missing required attribute '{attr_name}' "
                        f"(declared by {profile.pid})"
                    )
                    self.logger.log_step("Attribute Check", f"✗ {error_msg}", indent=3)
                    result.add_error(
                        MissingRequiredAttribute(
                            within_pid=record.pid, expected_attribute=attr_name
                        )
                    )
                else:
                    self.logger.log_step(
                        "Attribute Check", f"✓ {attr_name} present", indent=3
                    )

            result.attributes_checked += len(required_attrs)
            result.additional_attributes = [
                attr for attr in record.data.keys() if attr not in required_attrs
            ]
            if len(result.additional_attributes) > 0:
                self.logger.log_step(
                    "Attribute Check",
                    f"✓ Additional attributes: {', '.join(result.additional_attributes)}",
                    indent=3,
                )

        return result

    def _get_required_attributes(self, assembled: ExtensionsInfo) -> List[str]:
        """
        Get the list of required attributes from an assembled profile.

        In the current draft, all attributes in the profile's declared list are required,
        and cardinality is determined in the attributes themself.

        Args:
            assembled: The assembled profile information

        Returns:
            List of required attribute names
        """
        return assembled.all_attributes

    def _is_pid_reference(self, value: Any) -> bool:
        """
        Check if a string is a PID reference (not a literal value).

        Uses a blacklist of known non-PID literals.

        Args:
            value: The value to check

        Returns:
            True if value looks like a PID reference
        """
        if not isinstance(value, str):
            return False

        non_pid_literals: Set[str] = {
            "Not_Applicable",
            "Not_Applicable_Numeric",
            "Not_Applicable_String",
        }
        result: bool = value not in non_pid_literals
        return result


class AttributeValidator:
    """Validates attribute values against their definitions.

    Uses AttributeAssembly to gather validation rules from attribute
    definitions and syntax definitions, then checks if record values
    conform to those rules.

    Validates:
    - Cardinality (number of values)
    - Primitive type (string, number, integer, boolean)
    - Regex patterns
    - Numeric intervals
    - Whitelists and blacklists

    Usage:
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        assembly = AttributeAssembly(registry, logger)
        validator = AttributeValidator(registry, logger, assembly)

        record = registry.resolve_pid("0.FDO/Type")
        result = validator.validate(record, "0.FDO/Type")
        print(f"Valid: {result.valid}")
    """

    def __init__(
        self,
        registry: PidRegistry,
        logger: ValidationLogger,
        assembly: AttributeAssembly,
    ) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger
        self.assembly: AttributeAssembly = assembly

    def validate(self, record: PidRecord, record_pid: str) -> ValidationResult:
        """
        Validate all attribute values in the record.

        For each attribute in the record:
        1. Assemble validation rules
        2. Check cardinality
        3. Validate each value against syntax rules

        Args:
            record: The record to validate
            record_pid: PID of the record (for logging)

        Returns:
            ValidationResult with errors/warnings
        """
        result: ValidationResult = ValidationResult()

        self.logger.log_step(
            "Attribute Validation",
            f"Starting validation for {record_pid}",
            indent=0,
        )

        for attr_name, values in record.data.items():
            if not values:
                continue

            self.logger.log_step(
                "Attribute Validation",
                f"→ Validating {attr_name} ({len(values)} value(s))",
                indent=1,
            )

            # ASSEMBLY: Get validation rules for this attribute
            rules: ValidationRules = self.assembly.assemble_rules(attr_name)
            result.resolutions_performed += 1

            # VALIDATION: Check cardinality
            if rules.cardinality:
                if not self._check_cardinality(
                    len(values), rules.cardinality, attr_name, record_pid, result
                ):
                    result.add_error(
                        CardinalityViolation(
                            pid=record_pid,
                            attribute=attr_name,
                            rule=rules.cardinality,
                            actual_count=len(values),
                        )
                    )

            # VALIDATION: Check each value against syntax rules
            for value in values:
                value_result: ValidationResult = self._validate_value(
                    value, rules, attr_name, record_pid
                )
                result.merge(value_result)

            result.attributes_checked += 1

        return result

    def _check_cardinality(
        self,
        actual_count: int,
        cardinality_str: str,
        attr_name: str,
        owning_record_pid: str,
        result: ValidationResult,
    ) -> bool:
        """
        Check if the number of values matches the cardinality constraint.

        Cardinality format:
        - "1" - exactly one (mandatory)
        - "0..1" - zero or one (optional)
        - "1..*" - one or more (mandatory, repeatable)
        - "0..*" - zero or more (optional, repeatable)
        - "2..3" - between 2 and 3 inclusive

        Args:
            actual_count: Number of values present
            cardinality_str: Cardinality expression
            attr_name: Name of the attribute (for error messages)
            owning_record_pid: PID of the record using this attribute
            result: ValidationResult to add errors to

        Returns:
            True if cardinality is satisfied
        """
        min_count: int
        max_count: Optional[int]
        try:
            # Parse cardinality expression
            if ".." in cardinality_str:
                parts: List[str] = cardinality_str.split("..")
                min_count = int(parts[0])
                max_count = None if parts[1] == "*" else int(parts[1])
            else:
                min_count = int(cardinality_str)
                max_count = min_count

            # Check constraints
            if actual_count < min_count:
                self.logger.log_step(
                    "Cardinality",
                    f"✗ {attr_name}: expected at least {min_count}, got {actual_count}",
                    indent=2,
                )
                result.add_error(
                    CardinalityViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=cardinality_str,
                        actual_count=actual_count,
                    )
                )
                return False

            if max_count is not None and actual_count > max_count:
                self.logger.log_step(
                    "Cardinality",
                    f"✗ {attr_name}: expected at most {max_count}, got {actual_count}",
                    indent=2,
                )
                result.add_error(
                    CardinalityViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=cardinality_str,
                        actual_count=actual_count,
                    )
                )
                return False

            self.logger.log_step(
                "Cardinality",
                f"✓ {attr_name}: {actual_count} value(s) satisfies {cardinality_str}",
                indent=2,
            )
            return True

        except (ValueError, IndexError):
            self.logger.log_step(
                "Cardinality",
                f"⚠ {attr_name}: invalid cardinality expression '{cardinality_str}'",
                indent=2,
            )
            # Don't fail validation for invalid cardinality expressions
            return True

    def _validate_value(
        self, value: Any, rules: ValidationRules, attr_name: str, owning_record_pid: str
    ) -> ValidationResult:
        """
        Validate a single value against assembled rules.

        Checks:
        1. Primitive type (if specified)
        2. Regex pattern (if specified)
        3. Numeric interval (if specified)
        4. Whitelist (if specified)
        5. Blacklist (if specified)

        Args:
            value: The value to validate
            rules: Assembled validation rules
            attr_name: Name of the attribute (for error messages)
            owning_record_pid: PID of the owning record (for error messages)

        Returns:
            ValidationResult with any errors found
        """
        result: ValidationResult = ValidationResult()
        value_str: str = str(value)[:50]  # Truncate for logging

        # Type check
        if rules.primitive_type:
            if not self._check_type(value, rules.primitive_type):
                error_msg: str = (
                    f"{attr_name}: {value_str} is not {rules.primitive_type}"
                )
                self.logger.log_step("Type Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=rules.primitive_type,
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Type Check",
                    f"✓ {attr_name}: type OK ({rules.primitive_type})",
                    indent=3,
                )

        # Regex check (only for strings)
        if rules.regex and isinstance(value, str):
            if not self._check_regex(value, rules.regex):
                error_msg = (
                    f"{attr_name}: {value_str} doesn't match pattern {rules.regex}"
                )
                self.logger.log_step("Regex Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=rules.regex,
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Regex Check", f"✓ {attr_name}: matches pattern", indent=3
                )

        # Numeric interval check (only for numbers)
        if rules.numeric_interval and isinstance(value, (int, float)):
            if not self._check_numeric_interval(value, rules.numeric_interval):
                error_msg = (
                    f"{attr_name}: {value} outside interval "
                    f"[{rules.numeric_interval.get('min')}, {rules.numeric_interval.get('max')}]"
                )
                self.logger.log_step("Interval Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=str(rules.numeric_interval),
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Interval Check", f"✓ {attr_name}: within interval", indent=3
                )

        # Whitelist check
        if rules.whitelist is not None:
            if value not in rules.whitelist:
                error_msg = f"{attr_name}: {value_str} not in whitelist"
                self.logger.log_step("Whitelist Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=str(rules.whitelist),
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Whitelist Check", f"✓ {attr_name}: in whitelist", indent=3
                )

        # Blacklist check
        if rules.blacklist is not None:
            if value in rules.blacklist:
                error_msg = f"{attr_name}: {value_str} in blacklist"
                self.logger.log_step("Blacklist Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=str(rules.blacklist),
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Blacklist Check", f"✓ {attr_name}: not in blacklist", indent=3
                )

        return result

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """
        Check if a value matches the expected primitive type.

        Args:
            value: The value to check
            expected_type: One of "string", "number", "integer", "boolean"

        Returns:
            True if type matches
        """
        if expected_type == "string":
            return isinstance(value, str)
        elif expected_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected_type == "boolean":
            return isinstance(value, bool)
        else:
            # Unknown type, be permissive
            return True

    def _check_regex(self, value: str, pattern: str) -> bool:
        """
        Check if a string value matches a regex pattern.

        Args:
            value: The string value to check
            pattern: ECMA-262 regex pattern (converted to Python)

        Returns:
            True if value matches pattern
        """
        try:
            # Note: ECMA-262 regex is mostly compatible with Python
            # Some edge cases might differ, but this works for most patterns
            return bool(re.fullmatch(pattern, value))
        except re.error:
            # Invalid regex, be permissive
            return True

    def _check_numeric_interval(self, value: float, interval: Dict[str, Any]) -> bool:
        """
        Check if a numeric value is within an interval.

        Args:
            value: The numeric value to check
            interval: Dict with optional "min" and "max" keys

        Returns:
            True if value is within interval
        """
        min_val: Optional[Any] = interval.get("min")
        max_val: Optional[Any] = interval.get("max")

        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False

        return True


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
    ) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger

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
