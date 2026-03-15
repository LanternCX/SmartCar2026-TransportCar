# OpenArt 与 RT1021 通信协议

## 1. 文档目的

本文档描述当前 OpenArt（vision 端）与 RT1021（车模主控端）之间已经落地的串口通信协议,重点分成两个模块:

1. 车模控制协议（遥控协议）
2. 车模与视觉端通信协议

其中,车模控制协议用于人工调试、脚本控制和兼容旧链路；视觉通信协议用于当前重构目标下的 OpenArt -> RT1021 视觉观测上报。

## 2. 共享传输约定

### 2.1 串口角色

| 链路 | OpenArt 侧 | RT1021 侧 | 推荐用途 |
| :--- | :--- | :--- | :--- |
| 主通信链路 | `UART(2)` | `UART6` | 视觉观测上报、兼容旧遥控命令、同口查询 |
| 调试链路 | 可不接 | `UART3` | 人工调试、日志输出、手工查询 |

说明:

- 当前 OpenArt 代码通过 `UART(2, baudrate=115200)` 与底盘通信。
- RT1021 侧 `UART6` 对应主通信链路,`UART3` 对应调试链路。
- 从实现上看,`UART3` 和 `UART6` 都能接收普通命令与查询；但为了避免语义混杂,推荐将 `UART6` 留给 vision 端,`UART3` 留给人工调试与全局日志观察。

### 2.2 传输格式

- 默认波特率: `115200`
- 文本编码: 以 ASCII 风格单行文本为主
- 分帧方式: 按行收发,建议每条消息以 `\r\n` 结束
- 命令格式: `key=value[,key=value...]`
- 查询格式: `?token`
- 查询响应: 默认回写到收到该查询的同一串口
- 运行时日志: 默认由 RT1021 通过 `UART3` 输出,用于持续诊断观察

补充约定:

- 大多数 `key` 与 `token` 在解析时会转成小写,因此通常可视为大小写不敏感；裸 `reset` 也接受大小写变体,但为避免歧义,仍建议统一发送 `reset=1`。
- 普通数值命令的 `value` 按浮点数解析。
- `print` 是特例,`value` 按原字符串透传,但由于命令行以逗号分割,`print` 内容不应再包含逗号。
- `log_profile`、`log_level`、`log_filter`、`log_modules`、`log_color` 这类运行时日志命令的 `value` 按原字符串透传。
- 未识别的查询会返回 `?unknown=<token>`。
- 查询响应与日志输出是两条职责分离的通道: 查询始终回写到收到该查询的同一串口；运行时日志仍按日志系统配置输出到 `UART3`。
- `UART3` 上的人工查询客户端可能看到额外调试输出,例如结构化运行时日志与 `print` 命令透传出的原始文本,因此它不是绝对纯净的查询专用串口。

### 2.3 坐标与方向约定

- 车体系 `y+` 表示前进方向（纵向）
- 车体系 `x+` 表示向右平移（横向）
- `w+` / `omega+` 表示顺时针旋转
- `x`、`y`、`angle` 在遥控协议中表示世界系目标
- `dx`、`dy`、`d_angle` 在遥控协议中表示车体系相对增量

注意: 视觉协议中也会出现 `x`、`y`,但它们表示图像平面像素坐标,不是世界坐标命令。两者的区分条件见第 4 节。

### 2.4 上电入口与车辆角色约定

- `boot.py` 的职责已拆分为两部分: `D8/D9` 只声明车辆角色, 按钮长按只决定启动脚本
- `D8=1,D9=0` 表示主车, `D8=0,D9=1` 表示辅车
- `D8/D9` 板级输入带上拉电阻, 因此读到 `1` 表示开关关闭(断开), 读到 `0` 表示开关闭合; 排障时必须区分“输入电平”和“物理开关状态”
- `D8/D9` 若为 `0/0` 或 `1/1`, 视为非法角色组合, 启动阶段应安全失败, 不进入任何业务脚本
- 上电长按按钮 1 进入 `script/pid_identify.py`
- 上电长按按钮 2 进入 `script/calibrate_gyro.py`
- 上电时未长按按钮则进入 `script/remote_control.py`, 且正常运行路径可读取 `VEHICLE_ROLE`

## 3. 模块 A：车模控制协议（遥控协议）

### 3.1 适用范围

本模块用于:

- 人工串口调试
- 上位机脚本控制
- 兼容旧版 OpenArt 主导式控制链路
- 查询底盘位置、锁状态和诊断快照

### 3.2 控制命令格式

单条命令可以只包含一个键,也可以聚合多个键,例如:

```text
vy=10
x=1.0,y=0.5,angle=45
rear=1,angle=-90
```

### 3.3 控制命令表

| 参数标签 | 含义 | 典型单位 | 类型 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `vx` | 车体系 X 方向速度目标 | 控制器速度单位 | 速度 | 锁定时忽略,内部限幅到 `V_CMD_MAX`；仅在没有挂起位置目标时直接生效 |
| `vy` | 车体系 Y 方向速度目标 | 控制器速度单位 | 速度 | 锁定时忽略,内部限幅到 `V_CMD_MAX`；仅在没有挂起位置目标时直接生效 |
| `omega` / `w` | 角速度目标 | 控制器角速度单位 | 速度 | 锁定时忽略,内部限幅到 `V_CMD_MAX`；仅在没有挂起绝对角目标时直接生效 |
| `x` | 世界系绝对 X 目标 | 米 | 位置 | 锁定时忽略；进入位置模式 |
| `y` | 世界系绝对 Y 目标 | 米 | 位置 | 锁定时忽略；进入位置模式 |
| `dx` | 车体系相对 X 位移 | 米 | 位置 | 锁定时忽略；由 RT1021 转成世界系绝对目标 |
| `dy` | 车体系相对 Y 位移 | 米 | 位置 | 锁定时忽略；由 RT1021 转成世界系绝对目标 |
| `angle` / `yaw` | 世界系绝对航向角目标 | 度 | 位置 | 锁定时忽略 |
| `d_angle` / `dyaw` / `da` | 相对航向角增量 | 度 | 位置 | 锁定时忽略；由 RT1021 叠加到当前目标角 |
| `rear` | 后轮动作修饰位 | 推荐 `0/1` | 模式 | 实现上 `0` 为关闭、非零为开启；常与锁定动作一起使用；解锁后会自动回到全向模式 |
| `reset` / `reset=1` | 运行态复位 | - | 系统 | 不受 `command_lock` 限制；清零里程计/姿态/锁与视觉状态,并重置 `last_cmd` |
| `print=<text>` | 调试打印 | 文本 | 系统 | 透传到 RT1021 的 `UART3` 输出 |

说明:

- 位置类命令与 `rear` 模式变更会触发 `command_lock`。
- 速度类命令不会触发 `command_lock`,适合持续遥控；但若旧的 `x/y/angle` 目标仍挂起,位置/角度控制仍会继续优先生效。
- `dx/dy/d_angle` 是“相对目标”,由 RT1021 在本地结合当前位姿换算后执行。
- `reset` 可以写成裸 `reset`（大小写均可）,也可以写成 `reset=1`。
- `rear=1` 更适合作为一次动作的修饰条件,而不是长期保持的全局模式；车辆解锁后会自动回到全向模式。
- `reset` 会清空 `last_cmd`、锁状态、暂存相对量和视觉状态,但当前实现并未在该命令里显式清除 `rear_only_mode` / `last_rear_mode` 字段。

### 3.4 运行时日志控制

全局日志系统用于在不改代码、不重启的前提下,动态调整 RT1021 的诊断输出强度与范围。其主要目标是:

- 在常规运行阶段保持较低噪声,避免调试输出干扰主链路观察
- 在排障阶段临时打开更细粒度日志,缩小问题模块范围
- 保持日志输出与查询应答职责分离: 日志负责持续观测,查询负责按需返回结构化快照

运行时日志控制命令如下:

| 参数标签 | 含义 | 典型取值 | 类型 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `log_profile` | 切换日志预设档位 | `run` / `diag` | 系统 | `run` 恢复常规运行档位；`diag` 切到调试档位 |
| `log_level` | 设置日志等级下限 | `trace` / `debug` / `info` / `warn` / `error` / `fatal` | 系统 | 低于当前等级的日志不会输出 |
| `log_filter` | 设置模块过滤模式 | `off` / `whitelist` / `blacklist` | 系统 | `off` 不按模块过滤；其余模式与 `log_modules` 联动 |
| `log_modules` | 设置模块过滤列表 | `vision|control.yaw` / `none` | 系统 | 使用 `|` 分隔多个模块前缀；`none` 或空白表示清空列表 |
| `log_color` | 设置 ANSI 颜色开关 | `0` / `1` | 系统 | `1` 开启颜色；`0` 关闭颜色 |
| `log_reset` | 恢复运行时日志默认配置 | 推荐 `1` | 系统 | 恢复 `RUN` 缺省档位、关闭颜色并清空模块过滤列表 |

说明:

- `log_profile=run` 当前对应 `level=info`、`filter=off`；`log_profile=diag` 当前对应 `level=debug`、`filter=off`。
- `log_level`、`log_profile` 的取值按文本 token 解析,推荐统一使用小写发送。
- 若已先设置 `log_profile`,后续手工执行 `log_level` 或 `log_filter` 且该调用实际改变了当前由预设档位派生的配置,则当前档位名会变为 `custom`；若手工调用未改变状态,则可保留原档位名。
- `log_modules` 按模块名前缀匹配,并遵循点号边界；例如 `vision` 会匹配 `vision.state`,但不会匹配 `vision2`。
- 当 `log_filter=whitelist` 时,只有命中的模块会输出；当 `log_filter=blacklist` 时,命中的模块会被抑制。
- `log_reset` 只恢复日志运行态配置,不等价于整车 `reset`。
- `print=<text>` 仍是原始文本透传接口,不参与日志等级、模块过滤或颜色格式化。

### 3.5 查询命令表

| 查询指令 | 返回格式 | 用途 | 备注 |
| :--- | :--- | :--- | :--- |
| `?pos` | `?pos=x,y,yaw` | 查询当前世界坐标与航向角 | 简洁返回 |
| `?lock` | `?lock=0/1` | 查询是否处于位置/模式锁定状态 | 简洁返回 |
| `?log` | `?log=profile:<p>,level:<l>,filter:<m>,color:<0/1>,modules:<list>` | 查询当前运行时日志配置 | `modules` 为空时返回 `none`,`profile` 可能为 `run` / `diag` / `custom` |
| `?vision` | `?vision=key:value,...` | 查询视觉观测与视觉目标摘要 | 结构化快照 |
| `?health` | `?health=key:value,...` | 查询系统健康摘要 | 结构化快照 |
| `?tick` | `?tick=key:value,...` | 查询控制周期统计 | 结构化快照 |
| `?imu` | `?imu=key:value,...` | 查询 IMU 状态 | 结构化快照 |
| `?enc` | `?enc=key:value,...` | 查询编码器观测 | 结构化快照 |
| `?motor` | `?motor=key:value,...` | 查询电机目标和占空比 | 结构化快照 |

结构化快照统一格式:

```text
?token=key:value,key:value,...
```

其中:

- 空值统一写成 `none`
- 文本字段中的换行会被清理为空格
- 文本字段中的逗号会被替换成分号,便于继续按逗号分隔解析
- `?log` 中的 `modules` 使用 `|` 分隔多个模块；若当前列表为空,固定返回 `none`

### 3.6 典型查询响应示例

```text
?pos=0.125,0.340,15.00
?lock=1
?log=profile:run,level:info,filter:off,color:0,modules:none
?vision=state:ALIGN_DX,obs_age_ms:100,obs_left:100.0,obs_top:20.0,obs_right:140.0,obs_bottom:90.0,obs_center_x:120.0,obs_center_y:55.0,target_x:0.2,target_y:0.4,target_angle:15.0
?health=alive:1,uptime_ms:1500,lock:1,rear:1,last_err:none,vision_state:ALIGN_DX
```

### 3.7 锁语义与互斥关系

- 当发送位置类命令（`x/y/angle/dx/dy/d_angle`）时,RT1021 会进入 `command_lock`
- 当切换 `rear` 模式且模式确实变化时,RT1021 也会进入 `command_lock`
- `command_lock=1` 期间,大多数普通控制命令会被忽略,直到动作完成或被 `reset` 打断
- 旧版 OpenArt 可以通过轮询 `?lock` 实现“先等空闲再发下一条”的同步控制
- 对 `rear=1` 这类仅改模式的短动作,`?lock` 的同步价值相对有限,更推荐把它与 `angle/x/y` 等锁定动作组合发送

### 3.8 典型控制示例

```text
# 速度控制：向前运动
vy=10

# 绝对位置：移动到世界坐标 (1.0, 0.5) 并转到 45 度
x=1.0,y=0.5,angle=45

# 相对位移：相对当前位置向前移动 0.3 m
dy=0.3

# 启用后轮模式并转到 -90 度
rear=1,angle=-90

# 复位
reset
```

## 4. 模块 B：车模与视觉端通信协议

### 4.1 设计目标

RT1021 端已经支持本节描述的视觉协议；它是后续 vision 端重构的目标接口,但当前 `main.py` 仍主要使用旧式“发控制命令 + 轮询 `?lock/?pos`”链路。

目标边界是:

- OpenArt 负责图像采集、目标检测和目标选择
- RT1021 负责视觉状态机、位置/姿态控制、推行与返回动作
- OpenArt 不再需要在每一帧里主动发 `dx/dy/d_angle` 或反复等待 `?lock`

换句话说,视觉协议传的是“观测”,不是“动作”。

### 4.2 视觉查询/响应方向

- 主方向: `RT1021 -> OpenArt`, 由主车主动查询某个相机当前缓存帧
- 物理链路: OpenArt `UART(2)` <-> RT1021 `UART6`
- `camera_id` 只表示物理相机身份, 不表示职责相机
- `category` 只表示检测类别, 可在不同物理相机上重复出现
- 单次查询只点名一个相机, 被点名相机立即返回当前缓存帧结果
- 未被点名相机在共享视觉 UART 上必须严格静默
- 单次查询响应允许返回 `0..N` 条检测消息, 并必须带显式结束标记

### 4.3 查询格式与多检测响应格式

主车查询当前某个相机的缓存帧时, 发送:

```text
?frame=<camera_id>
```

例如:

```text
?frame=cam_a
?frame=cam_b
```

约束:

1. 单次查询只允许点名一个 `camera_id`
2. 只有被点名相机会响应, 未被点名相机必须保持静默
3. 响应中的所有检测消息都属于同一次查询的同一帧
4. 无论该帧返回 `0` 条还是多条检测, 最后一条都必须是显式 `frame_end` 标记

检测消息格式:

```text
camera_id=<camera_id>,frame_id=<frame_id>,category=<category>,left=<l>,top=<t>,right=<r>,bottom=<b>
```

帧结束标记格式:

```text
camera_id=<camera_id>,frame_id=<frame_id>,frame_end=1
```

字段语义:

| 字段 | 含义 | 单位 | 说明 |
| :--- | :--- | :--- | :--- |
| `camera_id` | 物理相机标识 | 文本 | 例如 `cam_a`、`cam_b`, 不表示职责 |
| `frame_id` | 相机本地帧标识 | 文本或整数文本 | 同一次查询返回的多条检测必须一致 |
| `category` | 检测类别 | 文本 | 例如 `cargo`、`follower`、`obstacle`, 可跨相机重复 |
| `left` | 识别框左边界 | 像素 | 相对图像左边界定义 |
| `top` | 识别框上边界 | 像素 | 相对图像上边界定义 |
| `right` | 识别框右边界 | 像素 | 必须大于 `left` |
| `bottom` | 识别框下边界 | 像素 | 必须大于 `top` |
| `frame_end` | 当前帧响应结束标记 | 推荐 `1` | 不带 bbox, 仅用于声明本批次结束 |

合法示例:

```text
?frame=cam_a
camera_id=cam_a,frame_id=12,category=cargo,left=100,top=20,right=140,bottom=90
camera_id=cam_a,frame_id=12,category=follower,left=150,top=25,right=190,bottom=95
camera_id=cam_a,frame_id=12,frame_end=1

?frame=cam_b
camera_id=cam_b,frame_id=33,category=cargo,left=120,top=18,right=170,bottom=110
camera_id=cam_b,frame_id=33,category=obstacle,left=20,top=30,right=80,bottom=140
camera_id=cam_b,frame_id=33,frame_end=1
```

空结果示例:

```text
?frame=cam_a
camera_id=cam_a,frame_id=13,frame_end=1
```

补充说明:

- 当前 OpenArt 在发送前已启用 `set_vflip(True)` 与 `set_hmirror(True)`; 因此 RT1021 收到的 `left,top,right,bottom` 已经是翻转后画面的像素坐标, 主控侧不应再次做上下或左右翻转。
- `center_x`、`center_y`、`width`、`height` 由 RT1021 在本地从识别框派生, 不需要由视觉端重复发送。
- `category` 当前只作为协议字段保留, 主车如何消费多类结果由后续任务决定。
- 为兼容旧单框状态机, RT1021 当前仍保留“提交后取该帧最后一条检测作为最新观测”的兼容入口, 但新的协议主语义已经升级为“同一帧检测集合”。

### 4.4 不会被当作有效视觉响应的情况

以下消息会被视觉协议保留并吞掉, 但不会形成有效观测或有效帧结果:

- 来源不是 `UART6`
- 旧 `x,y` 载荷或不完整 bbox 载荷
- 多检测消息缺少 `camera_id`、`frame_id` 或 `category`
- 同一条消息出现重复键
- `right <= left` 或 `bottom <= top`
- 同一批次内 `camera_id` / `frame_id` 发生跳变
- 缺少显式 `frame_end` 标记
- `frame_end` 与当前缓存批次的 `camera_id` / `frame_id` 不匹配
- 任一数值字段不是数字

其中, 若某个尚未 `frame_end` 的批次中途出现 `camera_id` 或 `frame_id` 跳变, 则跳变后对应的整批消息会被视为失效批次; 直到后续出现一个新的干净批次前, 该失效批次的后续检测与 `frame_end` 都不会被提交为有效帧。

重要兼容规则:

> `UART6` 上凡是包含视觉字段名 `x/y/left/top/right/bottom/camera_id/frame_id/category/frame_end` 的消息, 都会先被视觉协议截获。只有合法单框兼容包或带显式 `frame_end` 的合法多检测批次会更新缓存；旧 `x,y`、不完整框或未结束批次会被直接丢弃, 不再回落到遥控协议。

例如:

```text
x=120,y=80,angle=0
```

在 `UART6` 上会被视为冲突视觉载荷并直接丢弃,不会再被当成绝对位置/角度控制命令执行。

再例如:

```text
x=1,y=bad
```

这条消息会被视为旧视觉载荷并直接丢弃。因此 vision 端应保证视觉帧始终升级到完整框格式。

### 4.5 RT1021 对视觉帧的消费规则

- RT1021 当前同时保留两个兼容视图: `latest_frame` 表示最近一帧已结束的检测集合, `latest_observation` 表示兼容旧状态机的最近单条观测
- 只有收到显式 `frame_end` 后, 当前批次才会被提交为可消费帧
- 若某帧 `0` 条检测, 也必须在收到 `frame_end` 后提交为空帧, 此时 `latest_observation` 保持为空
- 若观测超过 `VISION_OBSERVATION_TIMEOUT_MS` 未更新, 则视为目标丢失
- 视觉观测被消费后, RT1021 会先在本地派生 `center_x`、`center_y`、`bottom` 等几何量, 再驱动状态机生成连续控制意图并换算为当前位置/角度目标
- Task 3 阶段先升级协议和 ingress 边界, 暂不在运行时引入真正的双摄轮询调度和批次选择缓存
- 若此时外部离散命令已进入 `command_lock`, RT1021 会清空当前视觉缓存并重置视觉状态机, 避免控制权冲突

### 4.6 视觉状态诊断接口

虽然视觉上报本身没有逐帧 ACK,但可以通过 `?vision` 查询 RT1021 当前已经接收到和解析出的视觉状态。

当前 `?vision` 快照字段如下:

| 字段 | 含义 |
| :--- | :--- |
| `state` | 视觉状态机状态名 |
| `obs_age_ms` | 最近视觉观测距今的时间 |
| `obs_left` | 最近观测到的识别框左边界 |
| `obs_top` | 最近观测到的识别框上边界 |
| `obs_right` | 最近观测到的识别框右边界 |
| `obs_bottom` | 最近观测到的识别框下边界 |
| `obs_center_x` | 由识别框派生出的横向中心 |
| `obs_center_y` | 由识别框派生出的纵向中心 |
| `target_x` | RT1021 当前解析出的世界系目标 `x` |
| `target_y` | RT1021 当前解析出的世界系目标 `y` |
| `target_angle` | RT1021 当前解析出的目标航向角 |

当前状态名可能包括:

```text
IDLE
ALIGN_ANGLE
ALIGN_DIST
ALIGN_DX
ORBITING
PUSHING
RETURNING
DONE
```

### 4.7 推荐交互方式

下面的交互方式是当前重构目标。

推荐的交互方式如下:

1. 初始化阶段可按需发送一次 `reset`
2. 主车通过 `?frame=<camera_id>` 查询单个相机当前缓存帧
3. 被点名相机立即返回 `0..N` 条检测消息, 最后追加 `frame_end`
4. 不要让未被点名相机自由持续发包
5. 如需调试当前联动状态, 按需查询 `?vision`、`?lock`、`?pos`

一个最小示例:

```text
reset
?frame=cam_a
camera_id=cam_a,frame_id=12,category=cargo,left=145,top=20,right=175,bottom=240
camera_id=cam_a,frame_id=12,frame_end=1
?vision
```

## 5. 兼容与迁移说明

### 5.1 同名字段的语义区分

这是本协议最重要的兼容规则:

| 条件 | 消息语义 |
| :--- | :--- |
| 来自 `UART6`, 且为 `?frame=<camera_id>` | 保留给视觉协议的单相机帧查询 |
| 来自 `UART6`, 且整行消息恰好只有 `left/top/right/bottom` 四个键 | 旧单框兼容观测 |
| 来自 `UART6`, 且消息含 `camera_id/frame_id/category` 与 bbox | 多检测帧中的单条检测 |
| 来自 `UART6`, 且消息含 `camera_id/frame_id/frame_end` | 当前查询批次结束标记 |
| 来自 `UART6`, 且包含视觉字段但不满足上述合法条件 | 废弃, 冲突或不完整视觉载荷, 会被丢弃 |
| 其他情况（例如来自 `UART3`, 或为 `vx/angle/rear` 等控制键） | 遥控协议中的控制命令 |

因此:

- `UART6: ?frame=cam_a` -> 视觉查询, 不进入普通 query 路由
- `UART6: left=100,top=20,right=140,bottom=90` -> 旧单框兼容观测
- `UART6: camera_id=cam_a,frame_id=12,category=cargo,left=100,top=20,right=140,bottom=90` -> 当前帧中的单条检测
- `UART6: camera_id=cam_a,frame_id=12,frame_end=1` -> 当前帧结束
- `UART6: x=120,y=80` -> 旧视觉载荷,会被忽略
- `UART3: x=120,y=80` -> 绝对位置命令
- `UART6: vx=1` -> 速度命令

### 5.2 对旧 OpenArt 代码的兼容

旧版 OpenArt 控制逻辑中常见的做法包括:

- 发送 `dx/dy/d_angle`
- 发送 `rear=1,angle=...`
- 查询 `?pos`
- 轮询 `?lock`
- 通过 `send_cmd_sync()` 实现“发一条、等完成、再发下一条”

RT1021 当前仍兼容这些命令与查询, 但旧 OpenArt 若继续通过 `UART6` 发送 `x,y`, 将不会再驱动视觉状态机。新的视觉端应升级到“单次查询, 多条检测响应, 显式 frame_end”的协议。

### 5.3 对新 vision 重构的建议

新的重构方向建议收敛为:

- OpenArt: 负责感知与目标选择
- RT1021: 负责状态机、控制与动作编排
- OpenArt 与 RT1021 之间的常态交互: `?frame=<camera_id>` / `camera_id,frame_id,category,bbox...` / `frame_end` + `按需查询诊断`

这意味着 OpenArt 端可以逐步删除:

- 每帧 `send_cmd_sync()`
- 每阶段主动 `?lock` 等待
- 每阶段主动 `?pos` 回读再做状态机跳转

保留这些接口只作为兼容与排障手段,而不是新的主控制链路。
