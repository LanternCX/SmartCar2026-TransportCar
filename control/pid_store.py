"""PID 参数与辨识参数的持久化工具.

提供保存和加载 PID 参数、系统辨识结果(增益和时间常数)的函数.
"""
import io
from typing import Dict, List, Any, Optional


def save_pid_params(path: str, states: List[Dict[str, Any]], hardness: str) -> None:
    """保存 PID 参数到文件.
    
    参数:
        path: 文件路径.
        states: 轮子状态列表.
        hardness: 调谐硬度级别.
    
    副作用:
        创建或覆盖指定文件.
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


def save_ident_params(path: str, states: List[Dict[str, Any]]) -> None:
    """保存系统辨识参数(增益和时间常数)到文件.
    
    参数:
        path: 文件路径.
        states: 轮子状态列表.
    
    副作用:
        创建或覆盖指定文件;跳过增益或时间常数为 None 的轮子.
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


def load_ident_params(path: str) -> Dict[str, Dict[str, float]]:
    """从文件加载系统辨识参数.
    
    参数:
        path: 文件路径.
    
    返回:
        字典,格式:{轮子名 -> {"gain": float, "tau": float}}.
        若文件不存在或读取失败,返回空字典.
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


def load_pid_params(path: str) -> Dict[str, Any]:
    """从文件加载 PID 参数.
    
    参数:
        path: 文件路径.
    
    返回:
        字典,格式:
        {
            "hardness": str 或 None,
            "params": {轮子名 -> {"gain", "tau", "kp", "ki"}}
        }
        若文件不存在或读取失败,返回默认空字典.
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
