# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

import logging
from datetime import datetime, timezone

import pytz

from apps.entities.user import User as UserInfo
from apps.models.mysql import MysqlDB, User


class UserManager:
    logger = logging.getLogger('gunicorn.error')

    @staticmethod
    def add_userinfo(userinfo: User):
        user_slice = User(
            user_sub=userinfo.user_sub,
            revision_number=userinfo.revision_number,
            login_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
        )
        try:
            with MysqlDB().get_session() as session:
                session.add(user_slice)
                session.commit()
                session.refresh(user_slice)
        except Exception as e:
            UserManager.logger.info(f"Add userinfo failed due to error: {e}")

    @staticmethod
    def get_all_user_sub():
        result = None
        try:
            with MysqlDB().get_session() as session:
                result = session.query(User.user_sub).all()
        except Exception as e:
            UserManager.logger.info(
                f"Get all user_sub failed due to error: {e}")
        return result

    @staticmethod
    def get_userinfo_by_user_sub(user_sub):
        result = None
        try:
            with MysqlDB().get_session() as session:
                result = session.query(User).filter(
                    User.user_sub == user_sub).first()
        except Exception as e:
            UserManager.logger.info(
                f"Get userinfo by user_sub failed due to error: {e}")
        return result

    @staticmethod
    def get_revision_number_by_user_sub(user_sub):
        userinfo = UserManager.get_userinfo_by_user_sub(user_sub)
        revision_number = None
        if userinfo is not None:
            revision_number = userinfo.revision_number
        return revision_number

    @staticmethod
    def update_userinfo_by_user_sub(userinfo: UserInfo, refresh_revision=False):
        user_slice = UserManager.get_userinfo_by_user_sub(
            userinfo.user_sub)
        if not user_slice:
            UserManager.add_userinfo(userinfo)
            return UserManager.get_userinfo_by_user_sub(userinfo.user_sub)
        user_dict = {
            "user_sub": userinfo.user_sub,
            "login_time": datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
        }
        if refresh_revision:
            user_dict.update({"revision_number": userinfo.revision_number})
        try:
            with MysqlDB().get_session() as session:
                session.query(User).filter(User.user_sub == userinfo.user_sub).update(user_dict)
                session.commit()
        except Exception as e:
            UserManager.logger.info(
                f"Update userinfo by user_sub failed due to error: {e}")
        ret = UserManager.get_userinfo_by_user_sub(userinfo.user_sub)
        ret_dict = ret.__dict__
        if '_sa_instance_state' in ret_dict:
            del ret_dict['_sa_instance_state']
        return User(**ret_dict)

    @staticmethod
    def query_userinfo_by_login_time(login_time):
        result = []
        try:
            with MysqlDB().get_session() as session:
                result = session.query(User).filter(
                    User.login_time <= login_time).all()
        except Exception as e:
            UserManager.logger.info(
                f"Get userinfo by login_time failed due to error: {e}")
        return result

    @staticmethod
    def delete_userinfo_by_user_sub(user_sub):
        try:
            with MysqlDB().get_session() as session:
                session.query(User).filter(
                    User.user_sub == user_sub).delete()
                session.commit()
        except Exception as e:
            UserManager.logger.info(
                f"Delete userinfo by user_sub failed due to error: {e}")
