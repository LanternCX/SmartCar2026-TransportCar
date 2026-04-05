"""主辅车注释覆盖检查基线.

@file tests/unit/test_comment_annotation_layout.py
"""

import ast
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_RUNTIME_NAMES = ("master", "assistant")
TARGET_SUFFIXES = (".py", ".txt")
FLOW_FILE_NAMES = {"main.py", "app.py", "motion_runtime.py"}
KEY_FLOW_FUNCTION_NAMES = {
    "main",
    "step",
    "tick",
    "handle_line",
    "run_calibrate_gyro",
    "run_pid_identify",
    "build_hw_bundle",
}
# 这些函数虽然使用私有命名, 但承担主链阶段切换职责；新增同类主链流程函数时要同步更新这里。
FLOW_SEGMENT_SPECIAL_FUNCTION_NAMES = {
    "_drive_loop",
    "_start_runtime",
    "_tick",
    "_apply_command",
}
PARAMETER_TEXT_NAMES = {"gyro_offset.txt", "ident_params.txt"}
COMMENT_LINE_RE = re.compile(r"^\s*#")
PARAMETER_PURPOSE_KEYWORDS = (
    "用途",
    "作用",
    "内容",
    "格式",
    "参数",
    "零漂",
    "辨识",
    "校准",
    "结果",
)


def _iter_target_files() -> "list[Path]":
    files = []
    for runtime_name in TARGET_RUNTIME_NAMES:
        runtime_root = PROJECT_ROOT / "src" / runtime_name
        for file_path in runtime_root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in TARGET_SUFFIXES:
                continue
            relative_parts = file_path.relative_to(PROJECT_ROOT / "src").parts
            if "legacy" in relative_parts:
                continue
            if "test" in relative_parts:
                continue
            if "__pycache__" in relative_parts:
                continue
            files.append(file_path)
    return sorted(files)


def _read_text(file_path):
    return file_path.read_text(encoding="utf-8")


def _parse_python_module(file_path):
    return ast.parse(_read_text(file_path), filename=str(file_path))


def _has_file_header_docstring(module):
    docstring = ast.get_docstring(module, clean=False)
    if not docstring:
        return False
    lines = [line.strip() for line in docstring.splitlines() if line.strip()]
    if not lines:
        return False
    has_brief_text = any(not line.startswith("@") for line in lines)
    has_file_tag = any(line.startswith("@file ") for line in lines)
    return has_brief_text and has_file_tag


def _iter_target_callables(module):
    target_nodes = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            target_nodes.append((None, node))
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    target_nodes.append((node.name, child))
    return target_nodes


def _control_flow_count(node):
    control_flow_types = (ast.For, ast.While, ast.If, ast.Try, ast.With)
    return sum(isinstance(child, control_flow_types) for child in ast.walk(node))


def _is_simple_control_proxy(node):
    body = list(getattr(node, "body", ()))
    if len(body) != 1:
        return False
    statement = body[0]
    if isinstance(statement, ast.Return):
        value = statement.value
        return (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Attribute)
            and isinstance(value.value.value, ast.Name)
            and value.value.value.id == "self"
            and value.value.attr == "control"
        )
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        value = statement.value
        return (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Attribute)
            and isinstance(target.value.value, ast.Name)
            and target.value.value.id == "self"
            and target.value.attr == "control"
            and isinstance(value, ast.Name)
            and value.id == "value"
        )
    return False


def _is_callable_annotation_target(file_path, owner_name, node):
    # 这组规则只想抓住三类对象: 对外入口、长流程骨架、理解成本高的方法。
    # 显式名单覆盖入口文件里那些虽是私有命名、但实际承担主链阶段切换的函数；
    # 新增主链流程函数时, 要同步更新这些特殊名单, 避免基线漏检关键骨架。
    # 其余阈值用来兜住明显偏长或控制分支较多的方法，避免把简单工具函数也强行纳入。
    if node.name.startswith("__") and node.name.endswith("__"):
        return False
    if _is_simple_control_proxy(node):
        return False
    if not node.name.startswith("_"):
        return True
    if (
        file_path.name in FLOW_FILE_NAMES
        and node.name in FLOW_SEGMENT_SPECIAL_FUNCTION_NAMES
    ):
        return True
    if node.name in KEY_FLOW_FUNCTION_NAMES:
        return True
    body_span = int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno) + 1
    if body_span >= 30:
        return True
    if _control_flow_count(node) >= 4:
        return True
    return bool(owner_name) and body_span >= 24


def _has_responsibility_docstring(node):
    docstring = ast.get_docstring(node, clean=False)
    if not docstring:
        return False
    lines = [line.strip() for line in docstring.splitlines() if line.strip()]
    if not lines:
        return False
    has_brief_text = any(not line.startswith("@") for line in lines)
    has_brief_tag = any(line.startswith("@brief") for line in lines)
    return has_brief_text and has_brief_tag


def _function_span_lines(file_path, node):
    lines = _read_text(file_path).splitlines()
    start_index = int(node.lineno) - 1
    end_index = int(getattr(node, "end_lineno", node.lineno))
    return lines[start_index:end_index]


def _line_indent(raw_line):
    return len(raw_line) - len(raw_line.lstrip(" "))


def _leading_comment_block_count(file_path, node):
    lines = _read_text(file_path).splitlines()
    index = int(node.lineno) - 2
    count = 0
    while index >= 0:
        stripped = lines[index].strip()
        if not stripped:
            break
        if not COMMENT_LINE_RE.match(lines[index]):
            break
        count += 1
        index -= 1
    return count


def _body_comment_count(file_path, node):
    span_lines = _function_span_lines(file_path, node)
    function_indent = _line_indent(span_lines[0])
    return sum(
        1
        for raw_line in span_lines[1:]
        if COMMENT_LINE_RE.match(raw_line) and _line_indent(raw_line) > function_indent
    )


def _is_flow_segment_target(file_path, node):
    if file_path.name not in FLOW_FILE_NAMES:
        return False
    if node.name in FLOW_SEGMENT_SPECIAL_FUNCTION_NAMES:
        return True
    if node.name not in KEY_FLOW_FUNCTION_NAMES and node.name.startswith("_"):
        return False
    body_span = int(getattr(node, "end_lineno", node.lineno)) - int(node.lineno) + 1
    return body_span >= 25 and _control_flow_count(node) >= 3


def _has_flow_segment_comment(file_path, node):
    body_comment_count = _body_comment_count(file_path, node)
    leading_comment_count = _leading_comment_block_count(file_path, node)
    return body_comment_count >= 2 or (
        body_comment_count >= 1 and leading_comment_count >= 1
    )


def _comment_and_doc_lines(file_path):
    lines = []
    content = _read_text(file_path)
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if COMMENT_LINE_RE.match(raw_line):
            lines.append(stripped)

    module = _parse_python_module(file_path)
    module_doc = ast.get_docstring(module, clean=False)
    if module_doc:
        lines.extend(line.strip() for line in module_doc.splitlines() if line.strip())

    for _, node in _iter_target_callables(module):
        docstring = ast.get_docstring(node, clean=False)
        if docstring:
            lines.extend(
                line.strip() for line in docstring.splitlines() if line.strip()
            )
    return lines


def _has_parameter_file_explanation(file_path, python_files):
    content_lines = [
        line.strip() for line in _read_text(file_path).splitlines() if line.strip()
    ]
    if content_lines and content_lines[0].startswith("#"):
        first_line = content_lines[0]
        if file_path.name in first_line and any(
            keyword in first_line for keyword in PARAMETER_PURPOSE_KEYWORDS
        ):
            return True

    for python_file in python_files:
        for line in _comment_and_doc_lines(python_file):
            if file_path.name not in line:
                continue
            if any(keyword in line for keyword in PARAMETER_PURPOSE_KEYWORDS):
                return True
    return False


def test_comment_annotation_target_inventory() -> None:
    """注释覆盖基线必须锁定主辅车目标文件集合."""

    target_files = _iter_target_files()
    target_relatives = {
        str(file_path.relative_to(PROJECT_ROOT)) for file_path in target_files
    }

    assert target_files
    assert all("/test/" not in relative for relative in target_relatives)
    assert all("/__pycache__/" not in relative for relative in target_relatives)
    assert all(not relative.startswith("src/legacy/") for relative in target_relatives)
    assert "src/master/script/calibrate_gyro.py" in target_relatives
    assert "src/assistant/script/calibrate_gyro.py" in target_relatives
    assert "src/master/gyro_offset.txt" in target_relatives
    assert "src/master/ident_params.txt" in target_relatives


def test_comment_annotation_baseline_reports_missing_categories() -> None:
    """注释覆盖基线需要指出当前还缺哪类说明."""

    target_files = _iter_target_files()
    python_files = [
        file_path for file_path in target_files if file_path.suffix == ".py"
    ]
    missing_method_docs = {}
    findings = {
        "缺文件头定位": [],
        "缺长流程分段说明": [],
        "缺参数文件说明": [],
    }

    for file_path in python_files:
        module = _parse_python_module(file_path)
        relative_path = str(file_path.relative_to(PROJECT_ROOT))
        if not _has_file_header_docstring(module):
            findings["缺文件头定位"].append(relative_path)
        for owner_name, node in _iter_target_callables(module):
            qualified_name = (
                node.name if owner_name is None else "%s.%s" % (owner_name, node.name)
            )
            if _is_flow_segment_target(
                file_path, node
            ) and not _has_flow_segment_comment(file_path, node):
                findings["缺长流程分段说明"].append(
                    "%s::%s" % (relative_path, qualified_name)
                )
            if not _is_callable_annotation_target(file_path, owner_name, node):
                continue
            if _has_responsibility_docstring(node):
                continue
            missing_method_docs.setdefault(relative_path, []).append(qualified_name)

    parameter_files = [
        file_path
        for file_path in target_files
        if file_path.name in PARAMETER_TEXT_NAMES and file_path.suffix == ".txt"
    ]
    for file_path in parameter_files:
        if _has_parameter_file_explanation(file_path, python_files):
            continue
        findings["缺参数文件说明"].append(str(file_path.relative_to(PROJECT_ROOT)))

    failure_lines = []
    if missing_method_docs:
        method_lines = ["缺方法职责说明:"]
        for relative_path in sorted(missing_method_docs):
            method_names = missing_method_docs[relative_path]
            method_lines.append("- %s" % relative_path)
            for method_name in method_names:
                method_lines.append("  * %s" % method_name)
        failure_lines.append("\n".join(method_lines))
    for category, entries in findings.items():
        if not entries:
            continue
        category_lines = ["%s:" % category]
        for entry in entries:
            category_lines.append("- %s" % entry)
        failure_lines.append("\n".join(category_lines))

    assert not failure_lines, "\n".join(failure_lines)


def test_runtime_parameter_text_files_keep_data_only() -> None:
    """运行时参数文本文件必须保持纯数据格式."""

    expected_first_line = {
        "gyro_offset.txt": lambda line: (
            "," in line and not line.lstrip().startswith("#")
        ),
        "ident_params.txt": lambda line: bool(re.match(r"^[mlr]\s", line)),
    }

    for file_path in _iter_target_files():
        if file_path.name not in PARAMETER_TEXT_NAMES:
            continue
        lines = [
            line.strip() for line in _read_text(file_path).splitlines() if line.strip()
        ]
        assert lines, "%s 不能为空" % str(file_path.relative_to(PROJECT_ROOT))
        assert expected_first_line[file_path.name](lines[0]), (
            "%s 必须以纯数据首行开头, 不能把说明文字写进运行时参数文件"
            % str(file_path.relative_to(PROJECT_ROOT))
        )


def test_runtime_comment_annotations_do_not_revive_legacy_wording() -> None:
    """当前主线注释不应把 legacy 口径带回运行时代码."""

    offenders = []
    for file_path in _iter_target_files():
        if file_path.suffix != ".py":
            continue
        relative_path = str(file_path.relative_to(PROJECT_ROOT))
        if "/test/" in relative_path:
            continue
        if any("legacy" in line.lower() for line in _comment_and_doc_lines(file_path)):
            offenders.append(relative_path)

    assert not offenders, "当前主线注释仍包含 legacy 口径: %s" % ", ".join(offenders)
