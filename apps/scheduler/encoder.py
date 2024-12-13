# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from json import JSONEncoder
import logging

import numpy


logger = logging.getLogger('gunicorn.error')


class JSONSerializer(JSONEncoder):
    """
    自定义的JSON序列化方法。
    当一个字段无法被序列化时，会使用掩码`[Data unable to represent in string]`替代
    """
    def default(self, o):
        try:
            if isinstance(o, numpy.integer):
                return int(o)
            elif isinstance(o, numpy.floating):
                return float(o)
            elif isinstance(o, numpy.ndarray):
                return o.tolist()
            result = JSONEncoder.default(self, o)
        except TypeError as e:
            logger.error(f"工具输出无法被序列化为字符串：{str(e)}")
            result = "[Data unable to represent in string]"
        return result
