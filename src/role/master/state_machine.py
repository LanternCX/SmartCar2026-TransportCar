"""主车单车状态机

@file src/role/master/state_machine.py
"""

from config import motion as motion_params
from role.clear_phase import CLEAR_PHASE_FORWARD, CLEAR_PHASE_NONE, CLEAR_PHASE_RETREAT
from role.task_sync import (
    pack_assistant_orbit_arg,
    pack_task_arg,
    unpack_assistant_orbit_offset_deg,
)
from role.transport_plan import (
    heading_with_offset,
    plan_transport_heading,
    push_heading_for_edge,
    target_edge_for_object,
)
from utils.startup_log import log

try:
    from micropython import const  # pyright: ignore[reportMissingImports]
except ImportError:

    def const(value):
        return value


ASSISTANT_FOLLOW_SYNC_STATE = const(1)
ASSISTANT_FOLLOW_SYNC_TARGET = const(0)
ASSISTANT_OBJECT_SYNC_STATE = const(2)
ASSISTANT_OBJECT_SYNC_TARGET = const(1)
ASSISTANT_ORBIT_SYNC_STATE = const(3)
ASSISTANT_ORBIT_SYNC_TARGET = const(1)
ASSISTANT_TRANSPORT_SYNC_STATE = const(4)
ASSISTANT_TRANSPORT_SYNC_TARGET = const(1)
ASSISTANT_CLEAR_SYNC_STATE = const(5)
ASSISTANT_CLEAR_SYNC_TARGET = const(1)
ASSISTANT_RETURN_FOLLOW_SYNC_STATE = const(6)
ASSISTANT_RETURN_FOLLOW_SYNC_TARGET = const(0)
ASSISTANT_FINISHED_SYNC_STATE = const(7)
ASSISTANT_FINISHED_SYNC_TARGET = const(0)
ASSISTANT_STARTUP_SYNC_STATE = const(8)
ASSISTANT_STARTUP_SYNC_TARGET = const(0)

# 主车全局状态编号
STATE_IDLE = const(0)
STATE_SEARCH_OBJECT = const(1)
STATE_ORBITING = const(2)
# STATE_STOP: 暂不启用，详细原因见 docs/developer/vision.md。
STATE_STOP = const(3)
STATE_TRANSPORT_OBJECT = const(4)
STATE_CLEAR_OBJECT = const(5)
STATE_RETURN_GARAGE_RETREAT = const(6)
STATE_FINISHED = const(7)
STATE_STARTUP_MOVE = const(8)
STATE_STARTUP_SYNC = const(9)
_STATE_NAMES = (
    "IDLE",
    "SEARCH_OBJECT",
    "ORBITING",
    "STOP",
    "TRANSPORT_OBJECT",
    "CLEAR_OBJECT",
    "RETURN_GARAGE_RETREAT",
    "FINISHED",
    "STARTUP_MOVE",
    "STARTUP_SYNC",
)

# 主车目标编号
TARGET_NONE = const(0)
TARGET_OBJECT = const(1)

# 主车视觉事件编号
EVENT_TARGET_FOUND = const(6)
EVENT_ALIGNED = const(7)
EVENT_ARRIVED = const(8)
EVENT_CLEARED = const(9)
EVENT_ORBIT_FINISHED = const(10)

_CLEAR_STAGE_TURN_BACK = const(3)

_ORBIT_PHASE_NORMAL = const(0)
_ORBIT_PHASE_AVOID = const(1)
_ORBIT_PHASE_WAIT_RETURN = const(2)
_ORBIT_PHASE_PUSH = const(3)
_ORBIT_PHASE_RETURN = const(4)

RK_NONE = const(0)
RK_A_START = const(1)
RK_A_OBJ = const(2)
RK_A_ORBIT = const(3)
RK_A_FOLLOW = const(4)
RK_A_TRANSPORT = const(5)
RK_A_CLEAR = const(6)
RK_A_RETURN = const(7)
RK_T_TRANSPORT = const(8)
RK_T_ORBIT = const(9)
RK_A_FINISHED = const(10)
RK_A_REALIGN = const(11)

RQ_KIND = const(0)
RQ_CONTEXT = const(1)
RQ_STATE = const(2)
RQ_TARGET = const(3)
RQ_ARG = const(4)


class MasterStateMachine:
    """维护主车单车寻找、搬运与回身状态"""

    def __init__(
        self,
        search_task_arg,
        boot_heading_deg,
        obstacle_slots,
        obstacle_margin_m,
        orbit_avoid_trigger_deg,
        orbit_avoid_heading_deg,
        orbit_avoid_push_distance_m=0.0,
        assistant_object_arg=1,
        assistant_transport_arg=1,
        transport_task_arg=2,
        total_object_count=999,
        initial_context_id=0,
    ):
        self.state = STATE_IDLE
        _ = boot_heading_deg
        # 主运行链使用短字段降低 qstr 常驻压力；字段按参数、pending、回合状态分组。
        # *_arg 是下发给视觉或辅车的配置编号；obj/ctx 分别表示物体进度和同步上下文。
        self._s_arg = int(search_task_arg)
        self._a_obj_arg = int(assistant_object_arg)
        self._a_tr_arg = int(assistant_transport_arg)
        self._tr_task_arg = int(transport_task_arg)
        self._obj_need = int(total_object_count)
        self._obstacles = tuple(obstacle_slots)
        self._path_margin = float(obstacle_margin_m)
        self._av_tr = float(orbit_avoid_trigger_deg)
        self._av_hd = float(orbit_avoid_heading_deg)
        self._av_push = float(orbit_avoid_push_distance_m)
        self._push_heading = None
        self._orbit_arg = 0
        self._orb_phase = _ORBIT_PHASE_NORMAL
        # 主车目标朝向已在控制容差内时直接进入二次对正
        self._orb_skip = False
        self.obj_done = 0
        self._ctx = int(initial_context_id) % 256
        # _p_task: 本车视觉 task；_p_ast: 辅车同步；_p_orbit: 本车绕行动作。
        self._p_task = None
        self._p_ast = None
        self._p_orbit = None
        self._p_push = None
        # 单轮任务标记：search/orbit 表示阶段完成度，wait/req 表示未确认请求。
        self._search_on = False
        self._orbit_done = False
        self._wait_obj_ack = False
        self._wait_fol_ack = False
        self._wait_task_ack = False
        self._obj_req = False
        self._obj_pending = False
        self._orbit_req = False
        self._tr_req = False
        # 对齐和清障标记按主车 m 与辅车 a 拆分，避免用字符串键保存角色状态。
        self._m_aligned = False
        self._a_aligned = False
        # 初赛并行绕行时保留辅车提前完成结果, 等主车让位完成后继续
        self._a_orbit_done = False
        self._tr_ready = False
        self._clr_phase = CLEAR_PHASE_NONE
        self._m_clear = False
        self._a_clear = False
        self._obj_id = 0
        self._edge = None
        self._prelim_final = False

    def _enter_state(self, state):
        """进入主车全局状态并输出一次跳转日志"""

        state = int(state)
        if self.state == state:
            return
        self.state = state
        log("master_state", _STATE_NAMES[state])

    def step(self, orbit_finished):
        """推进单拍状态机"""

        if not self._search_on and self.state == STATE_IDLE:
            self._search_on = True
            self._enter_state(STATE_STARTUP_SYNC)
            self._p_ast = (
                RK_A_START,
                0,
                ASSISTANT_STARTUP_SYNC_STATE,
                ASSISTANT_STARTUP_SYNC_TARGET,
                0,
            )
            return

        if self.state == STATE_ORBITING and orbit_finished:
            if self._orb_phase == _ORBIT_PHASE_AVOID:
                self._orb_phase = _ORBIT_PHASE_WAIT_RETURN
                if self._obj_pending:
                    self._queue_assistant_orbit()
                if self._a_orbit_done:
                    self._orb_phase = _ORBIT_PHASE_PUSH
                    self._p_push = self._av_push
                return
            self._enter_realign()

    def _enter_realign(self):
        """进入主辅车二次对正阶段"""

        self._enter_state(STATE_SEARCH_OBJECT)
        self._orbit_done = True
        self._m_aligned = False
        self._orb_phase = _ORBIT_PHASE_NORMAL
        self._ctx = (self._ctx + 1) % 256
        self._p_task = (
            RK_NONE,
            self._ctx,
            STATE_SEARCH_OBJECT,
            TARGET_OBJECT,
            self._tr_task_arg,
        )
        if self._obj_pending and not self._orbit_req:
            if self._orb_skip:
                self._queue_assistant_realign()
            else:
                self._queue_assistant_orbit()

    def mark_startup_move_completed(self):
        """标记启动动作完成并进入找物体状态"""

        if self.state != STATE_STARTUP_MOVE:
            return
        self._enter_search_with_task(self._s_arg)

    def mark_startup_sync_acknowledged(self):
        """标记辅车启动同步已确认并进入启动动作状态"""

        if self.state != STATE_STARTUP_SYNC:
            return
        self._enter_state(STATE_STARTUP_MOVE)

    def handle_event(self, context_id, event, value):
        """消费视觉事件"""

        if int(context_id) != self._ctx:
            return
        event = int(event)
        if self.state == STATE_SEARCH_OBJECT:
            if (
                self._wait_obj_ack
                or self._wait_fol_ack
                or self._wait_task_ack
            ):
                return
            if event == EVENT_TARGET_FOUND:
                if self._orbit_done:
                    return
                self._obj_id = int(value) & 0xFF
                final_object = self.obj_done + 1 >= self._obj_need
                self._prelim_final = bool(
                    not motion_params.IS_FINAL_ROUND and final_object
                )
                self._edge = target_edge_for_object(
                    self._obj_id,
                    final_object=final_object,
                )
                self._wait_obj_ack = True
                self._obj_req = True
                self._p_ast = (
                    RK_A_OBJ,
                    0,
                    ASSISTANT_OBJECT_SYNC_STATE,
                    ASSISTANT_OBJECT_SYNC_TARGET,
                    pack_task_arg(
                        self._a_obj_arg,
                        self._obj_id,
                        self._prelim_final,
                    ),
                )
                return
            if event == EVENT_ALIGNED:
                if not self._orbit_done:
                    return
                self._m_aligned = True
                self._try_enter_transport()
            return
        if self.state == STATE_TRANSPORT_OBJECT:
            if event != EVENT_ARRIVED:
                return
            self._enter_state(STATE_CLEAR_OBJECT)
            self._enter_clear_phase(CLEAR_PHASE_RETREAT)
            return
        if self.state == STATE_CLEAR_OBJECT:
            return
        if self.state == STATE_RETURN_GARAGE_RETREAT:
            return

    def mark_assistant_object_acknowledged(
        self,
        position_x,
        position_y,
        heading_deg,
    ):
        """按主车当前世界位姿确定绕行或直接对正"""

        if self._wait_obj_ack:
            self._wait_obj_ack = False
            self._ctx = (self._ctx + 1) % 256
            push_heading = push_heading_for_edge(self._edge)
            planned_heading = plan_transport_heading(
                self._edge,
                position_x,
                position_y,
                self._obstacles,
                self._path_margin,
            )
            offset_deg = heading_with_offset(planned_heading, -push_heading)
            self._orbit_arg = pack_assistant_orbit_arg(
                offset_deg,
                self._obj_id,
                preliminary_final=self._prelim_final,
            )
            offset_deg = unpack_assistant_orbit_offset_deg(self._orbit_arg)
            self._push_heading = heading_with_offset(push_heading, offset_deg)
            orbit_delta_deg = heading_with_offset(
                self._push_heading,
                -float(heading_deg),
            )
            self._m_aligned = False
            self._a_aligned = False
            self._orb_skip = abs(orbit_delta_deg) <= float(
                motion_params.ANGLE_TOLERANCE
            )
            if self._orb_skip:
                self._enter_realign()
                return
            self._enter_state(STATE_ORBITING)
            assistant_orbit_direction = 0
            if abs(orbit_delta_deg) < self._av_tr:
                self._orb_phase = _ORBIT_PHASE_AVOID
                avoid_offset = self._av_hd
                if orbit_delta_deg < 0:
                    avoid_offset = -avoid_offset
                assistant_orbit_direction = -1 if avoid_offset > 0 else 1
                self._p_orbit = heading_with_offset(push_heading, avoid_offset)
            else:
                self._orb_phase = _ORBIT_PHASE_NORMAL
                self._p_orbit = self._push_heading
            self._orbit_arg = pack_assistant_orbit_arg(
                offset_deg,
                self._obj_id,
                assistant_orbit_direction,
                self._prelim_final,
            )

    def handle_assistant_target_found(self, value):
        """消费辅车目标命中回报"""

        _ = value
        if self.state == STATE_ORBITING:
            if self._obj_req and not self._orbit_req:
                if (
                    not motion_params.IS_FINAL_ROUND
                    or self._orb_phase == _ORBIT_PHASE_WAIT_RETURN
                ):
                    self._queue_assistant_orbit()
                else:
                    self._obj_pending = True
            return
        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._obj_req:
            return
        if self._orbit_req:
            return
        if self._orb_skip:
            self._queue_assistant_realign()
        else:
            self._queue_assistant_orbit()

    def _queue_assistant_orbit(self):
        """下发一次辅车绕行同步请求"""

        self._obj_pending = False
        self._orbit_req = True
        self._p_ast = (
            RK_A_ORBIT,
            0,
            ASSISTANT_ORBIT_SYNC_STATE,
            ASSISTANT_ORBIT_SYNC_TARGET,
            self._orbit_arg,
        )

    def _queue_assistant_realign(self):
        """下发一次辅车二次对正同步请求"""

        self._obj_pending = False
        self._orbit_req = True
        self._p_ast = (
            RK_A_REALIGN,
            0,
            ASSISTANT_OBJECT_SYNC_STATE,
            ASSISTANT_OBJECT_SYNC_TARGET,
            pack_task_arg(
                self._a_tr_arg,
                self._obj_id,
                self._prelim_final,
            ),
        )

    def handle_assistant_orbit_finished(self, value):
        """记录辅车进入二次对正, 并在主车让位完成后启动侧推"""

        _ = value
        if self.state != STATE_ORBITING:
            return
        if self._orb_phase == _ORBIT_PHASE_AVOID and self._orbit_req:
            self._a_orbit_done = True
            return
        if self._orb_phase != _ORBIT_PHASE_WAIT_RETURN:
            return
        if not self._orbit_req:
            return
        self._orb_phase = _ORBIT_PHASE_PUSH
        self._p_push = self._av_push

    def mark_avoid_push_completed(self):
        """主车完成侧推后返回正式推行朝向"""

        if self.state != STATE_ORBITING:
            return
        if self._orb_phase != _ORBIT_PHASE_PUSH:
            return
        self._orb_phase = _ORBIT_PHASE_RETURN
        self._p_orbit = self._push_heading
        self._queue_assistant_realign()

    def handle_assistant_aligned(self, value):
        """消费辅车二次对正完成回报"""

        _ = value
        if self.state == STATE_ORBITING:
            if self._orb_phase == _ORBIT_PHASE_RETURN and self._orbit_req:
                self._a_aligned = True
            elif (
                not motion_params.IS_FINAL_ROUND
                and self._orb_phase == _ORBIT_PHASE_NORMAL
                and self._orbit_req
            ):
                self._a_aligned = True
            return
        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._orbit_req:
            return
        self._a_aligned = True
        self._try_enter_transport()

    def _try_enter_transport(self):
        """在两侧都完成对正后切入搬运态"""

        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._orbit_done:
            return
        if not self._orbit_req:
            return
        if not self._m_aligned or not self._a_aligned:
            return
        if self._tr_req:
            return
        self._tr_req = True
        self._p_ast = (
            RK_A_TRANSPORT,
            0,
            ASSISTANT_TRANSPORT_SYNC_STATE,
            ASSISTANT_TRANSPORT_SYNC_TARGET,
            pack_task_arg(
                self._a_tr_arg,
                self._obj_id,
                self._prelim_final,
            ),
        )

    def mark_transport_ready(self):
        """在运行时完成搬运入口同步后切入搬运态"""

        if self.state != STATE_SEARCH_OBJECT:
            return
        if not self._tr_req:
            return
        if not self._m_aligned or not self._a_aligned:
            return
        self._tr_ready = True
        self._enter_state(STATE_TRANSPORT_OBJECT)
        self._ctx = (self._ctx + 1) % 256

    def mark_master_cleared(self):
        """标记主车已完成搬运收尾当前段位置动作"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if self._clr_phase not in (
            CLEAR_PHASE_RETREAT,
            CLEAR_PHASE_FORWARD,
        ):
            return
        self._m_clear = True
        self._try_advance_clear_phase()

    def handle_assistant_cleared(self, value):
        """消费辅车搬运后脱离完成回报"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if int(value) != int(self._clr_phase):
            return
        self._a_clear = True
        self._try_advance_clear_phase()

    def _try_advance_clear_phase(self):
        """在当前收尾阶段完成后推进到下一阶段"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if not self._m_clear or not self._a_clear:
            return
        if self._clr_phase == CLEAR_PHASE_RETREAT:
            if self.obj_done + 1 >= self._obj_need:
                self.obj_done += 1
                self._p_ast = (
                    RK_A_RETURN,
                    0,
                    ASSISTANT_RETURN_FOLLOW_SYNC_STATE,
                    ASSISTANT_RETURN_FOLLOW_SYNC_TARGET,
                    int(self._prelim_final),
                )
                self._enter_return_retreat()
                return
            self._clr_phase = _CLEAR_STAGE_TURN_BACK
            self._m_clear = False
            self._a_clear = False
            return
        if self._clr_phase == CLEAR_PHASE_FORWARD:
            self._restart_search_after_clear()

    def can_start_turn_back_rotation(self):
        """判断回身阶段是否已经满足开始旋转条件"""

        return self.state == STATE_CLEAR_OBJECT and self._clr_phase == _CLEAR_STAGE_TURN_BACK

    def mark_turn_back_completed(self):
        """标记主车回身完成并推进下一阶段"""

        if self.state != STATE_CLEAR_OBJECT:
            return
        if self._clr_phase != _CLEAR_STAGE_TURN_BACK:
            return
        if self.obj_done + 1 >= self._obj_need:
            self.obj_done += 1
            self._enter_return_retreat()
            return
        self._enter_clear_phase(CLEAR_PHASE_FORWARD)

    def _restart_search_after_clear(self):
        """在搬运收尾完成后重启寻找阶段"""

        self.obj_done += 1
        if self.obj_done >= self._obj_need:
            self._enter_return_retreat()
            return
        self._orbit_done = False
        self._wait_obj_ack = False
        self._wait_fol_ack = True
        self._wait_task_ack = True
        self._obj_req = False
        self._obj_pending = False
        self._orbit_req = False
        self._tr_req = False
        self._m_aligned = False
        self._a_aligned = False
        self._a_orbit_done = False
        self._tr_ready = False
        self._clr_phase = CLEAR_PHASE_NONE
        self._m_clear = False
        self._a_clear = False
        self._obj_id = 0
        self._edge = None
        self._prelim_final = False
        self._push_heading = None
        self._orbit_arg = 0
        self._orb_phase = _ORBIT_PHASE_NORMAL
        self._orb_skip = False
        self._p_push = None
        self._enter_state(STATE_SEARCH_OBJECT)
        self._enter_search_with_task(self._s_arg)
        self._p_ast = (
            RK_A_FOLLOW,
            0,
            ASSISTANT_FOLLOW_SYNC_STATE,
            ASSISTANT_FOLLOW_SYNC_TARGET,
            0,
        )

    def _reset_round_flags(self):
        """清理单轮找物体、搬运和收尾阶段标记"""

        self._orbit_done = False
        self._wait_obj_ack = False
        self._wait_fol_ack = False
        self._wait_task_ack = False
        self._obj_req = False
        self._obj_pending = False
        self._orbit_req = False
        self._tr_req = False
        self._m_aligned = False
        self._a_aligned = False
        self._a_orbit_done = False
        self._tr_ready = False
        self._clr_phase = CLEAR_PHASE_NONE
        self._m_clear = False
        self._a_clear = False
        self._obj_id = 0
        self._edge = None
        self._push_heading = None
        self._orbit_arg = 0
        self._orb_phase = _ORBIT_PHASE_NORMAL
        self._orb_skip = False
        self._p_push = None

    def _enter_return_retreat(self):
        """进入主车回库动作"""

        self._reset_round_flags()
        self._enter_state(STATE_RETURN_GARAGE_RETREAT)

    def _enter_finished(self):
        """进入全部任务完成态"""

        self._enter_state(STATE_FINISHED)

    def mark_assistant_follow_acknowledged(self):
        """标记辅车 follow 同步已确认"""

        self._wait_fol_ack = False

    def mark_restart_search_task_acknowledged(self):
        """标记回身后主车本车视觉搜索 task 已确认"""

        self._wait_task_ack = False

    def is_post_clear_turn_back_pending(self):
        """当前是否处于收尾阶段中的主车转身段"""

        return self.state == STATE_CLEAR_OBJECT and self._clr_phase == _CLEAR_STAGE_TURN_BACK

    def get_clear_phase(self):
        """返回当前搬运收尾阶段编号"""

        return self._clr_phase

    def get_push_heading_deg(self):
        """返回当前物体目标边对应的推动朝向."""

        if self._push_heading is not None:
            return self._push_heading
        return push_heading_for_edge(self._edge)

    def get_target_edge(self):
        """返回当前轮次物体目标边"""

        if self._edge is None:
            raise ValueError
        return self._edge

    def uses_preliminary_fast_return(self):
        """当前回库是否使用预赛最后一轮快速路径"""

        return bool(self._prelim_final)

    def _enter_clear_phase(self, clear_phase):
        """进入指定的搬运收尾阶段并按需同步辅车"""

        self._clr_phase = int(clear_phase)
        self._m_clear = False
        self._a_clear = False
        self._p_ast = (
            RK_A_CLEAR,
            0,
            ASSISTANT_CLEAR_SYNC_STATE,
            ASSISTANT_CLEAR_SYNC_TARGET,
            int(clear_phase),
        )

    def _enter_search_with_task(self, task_arg):
        """创建新一轮主车找物体 task 上下文"""

        self._enter_state(STATE_SEARCH_OBJECT)
        self._ctx = (self._ctx + 1) % 256
        self._p_task = (
            RK_NONE,
            self._ctx,
            STATE_SEARCH_OBJECT,
            TARGET_OBJECT,
            int(task_arg),
        )

    def poll_task_request(self):
        """取出一次性 task 请求"""

        pending = self._p_task
        self._p_task = None
        return pending

    def poll_assistant_request(self):
        """取出一次性辅车状态同步请求"""

        pending = self._p_ast
        self._p_ast = None
        return pending

    def poll_orbit_command(self):
        """取出一次性绕行命令"""

        pending = self._p_orbit
        self._p_orbit = None
        return pending

    def poll_avoid_push_command(self):
        """取出一次性避让侧推距离"""

        pending = self._p_push
        self._p_push = None
        return pending

    def is_waiting_assistant_object_ack(self):
        """当前是否正在等待辅车找物体同步确认"""

        return self._wait_obj_ack

    def allows_search_velocity(self):
        """当前状态是否允许主车视觉搜索速度生效"""

        if self.state != STATE_SEARCH_OBJECT:
            return False
        if self._wait_obj_ack:
            return False
        if self._wait_fol_ack:
            return False
        if self._wait_task_ack:
            return False
        if self._m_aligned:
            return False
        if self._tr_req and not self._tr_ready:
            return False
        return True

    def allows_assistant_velocity_forward(self):
        """当前状态是否允许向辅车转发速度前馈"""

        return self.allows_search_velocity()

    def needs_assistant_report_turn(self):
        """当前是否需要给辅车可靠回报保留 UART8 回话窗口"""

        if self.state != STATE_SEARCH_OBJECT:
            return False
        if not self._orbit_done:
            return False
        if not self._obj_req:
            return False
        if self._tr_req:
            return False
        return not self._a_aligned
