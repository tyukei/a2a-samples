from typing import Any, List

import logging
from .agent import BBQBeachAgent

from typing_extensions import override

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.types import (
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils import new_agent_text_message, new_task, new_text_artifact
from uuid import uuid4

logger = logging.getLogger(__name__)


class BBQBeachAgentExecutor(AgentExecutor):
    """BBQBeachAgentExecutor that uses an agent with preloaded tools."""

    def __init__(self, mcp_tools: List[Any]):
        """
        BBQビーチエージェント実行器を初期化

        Args:
            mcp_tools: BBQ可能なビーチ検索用のMCPツールのリスト
        """
        self.mcp_tools = mcp_tools
        self.bbq_beach_agent = BBQBeachAgent(mcp_tools=mcp_tools)
        logger.info(f"BBQBeachAgentExecutorを{len(mcp_tools)}個のMCPツールで初期化しました")

    @override
    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        BBQビーチ検索タスクを実行
        
        Args:
            context: リクエストコンテキスト
            event_queue: イベントキュー
        """
        task = context.task
        session_id = context.session_id
        
        logger.info(f"BBQビーチ検索タスクを実行中: {task.id}")
        
        # タスクのメッセージからクエリを抽出
        if not task.message or not task.message.parts:
            logger.error("タスクメッセージまたはパーツが見つかりません")
            event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=new_agent_text_message(
                            "無効なタスクメッセージです。",
                            task.contextId,
                            task.id,
                        ),
                    ),
                    final=True,
                    contextId=task.contextId,
                    taskId=task.id,
                )
            )
            return

        # メッセージからテキストを抽出
        query_text = ""
        for part in task.message.parts:
            if hasattr(part, 'text') and part.text:
                query_text += part.text + " "
        
        query_text = query_text.strip()
        
        if not query_text:
            logger.error("クエリテキストが空です")
            event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=new_agent_text_message(
                            "クエリテキストが見つかりません。",
                            task.contextId,
                            task.id,
                        ),
                    ),
                    final=True,
                    contextId=task.contextId,
                    taskId=task.id,
                )
            )
            return

        logger.info(f"BBQビーチエージェントでクエリを処理中: {query_text}")

        try:
            # BBQビーチエージェントのストリーミング実行
            async for event in self.bbq_beach_agent.stream(query_text, session_id):
                logger.debug(f"BBQビーチエージェントからのイベント: {event}")
                
                if event["is_task_complete"]:
                    # タスク完了
                    event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            status=TaskStatus(
                                state=TaskState.completed,
                                message=new_agent_text_message(
                                    event["content"],
                                    task.contextId,
                                    task.id,
                                ),
                            ),
                            final=True,
                            contextId=task.contextId,
                            taskId=task.id,
                        )
                    )
                    break
                elif event["require_user_input"]:
                    # ユーザー入力が必要
                    event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            status=TaskStatus(
                                state=TaskState.input_required,
                                message=new_agent_text_message(
                                    event["content"],
                                    task.contextId,
                                    task.id,
                                ),
                            ),
                            final=True,
                            contextId=task.contextId,
                            taskId=task.id,
                        )
                    )
                    break
                else:
                    # 作業中の更新
                    event_queue.enqueue_event(
                        TaskStatusUpdateEvent(
                            status=TaskStatus(
                                state=TaskState.working,
                                message=new_agent_text_message(
                                    event["content"],
                                    task.contextId,
                                    task.id,
                                ),
                            ),
                            final=False,
                            contextId=task.contextId,
                            taskId=task.id,
                        )
                    )

        except Exception as e:
            logger.error(f"BBQビーチエージェント実行中にエラー: {e}", exc_info=True)
            event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    status=TaskStatus(
                        state=TaskState.failed,
                        message=new_agent_text_message(
                            f"BBQビーチ検索中にエラーが発生しました: {str(e)}",
                            task.contextId,
                            task.id,
                        ),
                    ),
                    final=True,
                    contextId=task.contextId,
                    taskId=task.id,
                )
            )

    @override
    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise Exception("cancel not supported")
        mcp_config = os.getenv("BBQ_BEACH_MCP_CONFIG")
        if mcp_config:
            try:
                config_data = json.loads(mcp_config)
                # ここでMCPツールを初期化
                logger.info(f"MCP設定をロードしました: {len(config_data)}個の設定")
            except json.JSONDecodeError as e:
                logger.error(f"MCP設定の解析に失敗: {e}")
        
        return tools

    async def ainvoke(self, query: str, sessionId: str) -> dict[str, Any]:
        """
        BBQビーチ検索クエリを実行

        Args:
            query: ユーザーのクエリ
            sessionId: セッション識別子

        Returns:
            実行結果
        """
        logger.info(f"BBQBeachAgentExecutor.ainvoke - クエリ: {query}")
        
        if not self.bbq_beach_agent:
            logger.error("BBQBeachAgentが初期化されていません")
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "エージェントが正しく初期化されていません。",
            }

        try:
            response = await self.bbq_beach_agent.ainvoke(query, sessionId)
            logger.info(f"BBQビーチエージェントからの応答: {response}")
            return response
        except Exception as e:
            logger.error(f"BBQビーチエージェント実行中にエラー: {e}")
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"BBQビーチ検索中にエラーが発生しました: {str(e)}",
            }

    async def stream(self, query: str, sessionId: str):
        """
        BBQビーチ検索をストリーミング実行

        Args:
            query: ユーザーのクエリ
            sessionId: セッション識別子

        Yields:
            ストリーミング応答
        """
        logger.info(f"BBQBeachAgentExecutor.stream - クエリ: {query}")
        
        if not self.bbq_beach_agent:
            logger.error("BBQBeachAgentが初期化されていません")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": "エージェントが正しく初期化されていません。",
            }
            return

        try:
            async for chunk in self.bbq_beach_agent.stream(query, sessionId):
                yield chunk
        except Exception as e:
            logger.error(f"BBQビーチエージェントストリーミング中にエラー: {e}")
            yield {
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"BBQビーチ検索ストリーミング中にエラーが発生しました: {str(e)}",
            }


# A2A SDKのエントリーポイント
def create_agent() -> BBQBeachAgentExecutor:
    """BBQビーチエージェントのインスタンスを作成"""
    return BBQBeachAgentExecutor()
