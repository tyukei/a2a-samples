#!/usr/bin/env python3
"""
BBQビーチエージェントのA2A テストクライアント
"""

import asyncio
import traceback
import httpx

from a2a.client.a2a_client import A2AClient

# BBQビーチエージェントサーバーのURL
AGENT_URL = 'http://localhost:10003'


async def run_single_turn_test(client: A2AClient) -> None:
    """単発テストを実行"""
    
    test_queries = [
        "神奈川県でBBQのできるビーチを探して",
        "湘南でバーベキューができる海岸を教えて",
        "千葉でBBQ設備のあるビーチはある？",
        "BBQ可能な海水浴場の予約方法を知りたい"
    ]
    
    print("BBQビーチエージェントの単発テストを開始します...")
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n=== テスト {i}/{len(test_queries)} ===")
        print(f"クエリ: {query}")
        print("-" * 50)
        
        try:
            # クエリを送信してストリーミング応答を受信
            async for chunk in client.stream(query):
                if hasattr(chunk, 'content') and chunk.content:
                    print(chunk.content, end='', flush=True)
                elif isinstance(chunk, dict) and 'content' in chunk:
                    print(chunk['content'], end='', flush=True)
                elif isinstance(chunk, str):
                    print(chunk, end='', flush=True)
                else:
                    print(f"[チャンク: {chunk}]", end='', flush=True)
            
            print("\n" + "=" * 50)
            
        except Exception as e:
            print(f"テスト {i} でエラーが発生: {e}")
            traceback.print_exc()
        
        # 次のテストまで少し待機
        if i < len(test_queries):
            await asyncio.sleep(1)


async def run_streaming_test(client: A2AClient) -> None:
    """ストリーミングテストを実行"""
    
    print("\nBBQビーチエージェントのストリーミングテストを開始します...")
    
    query = "神奈川県の海岸でBBQをしたいです。家族4人で利用予定で、駐車場があって、器材レンタルができる場所を教えてください。"
    
    print(f"詳細クエリ: {query}")
    print("-" * 80)
    
    try:
        chunk_count = 0
        async for chunk in client.stream(query):
            chunk_count += 1
            
            if hasattr(chunk, 'content') and chunk.content:
                content = chunk.content
            elif isinstance(chunk, dict) and 'content' in chunk:
                content = chunk['content']
            elif isinstance(chunk, str):
                content = chunk
            else:
                content = f"[未知のチャンク形式: {type(chunk)}]"
            
            print(f"[{chunk_count:03d}] {content}", flush=True)
        
        print(f"\n合計 {chunk_count} 個のチャンクを受信しました。")
        print("=" * 80)
        
    except Exception as e:
        print(f"ストリーミングテストでエラーが発生: {e}")
        traceback.print_exc()


async def main() -> None:
    """メイン関数"""
    print(f'BBQビーチエージェント（{AGENT_URL}）に接続中...')
    
    try:
        async with httpx.AsyncClient(timeout=30) as httpx_client:
            client = await A2AClient.get_client_from_agent_card_url(
                httpx_client, AGENT_URL
            )
            print('接続成功。')

            # 単発テストを実行
            await run_single_turn_test(client)
            
            # ストリーミングテストを実行
            await run_streaming_test(client)
            
            print("\n🎉 全てのテストが完了しました！")

    except Exception as e:
        traceback.print_exc()
        print(f'エラーが発生しました: {e}')
        print('エージェントサーバーが起動していることを確認してください。')
        print(f'サーバー起動コマンド: cd bbq_beach_agent && uv run .')


if __name__ == '__main__':
    asyncio.run(main())
