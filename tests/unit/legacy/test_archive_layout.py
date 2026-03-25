"""校验旧系统代码已真实归档到 src/legacy."""

from pathlib import Path


def test_legacy_tree_contains_original_runtime_roots() -> None:
    root = Path("src/legacy")

    assert (root / "boot.py").exists()
    assert (root / "config").exists()
    assert (root / "diagnostics").exists()
    assert (root / "services").exists()
    assert (root / "vision").exists()
    assert (root / "control").exists()
    assert (root / "filters").exists()
    assert (root / "hardware").exists()
    assert (root / "script").exists()
    assert (root / "storage").exists()
    assert (root / "utils").exists()


def test_src_root_is_reduced_to_legacy_master_assistant() -> None:
    src_root = Path("src")

    assert not (src_root / "boot.py").exists()
    assert not (src_root / "config").exists()
    assert not (src_root / "diagnostics").exists()
    assert not (src_root / "services").exists()
    assert not (src_root / "vision").exists()
    assert not (src_root / "control").exists()
    assert not (src_root / "filters").exists()
    assert not (src_root / "hardware").exists()
    assert not (src_root / "script").exists()
    assert not (src_root / "storage").exists()
    assert not (src_root / "utils").exists()
    assert (src_root / "legacy").exists()
