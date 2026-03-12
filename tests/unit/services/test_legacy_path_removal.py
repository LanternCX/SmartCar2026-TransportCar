"""约束 Task 8 已移除 legacy 服务路径与引用."""

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


REPO_ROOT = Path(__file__).resolve().parents[3]
LEGACY_PATHS = (
    "src/services/vision_debug.py",
    "src/services/vision_protocol.py",
    "src/services/vision_state_defs.py",
    "src/services/vision_state_machine.py",
    "src/services/vision_state_registry.py",
    "src/services/command_router.py",
    "src/services/commands",
    "src/services/commander.py",
)
FORBIDDEN_REFERENCES = (
    ("services.command_router import", "services.command_router"),
    ("services.commands import", "services.commands"),
    ("services.commander import", "services.commander"),
    ("services.vision_debug import", "services.vision_debug"),
    ("services.vision_protocol import", "services.vision_protocol"),
    ("services.vision_state_defs import", "services.vision_state_defs"),
    ("services.vision_state_machine import", "services.vision_state_machine"),
    ("services.vision_state_registry import", "services.vision_state_registry"),
)


def test_task8_legacy_service_paths_are_deleted() -> None:
    missing_cleanup = [path for path in LEGACY_PATHS if (REPO_ROOT / path).exists()]

    assert missing_cleanup == []


def test_task8_runtime_and_tests_no_longer_reference_legacy_service_paths() -> None:
    scan_roots = (
        REPO_ROOT / "src",
        REPO_ROOT / "tests/unit",
        REPO_ROOT / "tests/contract",
    )
    violations = []

    for root in scan_roots:
        for file_path in sorted(root.rglob("*.py")):
            if file_path == Path(__file__).resolve():
                continue
            text = file_path.read_text(encoding="utf-8")
            for needle, label in FORBIDDEN_REFERENCES:
                if needle in text:
                    violations.append(
                        "%s -> %s" % (file_path.relative_to(REPO_ROOT), label)
                    )

    assert violations == []
