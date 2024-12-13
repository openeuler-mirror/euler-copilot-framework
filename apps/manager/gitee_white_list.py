# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import logging

from apps.models.mysql import GiteeIDWhiteList, MysqlDB

class GiteeIDManager:
    logger = logging.getLogger('gunicorn.error')

    @staticmethod
    def check_user_exist_or_not(gitee_id):
        result = None
        try:
            with MysqlDB().get_session() as session:
                result = session.query(GiteeIDWhiteList).filter(
                    GiteeIDWhiteList.gitee_id == gitee_id).count()
        except Exception as e:
            GiteeIDManager.logger.info(
                f"check user exist or not fail: {e}")
        if not result:
            return False
        return True

