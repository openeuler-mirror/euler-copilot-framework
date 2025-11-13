import logging
from sqlalchemy import select, delete, update, text
from apps.common.postgres import DataBase, FlowPoolVector, ServicePoolVector, CallPoolVector, NodePoolVector, McpVector, McpToolVector
from apps.schemas.enum_var import VectorPoolType

logger = logging.getLogger(__name__)


class VectorManager:
    """向量管理器"""

    @staticmethod
    async def add_vector(
        data: FlowPoolVector | ServicePoolVector | CallPoolVector | NodePoolVector
    ) -> None:
        """添加向量数据"""
        try:
            async with await DataBase.get_session() as session:
                session.add(data)
                await session.commit()
        except Exception as e:
            # 这里可以添加日志记录或其他错误处理逻辑
            logger.error(f"[VectorManager] 添加向量数据失败: {e}")

    @staticmethod
    async def add_vectors(
        data_list: list[FlowPoolVector | ServicePoolVector |
                        CallPoolVector | NodePoolVector]
    ) -> None:
        """批量添加向量数据"""
        try:
            async with await DataBase.get_session() as session:
                session.add_all(data_list)
                await session.commit()
        except Exception as e:
            # 这里可以添加日志记录或其他错误处理逻辑
            logger.error(f"[VectorManager] 批量添加向量数据失败: {e}")

    @staticmethod
    async def delete_vectors(
        vector_type: VectorPoolType,
        ids: list[str],
    ) -> None:
        """删除向量数据"""
        table_map = {
            VectorPoolType.FLOW: FlowPoolVector,
            VectorPoolType.SERVICE: ServicePoolVector,
            VectorPoolType.CALL: CallPoolVector,
            VectorPoolType.NODE: NodePoolVector,
            VectorPoolType.MCP: McpVector,
            VectorPoolType.MCP_TOOL: McpToolVector,
        }
        table = table_map.get(vector_type)
        if not table:
            err = f"[VectorManager] 不支持的向量类型: {vector_type}"
            logger.error(err)
            raise ValueError(err)

        stmt = (
            delete(table)
            .where(table.id.in_(ids))
        )

        try:
            async with await DataBase.get_session() as session:
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logger.error(f"[VectorManager] 删除向量数据失败: {e}")

    @staticmethod
    async def delete_mcp_tool_vectors_by_mcp_ids(mcp_ids: list[str]) -> None:
        """根据MCP ID删除MCP工具向量数据"""
        stmt = (
            delete(McpToolVector)
            .where(McpToolVector.mcp_id.in_(mcp_ids))
        )

        try:
            async with await DataBase.get_session() as session:
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logger.error(f"[VectorManager] 根据MCP ID删除MCP工具向量数据失败: {e}")

    @staticmethod
    async def delete_call_vectors_by_service_ids(service_ids: list[str]) -> None:
        """根据Service ID删除Call向量数据"""
        stmt = (
            delete(CallPoolVector)
            .where(CallPoolVector.service_id.in_(service_ids))
        )

        try:
            async with await DataBase.get_session() as session:
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            logger.error(f"[VectorManager] 根据Service ID删除Call向量数据失败: {e}")

    @staticmethod
    async def select_topk_mcp_tool_by_mcp_ids(
        vector: list[float],
        mcp_ids: list[str],
        top_k: int = 10
    ) -> list[McpToolVector]:
        """根据MCP ID选择TopK的MCP工具向量数据"""
        base_sql = """
            SELECT
                id, mcp_id, embedding
            FROM mcp_tool_vector
            WHERE mcp_id = ANY(:mcp_ids)
            ORDER BY embedding <=> :vector ASC
            LIMIT :top_k
        """
        try:
            async with await DataBase.get_session() as session:
                result = await session.execute(
                    text(base_sql),
                    {
                        "vector": vector,
                        "mcp_ids": mcp_ids,
                        "top_k": top_k,
                    },
                )
                rows = result.fetchall()

                mcp_tool_vectors = []
                for row in rows:
                    mcp_tool_vector = McpToolVector(
                        id=row.id,
                        mcp_id=row.mcp_id,
                        embedding=row.embedding,
                    )
                    mcp_tool_vectors.append(mcp_tool_vector)

                return mcp_tool_vectors

        except Exception as e:
            err = f"根据MCP ID选择TopK的MCP工具向量数据失败: {str(e)}"
            logger.exception("[VectorManager] %s", err)
            return []
