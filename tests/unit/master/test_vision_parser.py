def test_master_vision_parser_module_no_longer_exists_in_current_thin_runtime() -> None:
    import importlib
    import pytest

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("master.vision.parser")
