"""src 运行时代码非注释行数门禁测试."""

from pathlib import Path
import ast
import tokenize
from io import StringIO

import pytest


pytestmark = pytest.mark.unit


RUNTIME_FILES = (
    "src/services/car/core.py",
    "src/services/runtime/diagnostics_facade.py",
    "src/diagnostics/manager/__init__.py",
)

RUNTIME_DIAGNOSTICS_FILES = (
    "src/services/runtime/diag_format.py",
    "src/services/runtime/diag_health.py",
    "src/services/runtime/diag_motion.py",
    "src/services/runtime/diag_vision.py",
)


def _line_count(relative_path: str) -> int:
    source = (Path(__file__).resolve().parents[2] / relative_path).read_text(
        encoding="utf-8"
    )
    docstring_lines = set()
    tree = ast.parse(source)

    def collect_docstring_lines(node) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first_stmt = body[0]
        value = getattr(first_stmt, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            end_lineno = getattr(first_stmt, "end_lineno", first_stmt.lineno)
            for line_no in range(first_stmt.lineno, end_lineno + 1):
                docstring_lines.add(line_no)

    collect_docstring_lines(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            collect_docstring_lines(node)

    code_lines = set()

    for token in tokenize.generate_tokens(StringIO(source).readline):
        if token.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENDMARKER):
            continue
        if token.type == tokenize.COMMENT:
            continue
        if token.start[0] in docstring_lines:
            continue
        code_lines.add(token.start[0])

    return len(code_lines)


def test_line_count_ignores_comments_and_docstrings() -> None:
    source = '''"""模块文档注释."""

# 单行注释

class Demo:
    """Doxygen 风格文档注释示例.

    @brief 示例类.
    """

    def run(self):
        """@brief 执行示例."""
        # 行内块注释
        value = 1
        return value
'''
    temp_path = Path(__file__).resolve().parent / "_tmp_comment_gate_sample.py"
    temp_path.write_text(source, encoding="utf-8")

    try:
        assert (
            _line_count(str(temp_path.relative_to(Path(__file__).resolve().parents[2])))
            == 5
        )
    finally:
        temp_path.unlink(missing_ok=True)


def test_runtime_python_files_stay_within_300_lines() -> None:
    oversized = [
        (path, _line_count(path)) for path in RUNTIME_FILES if _line_count(path) > 300
    ]

    assert oversized == []


def test_runtime_diagnostics_facade_uses_split_submodules() -> None:
    root = Path(__file__).resolve().parents[2]

    for relative_path in RUNTIME_DIAGNOSTICS_FILES:
        assert (root / relative_path).is_file()
