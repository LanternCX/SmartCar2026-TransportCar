"""
@brief 运行时诊断输出辅助函数

提供串口安全的诊断数据格式化功能, 支持查询响应和实时观测两种输出格式
"""


def _sanitize_text(value):
    """
    @brief 将字符串值清理为单行串口安全文本
    @param value 原始值, 任意类型, 将被转换为字符串处理
    @return 清理后的单行文本, 已移除换行符并将逗号替换为分号
    @note 串口通信需要避免多行输出和特殊分隔符, 因此需要此清理步骤
    """
    text = str(value)
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = text.replace(",", ";")
    return text


def format_snapshot_value(value):
    """
    @brief 格式化单个诊断字段值
    @param value 字段原始值, 可能为 None 或其他类型
    @return 格式化后的字符串, None 值返回 "none", 其他值经清理后返回
    """
    if value is None:
        return "none"
    return _sanitize_text(value)


def format_query_response(token, snapshot):
    """
    @brief 将快照字典编码为查询响应行
    @param token 查询令牌, 用于标识此次查询请求
    @param snapshot 诊断快照字典, 键为字段名, 值为字段值
    @return 格式化的查询响应字符串, 格式为 "?token=key1:value1,key2:value2\r\n"
    """
    parts = []
    for key, value in snapshot.items():
        parts.append("%s:%s" % (key, format_snapshot_value(value)))
    return "?%s=%s\r\n" % (token, ",".join(parts))


def format_observe_line(token, snapshot):
    """
    @brief 将快照字典编码为设备观测输出行
    @param token 观测标识令牌, 用于区分不同的观测数据源
    @param snapshot 诊断快照字典, 键为字段名, 值为字段值
    @return 格式化的观测输出字符串, 格式为 "OBSERVE token key1=value1 key2=value2"
    """
    parts = []
    for key, value in snapshot.items():
        parts.append("%s=%s" % (key, format_snapshot_value(value)))
    return "OBSERVE %s %s" % (token, " ".join(parts))
