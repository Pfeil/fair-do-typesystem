import sys

from assembly import AttributeAssembly, ExtensionsAssembly, ProfilesAssembly
from registry import PidRegistry
from validation_logger import ValidationLogger
from validators import AttributeValidator, ProfileValidator


def validate_pid(pid_string) -> bool:

    logger = ValidationLogger(verbose=True)
    registry = PidRegistry(logger)
    extensions_assembly = ExtensionsAssembly(registry, logger)
    profiles_assembly = ProfilesAssembly(registry, logger)

    attribute_assembly = AttributeAssembly(registry, logger)
    profile_validator = ProfileValidator(
        registry, logger, profiles_assembly, extensions_assembly
    )
    attribute_validator = AttributeValidator(registry, logger, attribute_assembly)

    record = registry.resolve_pid(pid_string)
    if not record:
        return ValidationResult(False, f"PID {pid_string} not found in registry.")
    result = profile_validator.validate(record)
    result = attribute_validator.validate(record, pid_string)
    return result.valid


def main():
    if len(sys.argv) != 2:
        print("Usage: uv run validator.py <PID-String>")
        sys.exit(1)

    pid_string = sys.argv[1]

    if validate_pid(pid_string):
        print("PID is valid!")
    else:
        print("PID is invalid.")
        sys.exit(1)


if __name__ == "__main__":
    main()
