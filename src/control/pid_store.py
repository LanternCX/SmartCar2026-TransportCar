"""@file pid_store.py
@brief PID 参数与系统辨识参数的持久化工具

提供 PID 参数(增益和辨识参数)的保存和加载功能, 支持跨运行的参数恢复
"""
import io


def save_pid_params(path, states, hardness):
    """@brief 保存 PID 参数到文件

    将所有轮子的系统增益、时间常数、PID 增益以及调谐硬度级别写入文件,
    格式为文本行, 便于手动编辑和审查

    @details
    文件格式:
    ```
    hardness <级别>
    <轮子名> <增益> <时间常数> <kp> <ki>
    <其余轮子参数行>
    ```
    浮点数默认保留 6 位小数, 使用空格分隔

    @param path 文件路径, 若文件已存在则覆盖
    @param states 轮子状态列表, 每个状态字典应包含 "name"、"id_gain"、"id_tau"、"kp"、"ki" 字段
    @param hardness 调谐硬度级别字符串, 如 "soft"、"hard" 等
    """
    f = io.open(path, "w")
    try:
        f.write("hardness %s\n" % hardness)
        for state in states:
            gain = state.get("id_gain") or 0.0
            tau = state.get("id_tau") or 0.0
            kp = state.get("kp") or 0.0
            ki = state.get("ki") or 0.0
            f.write("%s %.6f %.6f %.6f %.6f\n" % (state["name"], gain, tau, kp, ki))
    finally:
        f.close()


def save_ident_params(path, states):
    """@brief 保存系统辨识参数(增益和时间常数)到文件

    仅保存系统增益和时间常数, 不包含 PID 增益, 用于独立存储辨识结果
    仅保存已成功辨识的轮子(id_gain 和 id_tau 不为 None)

    @details
    文件格式:
    ```
    <轮子名> <增益> <时间常数>
    <其余轮子参数行>
    ```

    @param path 文件路径
    @param states 轮子状态列表, 每个状态字典应包含 "name"、"id_gain"、"id_tau" 字段
    """
    f = io.open(path, "w")
    try:
        for state in states:
            gain = state.get("id_gain")
            tau = state.get("id_tau")
            if gain is None or tau is None:
                continue
            f.write("%s %.6f %.6f\n" % (state["name"], gain, tau))
    finally:
        f.close()


def load_ident_params(path):
    """@brief 从文件加载系统辨识参数

    按行解析文件, 提取轮子名称、增益和时间常数, 忽略格式错误的行

    @details
    预期文件格式:
    ```
    <轮子名> <增益> <时间常数>
    <其余轮子参数行>
    ```
    每行至少需要 3 个字段; 缺少字段或数值解析失败的行会被跳过

    @param path 文件路径
    @return 字典, 格式: {轮子名 -> {"gain": float, "tau": float}}
            若文件不存在或无法读取, 返回空字典
    """
    meta = {}
    try:
        f = io.open(path, "r")
    except OSError:
        return meta

    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            name = parts[0]
            try:
                gain = float(parts[1])
                tau = float(parts[2])
                meta[name] = {"gain": gain, "tau": tau}
            except ValueError:
                continue
    finally:
        f.close()

    return meta


def load_pid_params(path):
    """@brief 从文件加载 PID 参数

    解析包含硬度级别和各轮子参数的文件, 返回汇总字典
    格式错误的行会被忽略, 允许部分数据缺失

    @details
    预期文件格式:
    ```
    hardness <级别>
    <轮子名> <增益> <时间常数> <kp> <ki>
    <其余轮子参数行>
    ```
    第一行可选: 若以 "hardness" 开头, 则提取硬度级别
    数据行需要至少 5 个字段; 不足的行被跳过

    @param path 文件路径
    @return 字典, 格式
            {
                "hardness": 硬度级别字符串或 None,
                "params": {轮子名 -> {"gain": float, "tau": float, "kp": float, "ki": float}}
            }
            若文件不存在或无法读取, 返回 {"hardness": None, "params": {}}
    """
    meta = {"hardness": None, "params": {}}
    try:
        f = io.open(path, "r")
    except OSError:
        return meta

    try:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if parts[0] == "hardness" and len(parts) >= 2:
                meta["hardness"] = parts[1]
                continue
            if len(parts) >= 5:
                name = parts[0]
                try:
                    gain = float(parts[1])
                    tau = float(parts[2])
                    kp = float(parts[3])
                    ki = float(parts[4])
                    meta["params"][name] = {
                        "gain": gain,
                        "tau": tau,
                        "kp": kp,
                        "ki": ki,
                    }
                except ValueError:
                    continue
    finally:
        f.close()

    return meta
