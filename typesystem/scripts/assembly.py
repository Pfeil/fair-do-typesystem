"""Assembly components for FDO record validation.

Assembly is responsible for gathering and combining information from multiple sources:
- Profiles and their extension chains
- Attribute definitions and their syntax rules

This module handles the complex logic of recursive resolution, cycle detection,
and merging. Validators use assembled data without worrying about how it was gathered.
"""

from typing import List, Optional, Set

try:
    # When imported as a package
    from .models import AssembledProfile, PidRecord
    from .registry import PidRegistry
    from .validation_logger import ValidationLogger
except ImportError:
    # When run directly
    from models import AssembledProfile, PidRecord
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

    def __init__(self, registry: PidRegistry, logger: ValidationLogger):
        self.registry = registry
        self.logger = logger

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
        all_attrs: List[str] = []
        extends_chain: List[str] = []
        has_cycle = False

        self.logger.log_step(
            "Profile Assembly", f"Starting assembly for {profile_pid}", indent=0
        )

        self._resolve_profile_chain(
            profile_pid, visited, all_attrs, extends_chain, has_cycle
        )

        # Get declared attributes from the main profile
        declared_attrs = self._get_declared_attributes(profile_pid)

        result = AssembledProfile(
            pid=profile_pid,
            all_attributes=all_attrs,
            declared_attributes=declared_attrs,
            extends_chain=extends_chain,
            profiles_resolved=len(visited),
            has_cycle=has_cycle,
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
        pid: str,
        visited: Set[str],
        all_attrs: List[str],
        extends_chain: List[str],
        has_cycle: bool,
    ):
        """
        Recursively resolve profile extension chain.

        Mutates visited, all_attrs, extends_chain, and has_cycle in place.

        Args:
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
            has_cycle = True
            return

        visited.add(pid)
        extends_chain.append(pid)

        # Resolve the profile
        profile = self.registry.resolve_pid(pid)
        if not profile:
            self.logger.log_step("Resolution", f"✗ Failed to resolve {pid}", indent=1)
            return

        # Add this profile's attributes (avoiding duplicates)
        attrs = profile.get_values("0.FDO/Attribute")
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
                        ext_pid, visited, all_attrs, extends_chain, has_cycle
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
