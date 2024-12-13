# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from datetime import datetime, timezone

import pytz
import logging

from apps.models.mysql import MysqlDB, Domain
from apps.entities.request_data import AddDomainData

logger = logging.getLogger('gunicorn.error')


class DomainManager:
    def __init__(self):
        raise NotImplementedError()

    @staticmethod
    def get_domain():
        results = []
        try:
            with MysqlDB().get_session() as session:
                results = session.query(Domain).all()
        except Exception as e:
            logger.info(f"Get domain by domain_name failed: {e}")
        return results

    @staticmethod
    def get_domain_by_domain_name(domain_name):
        results = []
        try:
            with MysqlDB().get_session() as session:
                results = session.query(Domain).filter(
                    Domain.domain_name == domain_name).all()
        except Exception as e:
            logger.info(f"Get domain by domain_name failed: {e}")
        return results

    @staticmethod
    def add_domain(add_domain_data: AddDomainData) -> bool:
        try:
            domain = Domain(
                domain_name=add_domain_data.domain_name,
                domain_description=add_domain_data.domain_description,
                created_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')),
                updated_time=datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai')))
            with MysqlDB().get_session() as session:
                session.add(domain)
                session.commit()
            return True
        except Exception as e:
            logger.info(f"Add domain failed due to error: {e}")
            return False

    @staticmethod
    def update_domain_by_domain_name(update_domain_data: AddDomainData):
        result = None
        try:
            update_dict = {
                "domain_description": update_domain_data.domain_description,
                "updated_time": datetime.now(timezone.utc).astimezone(pytz.timezone('Asia/Shanghai'))
            }

            with MysqlDB().get_session() as session:
                session.query(Domain).filter(Domain.domain_name == update_domain_data.domain_name).update(update_dict)
                session.commit()
            result = DomainManager.get_domain_by_domain_name(update_domain_data.domain_name)
        except Exception as e:
            logger.info(f"Update domain by domain_name failed due to error: {e}")
        finally:
            return result

    @staticmethod
    def delete_domain_by_domain_name(delete_domain_data: AddDomainData):
        try:
            with MysqlDB().get_session() as session:
                session.query(Domain).filter(Domain.domain_name == delete_domain_data.domain_name).delete()
                session.commit()
            return True
        except Exception as e:
            logger.info(f"Delete domain by domain_name failed due to error: {e}")
            return False
