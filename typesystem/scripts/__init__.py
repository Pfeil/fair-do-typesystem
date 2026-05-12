"""FDO Type System Validator - Generic Record Validation.

This package provides tools for validating FDO records against their profiles
and attribute definitions. The validator is content-driven, deriving validation
rules from the profiles and attribute definitions that records reference.

Main components:
- models: Data classes (PidRecord, AssembledProfile, ValidationRules, etc.)
- logging: Structured validation logger
- registry: PID resolution with file system abstraction
- assembly: Profile and attribute assembly (gathering validation rules)
- validators: Profile, attribute, and specification validators
- orchestrator: Coordinates all validation components
"""

from .models import (
    AssembledProfile,
    PidRecord,
    ValidationResult,
    ValidationRules,
)
from .registry import PidRegistry
from .validation_logger import ValidationLogger

__all__ = [
    "PidRecord",
    "AssembledProfile",
    "ValidationRules",
    "ValidationResult",
    "ValidationLogger",
    "PidRegistry",
]
