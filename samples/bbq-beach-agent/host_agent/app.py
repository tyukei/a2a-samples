#!/usr/bin/env python3
"""
BBQ & Weather Host Agent with Gradio UI
BBQビーチと天気を統合するホストエージェントのWebUI
"""

import asyncio
import os
import logging
from typing import AsyncIterable

import gradio as gr
from dotenv import load_dotenv
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from agent import BBQWeatherRoutingAgent

# 環境変数をロード
load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 定数
APP_NAME = "BBQ Weather Host Agent"
USER_ID = "host_user_001"
SESSION_ID = "host_session_001"

# リモートエージェントのURL
REMOTE_AGENT_URLS = [
    "http://localhost:10003",  # BBQ Beach Agent
    "http://localhost:10001",  # Weather Agent
]

# グローバル変数
routing_agent = None
session_service = None


async def initialize_host_agent():
    """ホストエージェントを初期化"""
    global routing_agent, session_service
    
    try:
        logger.info("BBQ Weather Host Agent を初期化中...")
        
        # リモートエージェント接続の初期化
        routing_agent = await BBQWeatherRoutingAgent.create(
            remote_agent_addresses=REMOTE_AGENT_URLS
        )
        
        # ADK セッションサービスの初期化
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID
        )
        
        logger.info("ホストエージェントの初期化が完了しました")
        return True
        
    except Exception as e:
        logger.error(f"ホストエージェントの初期化に失敗: {e}")
        return False


async def get_response_from_agent(message: str, history) -> AsyncIterable[str]:
    """エージェントからの応答を取得（ストリーミング）"""
    global routing_agent, session_service
    
    if not routing_agent or not session_service:
        yield "❌ エージェントが初期化されていません。"
        return
    
    try:
        logger.info(f"ユーザーメッセージを処理中: {message}")
        
        # ADK エージェントを作成
        adk_agent = routing_agent.create_agent()
        
        # ランナーを作成
        runner = Runner(
            app_name=APP_NAME,
            agent=adk_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=session_service,
            memory_service=InMemoryMemoryService(),
        )
        
        # メッセージを送信してストリーミング応答を取得
        partial_response = ""
        async for event in runner.stream_events(
            user_id=USER_ID,
            session_id=SESSION_ID,
            message=message
        ):
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            partial_response += part.text
                            yield partial_response
                elif hasattr(event.content, 'text') and event.content.text:
                    partial_response += event.content.text
                    yield partial_response
        
        if not partial_response:
            yield "応答がありませんでした。"
            
    except Exception as e:
        logger.error(f"エージェント応答の取得でエラー: {e}")
        yield f"❌ エラーが発生しました: {str(e)}"


def create_gradio_interface():
    """Gradio UI を作成"""
    
    # カスタムCSS
    custom_css = """
    .main-header {
        text-align: center;
        background: linear-gradient(90deg, #4CAF50, #2196F3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5em;
        font-weight: bold;
        margin-bottom: 20px;
    }
    .agent-info {
        background-color: #f0f8ff;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 4px solid #2196F3;
    }
    .example-queries {
        background-color: #f9f9f9;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    """
    
    with gr.Blocks(
        title="BBQ Beach & Weather Host Agent",
        css=custom_css,
        theme=gr.themes.Ocean()
    ) as demo:
        
        # ヘッダー
        gr.HTML("""
            <div class="main-header">
                🏖️ BBQ Beach & Weather Host Agent 🌤️
            </div>
        """)
        
        # エージェント情報
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML("""
                    <div class="agent-info">
                        <h3>🏖️ BBQ Beach Agent</h3>
                        <p>BBQのできるビーチを検索し、詳細情報を提供</p>
                        <ul>
                            <li>BBQ設備のあるビーチ検索</li>
                            <li>料金・予約情報</li>
                            <li>アクセス方法</li>
                            <li>必要な持ち物</li>
                        </ul>
                    </div>
                """)
            
            with gr.Column(scale=1):
                gr.HTML("""
                    <div class="agent-info">
                        <h3>🌤️ Weather Agent</h3>
                        <p>天気予報と気象情報を提供</p>
                        <ul>
                            <li>現在の天気</li>
                            <li>週間天気予報</li>
                            <li>降水確率</li>
                            <li>気温・湿度</li>
                        </ul>
                    </div>
                """)
        
        # 例文
        with gr.Row():
            gr.HTML("""
                <div class="example-queries">
                    <h3>💡 利用例</h3>
                    <ul>
                        <li>「神奈川県でBBQのできるビーチを教えて」</li>
                        <li>「湘南の今日の天気は？」</li>
                        <li>「千葉でBBQをしたいけど、明日は晴れる？」</li>
                        <li>「BBQ用品のレンタルができて天気の良いビーチを探して」</li>
                        <li>「週末のBBQ計画を立てたい。おすすめのビーチと天気を教えて」</li>
                    </ul>
                </div>
            """)
        
        # チャットインターフェース
        chatbot = gr.ChatInterface(
            fn=get_response_from_agent,
            title="",
            description="BBQビーチ情報と天気予報を統合してお答えします。お気軽にお聞きください！",
            examples=[
                "神奈川県でBBQのできるビーチを教えて",
                "湘南の今日の天気は？",
                "千葉でBBQをしたいけど、明日は晴れる？",
                "BBQ用品のレンタルができて天気の良いビーチを探して",
                "週末のBBQ計画を立てたい。おすすめのビーチと天気を教えて"
            ],
            cache_examples=False,
            retry_btn="🔄 再試行",
            undo_btn="↩️ 取り消し",
            clear_btn="🗑️ クリア",
            submit_btn="📤 送信",
            stop_btn="⏹️ 停止"
        )
        
        # フッター
        gr.HTML("""
            <div style="text-align: center; margin-top: 20px; color: #666;">
                <p>🤖 Powered by Google A2A (Agent-to-Agent) Protocol</p>
                <p>BBQ Beach Agent (Port: 10003) | Weather Agent (Port: 10001)</p>
            </div>
        """)
    
    return demo


async def main():
    """メイン実行関数"""
    print("🏖️ BBQ Beach & Weather Host Agent を起動中...")
    
    # APIキーの確認
    if not os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE":
        print("❌ GOOGLE_API_KEY または GOOGLE_GENAI_USE_VERTEXAI=TRUE が設定されていません。")
        print("環境変数を設定してから再実行してください。")
        return
    
    # ホストエージェントの初期化
    if not await initialize_host_agent():
        print("❌ ホストエージェントの初期化に失敗しました。")
        print("リモートエージェントが起動していることを確認してください:")
        print("- BBQ Beach Agent: http://localhost:10003")
        print("- Weather Agent: http://localhost:10001")
        return
    
    print("✅ ホストエージェントの初期化が完了しました。")
    
    # Gradio インターフェースを作成・起動
    demo = create_gradio_interface()
    
    print("🌐 Web UIを起動中...")
    print("ブラウザで http://localhost:8084 にアクセスしてください")
    
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=8084,
        share=False,
        inbrowser=True
    )
    
    print("👋 BBQ Beach & Weather Host Agent を終了しました。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Host Agent を終了します...")
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        logging.error(f"Host Agent でエラー: {e}", exc_info=True)
