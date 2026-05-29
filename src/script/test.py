"""板端测试入口."""

from config import startup as startup_params


TEST_MODULES = {
    "wireless_contention": "script.test.wireless_contention",
}


def _import_module(module_name):
    """导入指定测试模块."""

    return __import__(module_name, None, None, ["*"])


def main():
    """运行配置指定的板端测试."""

    test_name = startup_params.STARTUP_TEST_NAME
    module_name = TEST_MODULES.get(test_name)
    if module_name is None:
        raise ValueError("未知测试脚本: %s" % test_name)
    return _import_module(module_name).main()


if __name__ == "__main__" and globals().get("__spec__") is None:
    main()
