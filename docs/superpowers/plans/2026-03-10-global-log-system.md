# Global Log System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a global industrial-style logging system for SmartCar that supports UART3 output, log levels, white/blacklist module filtering, color fallback, and run-time switching without adding external config files.

**Architecture:** Add a small `services`-layer logging core that owns runtime config, level checks, module matching, formatting, and UART sinks. Keep defaults in `src/config/params.py`, expose runtime changes through command handlers and `?log`, and migrate `TransportCar` / `vision_debug` away from ad-hoc `uart3.write(...)` logging while keeping query responses separate from logs.

**Tech Stack:** Python, MicroPython-compatible services modules, pytest unit tests, pytest contract tests.

---

### Task 1: Add logging defaults and core unit tests

**Files:**
- Modify: `src/config/params.py`
- Create: `src/services/logging.py`
- Create: `tests/unit/services/test_logging.py`

**Step 1: Write the failing test**

Add unit tests that pin the core runtime rules before implementation:

```python
import pytest

from services.logging import LogManager, LOG_DEBUG, LOG_INFO


pytestmark = pytest.mark.unit


class FakeSink:
    def __init__(self):
        self.lines = []

    def write(self, text):
        self.lines.append(text)


def test_logger_blocks_debug_below_info_level() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, sinks=[sink])
    logger = manager.get_logger("vision.state")

    logger.debug("hidden")
    logger.info("shown")

    assert len(sink.lines) == 1


def test_logger_supports_whitelist_prefix_match() -> None:
    sink = FakeSink()
    manager = LogManager(
        level=LOG_DEBUG,
        filter_mode="whitelist",
        filter_modules=("vision",),
        sinks=[sink],
    )

    manager.get_logger("vision.state").debug("keep")
    manager.get_logger("control.yaw").debug("drop")

    assert len(sink.lines) == 1
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_logging.py -q`
Expected: FAIL with import errors because `services.logging` and new config constants do not exist yet.

**Step 3: Write minimal implementation**

Add log defaults in `src/config/params.py` and create `src/services/logging.py` with the smallest MicroPython-safe API:

```python
LOG_TRACE = 10
LOG_DEBUG = 20
LOG_INFO = 30
LOG_WARN = 40
LOG_ERROR = 50
LOG_FATAL = 60


class LogManager:
    def __init__(self, level=LOG_INFO, filter_mode="off", filter_modules=(), sinks=()):
        self.level = level
        self.filter_mode = filter_mode
        self.filter_modules = tuple(filter_modules)
        self.sinks = list(sinks)

    def get_logger(self, module_name):
        return Logger(self, module_name)

    def should_emit(self, level, module_name):
        return level >= self.level and self._module_allowed(module_name)
```

Implement only the logic needed for level threshold, `off / whitelist / blacklist`, and dot-boundary prefix matching.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_logging.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/config/params.py src/services/logging.py tests/unit/services/test_logging.py
git commit -m "feat(services): add global logging core"
```

### Task 2: Add formatter, color fallback, and busy-drop tests

**Files:**
- Create: `src/services/log_format.py`
- Create: `src/services/log_sink.py`
- Modify: `src/services/logging.py`
- Modify: `tests/unit/services/test_logging.py`

**Step 1: Write the failing test**

Extend `tests/unit/services/test_logging.py` with formatter and sink expectations:

```python
def test_plain_formatter_keeps_logs_readable_without_color() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_DEBUG, color_enabled=False, sinks=[sink])

    manager.get_logger("control.yaw").debug("err=12.5")

    assert sink.lines == ["D [control.yaw   ] err=12.5\r\n"]


def test_color_formatter_can_be_disabled_at_runtime() -> None:
    sink = FakeSink()
    manager = LogManager(level=LOG_INFO, color_enabled=True, sinks=[sink])

    manager.get_logger("system.boot").info("init ok")

    assert "\x1b[" in sink.lines[0]


def test_busy_sink_drops_debug_before_error() -> None:
    sink = RingBufferSink(max_lines=1)
    manager = LogManager(level=LOG_DEBUG, sinks=[sink])
    logger = manager.get_logger("vision.state")

    logger.debug("drop-me")
    logger.error("keep-me")

    assert sink.snapshot()[-1].endswith("keep-me\r\n")
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_logging.py -q`
Expected: FAIL because formatter and sink helpers do not exist yet.

**Step 3: Write minimal implementation**

Create formatter and sink helpers with deterministic output:

```python
LEVEL_PREFIX = {
    LOG_TRACE: "T",
    LOG_DEBUG: "D",
    LOG_INFO: "I",
    LOG_WARN: "W",
    LOG_ERROR: "E",
    LOG_FATAL: "F",
}


def format_log_record(record, color_enabled=False):
    line = "%s [%-14s] %s" % (
        LEVEL_PREFIX[record.level],
        record.module_name,
        record.message,
    )
    return maybe_colorize(record.level, line, color_enabled) + "\r\n"
```

For sink behavior, keep it simple: UART sink writes immediately; optional ring buffer keeps the most important recent lines and prefers retaining `ERROR` / `FATAL` over `DEBUG` / `TRACE`.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_logging.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/logging.py src/services/log_format.py src/services/log_sink.py tests/unit/services/test_logging.py
git commit -m "feat(services): add logging formatters and sinks"
```

### Task 3: Extend command routing for string-based log commands

**Files:**
- Modify: `src/services/command_router.py`
- Modify: `tests/unit/services/test_command_router.py`

**Step 1: Write the failing test**

Add router tests for command-specific value parsing instead of the current hard-coded `print` exception:

```python
def test_route_can_dispatch_raw_string_commands() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("log_level", value_type="raw")
    def cmd_log_level(local_ctx, value):
        local_ctx.calls.append(("log_level", value))

    ok = router.route("log_level=debug", ctx)

    assert ok is True
    assert ctx.calls == [("log_level", "debug")]


def test_route_can_dispatch_module_lists_as_raw_string() -> None:
    router = CommandRouter()
    ctx = FakeContext()

    @router.command("log_modules", value_type="raw")
    def cmd_log_modules(local_ctx, value):
        local_ctx.calls.append(("log_modules", value))

    ok = router.route("log_modules=vision|control.yaw", ctx)

    assert ok is True
    assert ctx.calls == [("log_modules", "vision|control.yaw")]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_command_router.py -q`
Expected: FAIL because `router.command()` does not accept parser metadata yet.

**Step 3: Write minimal implementation**

Refactor the router registry to store per-command metadata:

```python
def command(self, *keys, value_type="float"):
    def decorator(func):
        for key in keys:
            self._cmd_handlers[key] = {
                "handler": func,
                "value_type": value_type,
            }
        return func
    return decorator
```

Route logic should:

- keep bare `reset` support
- parse `value_type="float"` with `float(...)`
- parse `value_type="raw"` as the original trimmed string
- preserve existing `print` behavior by re-registering it with `value_type="raw"`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_command_router.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/command_router.py tests/unit/services/test_command_router.py
git commit -m "refactor(services): support string command parsing"
```

### Task 4: Add runtime log commands and `?log` contract coverage

**Files:**
- Create: `src/services/commands/cmd_log_profile.py`
- Create: `src/services/commands/cmd_log_level.py`
- Create: `src/services/commands/cmd_log_filter.py`
- Create: `src/services/commands/cmd_log_modules.py`
- Create: `src/services/commands/cmd_log_color.py`
- Create: `src/services/commands/cmd_log_reset.py`
- Create: `src/services/commands/query_log.py`
- Modify: `tests/fakes/fake_context.py`
- Create: `tests/contract/services/commands/test_log_commands.py`

**Step 1: Write the failing test**

Add contract tests for command handlers and the query response:

```python
import pytest

from services.commands import (
    cmd_log_color,
    cmd_log_filter,
    cmd_log_level,
    cmd_log_modules,
    cmd_log_profile,
    cmd_log_reset,
    query_log,
)
from tests.fakes.fake_context import FakeCommandContext


pytestmark = pytest.mark.contract


def test_log_level_command_updates_runtime_logger() -> None:
    ctx = FakeCommandContext()

    cmd_log_level.handle(ctx, "debug")

    assert ctx.logger_manager.level_name == "DEBUG"


def test_log_modules_command_splits_pipe_delimited_modules() -> None:
    ctx = FakeCommandContext()

    cmd_log_modules.handle(ctx, "vision|control.yaw")

    assert ctx.logger_manager.filter_modules == ("vision", "control.yaw")


def test_query_log_formats_current_runtime_config() -> None:
    ctx = FakeCommandContext()
    ctx.logger_manager.set_profile("DIAG")
    ctx.logger_manager.set_level_name("DEBUG")
    ctx.logger_manager.set_filter_mode("whitelist")
    ctx.logger_manager.set_filter_modules(("vision", "control.yaw"))
    ctx.logger_manager.set_color_enabled(True)

    query_log.handle(ctx)

    assert ctx.uart6.messages == [
        "?log=profile:diag,level:debug,filter:whitelist,color:1,modules:vision|control.yaw\r\n"
    ]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/services/commands/test_log_commands.py -q`
Expected: FAIL because the command/query modules and fake logger context do not exist yet.

**Step 3: Write minimal implementation**

Create thin command handlers that only validate and delegate to the logger manager:

```python
@router.command("log_level", value_type="raw")
def handle(ctx, value):
    ctx.logger_manager.set_level_name(value)


@router.query("log")
def handle(ctx):
    ctx.get_query_uart().write(ctx.logger_manager.build_query_response())
```

Update `FakeCommandContext` with a minimal fake `logger_manager` exposing:

- `set_profile(...)`
- `set_level_name(...)`
- `set_filter_mode(...)`
- `set_filter_modules(...)`
- `set_color_enabled(...)`
- `reset_defaults()`
- `build_query_response()`

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/services/commands/test_log_commands.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/commands/cmd_log_profile.py src/services/commands/cmd_log_level.py src/services/commands/cmd_log_filter.py src/services/commands/cmd_log_modules.py src/services/commands/cmd_log_color.py src/services/commands/cmd_log_reset.py src/services/commands/query_log.py tests/fakes/fake_context.py tests/contract/services/commands/test_log_commands.py
git commit -m "feat(services): add runtime log commands"
```

### Task 5: Integrate logger into `TransportCar` and `vision_debug`

**Files:**
- Modify: `src/services/transport_car.py`
- Modify: `src/services/vision_debug.py`
- Modify: `src/services/commands/cmd_print.py`
- Create: `tests/unit/services/test_transport_car_logging.py`
- Modify: `tests/unit/services/test_transport_car_vision_integration.py`

**Step 1: Write the failing test**

Add integration-focused unit tests that pin the first migration scope:

```python
def test_transport_car_boot_logs_go_through_logger() -> None:
    car = build_transport_car()

    car.logger_manager.get_logger("system.boot").info("boot ok")

    assert car.uart3.messages[-1].startswith("I [system.boot")


def test_transport_car_error_path_uses_structured_error_log() -> None:
    car = build_transport_car()

    car._emit_error_log("imu init failed")

    assert car.uart3.messages[-1].startswith("E [system.health")


def test_transport_car_vision_debug_uses_global_logger_format() -> None:
    car = build_transport_car()
    event = build_transition_event(...)

    car._emit_vision_debug(event)

    assert "[vision.state" in car.uart3.messages[-1]
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: FAIL because `TransportCar` still writes raw strings directly and `vision_debug` is not bound to the global logger.

**Step 3: Write minimal implementation**

Inside `TransportCar.__init__`:

```python
self.logger_manager = build_uart3_logger_manager(self.uart3)
self.log_system = self.logger_manager.get_logger("system.boot")
self.log_command = self.logger_manager.get_logger("services.command")
self.log_vision = self.logger_manager.get_logger("vision.state")
```

Refactor the first batch of outputs to use structured logger calls:

- boot messages
- IMU / motor init notices
- exception paths now printed as `ERROR`
- `RCV:` command echo becomes `services.command` debug/info log
- `vision_debug` text emission becomes a call into the global logger formatter path

Leave query handlers alone. `cmd_print` should stay as raw UART passthrough for manual text emission, not as a logger wrapper.

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add src/services/transport_car.py src/services/vision_debug.py src/services/commands/cmd_print.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py
git commit -m "refactor(services): route transport logs through logger"
```

### Task 6: Document the new runtime logging protocol

**Files:**
- Modify: `.agents/skills/using-rules/references/openart-protocol.md`

**Step 1: Write the failing test**

Search protocol docs for the new log commands and query.

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/contract/services/commands/test_log_commands.py -q && python3 -m pytest tests/unit/services/test_transport_car_logging.py -q`
Expected: code tests pass, but `.agents/skills/using-rules/references/openart-protocol.md` still lacks `log_profile`, `log_level`, `log_filter`, `log_modules`, `log_color`, `log_reset`, and `?log` documentation.

**Step 3: Write minimal implementation**

Update `.agents/skills/using-rules/references/openart-protocol.md` to document:

- purpose of the global log system
- each new runtime command
- `|`-delimited module lists
- `?log` response format
- reminder that log output and query output remain separate responsibilities

**Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/contract/services/commands/test_log_commands.py -q`
Expected: PASS, and protocol doc matches the implemented behavior.

**Step 5: Commit**

```bash
git add .agents/skills/using-rules/references/openart-protocol.md
git commit -m "docs: document runtime logging controls"
```

### Task 7: Final verification

**Files:**
- Verify only

**Step 1: Run focused unit and contract suites**

Run: `python3 -m pytest tests/unit/services/test_logging.py tests/unit/services/test_command_router.py tests/unit/services/test_transport_car_logging.py tests/unit/services/test_transport_car_vision_integration.py tests/contract/services/commands/test_log_commands.py -q`
Expected: PASS.

**Step 2: Run the full host-verifiable regression suite**

Run: `python3 -m pytest tests/unit tests/contract -q`
Expected: PASS.

**Step 3: Inspect working tree**

Run: `git status --short`
Expected: only the planned logging source, tests, and docs changes remain.

**Step 4: Report evidence**

Summarize:

- new logger core behavior
- supported runtime commands and `?log`
- tests executed and their results
- any device-path follow-up still needed for Stage 2 / Stage 3 / HIL
