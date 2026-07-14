import pytest

from assembly import AttributeAssembly, ExtensionsAssembly, ProfilesAssembly
from registry import PidRegistry
from validation_logger import ValidationLogger
from validators import AttributeValidator, ProfileValidator


@pytest.fixture
def logger() -> ValidationLogger:
    return ValidationLogger(verbose=True)


@pytest.fixture
def registry(logger: ValidationLogger) -> PidRegistry:
    return PidRegistry(logger)


@pytest.fixture
def extensions_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> ExtensionsAssembly:
    return ExtensionsAssembly(registry, logger)


@pytest.fixture
def profiles_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> ProfilesAssembly:
    return ProfilesAssembly(registry, logger)


@pytest.fixture
def attribute_assembly(
    registry: PidRegistry, logger: ValidationLogger
) -> AttributeAssembly:
    return AttributeAssembly(registry, logger)


@pytest.fixture
def profile_validator(
    registry: PidRegistry,
    logger: ValidationLogger,
    profiles_assembly: ProfilesAssembly,
    extensions_assembly: ExtensionsAssembly,
) -> ProfileValidator:
    return ProfileValidator(registry, logger, profiles_assembly, extensions_assembly)


@pytest.fixture
def attribute_validator(
    registry: PidRegistry,
    logger: ValidationLogger,
    attribute_assembly: AttributeAssembly,
) -> AttributeValidator:
    return AttributeValidator(registry, logger, attribute_assembly)


class TestOverall:
    def test_validate_all_pids(
        self,
        logger: ValidationLogger,
        registry: PidRegistry,
        profile_validator: ProfileValidator,
        attribute_validator: AttributeValidator,
    ):
        pids = registry.get_all_pids()
        assert len(pids) > 0, "No PIDs found in registry"

        for pid in pids:
            print("-----------------------")
            print(f"Processing PID {pid}")
            assert pid in registry.get_all_pids(), f"PID {pid} not found in registry"
            resolved = registry.resolve_pid(pid)
            assert resolved is not None, f"PID {pid} not found in registry"
            profile_result = profile_validator.validate(resolved)
            assert profile_result.valid, f"PID {pid} profile validation failed"
            attribute_result = attribute_validator.validate(resolved, pid)
            assert attribute_result.errors == [], (
                f"PID {pid} attribute validation failed: {attribute_result.errors}"
            )
            assert attribute_result.valid, f"PID {pid} attribute validation failed"
