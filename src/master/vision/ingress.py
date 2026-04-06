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


class VisionIngress:
    """整理视觉串口输入并维护当前目标快照.

    @brief 把多路串口输入统一转成主车决策层可直接消费的 observation 结构。
    """

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
        """开始一帧新的视觉输入统计窗口.

        @brief 每次主循环先重置本帧标记, 后续输入才能区分是旧缓存还是本拍新数据。
        """

        self._frame_has_input = False
        self._frame_updated_uarts = ()
        self._frame_now_ms = self._resolve_now_ms(now_ms)

    def _mark_uart_updated(self, uart_name):
        if uart_name not in self._frame_updated_uarts:
            self._frame_updated_uarts += (uart_name,)

    def _normalize_marker_error(self, uart_name, err_x, err_y):
        _ = uart_name
        return float(err_x), float(err_y)

    def _resolve_selected_target(self, observation):
        if int(observation.get("valid", 0)) != 1:
            return "idle"
        selected_target = str(observation.get("selected_target", "")).strip()
        if selected_target:
            return selected_target
        return "tracked"

    def _build_idle_observation(self, source_status):
        return {
            "configured_uart": self.active_uart,
            "source_uart": "",
            "reserved_uarts": self.reserved_uarts,
            "source_status": str(source_status),
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
        marked["selected_target"] = self._resolve_selected_target(marked)
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

    def _accept_uart_update(self, uart_name, vision_seq):
        current = self._latest_by_uart.get(uart_name)
        if current is None:
            return True
        current_seq = current.get("vision_seq")
        if current_seq is None:
            return True
        return int(vision_seq) > int(current_seq)

    def prepare_observation(self, observation=None, now_ms=None):
        """把原始串口输入整理成统一 observation.

        @brief 同时处理空输入、非法报文、直传字典和文本协议, 并刷新当前目标缓存。
        """

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
            if tuple(sorted(prepared.keys())) in (("now_ms", "uart"), ("uart",)):
                idle = self._build_idle_observation("missing")
                idle["source_uart"] = uart_name
                self.current_target = self._mark_target_state(idle, frame_now_ms, False)
                return dict(self.current_target)
            self._frame_has_input = True
            self._mark_uart_updated(uart_name)
            prepared["err_x"], prepared["err_y"] = self._normalize_marker_error(
                uart_name, prepared.get("err_x", 0.0), prepared.get("err_y", 0.0)
            )
            prepared.setdefault("configured_uart", self.active_uart)
            prepared.setdefault("source_uart", uart_name)
            prepared.setdefault("reserved_uarts", self.reserved_uarts)
            prepared.setdefault("source_status", "active")
            prepared.setdefault("valid", 0)
            prepared["last_seen_ms"] = frame_now_ms
            if "vision_seq" in prepared:
                self.latest_vision_seq = int(prepared["vision_seq"])
            self._latest_by_uart[uart_name] = dict(prepared)
            self.current_target = self._mark_target_state(prepared, frame_now_ms, True)
            return dict(self.current_target)

        self._frame_has_input = True
        self._mark_uart_updated(uart_name)
        try:
            parsed = parse_vision_line(line)
        except (KeyError, TypeError, ValueError):
            idle = self._build_idle_observation("invalid")
            idle["source_uart"] = uart_name
            idle["last_seen_ms"] = frame_now_ms
            idle["debug_raw_line"] = str(line).strip()
            self._latest_by_uart[uart_name] = dict(idle)
            self.current_target = self._mark_target_state(idle, frame_now_ms, True)
            return dict(self.current_target)

        if not self._accept_uart_update(uart_name, parsed["vision_seq"]):
            current = self._latest_by_uart.get(uart_name)
            if current is None:
                current = self._build_idle_observation("missing")
                current["source_uart"] = uart_name
            self.current_target = self._mark_target_state(current, frame_now_ms, False)
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
        """从当前缓存里挑选仍然可用的目标.

        @brief 优先返回新鲜且有效的输入, 否则退回缺失或过期状态供决策层降级处理。
        """

        frame_now_ms = self._resolve_now_ms(now_ms)
        best_item = None
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
                if int(marked.get("fresh", 0)) != 1:
                    continue
                if best_item is None:
                    best_item = marked
                    continue
                marked_seen_ms = int(marked.get("last_seen_ms", 0))
                best_seen_ms = int(best_item.get("last_seen_ms", 0))
                if marked_seen_ms > best_seen_ms:
                    best_item = marked
                    continue
                if (
                    marked_seen_ms == best_seen_ms
                    and str(marked.get("source_uart", "")) == self.active_uart
                ):
                    best_item = marked

        if best_item is None:
            source_status = "stale" if self._latest_by_uart else "missing"
            debug_raw_line = ""
            debug_uart = ""
            for uart_name in self._frame_updated_uarts:
                item = self._latest_by_uart.get(uart_name)
                if item is None:
                    continue
                item_status = str(item.get("source_status", "")).strip()
                if item_status and item_status != "active":
                    source_status = item_status
                    debug_raw_line = str(item.get("debug_raw_line", "")).strip()
                    debug_uart = str(item.get("source_uart", uart_name)).strip()
                    break
                if int(item.get("valid", 0)) != 1:
                    source_status = "active"
                    break
            idle = self._build_idle_observation(source_status)
            if debug_raw_line:
                idle["debug_raw_line"] = debug_raw_line
                idle["source_uart"] = debug_uart
            self.current_target = self._mark_target_state(
                idle,
                frame_now_ms,
                False,
            )
            return dict(self.current_target)

        self.current_target = dict(best_item)
        return dict(self.current_target)
