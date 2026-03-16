"""services 包布局门禁测试."""

from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


def test_services_root_uses_car_package_instead_of_transport_prefix_files() -> None:
    root = Path(__file__).resolve().parents[2] / "src/services"

    assert (root / "car").is_dir()
    assert (root / "car/__init__.py").is_file()
    assert (root / "car/core.py").is_file()
    assert sorted(path.name for path in root.glob("transport_*.py")) == []


def test_vision_protocol_uses_split_submodules() -> None:
    root = Path(__file__).resolve().parents[2] / "src/vision"

    assert (root / "protocol").is_dir()
    assert (root / "protocol/__init__.py").is_file()
    assert (root / "protocol/query.py").is_file()
    assert (root / "protocol/parse.py").is_file()
    assert (root / "protocol/batch.py").is_file()
    assert sorted(path.name for path in root.glob("protocol_*.py")) == []


def test_vision_state_machine_uses_split_submodules() -> None:
    root = Path(__file__).resolve().parents[2] / "src/vision"

    assert (root / "state_machine").is_dir()
    assert (root / "state_machine/__init__.py").is_file()
    assert (root / "state_machine/types.py").is_file()
    assert (root / "state_machine/core.py").is_file()
    assert (root / "state_machine/actions.py").is_file()
    assert sorted(path.name for path in root.glob("state_machine_*.py")) == []


def test_diagnostics_manager_uses_split_submodules() -> None:
    root = Path(__file__).resolve().parents[2] / "src/diagnostics"

    assert (root / "manager").is_dir()
    assert (root / "manager/__init__.py").is_file()
    assert (root / "manager/config.py").is_file()
    assert (root / "manager/emit.py").is_file()
    assert (root / "manager/logger.py").is_file()
    assert (root / "manager.py").exists() is False
    assert sorted(path.name for path in root.glob("log_*.py")) == []
