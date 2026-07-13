"""Validation logic for FDO records.

This module contains validators that check if records conform to their profiles
and if attribute values match their definitions.

Validators focus purely on validation logic - they delegate data gathering
to assembly components.
"""

import re
from itertools import chain
from typing import Any, List, Optional, Set

from assembly import ProfilesAssembly
from models import (
    CardinalityViolation,
    MissingRequiredAttribute,
    ProfilesInfo,
    SyntaxRules,
    UnresolvablePid,
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
            f"Record {record.pid} has {len(profiles_info.profiles)} profile(s)",
            indent=0,
        )

        # log which profile requires which attributes
        for profile in profiles_info.profiles:
            self.logger.log_step(
                "Profile Validation",
                f"→ Profile {profile.pid} requires attributes: {', '.join(self._get_required_attributes(profile))}",
                indent=1,
            )

        required_attributes: set[str] = set(
            chain.from_iterable(
                [
                    self._get_required_attributes(profile)
                    for profile in profiles_info.profiles
                ]
            )
        )

        self.logger.log_step(
            "Required Attributes",
            f"Checking {len(required_attributes)} required attribute(s)",
            indent=2,
        )

        for attr_name in required_attributes:
            if (
                not record.has_attribute(attr_name)
                or len(record.get_values(attr_name)) == 0
            ):
                profiles_declaring_attribute = set(
                    [
                        profile.pid
                        for profile in profiles_info.profiles
                        if attr_name in self._get_required_attributes(profile)
                    ]
                )
                error_msg: str = (
                    f"Missing required attribute '{attr_name}' "
                    f"(declared by {', '.join(profiles_declaring_attribute)})"
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

        result.profiles_checked += len(profiles_info.profiles)
        result.attributes_checked += len(required_attributes)
        result.additional_attributes = [
            attr for attr in record.data.keys() if attr not in required_attributes
        ]
        if len(result.additional_attributes) > 0:
            self.logger.log_step(
                "Attribute Check",
                f"✓ Additional attributes: {', '.join(result.additional_attributes)}",
                indent=3,
            )

        for profile in profiles_info.profiles:
            if profile.has_cycle:
                self.logger.log_step(
                    "Cycle Detection",
                    f"⚠ Cycle detected in profile chain of {profile.pid}",
                    indent=2,
                )
                # we added the warnings already above

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
        # Ensure consistent behavior by caching (but not hard coding) relevant structures
        self.mechanism_rules: ValidationRules = self.assembly.assemble_rules(
            "0.FDO/ValidationMechanism"
        )
        self.primitive_datatype_rules: ValidationRules = self.assembly.assemble_rules(
            "0.FDO/PrimitiveDataType"
        )

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
            result.merge(
                self._validate_attribute(attr_name, values, record_pid, record)
            )

        return result

    def _validate_attribute_by_rules(
        self,
        attr_name: str,
        attribute_rules: ValidationRules,
        values: list[Any],
        record_pid: str,
        record: PidRecord | None,
    ) -> ValidationResult:
        result = ValidationResult()

        self.logger.log_step(
            "Attribute Validation",
            f"→ Validating {attr_name} ({len(values)} value(s))",
            indent=1,
        )

        # VALIDATION: Check cardinality
        if attribute_rules.cardinality:
            if not self._check_cardinality(
                len(values), attribute_rules.cardinality, attr_name, record_pid, result
            ):
                result.add_error(
                    CardinalityViolation(
                        pid=record_pid,
                        attribute=attr_name,
                        rule=attribute_rules.cardinality,
                        actual_count=len(values),
                    )
                )
        result.merge(self._validate_mechanisms(attr_name, attribute_rules, values, record_pid, record))
        return result

    def _validate_mechanisms(
        self,
        attr_name: str,
        attribute_rules: ValidationRules,
        values: list[Any],
        record_pid: str,
        record: PidRecord | None,
    ) -> ValidationResult:
        """
        Validate all values against 0.FDO/ValidationMechanism.

        Resolves mechanisms from the attribute rules and validates each one
        against the attribute's values.

        Args:
            attr_name: Name of the attribute being validated.
            attribute_rules: Validation rules for the attribute.
            values: List of values to validate.
            record_pid: PID of the record being validated. Usually only
              used for logging.
            record: Resolved PID record for the attribute, if available. Contains
              attr_name and values. Usually
              only used for logging.

        Returns:
            A ValidationResult containing any validation errors or warnings.
        """
        result = ValidationResult()
        mechanism_attr: str = "0.FDO/ValidationMechanism"
        for mechanism in attribute_rules.validation_mechanisms:
            # Skipping is fine, as, in this case, this is what
            # this function actually does currently.
            if attr_name != mechanism_attr:
                # validate (mechanism_attr: mechanism)
                is_valid_mechanism: ValidationResult = (
                    self._validate_attribute_by_rules(
                        mechanism_attr,
                        self.mechanism_rules,
                        [mechanism],
                        mechanism_attr,
                        PidRecord(
                            pid=mechanism_attr,
                            data={mechanism_attr: [mechanism]},
                            source_pid=mechanism_attr,
                        ),
                    )
                )
                result.merge(is_valid_mechanism)

            for value in values:
                if value in attribute_rules.null_values:
                    continue

                match mechanism:
                    case "Syntax":
                        for syntax_rule in attribute_rules.syntax_rules:
                            value_result: ValidationResult = self._validate_syntax(
                                value, syntax_rule, attr_name, record_pid
                            )
                            result.merge(value_result)
                    case "AttributeReference":
                        is_reference_result = self._check_attribute_reference(value, attr_name, record_pid, record)
                        result.merge(is_reference_result)
                        if not is_reference_result.valid:
                            continue
                    case _:
                        result.add_error(NotImplementedError())

        result.attributes_checked += 1
        return result

    def _validate_attribute(
        self,
        attr_name: str,
        values: list[Any],
        record_pid: str,
        record: PidRecord,
    ) -> ValidationResult:
        result = ValidationResult()
        rules = self.assembly.assemble_rules(attr_name)
        result.merge(rules.validation_result)
        result.merge(
            self._validate_attribute_by_rules(
                attr_name,
                rules,
                values,
                record_pid,
                record,
            )
        )
        # TODO as long as the validation rules do not collect resolutions
        # during assembly, we do not really know how much to add here.
        result.resolutions_performed += 1
        return result

    def _check_attribute_reference(
        self,
        value: Any,
        attr_name: str,
        record_pid: str,
        record: PidRecord | None,
    ) -> ValidationResult:
        result = ValidationResult()

        if not record:
            record = self.registry.resolve_pid(record_pid)
            if not record:
                result.add_error(
                    UnresolvablePid(
                        pid=record_pid,
                        cause="Failed to resolve attribute reference",
                    )
                )
                return result
            result.resolutions_performed += 1
        is_reference: bool = (
            record.has_attribute(value)
            and len(record.get_values(value)) > 0
        )
        if not is_reference:
            result.add_error(
                ValueViolation(
                    pid=record_pid,
                    attribute=attr_name,
                    actual_value=value,
                    rule="ValidationMechanism = AttributeReference",
                    detail_message="Reference not found",
                )
            )

        return result

    def _check_cardinality_any(
        self,
        check_me: Any,
        cardinality_str: str,
        attr_name: str,
        owning_record_pid: str,
        result: ValidationResult,
    ) -> bool:
        if isinstance(check_me, (int, float)):
            return self._check_cardinality(
                check_me, cardinality_str, attr_name, owning_record_pid, result
            )
        return self._check_cardinality(
            len(check_me), cardinality_str, attr_name, owning_record_pid, result
        )

    def _check_cardinality(
        self,
        actual_count: int | float,
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
            # TODO we should actually assemble cardinalitysyntax in this function and use as much as we can
            # to figure out the usefulness of the granularity and see if we can improve on the record design.
            result.add_error(
                ValueViolation(
                    actual_value=cardinality_str,
                    attribute=attr_name,
                    pid=owning_record_pid,
                    rule="0.FDO/CardinalitySyntax",
                    detail_message="Does not match cardinality syntax (int | int..int).",
                )
            )
            return False

    def _validate_syntax(
        self, value: Any, rules: SyntaxRules, attr_name: str, owning_record_pid: str
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
        for primitive_type in rules.primitive_types:
            if not self._check_type(value, primitive_type):
                error_msg: str = f"{attr_name}: {value_str} is not {primitive_type}"
                self.logger.log_step("Type Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=primitive_type,
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Type Check",
                    f"✓ {attr_name}: type OK ({primitive_type})",
                    indent=3,
                )

        # Regex check (only for strings)
        for regex in rules.regexes:
            if not self._check_regex(value, regex):
                error_msg = f"{attr_name}: {value_str} doesn't match pattern {regex}"
                self.logger.log_step("Regex Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=regex,
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Regex Check", f"✓ {attr_name}: matches pattern", indent=3
                )

        # Numeric interval check (only for numbers)
        for interval in rules.numeric_intervals:
            if not self._check_cardinality_any(
                value, interval, attr_name, owning_record_pid, result
            ):
                error_msg = f"{attr_name}: {value} outside interval {interval}"
                self.logger.log_step("Interval Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=str(interval),
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Interval Check", f"✓ {attr_name}: within interval", indent=3
                )

        # Whitelist check
        if len(rules.whitelist) > 0:
            if value not in rules.whitelist:
                error_msg = f"{attr_name}: {value_str} not in whitelist"
                self.logger.log_step("Whitelist Check", f"✗ {error_msg}", indent=3)
                result.add_error(
                    ValueViolation(
                        pid=owning_record_pid,
                        attribute=attr_name,
                        rule=f"Whitelist: {str(rules.whitelist)}",
                        actual_value=str(value),
                        detail_message=error_msg,
                    )
                )
            else:
                self.logger.log_step(
                    "Whitelist Check", f"✓ {attr_name}: in whitelist", indent=3
                )

        # Blacklist check
        if len(rules.blacklist) > 0:
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
            return False

    def _check_regex(self, value: Any, pattern: str) -> bool:
        """
        Check if a string value matches a regex pattern.

        Args:
            value: The string value to check
            pattern: ECMA-262 regex pattern (converted to Python)

        Returns:
            True if value matches pattern
        """
        if not isinstance(value, str):
            return False
        try:
            # Note: ECMA-262 regex is mostly compatible with Python
            # Some edge cases might differ, but this works for most patterns
            return bool(re.fullmatch(pattern, value))
        except re.error:
            # Invalid regex
            return False


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
