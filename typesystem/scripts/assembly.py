"""Assembly components for FDO record validation.

Assembly is responsible for gathering and combining information from multiple sources:
- Profiles and their extension chains
- Attribute definitions and their syntax rules

This module handles the complex logic of recursive resolution, cycle detection,
and merging. Validators use assembled data without worrying about how it was gathered.
"""

from typing import Any, List, Optional, Set

from models import UnresolvablePid

try:
    # When imported as a package
    from .helpers import MutBool
    from .models import AssembledProfile, PidRecord, ValidationRules
    from .registry import PidRegistry
    from .validation_logger import ValidationLogger
except ImportError:
    # When run directly
    from helpers import MutBool
    from models import AssembledProfile, PidRecord, ValidationRules
    from registry import PidRegistry
    from validation_logger import ValidationLogger


class ProfileAssembly:
    """Assembles complete profile information from profile and all extensions.

    Given a profile PID, resolves the entire extension chain and collects
    all attributes from parent profiles. Handles cycles gracefully.

    Usage:
        logger = ValidationLogger(verbose=True)
        registry = PidRegistry(logger)
        assembly = ProfileAssembly(registry, logger)

        assembled = assembly.assemble("0.FDO/ChildProfile")
        print(f"Resolved {assembled.profiles_resolved} profiles")
        print(f"Total attributes: {len(assembled.all_attributes)}")
    """

    def __init__(self, registry: PidRegistry, logger: ValidationLogger) -> None:
        self.registry: PidRegistry = registry
        self.logger: ValidationLogger = logger

    def assemble(self, profile_pid: str) -> AssembledProfile:
        """
        Assemble complete profile information by resolving extension chain.

        Recursively resolves all extended profiles and merges their attributes.
        Handles cycles gracefully (marks has_cycle=True, continues with partial info).
        Logs resolution steps at appropriate detail level.

        Args:
            profile_pid: The PID of the profile to assemble

        Returns:
            AssembledProfile with all attributes from the extension chain
        """
        visited: Set[str] = set()
        root_attributes: List[str] = []
        all_attrs: List[str] = []
        extends_chain: List[str] = []
        processing_warnings: List[UnresolvablePid] = []
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

        result = AssembledProfile(
            pid=profile_pid,
            all_attributes=all_attrs,
            declared_attributes=root_attributes,
            extends_chain=extends_chain,
            profiles_resolved=len(visited),
            processing_warnings=processing_warnings,
            has_cycle=has_cycle.value,
        )

        self.logger.log_step(
            "Profile Assembly",
            f"✓ Complete: {result.profiles_resolved} profile(s), "
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
        processing_warnings: List[UnresolvablePid],
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

    def _get_declared_attributes(self, profile_pid: str) -> List[str]:
        """
        Get only the attributes directly declared by a profile (not inherited).

        Args:
            profile_pid: The PID of the profile

        Returns:
            List of attribute names declared in this profile's 0.FDO/Attribute
        """
        profile = self.registry.resolve_pid(profile_pid)
        if not profile:
            return []

        attrs = profile.get_values("0.FDO/Attribute")
        return [attr for attr in attrs if isinstance(attr, str)]

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
            return ValidationRules()

        self.logger.log_step(
            "Attribute Definition",
            f"✓ Resolved {attr_name}",
            indent=2,
        )

        # Extract cardinality
        cardinality_vals: List[Any] = attr_def.get_values("0.FDO/Cardinality")
        cardinality: Optional[str] = cardinality_vals[0] if cardinality_vals else None
        if cardinality:
            self.logger.log_step(
                "Cardinality",
                f"Found: {cardinality}",
                indent=2,
            )

        # Resolve syntax definition
        syntax_refs: List[Any] = attr_def.get_values("0.FDO/DataType")
        syntax_pid: Optional[str] = syntax_refs[0] if syntax_refs else None

        rules: ValidationRules = ValidationRules(
            cardinality=cardinality,
            syntax_definition_pid=syntax_pid,
        )

        # If syntax definition exists, extract its rules
        if syntax_pid:
            self.logger.log_step(
                "Syntax Definition",
                f"↓ Resolving syntax: {syntax_pid}",
                indent=2,
            )
            syntax_def: Optional[PidRecord] = self.registry.resolve_pid(syntax_pid)
            if syntax_def:
                self._extract_syntax_rules(syntax_def, rules)
            else:
                self.logger.log_step(
                    "Syntax Definition",
                    f"✗ Failed to resolve {syntax_pid}",
                    indent=3,
                )

        self.logger.log_step(
            "Attribute Assembly",
            f"✓ Complete: cardinality={rules.cardinality}, type={rules.primitive_type}",
            indent=1,
        )

        return rules

    def _extract_syntax_rules(
        self, syntax_def: PidRecord, rules: ValidationRules
    ) -> None:
        """
        Extract validation rules from a syntax definition.

        Populates the rules object with primitive type, regex, numeric interval,
        whitelist, and blacklist from the syntax definition.

        Args:
            syntax_def: The resolved syntax definition record
            rules: The ValidationRules object to populate
        """
        # Extract primitive data type
        type_vals: List[Any] = syntax_def.get_values("0.FDO/PrimitiveDataType")
        rules.primitive_type = self._extract_single_value(type_vals)
        if rules.primitive_type:
            self.logger.log_step(
                "Primitive Type",
                f"Found: {rules.primitive_type}",
                indent=3,
            )

        # Extract regex pattern
        regex_vals: List[Any] = syntax_def.get_values("0.FDO/Regex")
        rules.regex = self._extract_single_value(regex_vals)
        if rules.regex:
            self.logger.log_step(
                "Regex",
                f"Found: {rules.regex}",
                indent=3,
            )

        # Extract numeric interval
        interval_vals: List[Any] = syntax_def.get_values("0.FDO/NumericInterval")
        if interval_vals:
            rules.numeric_interval = self._extract_single_value(interval_vals)
            self.logger.log_step(
                "Numeric Interval",
                f"Found: {rules.numeric_interval}",
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

    def _extract_single_value(self, values: List[Any]) -> Optional[Any]:
        """
        Get first value if exactly one exists.

        Args:
            values: List of values from an attribute

        Returns:
            The single value, or None if not exactly one value
        """
        return values[0] if len(values) == 1 else None
