"""提取事实工具"""
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from apps.entities.scheduler import CallVars
from apps.llm.patterns.domain import Domain
from apps.llm.patterns.facts import Facts
from apps.manager.user_domain import UserDomainManager
from apps.scheduler.call.core import CoreCall


class FactsOutput(BaseModel):
    """提取事实工具的输出"""

    output: list[str] = Field(description="提取的事实")


class FactsCall(CoreCall, ret_type=FactsOutput):
    """提取事实工具"""

    name: ClassVar[str] = "提取事实"
    description: ClassVar[str] = "从对话上下文和文档片段中提取事实。"


    async def init(self, syscall_vars: CallVars, **kwargs: Any) -> dict[str, Any]:
        """初始化工具"""
        # 组装必要变量
        self._message = {
            "question": syscall_vars.question,
            "answer": kwargs["answer"],
        }
        self._task_id = syscall_vars.task_id
        self._user_sub = syscall_vars.user_sub

        return {
            "message": self._message,
            "task_id": self._task_id,
            "user_sub": self._user_sub,
        }


    async def exec(self) -> dict[str, Any]:
        """执行工具"""
        # 提取事实信息
        facts = await Facts().generate(self._task_id, message=self._message)
        # 更新用户画像
        domain_list = await Domain().generate(self._task_id, message=self._message)
        for domain in domain_list:
            await UserDomainManager.update_user_domain_by_user_sub_and_domain_name(self._user_sub, domain)

        return FactsOutput(output=facts).model_dump(exclude_none=True, by_alias=True)
