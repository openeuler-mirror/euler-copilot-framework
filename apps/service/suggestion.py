# Copyright (c) Huawei Technologies Co., Ltd. 2023-2024. All rights reserved.

from apps.manager.domain import DomainManager
from apps.manager.user_domain import UserDomainManager
from apps.service.domain import Domain


class Suggestion:
    def __init__(self):
        raise NotImplementedError("Suggestion类无法被实例化！")

    @staticmethod
    def update_user_domain(user_sub: str, question: str, answer: str):
        domain_list = DomainManager.get_domain()
        domain = {}
        for item in domain_list:
            domain[item.domain_name] = item.domain_description

        domain_list = Domain.check_domain(question, answer, domain)
        for item in domain_list:
            UserDomainManager.update_user_domain_by_user_sub_and_domain_name(user_sub=user_sub, domain_name=item)
        return

    @staticmethod
    def generate_suggestions(user_sub, summary, question, answer):
        user_domain = UserDomainManager.get_user_domain_by_user_sub_and_topk(user_sub, 1)
        domain = {}
        for item in user_domain:
            domain[item.domain_name] = item.domain_description
        format_result = Domain.generate_suggestion(summary, {
            "question": question,
            "answer": answer
        }, domain)
        return format_result