# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from datetime import datetime, timezone

import pytz
import logging

from apps.models.mysql import MysqlDB, UserDomain, Domain
from sqlalchemy import desc

logger = logging.getLogger('gunicorn.error')


class UserDomainManager:
    def __init__(self):
        raise NotImplementedError()

    @staticmethod
    def get_user_domain_by_user_sub_and_domain_name(user_sub, domain_name):
        result = None
        try:
            with MysqlDB().get_session() as session:
                result = session.query(UserDomain).filter(
                    UserDomain.user_sub == user_sub, UserDomain.domain_name == domain_name).first()
        except Exception as e:
            logger.info(f"Get user_domain by user_sub_and_domain_name failed: {e}")
        return result

    @staticmethod
    def get_user_domain_by_user_sub(user_sub):
        results = []
        try:
            with MysqlDB().get_session() as session:
                results = session.query(UserDomain).filter(
                    UserDomain.user_sub == user_sub).all()
        except Exception as e:
            logger.info(f"Get user_domain by user_sub failed: {e}")
        return results
    
    @staticmethod
    def get_user_domain_by_user_sub_and_topk(user_sub, topk):
        results = []
        try:
            with MysqlDB().get_session() as session:
                results = session.query(UserDomain.domain_count, Domain.domain_name, Domain.domain_description).join(Domain, UserDomain.domain_name==Domain.domain_name).filter(
                    UserDomain.user_sub == user_sub).order_by(
                    desc(UserDomain.domain_count)).limit(topk).all()
        except Exception as e:
            logger.info(f"Get user_domain by user_sub and topk failed: {e}")
        return results

    @staticmethod
    def update_user_domain_by_user_sub_and_domain_name(user_sub, domain_name):
        result = None
        try:
            with MysqlDB().get_session() as session:
                cur_user_domain = UserDomainManager.get_user_domain_by_user_sub_and_domain_name(user_sub, domain_name)
                if not cur_user_domain:
                    cur_user_domain = UserDomain(
                        user_sub=user_sub, domain_name=domain_name, domain_count=1,
                        created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                        updated_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')))
                    session.add(cur_user_domain)
                    session.commit()
                else:
                    update_dict = {
                        "domain_count": cur_user_domain.domain_count+1,
                        "updated_time": datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
                    }
                    session.query(UserDomain).filter(UserDomain.user_sub == user_sub,
                                                     UserDomain.domain_name == domain_name).update(update_dict)
                    session.commit()
            result = UserDomainManager.get_user_domain_by_user_sub_and_domain_name(user_sub, domain_name)
        except Exception as e:
            logger.info(f"Update user_domain by user_sub and domain_name failed due to error: {e}")
        finally:
            return result
