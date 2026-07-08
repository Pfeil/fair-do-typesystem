"""Assembly components for FDO record validation.

Assembly is responsible for gathering and combining information from multiple sources:
- Profiles and their extension chains
- Attribute definitions and their syntax rules

This module handles the complex logic of recursive resolution, cycle detection,
and merging. Validators use assembled data without worrying about how it was gathered.
"""

from typing import Any, List, Optional, Set

from models import (
    CycleDetected,
    ProfilesInfo,
    RecordProcessingError,
    SyntaxRules,
    UnresolvablePid,
    ZeroProfilesContained,
)

try:
    # When imported as a package
    from .helpers import MutBool
    from .models import ExtensionsInfo, PidRecord, ValidationRules
    from .registry import PidRegistry
    from .validation_logger import ValidationLogger
except ImportError:
    # When run directly
    from helpers import MutBool
    from models import ExtensionsInfo, PidRecord, ValidationRules
    from registry import PidRegistry
    from validation_logger import ValidationLogger


class ProfilesAssembly:
    def __init__(self, registry: PidRegistry, logger: ValidationLogger) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger

    def assemble(self, pid: str) -> ProfilesInfo | None:
        record = self.registry.resolve_pid(pid)
        return self.assemble_record(record) if record else None

    def assemble_record(self, record: PidRecord) -> ProfilesInfo:
        result = ProfilesInfo(record=record)
        profile_pids = record.get_values("0.FDO/Profile")
        if not profile_pids or len(profile_pids) == 0:
            self.logger.log_step(
                "Profile Assembly",
                f"⚠ No profile references found in {record.pid}",
                indent=0,
            )
            result.process_warnings.append(
                ZeroProfilesContained(pid_without_profiles=record.pid)
            )
            return result

        for profile_pid in profile_pids:
            if not isinstance(profile_pid, str):
                result.process_warnings.append(UnresolvablePid(profile_pid))

        profile_pids = list(filter(lambda p: isinstance(p, str), profile_pids))
        assembly = ExtensionsAssembly(self.registry, self.logger)

        def process_profile(profile_pid: str) -> ExtensionsInfo:
            result = assembly.assemble(profile_pid)
            if result.has_cycle:
                result.processing_warnings.append(
                    CycleDetected(pid=profile_pid, attribute="0.FDO/Profile")
                )
            return result

        result.profiles = [process_profile(profile_pid) for profile_pid in profile_pids]
        return result


class ExtensionsAssembly:
    """Assembles complete profile information from profile and all extensions.

    Given a profile PID, resolves the entire extension chain and collects
    all attributes from parent profiles. Handles cycles gracefully.
    """

    def __init__(self, registry: PidRegistry, logger: ValidationLogger) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger

    def assemble(self, profile_pid: str) -> ExtensionsInfo:
        """
        Assemble complete profile information by resolving extension chain.

        Recursively resolves all extended profiles and merges their attributes.
        Handles cycles gracefully (marks has_cycle=True, continues with partial info).
        Logs resolution steps at appropriate detail level.

        Args:
            profile_pid: The PID of the profile to assemble

        Returns:
            ExtensionsInfo with all attributes from the extension chain
        """
        visited: Set[str] = set()
        root_attributes: List[str] = []
        all_attrs: List[str] = []
        extends_chain: List[str] = []
        processing_warnings: List[RecordProcessingError] = []
        has_cycle = MutBool(False)

        self.logger.log_step(
            "Profile Assembly", f"Starting assembly for {profile_pid}", indent=0
        )

        self._resolve_profile_chain(
            profile_pid,  # root
            root_attributes,
            profile_pid,  # "current"
            visited,
            all_attrs,
            extends_chain,
            processing_warnings,
            has_cycle,
        )

        result = ExtensionsInfo(
            pid=profile_pid,
            all_attributes=all_attrs,
            declared_attributes=root_attributes,
            extends_chain=extends_chain,
            amount_resolved_extension_pids=len(visited),
            processing_warnings=processing_warnings,
            has_cycle=has_cycle.value,
        )

        self.logger.log_step(
            "Profile Assembly",
            f"✓ Complete: Resolved {result.amount_resolved_extension_pids} extension PID(s), "
            f"{len(result.all_attributes)} attribute(s)",
            indent=0,
        )

        return result

    def _resolve_profile_chain(
        self,
        root: str,
        root_attributes: List[str],
        pid: str,
        visited: Set[str],
        all_attrs: List[str],
        extends_chain: List[str],
        processing_warnings: List[RecordProcessingError],
        has_cycle: MutBool,
    ):
        """
        Recursively resolve profile extension chain.

        Mutates visited, all_attrs, extends_chain, and has_cycle in place.

        Args:
            root: Root profile PID
            root_attributes: Attributes of the root profile
            pid: Profile PID to resolve
            visited: Set of already visited PIDs (for cycle detection)
            all_attrs: Accumulated list of all attributes
            extends_chain: List of profiles in extension chain
            has_cycle: Flag indicating if cycle was detected
        """
        # Check for cycle
        if pid in visited:
            self.logger.log_step(
                "Cycle Detection", f"↩ {pid} already visited (cycle detected)", indent=1
            )
            has_cycle.value = True
            return

        visited.add(pid)
        extends_chain.append(pid)

        # Resolve the profile
        profile = self.registry.resolve_pid(pid)
        if not profile:
            self.logger.log_step("Resolution", f"✗ Failed to resolve {pid}", indent=1)
            processing_warnings.append(UnresolvablePid(pid))
            return

        # Add this profile's attributes (avoiding duplicates)
        attrs = profile.get_values("0.FDO/Attribute")
        if root == pid:
            root_attributes.extend(attrs)
        new_attrs_count = 0
        for attr in attrs:
            if isinstance(attr, str) and attr not in all_attrs:
                all_attrs.append(attr)
                new_attrs_count += 1

        self.logger.log_step(
            "Profile",
            f"✓ {pid}: {len(attrs)} attributes ({new_attrs_count} new)",
            indent=1,
        )

        # Recursively resolve extensions
        extends = profile.get_values("0.FDO/Extends")
        if extends:
            self.logger.log_step("Extension", f"↓ Extends: {extends}", indent=1)

            for ext_pid in extends:
                if self._is_pid_reference(ext_pid):
                    self._resolve_profile_chain(
                        root,
                        root_attributes,
                        ext_pid,
                        visited,
                        all_attrs,
                        extends_chain,
                        processing_warnings,
                        has_cycle,
                    )

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


class AttributeAssembly:
    """Assembles validation rules for attributes from their definitions.

    Given an attribute name (PID), resolves its definition and collects all
    validation rules including cardinality, type, regex, whitelist/blacklist.
    Handles syntax definition resolution recursively.

    Usage:
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        assembly = AttributeAssembly(registry, logger)

        rules = assembly.assemble_rules("0.FDO/Type")
        print(f"Cardinality: {rules.cardinality}")
        print(f"Type: {rules.primitive_type}")
    """

    def __init__(self, registry: PidRegistry, logger: ValidationLogger) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger

    def assemble_rules(self, attr_name: str) -> ValidationRules:
        """
        Assemble all validation rules for an attribute.

        Steps:
        1. Resolve attribute definition
        2. Extract cardinality
        3. Resolve syntax definition (if present)
        4. Extract syntax rules (primitive type, regex, etc.)
        5. Return combined rules

        Args:
            attr_name: The PID of the attribute definition

        Returns:
            ValidationRules with all assembled validation constraints
        """
        self.logger.log_step(
            "Attribute Assembly", f"Starting rule assembly for {attr_name}", indent=1
        )

        # Resolve attribute definition
        attr_def: Optional[PidRecord] = self.registry.resolve_pid(attr_name)
        if not attr_def:
            self.logger.log_step(
                "Attribute Assembly", f"✗ Failed to resolve {attr_name}", indent=2
            )
            result = ValidationRules()
            result.validation_result.add_error(UnresolvablePid(attr_name))
            return result

        self.logger.log_step(
            "Attribute Definition",
            f"✓ Resolved {attr_name}",
            indent=2,
        )
        return self.assemble_rules_by_record(attr_def, attr_name)

    def assemble_rules_by_record(
        self, attr_def: PidRecord, attr_name: str
    ) -> ValidationRules:
        """Assemble rules for an attribute within a specific record."""

        # Extract cardinality
        cardinality_vals: List[Any] = attr_def.get_values("0.FDO/Cardinality")
        cardinality: Optional[str] = (
            cardinality_vals[0]
            if cardinality_vals and len(cardinality_vals) > 0
            else None
        )
        if cardinality:
            self.logger.log_step(
                "Cardinality",
                f"Found: {cardinality}",
                indent=2,
            )

        # Resolve syntax definition
        syntax_refs: List[str] = attr_def.get_values("0.FDO/DataType")

        rules: ValidationRules = ValidationRules(
            cardinality=cardinality,
            validation_mechanisms=attr_def.get_values("0.FDO/ValidationMechanism"),
            syntax_rules=[
                self._extract_syntax_rules(syntax_ref) for syntax_ref in syntax_refs
            ],
            null_values=attr_def.get_values("0.FDO/ReferenceNull"),
        )

        for rule in rules.syntax_rules:
            rules.validation_result.merge(rule.validation_result)

        if rules.validation_mechanisms:
            self.logger.log_step(
                "Validation Mechanisms",
                f"Found: {', '.join(rules.validation_mechanisms)}",
                indent=2,
            )

        self.logger.log_step(
            "Attribute Assembly",
            f"✓ Complete: cardinality={rules.cardinality}, validation={', '.join(rules.validation_mechanisms)}",
            indent=1,
        )
        return rules

    def _extract_syntax_rules(self, syntax_pid: str) -> SyntaxRules:
        """
        Extract validation rules from a syntax definition.

        Populates the rules object with primitive type, regex, numeric interval,
        whitelist, and blacklist from the syntax definition.

        Args:
            syntax_pid: The PID to the syntax definition record
            rules: The ValidationRules object to populate
        """

        rules = SyntaxRules(
            syntax_pid=syntax_pid,
        )

        self.logger.log_step(
            "Syntax Definition",
            f"↓ Resolving syntax: {syntax_pid}",
            indent=2,
        )
        syntax_def: Optional[PidRecord] = self.registry.resolve_pid(syntax_pid)
        if not syntax_def:
            self.logger.log_step(
                "Syntax Definition",
                f"✗ Failed to resolve {syntax_pid}",
                indent=3,
            )
            rules.validation_result.add_error(UnresolvablePid(pid=syntax_pid))
            return rules

        # Extract primitive data type
        type_vals: List[Any] = syntax_def.get_values("0.FDO/PrimitiveDataType")
        rules.primitive_types.extend(type_vals)
        if len(rules.primitive_types) < 0:
            self.logger.log_step(
                "Primitive Type",
                f"Found: {','.join(rules.primitive_types)}",
                indent=3,
            )

        # Extract regex pattern
        regex_vals: List[Any] = syntax_def.get_values("0.FDO/Regex")
        rules.regexes.extend(regex_vals)
        if len(rules.regexes) > 0:
            self.logger.log_step(
                "Regex",
                f"Found: {','.join(rules.regexes)}",
                indent=3,
            )

        # Extract numeric interval
        interval_vals: List[Any] = syntax_def.get_values("0.FDO/NumericInterval")
        rules.numeric_intervals.extend(interval_vals)
        if interval_vals:
            self.logger.log_step(
                "Numeric Interval",
                f"Found: {','.join(rules.numeric_intervals)}",
                indent=3,
            )

        # Extract whitelist
        whitelist_vals: List[Any] = syntax_def.get_values("0.FDO/Whitelist")
        if whitelist_vals:
            rules.whitelist = whitelist_vals
            self.logger.log_step(
                "Whitelist",
                f"Found {len(rules.whitelist)} allowed value(s)",
                indent=3,
            )

        # Extract blacklist
        blacklist_vals: List[Any] = syntax_def.get_values("0.FDO/Blacklist")
        if blacklist_vals:
            rules.blacklist = blacklist_vals
            self.logger.log_step(
                "Blacklist",
                f"Found {len(rules.blacklist)} disallowed value(s)",
                indent=3,
            )

        return rules
