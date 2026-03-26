"""主车视觉接入组织.

@file src/master/vision_ingress.py
"""


class VisionIngress:
    """单视觉串口轮询双摄接入器

    @brief 保留单视觉串口轮询两颗相机的接入拓扑
    """

    def __init__(self, vision_uart, camera_ids):
        self.vision_uart = vision_uart
        self.camera_ids = tuple(camera_ids)
        self._poll_index = 0

    def build_poll_request(self, camera_id):
        """构造单相机轮询请求

        @brief 未被点名相机必须保持静默
        @param camera_id 相机标识
        @return str
        """

        return "?frame=%s" % str(camera_id)

    def build_next_poll_request(self):
        """构造下一次轮询请求

        @brief 在同一视觉串口上按顺序轮询两颗相机
        @return str
        """

        camera_id = self.camera_ids[self._poll_index % len(self.camera_ids)]
        self._poll_index += 1
        return self.build_poll_request(camera_id)

    def prepare_observation(self, observation=None):
        """补齐轮询上下文后的观测

        @brief 让主路径显式带上当前轮询请求
        @param observation 当前观测字典
        @return dict
        """

        prepared = {} if observation is None else dict(observation)
        prepared["poll_request"] = self.build_next_poll_request()
        return prepared
