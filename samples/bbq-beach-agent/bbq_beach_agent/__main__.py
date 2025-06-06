#!/usr/bin/env python3
"""
BBQビーチエージェントのA2A対応メインエントリーポイント
"""

import os
import sys
from typing import Dict, Any, List
import asyncio
from contextlib import asynccontextmanager

import click
import uvicorn

from .agent import BBQBeachAgent
from .agent_executor import BBQBeachAgentExecutor
from dotenv import load_dotenv

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from a2a.server.tasks import InMemoryTaskStore

# MCPクライアントのインポート（実際のMCPツールが必要な場合）
# from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(override=True)

# BBQ検索用のMCPサーバー設定（プレースホルダー）
SERVER_CONFIGS = {
    # 実際の実装では、BBQ可能なビーチ検索用のMCPサーバーを設定
    # 例: Google Places API、Tripadvisor API、自作のビーチデータベースなど
}

app_context: Dict[str, Any] = {}


@asynccontextmanager
async def app_lifespan(context: Dict[str, Any]):
    """共有リソース（MCPクライアントとツール）のライフサイクルを管理"""
    
    # MCPツールを初期化
    try:
        # 実際の実装では、ここでBBQ検索用のMCPツールを初期化
        # 現在はモックモードで動作
        mcp_tools = []
        context["mcp_tools"] = mcp_tools
        print(f"BBQBeachAgent: {len(mcp_tools)}個のMCPツールをロードしました（現在はモックモード）")
        
        yield context
        
    except Exception as e:
        print(f"BBQBeachAgent MCPツールの初期化に失敗: {e}", file=sys.stderr)
        # モックモードで続行
        context["mcp_tools"] = []
        yield context
    finally:
        # クリーンアップ処理
        print("BBQBeachAgent MCPクライアントをシャットダウンしています...")


def get_agent_card(host: str, port: int):
    """BBQビーチエージェント用のエージェントカードを返す"""
    skill = AgentSkill(
        id="bbq_beach_search",
        name="BBQ Beach Search",
        description="BBQのできるビーチを検索し、詳細情報を提供します",
        tags=["bbq", "beach", "outdoor", "recreation", "japan"],
        examples=[
            "神奈川県でBBQのできるビーチを探して",
            "湘南でバーベキューができる海岸を教えて",
            "千葉でBBQ設備のあるビーチはある？",
            "BBQ可能な海水浴場の予約方法を知りたい"
        ],
    )

    return AgentCard(
        name="BBQ Beach Agent",
        description="BBQのできるビーチを専門的に検索し、詳細情報（料金、設備、予約方法、アクセス）を提供するエージェント",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=BBQBeachAgent.SUPPORTED_CONTENT_TYPES,
        defaultOutputModes=BBQBeachAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=AgentCapabilities(
            inputModes=BBQBeachAgent.SUPPORTED_CONTENT_TYPES,
            outputModes=BBQBeachAgent.SUPPORTED_CONTENT_TYPES,
            streaming=True,
        ),
        skills=[skill],
        examples=[
            "神奈川県でBBQのできるビーチを探して",
            "湘南でバーベキューができる海岸を教えて",
            "千葉でBBQ設備のあるビーチはある？",
            "BBQ可能な海水浴場の予約方法を知りたい"
        ],
    )


@click.command()
@click.option(
    "--host", "host", default="localhost", help="サーバーをバインドするホスト名"
)
@click.option(
    "--port", "port", default=10003, type=int, help="サーバーをバインドするポート番号"
)
@click.option("--log-level", "log_level", default="info", help="Uvicornログレベル")
def cli_main(host: str, port: int, log_level: str):
    """BBQビーチエージェントサーバーを起動するためのコマンドラインインターフェース"""
    
    # APIキーの確認（オプション - 現在はモックモードで動作可能）
    if not os.getenv("GOOGLE_API_KEY"):
        print("注意: GOOGLE_API_KEYが設定されていません。モックモードで動作します。", file=sys.stderr)
        # sys.exit(1) # モックモードでの動作を許可

    async def run_server_async():
        async with app_lifespan(app_context):
            if not app_context.get("mcp_tools"):
                print(
                    "警告: MCPツールがロードされていません。エージェントはモックモードで動作します。",
                    file=sys.stderr,
                )

            # プリロードされたツールでBBQBeachAgentExecutorを初期化
            bbq_beach_agent_executor = BBQBeachAgentExecutor(
                mcp_tools=app_context.get("mcp_tools", [])
            )

            request_handler = DefaultRequestHandler(
                agent_executor=bbq_beach_agent_executor,
                task_store=InMemoryTaskStore(),
            )

            # A2AServerインスタンスを作成
            a2a_server = A2AStarletteApplication(
                agent_card=get_agent_card(host, port), http_handler=request_handler
            )

            # A2AServerインスタンスからASGIアプリを取得
            asgi_app = a2a_server.build()

            config = uvicorn.Config(
                app=asgi_app,
                host=host,
                port=port,
                log_level=log_level,
            )
            
            server = uvicorn.Server(config)
            print(f"BBQビーチエージェントサーバーを {host}:{port} で起動しています...")
            await server.serve()

    try:
        asyncio.run(run_server_async())
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            print(
                "重大なエラー: asyncio.run()のネストが試行されました。これは防がれるべきでした。",
                file=sys.stderr,
            )
        else:
            print(f"cli_mainでRuntimeError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"cli_mainで予期しないエラーが発生しました: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()
