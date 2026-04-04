"""主车视觉输入整理.

@file src/master/vision/ingress.py
"""

import time

_package_name = str(globals().get("__package__", ""))

if "." in _package_name:
    from .. import runtime_params
    from .parser import parse_vision_line
else:
    import runtime_params
    from vision.parser import parse_vision_line

FOLLOW_ACTIVE_UART = "uart6"
FOLLOW_RESERVED_UARTS = ("uart8",)
FOLLOW_TARGET_LABEL = "follower"


class VisionIngress:
    def __init__(
        self,
        active_uart=FOLLOW_ACTIVE_UART,
        reserved_uarts=None,
        timeout_ms=None,
    ):
        self.active_uart = str(active_uart)
        if reserved_uarts is None:
            reserved_uarts = FOLLOW_RESERVED_UARTS
        self.reserved_uarts = tuple(reserved_uarts)
        self.known_uarts = (self.active_uart,) + tuple(
            uart for uart in self.reserved_uarts if str(uart) != self.active_uart
        )
        if timeout_ms is None:
            timeout_ms = runtime_params.FOLLOW_TIMEOUT_MS
        self.timeout_ms = int(timeout_ms)
        self.latest_vision_seq = 0
        self.current_target = self._build_idle_observation("missing")
        self._latest_by_uart = {}
        self._frame_has_input = False
        self._frame_updated_uarts = ()
        self._frame_now_ms = self._resolve_now_ms(None)

    def _resolve_now_ms(self, now_ms):
        if now_ms is None:
            ticks_ms = getattr(time, "ticks_ms", None)
            if ticks_ms is not None:
                return int(ticks_ms())
            return int(time.time() * 1000)
        return int(now_ms)

    def begin_frame(self, now_ms=None):
        self._frame_has_input = False
        self._frame_updated_uarts = ()
        self._frame_now_ms = self._resolve_now_ms(now_ms)

    def _normalize_marker_error(self, uart_name, err_x, err_y):
        _ = uart_name
        return float(err_x), float(err_y)

    def _build_idle_observation(self, source_status):
        return {
            "configured_uart": self.active_uart,
            "source_uart": "",
            "reserved_uarts": self.reserved_uarts,
            "source_status": str(source_status),
            "camera_id": "",
            "target": "idle",
            "selected_target": "idle",
            "vision_seq": 0,
            "valid": 0,
            "fresh": 0,
            "stale": 0,
            "has_new_input": 0,
            "target_age_ms": self.timeout_ms + 1,
            "control_valid": 0,
            "err_x": 0.0,
            "err_y": 0.0,
        }

    def _mark_target_state(self, observation, now_ms, has_new_input):
        marked = dict(observation)
        marked.setdefault("selected_target", str(marked.get("target", "idle")))
        marked.setdefault("last_seen_ms", int(now_ms))
        is_valid = int(marked.get("valid", 0)) == 1
        is_fresh = False
        if is_valid:
            age_ms = int(now_ms) - int(marked.get("last_seen_ms", now_ms))
            is_fresh = age_ms <= self.timeout_ms
        else:
            age_ms = self.timeout_ms + 1
        marked["fresh"] = 1 if is_fresh else 0
        marked["stale"] = 0 if is_fresh else 1
        marked["has_new_input"] = 1 if has_new_input else 0
        marked["target_age_ms"] = int(age_ms)
        marked["control_valid"] = 1 if is_valid and is_fresh else 0
        return marked

    def prepare_observation(self, observation=None, now_ms=None):
        if now_ms is None and isinstance(observation, dict):
            now_ms = observation.get("now_ms")
        frame_now_ms = self._resolve_now_ms(now_ms)
        if observation is None:
            self.current_target = self._mark_target_state(
                self._build_idle_observation("missing"),
                frame_now_ms,
                False,
            )
            return dict(self.current_target)
        prepared = dict(observation)
        uart_name = str(prepared.get("uart", self.active_uart))

        if uart_name not in self.known_uarts:
            idle = self._build_idle_observation("unexpected_uart")
            idle["source_uart"] = uart_name
            self.current_target = self._mark_target_state(idle, frame_now_ms, False)
            return dict(self.current_target)

        line = prepared.get("line")
        if line is None:
            if len(prepared) == 1 and "uart" in prepared:
                idle = self._build_idle_observation("missing")
                idle["source_uart"] = uart_name
                self.current_target = self._mark_target_state(idle, frame_now_ms, False)
                return dict(self.current_target)
            self._frame_has_input = True
            self._frame_updated_uarts = tuple(
                set(self._frame_updated_uarts + (uart_name,))
            )
            prepared["err_x"], prepared["err_y"] = self._normalize_marker_error(
                uart_name, prepared.get("err_x", 0.0), prepared.get("err_y", 0.0)
            )
            prepared.setdefault("configured_uart", self.active_uart)
            prepared.setdefault("source_uart", uart_name)
            prepared.setdefault("reserved_uarts", self.reserved_uarts)
            prepared.setdefault("source_status", "active")
            prepared.setdefault("target", FOLLOW_TARGET_LABEL)
            prepared.setdefault("valid", 0)
            prepared["last_seen_ms"] = frame_now_ms
            if "vision_seq" in prepared:
                self.latest_vision_seq = int(prepared["vision_seq"])
            self._latest_by_uart[uart_name] = dict(prepared)
            self.current_target = self._mark_target_state(prepared, frame_now_ms, True)
            return dict(self.current_target)

        self._frame_has_input = True
        self._frame_updated_uarts = tuple(set(self._frame_updated_uarts + (uart_name,)))
        try:
            parsed = parse_vision_line(line)
        except (KeyError, TypeError, ValueError):
            idle = self._build_idle_observation("invalid")
            idle["source_uart"] = uart_name
            idle["last_seen_ms"] = frame_now_ms
            self._latest_by_uart[uart_name] = dict(idle)
            self.current_target = self._mark_target_state(idle, frame_now_ms, True)
            return dict(self.current_target)

        self.latest_vision_seq = int(parsed["vision_seq"])
        parsed["err_x"], parsed["err_y"] = self._normalize_marker_error(
            uart_name, parsed["err_x"], parsed["err_y"]
        )
        parsed["configured_uart"] = self.active_uart
        parsed["source_uart"] = uart_name
        parsed["reserved_uarts"] = self.reserved_uarts
        parsed["source_status"] = "active"
        parsed["last_seen_ms"] = frame_now_ms
        self._latest_by_uart[uart_name] = dict(parsed)
        self.current_target = self._mark_target_state(parsed, frame_now_ms, True)
        return dict(self.current_target)

    def select_current_target(self, now_ms=None):
        frame_now_ms = self._resolve_now_ms(now_ms)
        valid_items = []
        for uart_name in self.known_uarts:
            item = self._latest_by_uart.get(uart_name)
            if (
                item
                and item.get("source_status") == "active"
                and int(item.get("valid", 0)) == 1
            ):
                marked = self._mark_target_state(
                    item,
                    frame_now_ms,
                    uart_name in self._frame_updated_uarts,
                )
                if int(marked.get("fresh", 0)) == 1:
                    valid_items.append(marked)

        if not valid_items:
            source_status = "stale" if self._latest_by_uart else "missing"
            self.current_target = self._mark_target_state(
                self._build_idle_observation(source_status),
                frame_now_ms,
                False,
            )
            return dict(self.current_target)

        valid_items.sort(
            key=lambda item: (
                int(item.get("last_seen_ms", 0)),
                item.get("source_uart", "") == "uart6",
            ),
            reverse=True,
        )
        self.current_target = dict(valid_items[0])
        return dict(self.current_target)
