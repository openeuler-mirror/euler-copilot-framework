"""上下文压缩工具类"""
import inspect
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Dict

import jieba

from apps.llm.token import token_calculator
from apps.services.abstract_manager import AbstractManager

logger = logging.getLogger(__name__)


@dataclass
class ContextConfig:
    """上下文压缩配置"""
    short_window_size: int = 5  # 滑动窗口：保留最近 N 轮对话
    ctx_length: int = 128000  # 模型最大上下文长度
    token_safety_ratio: float = 0.8  # Token 安全占比
    enable_abstract_replace: bool = True  # 开启摘要替换
    enable_stopword_filter: bool = True  # 开启停用词过滤
    enable_smart_truncation: bool = True  # 开启兜底截断
    stop_words_path: Path = Path.cwd() / "apps" / "common" / "stopwords.txt"


class ContextManager:
    """上下文管理工具类"""
    # 静态类变量：存储当前对话ID
    _conversation_id: uuid.UUID | None = None
    # 静态类变量：存储配置
    _config: ContextConfig = ContextConfig()
    # 临时存储被移除的消息片段（用于Token统计）
    _removed_messages: List[Dict[str, Any]] = []
    # 静态缓存：加载后的停用词集合（仅初始化一次）
    _stopwords: set[str] | None = None

    # ==============================
    # 懒加载停用词的辅助方法
    # ==============================
    @staticmethod
    def _lazy_load_stopwords():
        """懒加载停用词：仅在首次使用时加载"""
        if ContextManager._stopwords is not None:
            return
        try:
            with Path.open(ContextManager._config.stop_words_path, encoding="utf-8") as f:
                ContextManager._stopwords = {
                    line.strip()
                    for line in f
                    if line.strip() and not line.strip().startswith("#")
                }
            logger.info(f"成功加载停用词表 | 路径: {ContextManager._config.stop_words_path} | 数量: {len(ContextManager._stopwords)}")
        except Exception as e:
            logger.exception(f"【停用词过滤】加载停用词失败: {e}")
            ContextManager._stopwords = set()

    # ==============================
    # 对外初始化方法（仅需调用一次）
    # ==============================
    @staticmethod
    def init(conversation_id: uuid.UUID | None = None, config: ContextConfig | None = None) -> None:
        """初始化：设置对话ID和配置（全局生效）"""
        if conversation_id:
            ContextManager._conversation_id = conversation_id
        if config:
            # 若路径变化，清空缓存（下次使用时重新加载）
            if ContextManager._config.stop_words_path != config.stop_words_path:
                ContextManager._stopwords = None
            ContextManager._config = config
        # 重置被移除的消息片段
        ContextManager._removed_messages = []

    # ==============================
    # 核心工具方法：计算指定消息列表的Token数
    # ==============================
    @staticmethod
    def _calc_token(msgs: List[Dict[str, Any]]) -> int:
        """计算消息列表Token数"""
        if not msgs:
            return 0
        try:
            return token_calculator.calculate_token_length(msgs, pure_text=False)
        except Exception as e:
            logger.exception(f"计算Token数失败: {e}")
            return -1

    # ==============================
    # 核心判断方法
    # ==============================
    @staticmethod
    def is_need_compress(messages: list[dict[str, Any]]) -> bool:
        """判断是否需要压缩（直接用类变量_config）"""
        if not messages:
            return False

        try:
            total = ContextManager._calc_token(messages)
        except Exception as e:
            logger.exception(f"计算token失败: {e}")
            return False

        return total >= ContextManager._config.ctx_length * ContextManager._config.token_safety_ratio

    # ==============================
    # 策略1：摘要替换
    # ==============================
    @staticmethod
    async def _abstract_replace_strategy(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # 无conversation_id则跳过
        if not ContextManager._conversation_id:
            logger.warning("未设置conversation_id，跳过摘要替换")
            return messages

        conv_id_str = str(ContextManager._conversation_id)
        n = ContextManager.calculate_n_by_round_threshold(messages, ContextManager._config.short_window_size)
        if n <= 0:
            logger.info(f"【摘要替换】对话ID: {conv_id_str} | 无需替换（轮数未超限）")
            return messages

        # 1. 获取被移除的消息片段并统计原始Token
        removed_msgs = ContextManager.get_oldest_record_message(messages, n)
        if not removed_msgs:
            logger.info(f"【摘要替换】对话ID: {conv_id_str} | 无待替换消息片段")
            return messages

        removed_token = ContextManager._calc_token(removed_msgs)
        logger.info(f"【摘要替换】对话ID: {conv_id_str} | 待替换片段轮数: {n} | 原始Token数: {removed_token}")

        # 2. 获取摘要并统计摘要的Token
        abstract_msgs = await ContextManager.build_new_messages_with_abstract(messages, n)
        # 提取新增的摘要消息（system类型）
        abstract_only = [msg for msg in abstract_msgs if msg in abstract_msgs and msg not in messages]
        abstract_token = ContextManager._calc_token(abstract_only)

        # 3. 输出摘要替换的Token变化
        token_reduction = removed_token - abstract_token
        reduction_ratio = (token_reduction / removed_token * 100) if removed_token > 0 else 0.0
        logger.info(
            f"【摘要替换】对话ID: {conv_id_str} | 替换完成 | "
            f"原始片段Token: {removed_token} | 摘要Token: {abstract_token} | "
            f"减少Token: {token_reduction} | 压缩率: {reduction_ratio:.2f}%"
        )

        return abstract_msgs

    # ==============================
    # 策略2：停用词过滤（统计被过滤片段的Token变化）
    # ==============================
    @staticmethod
    def _stopword_filter_strategy(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conv_id_str = str(ContextManager._conversation_id) if ContextManager._conversation_id else "未指定"

        # 1. 先懒加载停用词
        ContextManager._lazy_load_stopwords()

        # 2. 提取需要过滤的片段（system消息：主要是摘要内容）
        filter_targets = [msg for msg in messages if msg["role"] == "system"]
        if not filter_targets:
            logger.info(f"【停用词过滤】对话ID: {conv_id_str} | 无需过滤（无system消息）")
            return messages

        # 3. 空停用词表直接返回
        if not ContextManager._stopwords:
            logger.info(f"【停用词过滤】对话ID: {conv_id_str} | 无可用停用词表，跳过过滤")
            return messages

        # 4. 统计过滤前的Token数
        before_filter_token = ContextManager._calc_token(filter_targets)

        # 5. 执行停用词过滤
        original_system = []
        history = messages
        if messages and messages[0]["role"] == "system":
            original_system = [messages[0]]
            history = messages[1:]

        processed = []
        for msg in history:
            if msg["role"] == "system":
                content = msg.get("content", "")
                words = jieba.cut(str(content))
                filtered = [w for w in words if w not in ContextManager._stopwords]
                processed.append({**msg, "content": "".join(filtered)})
            else:
                processed.append(msg)

        filtered_messages = original_system + processed

        # 6. 统计过滤后的Token数（仅针对原过滤目标）
        filtered_targets = [msg for msg in filtered_messages if msg["role"] == "system"]
        after_filter_token = ContextManager._calc_token(filtered_targets)

        # 7. 输出停用词过滤的Token变化
        token_reduction = before_filter_token - after_filter_token
        reduction_ratio = (token_reduction / before_filter_token * 100) if before_filter_token > 0 else 0.0
        logger.info(
            f"【停用词过滤】对话ID: {conv_id_str} | 过滤完成 | "
            f"过滤前Token: {before_filter_token} | 过滤后Token: {after_filter_token} | "
            f"减少Token: {token_reduction} | 压缩率: {reduction_ratio:.2f}%"
        )

        return filtered_messages

    # ==============================
    # 策略3：智能截断（统计被截断片段的Token变化）
    # ==============================
    @staticmethod
    def _smart_truncation_strategy(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conv_id_str = str(ContextManager._conversation_id) if ContextManager._conversation_id else "未指定"
        target = int(ContextManager._config.ctx_length * ContextManager._config.token_safety_ratio * 0.9)

        # 1. 统计截断前的全量Token（用于对比）
        before_trunc_token = ContextManager._calc_token(messages)
        logger.info(
            f"【智能截断】对话ID: {conv_id_str} | 开始截断 | 截断前Token: {before_trunc_token} | 目标Token: {target}")

        system_msg = []
        real_msg = messages
        if messages and messages[0]["role"] == "system":
            system_msg = [messages[0]]
            real_msg = messages[1:]

        truncated = []
        current = 0
        truncated_count = 0
        for msg in reversed(real_msg):
            tok = ContextManager._calc_token([msg])
            if current + tok > target:
                # 记录被截断的消息数
                truncated_count = len(real_msg) - len(truncated) - 1
                content = token_calculator.get_k_tokens_words_from_content(msg["content"], k=target - current)
                truncated.append({**msg, "content": content})
                current = target
                break
            truncated.append(msg)
            current += tok

        truncated_messages = system_msg + list(reversed(truncated))

        # 2. 统计截断后的Token数
        after_trunc_token = ContextManager._calc_token(truncated_messages)
        token_reduction = before_trunc_token - after_trunc_token
        reduction_ratio = (token_reduction / before_trunc_token * 100) if before_trunc_token > 0 else 0.0
        logger.info(
            f"【智能截断】对话ID: {conv_id_str} | 截断完成 | "
            f"截断前Token: {before_trunc_token} | 截断后Token: {after_trunc_token} | "
            f"减少Token: {token_reduction} | 压缩率: {reduction_ratio:.2f}% | 截断消息数: {truncated_count}"
        )

        return truncated_messages

    # ==============================
    # 基础工具方法（记录被移除的消息）
    # ==============================
    @staticmethod
    def get_oldest_record_message(messages: list[dict[str, Any]], n: int = 1) -> list[dict[str, Any]] | None:
        """获取最旧的n条记录（不包含system消息），并记录到静态变量"""
        system_msg = []
        real_msg = messages
        if messages and messages[0]["role"] == "system":
            system_msg = [messages[0]]
            real_msg = messages[1:]

        q = deque(real_msg)
        removed = []
        user_count = 0

        while q:
            current_msg = q[0]  # 先看队首消息，不立即移除
            if user_count == n and current_msg["role"] == "user":
                break
            m = q.popleft()
            removed.append(m)
            if m["role"] == "user":
                user_count += 1

        # 记录被移除的消息（用于Token统计）
        ContextManager._removed_messages = removed
        messages[:] = system_msg + list(q)
        return removed

    @staticmethod
    async def get_oldest_record_abstract(n: int = 1) -> list[dict[str, Any]]:
        """获取最旧的n条记录的摘要"""
        if not ContextManager._conversation_id:
            return []
        abstracts = await AbstractManager.get_oldest_abstracts_by_conversation(ContextManager._conversation_id, n)
        return [{"role": "system", "content": a.abstract} for a in abstracts]

    @staticmethod
    async def build_new_messages_with_abstract(messages: list[dict[str, Any]], n: int = 1) -> list[dict[str, Any]]:
        """构建新的消息列表：在开头插入最旧n条记录的摘要（如果有）"""
        abstracts = await ContextManager.get_oldest_record_abstract(n)
        if not abstracts:
            return messages

        return messages[:1] + abstracts + messages[1:]

    @staticmethod
    def calculate_n_by_round_threshold(messages: list[dict[str, Any]], max_rounds: int | None = None) -> int:
        """根据轮数阈值计算需要压缩的轮数n（仅计算用户消息）"""
        if max_rounds is None:
            max_rounds = ContextManager._config.short_window_size
        real = messages[1:] if (messages and messages[0]["role"] == "system") else messages
        total = sum(1 for m in real if m["role"] == "user")
        return max(total - max_rounds, 0)

    # ==============================
    # 对外统一入口
    # ==============================
    @staticmethod
    def _get_strategies() -> list:
        """按优先级获取启用的压缩策略"""
        strategies = []
        if ContextManager._config.enable_abstract_replace:
            strategies.append(ContextManager._abstract_replace_strategy)
        if ContextManager._config.enable_stopword_filter:
            strategies.append(ContextManager._stopword_filter_strategy)
        if ContextManager._config.enable_smart_truncation:
            strategies.append(ContextManager._smart_truncation_strategy)
        return strategies

    @staticmethod
    async def build(
            messages: list[dict[str, Any]],
            conversation_id: uuid.UUID | None = None,
            config: ContextConfig | None = None,
    ) -> list[dict[str, Any]]:
        """对外统一入口：聚焦被压缩片段的Token统计"""
        # 初始化（重置被移除消息记录）
        ContextManager.init(conversation_id=conversation_id, config=config)
        conv_id_str = str(conversation_id) if conversation_id else "未指定"

        # 全量消息Token统计（仅用于整体参考）
        total_before = ContextManager._calc_token(messages)
        logger.info(f"【上下文压缩】开始处理 | 对话ID: {conv_id_str} | 全量消息原始Token: {total_before}")

        current = [m.copy() for m in messages]
        strategies = ContextManager._get_strategies()
        idx = 0

        # 执行各策略（每个策略内部输出自身的Token变化）
        while ContextManager.is_need_compress(current) and idx < len(strategies):
            try:
                strategy_func = strategies[idx]
                res = strategy_func(current)
                current = await res if inspect.isawaitable(res) else res
            except Exception as e:
                logger.exception(f"【上下文压缩】策略{idx + 1}执行失败: {e}")
            idx += 1

        # 兜底截断（内部已统计Token变化）
        if ContextManager.is_need_compress(current):
            current = ContextManager._smart_truncation_strategy(current)

        res_messages = ContextManager.merge_system_messages(current)
        # 全量消息最终Token（参考）
        total_after = ContextManager._calc_token(res_messages)
        logger.info(
            f"【上下文压缩】处理完成 | 对话ID: {conv_id_str} | "
            f"全量消息最终Token: {total_after} | 整体减少Token: {total_before - total_after}"
        )

        return res_messages


    @staticmethod
    def merge_system_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        合并所有system消息为单条
        规则：
        1. 第一条system保留核心角色设定
        2. 其他system（摘要/记忆）追加到第一条末尾
        3. 最终仅保留1条system消息，放在最开头
        """
        if not messages:
            return messages

        # 分离system消息和普通消息（user/assistant）
        system_msgs = [msg for msg in messages if msg["role"] == "system"]
        normal_msgs = [msg for msg in messages if msg["role"] != "system"]

        if not system_msgs:
            # 无system消息时，直接返回原普通消息
            return normal_msgs

        # 提取第一条system（核心角色设定）和其他system（摘要/记忆）
        main_system = system_msgs[0]["content"].strip()
        additional_systems = [msg["content"].strip() for msg in system_msgs[1:] if msg["content"].strip()]

        if not additional_systems:
            # 只有1条system，直接返回
            return [system_msgs[0]] + normal_msgs

        # 合并所有system内容（用分隔符区分，模型更容易理解）
        merged_content = f"{main_system}\n\n# 历史对话摘要\n\n{chr(10).join(additional_systems)}"
        merged_system = {"role": "system", "content": merged_content}

        # 最终消息列表：合并后的system + 普通消息
        return [merged_system] + normal_msgs
