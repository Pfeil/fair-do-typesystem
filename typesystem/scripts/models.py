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
class UnresolvablePid:
    """Error class that represents a profile that failed to resolve (e.g. is not defined)."""

    pid: str
    cause: Optional[str] = None

    def message(self) -> str:
        return f"Failed to resolve profile for PID: {self.pid}. {self.cause if self.cause else ''}"


@dataclass
class ZeroProfilesContained:
    """Error class that represents a record with zero profiles."""

    pid_without_profiles: str

    def message(self) -> str:
        return f"No 0.FDO/Profile attribute in {self.pid_without_profiles}"


@dataclass
class CycleDetected:
    """
    Error class that represents a cycle detected in a record
    when following the chain of a certain attribute.
    """

    pid: str
    attribute: str

    def message(self) -> str:
        return f"Cycle detected in {self.attribute} chain of: {self.pid}"


@dataclass
class MissingRequiredAttribute:
    """Error class that represents a missing required attribute in a record."""

    within_pid: str
    expected_attribute: str

    def message(self) -> str:
        return f"Missing required attribute {self.expected_attribute} in: {self.within_pid}"


@dataclass
class CardinalityViolation:
    """Error class that represents a cardinality violation in a record."""

    pid: str
    attribute: str
    rule: str
    actual_count: int

    def message(self) -> str:
        return f"Cardinality violation in {self.attribute} of: {self.pid}. Expected {self.rule}, got {self.actual_count}"


@dataclass
class ValueViolation:
    """Error class that represents a value violation in an attribute's value."""

    pid: str
    attribute: str
    rule: str
    actual_value: str
    detail_message: str

    def message(self) -> str:
        return f"Value violation in {self.attribute} of {self.pid}. {self.detail_message} The value {self.actual_value} does not fit rule: {self.rule}."


RecordProcessingError = (
    UnresolvablePid
    | ZeroProfilesContained
    | CycleDetected
    | MissingRequiredAttribute
    | CardinalityViolation
    | ValueViolation
)


@dataclass
class ExtensionsInfo:
    """Complete profile-like information assembled from profile and all extensions.

    Contains all values of 0.FDO/Attributes from the entire extension tree,
    with metadata about the resolution process.
    """

    # The PID of this profile.
    pid: str
    # All attributes required to this profile. Includes attributes defined in extended profiles.
    all_attributes: List[str] = field(default_factory=list)
    # Attributes declared in this profile specifically, exluding extended profiles.
    declared_attributes: List[str] = field(default_factory=list)
    # The list of profiles resolved, in resolving order.
    extends_chain: List[str] = field(default_factory=list)
    # The number of profiles this profile extends.
    amount_resolved_extension_pids: int = 0
    # Indicates if cycles occurred in the profile chain.
    has_cycle: bool = False
    # Warnings that occurred during the collection of information in this class.
    processing_warnings: List[RecordProcessingError] = field(default_factory=list)


@dataclass
class ProfilesInfo:
    """
    Represents the result of a record's direct profiles.
    """

    # The record the profiles belong to.
    record: PidRecord
    # Assembled profiles for this record. Can be used for validation.
    profiles: List[ExtensionsInfo] = field(default_factory=list)
    # Warnings that occurred during the collection of information in this class.
    process_warnings: List[RecordProcessingError] = field(default_factory=list)


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
    errors: List[RecordProcessingError] = field(default_factory=list)
    warnings: List[RecordProcessingError] = field(default_factory=list)
    profiles_checked: int = 0
    attributes_checked: int = 0
    resolutions_performed: int = 0
    # Additional attributes are such attributes that are not required by the given profiles.
    additional_attributes: List[str] = field(default_factory=list)

    def add_error(self, message: RecordProcessingError) -> None:
        """Add an error and mark result as invalid."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: RecordProcessingError) -> None:
        """Add a warning (doesn't affect validity)."""
        self.warnings.append(message)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        if not other.valid:
            self.valid = False
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.profiles_checked += other.profiles_checked
        self.attributes_checked += other.attributes_checked
        self.resolutions_performed += other.resolutions_performed
