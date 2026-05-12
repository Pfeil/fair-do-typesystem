"""Data classes for FDO record validation.

This module contains pure data structures with no business logic.
Used throughout the validation pipeline to pass structured data.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PidRecord:
    """Represents a resolved PID record.

    Hides file system details - validators work with pure PIDs and records.
    Once created, instances are immutable (no caching concerns).
    """

    pid: str
    data: Dict[str, Any]
    source_pid: str  # The PID used to resolve this record

    def get_values(self, attr_name: str) -> List[Any]:
        """Get all values for an attribute name."""
        return self.data.get(attr_name, [])

    def has_attribute(self, attr_name: str) -> bool:
        """Check if attribute exists and has values."""
        return bool(self.get_values(attr_name))

    def get_single_value(self, attr_name: str) -> Optional[Any]:
        """Get first value if exactly one exists."""
        values = self.get_values(attr_name)
        return values[0] if len(values) == 1 else None


@dataclass
class AssembledProfile:
    """Complete profile information assembled from profile and all extensions.

    Result of ProfileAssembly.assemble() - contains all attributes from the
    entire extension chain, with metadata about the resolution process.
    """

    pid: str
    all_attributes: List[str] = field(default_factory=list)
    declared_attributes: List[str] = field(default_factory=list)
    extends_chain: List[str] = field(default_factory=list)
    profiles_resolved: int = 0
    has_cycle: bool = False


@dataclass
class ValidationRules:
    """Assembled validation rules for an attribute.

    Result of AttributeAssembly.assemble_rules() - contains all validation
    rules collected from attribute definition and its syntax definition.
    """

    cardinality: Optional[str] = None
    primitive_type: Optional[str] = None
    regex: Optional[str] = None
    numeric_interval: Optional[Dict[str, Any]] = None
    whitelist: Optional[List[Any]] = None
    blacklist: Optional[List[Any]] = None
    syntax_definition_pid: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a record or attribute.

    Aggregates errors, warnings, and metadata from validation steps.
    Used to track what happened during validation for reporting.
    """

    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    profiles_checked: int = 0
    attributes_checked: int = 0
    resolutions_performed: int = 0

    def add_error(self, message: str):
        """Add an error and mark result as invalid."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str):
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(message)

    def merge(self, other: "ValidationResult"):
        """Merge another validation result into this one."""
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.profiles_checked += other.profiles_checked
        self.attributes_checked += other.attributes_checked
        self.resolutions_performed += other.resolutions_performed
