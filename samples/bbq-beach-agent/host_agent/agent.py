"""
BBQ & Weather Host Agent - A2A Routing Agent
BBQビーチエージェントと天気エージェントを統合するホストエージェント
"""

import json
import uuid
import logging
from typing import List, Dict, Any
import httpx
from google.adk.agents import Agent
from google.adk.core import ReadonlyContext, ToolContext
from a2a.client.agent_card_resolver import A2ACardResolver
from a2a.client.a2a_client import A2AClient
from a2a.types import AgentCard

logger = logging.getLogger(__name__)


class RemoteAgentConnections:
    """リモートエージェント接続の管理"""

    def __init__(self, agent_card: AgentCard, agent_url: str):
        self.agent_card = agent_card
        self.agent_url = agent_url


class BBQWeatherRoutingAgent:
    """BBQビーチとお天気情報を統合するルーティングエージェント"""

    def __init__(self, task_callback=None):
        self.task_callback = task_callback
        self.remote_agent_connections: Dict[str, RemoteAgentConnections] = {}
        self.cards: Dict[str, AgentCard] = {}
        self.agents: str = ""

    async def _async_init_components(self, remote_agent_addresses: List[str]):
        """リモートエージェントとの接続を非同期で初期化"""
        async with httpx.AsyncClient(timeout=30) as client:
            for address in remote_agent_addresses:
                card_resolver = A2ACardResolver(client, address)
                try:
                    card = await card_resolver.get_agent_card()
                    
                    remote_connection = RemoteAgentConnections(
                        agent_card=card, agent_url=address
                    )
                    self.remote_agent_connections[card.name] = remote_connection
                    self.cards[card.name] = card
                    logger.info(f"エージェント '{card.name}' ({address}) に接続しました")
                except httpx.ConnectError as e:
                    logger.error(f"エージェントカードの取得に失敗 {address}: {e}")
                except Exception as e:
                    logger.error(f"接続の初期化に失敗 {address}: {e}")
        
        # エージェント情報を文字列として構築
        agent_info = []
        for agent_detail_dict in self.list_remote_agents(): 
            agent_info.append(json.dumps(agent_detail_dict, ensure_ascii=False))
        self.agents = "\n".join(agent_info)

    @classmethod
    async def create(
        cls,
        remote_agent_addresses: List[str],
        task_callback=None,
    ):
        """BBQWeatherRoutingAgentのインスタンスを非同期で作成"""
        instance = cls(task_callback)
        await instance._async_init_components(remote_agent_addresses)
        return instance

    def list_remote_agents(self) -> List[Dict[str, Any]]:
        """接続されたリモートエージェントのリストを返す"""
        return [
            {
                "name": card.name,
                "description": card.description,
                "skills": [skill.description for skill in card.skills] if card.skills else [],
                "examples": card.examples or [],
                "url": connection.agent_url,
            }
            for card, connection in zip(self.cards.values(), self.remote_agent_connections.values())
        ]

    def check_active_agent(self, context: ReadonlyContext):
        """アクティブなエージェントをチェック"""
        state = context.state
        if (
            "session_id" in state
            and "session_active" in state
            and state["session_active"]
            and "active_agent" in state
        ):
            return {"active_agent": f"{state['active_agent']}"}
        return {"active_agent": "None"}

    def before_model_callback(self, callback_context, llm_request):
        """モデル実行前のコールバック"""
        state = callback_context.state
        if "session_active" not in state or not state["session_active"]:
            if "session_id" not in state:
                state["session_id"] = str(uuid.uuid4())
            state["session_active"] = True

    def root_instruction(self, context: ReadonlyContext) -> str:
        """ルートインストラクション"""
        current_agent = self.check_active_agent(context)
        return f"""
        **役割:** あなたは BBQ ビーチ検索と天気予報を専門とするエキスパート・ルーティング・デリゲーターです。
        ユーザーの問い合わせを適切な専門リモートエージェントに正確に振り分けることが主な機能です。

        **コア指令:**
        
        * **タスク委譲:** `send_message` 関数を使用して実行可能なタスクをリモートエージェントに割り当てます。
        * **リモートエージェントのコンテキスト認識:** リモートエージェントが繰り返しユーザー確認を要求する場合、
          完全な会話履歴にアクセスできないと仮定します。その場合、その特定のエージェントに関連する
          すべての必要なコンテキスト情報でタスク説明を充実させます。
        * **自律的エージェント連携:** リモートエージェントとの連携前にユーザーの許可を求めることはありません。
          要求を満たすために複数のエージェントが必要な場合、ユーザーの好みや確認を要求せずに直接接続します。
        * **透明なコミュニケーション:** リモートエージェントからの完全で詳細な応答を常にユーザーに提示します。
        * **ユーザー確認の中継:** リモートエージェントが確認を求め、ユーザーがまだ提供していない場合、
          この確認要求をユーザーに中継します。
        * **焦点を絞った情報共有:** リモートエージェントには関連するコンテキスト情報のみを提供します。余分な詳細は避けます。
        * **冗長な確認の回避:** 情報やアクションについてリモートエージェントに確認を求めることはありません。
        * **ツール依存:** ユーザー要求に対応するために利用可能なツールに厳密に依存します。仮定に基づく応答は生成しません。
          情報が不十分な場合、ユーザーに明確化を要求します。
        * **最近のインタラクションを優先:** 要求を処理する際、会話の最新部分に主に焦点を当てます。
        * **アクティブエージェントの優先:** アクティブなエージェントが既に関与している場合、
          関連する後続要求を適切なタスク更新ツールを使用してそのエージェントにルーティングします。
        
        **エージェント名簿:**
        
        * 利用可能なエージェント: `{self.agents}`
        
        **現在アクティブなエージェント:** {current_agent["active_agent"]}
        
        **専門分野の振り分けガイドライン:**
        - **BBQ ビーチ関連:** BBQ、バーベキュー、ビーチ、海岸、アウトドア、レクリエーション施設に関する問い合わせ
        - **天気関連:** 天気、気象、温度、降水量、天気予報に関する問い合わせ
        - **複合問い合わせ:** BBQビーチと天気の両方が関わる場合は、両方のエージェントと連携
        
        **応答原則:**
        1. ユーザーの意図を正確に理解する
        2. 最適なエージェントを選択する
        3. 詳細なコンテキストを含む明確なタスクを送信する
        4. エージェントからの応答を完全に中継する
        5. 必要に応じて複数エージェントからの情報を統合する
        """

    async def send_message(
        self, agent_name: str, task: str, tool_context: ToolContext
    ):
        """指定されたエージェントにメッセージを送信"""
        logger.info(f"エージェント '{agent_name}' にタスクを送信中: {task}")
        
        if agent_name not in self.remote_agent_connections:
            available_agents = list(self.remote_agent_connections.keys())
            return [
                {
                    "type": "text",
                    "text": f"エージェント '{agent_name}' が見つかりません。利用可能なエージェント: {', '.join(available_agents)}"
                }
            ]

        state = tool_context.state
        connection = self.remote_agent_connections[agent_name]
        
        # セッション管理
        session_id = state.get("session_id", str(uuid.uuid4()))
        task_id = str(uuid.uuid4())
        context_id = state.get("context_id", str(uuid.uuid4()))
        message_id = str(uuid.uuid4())

        # メタデータの設定
        metadata = {}
        if "input_message_metadata" in state:
            metadata.update(**state["input_message_metadata"])
            if "message_id" in state["input_message_metadata"]:
                message_id = state["input_message_metadata"]["message_id"]

        # ペイロード作成
        payload = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": task}],
                "messageId": message_id,
                "taskId": task_id,
            },
        }

        if context_id:
            payload["message"]["contextId"] = context_id

        try:
            # A2A クライアントでリモートエージェントと通信
            async with httpx.AsyncClient(timeout=60) as httpx_client:
                client = A2AClient(httpx_client, connection.agent_url)
                
                logger.info(f"エージェント {agent_name} にペイロードを送信: {payload}")
                response = await client.send_and_receive(payload)
                
                # アクティブエージェントを更新
                state["active_agent"] = agent_name
                
                logger.info(f"エージェント {agent_name} からの応答を受信")
                
                # 応答の解析
                resp = []
                json_content = response if isinstance(response, dict) else {}
                
                if json_content.get("result") and json_content["result"].get("artifacts"):
                    for artifact in json_content["result"]["artifacts"]:
                        if artifact.get("parts"):
                            resp.extend(artifact["parts"])
                
                return resp if resp else [{"type": "text", "text": "エージェントから応答がありませんでした。"}]

        except Exception as e:
            logger.error(f"エージェント {agent_name} との通信でエラー: {e}")
            return [
                {
                    "type": "text", 
                    "text": f"エージェント '{agent_name}' との通信中にエラーが発生しました: {str(e)}"
                }
            ]

    def create_agent(self) -> Agent:
        """ADK エージェントを作成"""
        return Agent(
            model="gemini-2.5-flash-preview-04-17",
            name="BBQ_Weather_Routing_Agent",
            instruction=self.root_instruction,
            before_model_callback=self.before_model_callback,
            description=(
                "BBQビーチ検索と天気予報を統合し、ユーザーの問い合わせを適切な専門エージェントに振り分けるルーティングエージェント"
            ),
            tools=[
                self.send_message,
            ],
        )
