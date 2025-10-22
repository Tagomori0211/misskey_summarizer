# 【ファイル名: bot/summarize.py】
# (cron で 1日1回, 例: 04:00 に実行されることを想定)

import os
import requests
from datetime import datetime, timedelta
import config # config.py から秘密情報を読み込む
import sys # sys.path のために追加

# --- AIに指示するプロンプト（変更なし） ---
PROMPT_FOR_CHUNK = """
あなたはMisskeyタイムラインの分析アシスタントです。
以下は、あるコミュニティの1日の投稿の一部（断片）です。
この断片から、特に重要と思われるトピックや会話を箇条書きで簡潔に抽出してください。
後で他の断片と結合されることを意識してください。

---
[テキスト]
"""

PROMPT_FOR_FINAL = """
あなたはMisskeyタイムラインの分析アシスタントです。
以下に、あるコミュニティの1日の投稿を分割して要約した「要約の断片」が複数あります。

## 指示
これらの要約の断片をすべて統合し、その日のコミュニティ全体の出来事がわかるように、一つの最終的なレポートとしてまとめてください。
Misskeyで読みやすいように、重要なトピックを見出しにするなど、MFM(Misskey Flavored Markdown)を使って工夫してフォーマットしてください。

## MFMの例
- 見出し: `$[x2 見出し]`
- 太字: `**太字**`
- 引用: `> 引用`

## 要約の断片群
---
[テキスト]
"""

# --- 関数群（get_summary_from_gcp, split_text は変更なし） ---

def get_summary_from_gcp(text, prompt):
    """
    GCPのAIサーバーに「テキスト」と「プロンプト」を送って、要約結果をもらう関数
    """
    if not text or not text.strip():
        # なぜ？: 空のテキストをAIに送っても無駄なため、ここで処理を中断します。
        print("  GCPリクエスト: テキストが空のためスキップします。")
        return None
    
    print(f"  GCPのAIにリクエストを送信します... (文字数: {len(text)})")
    headers = {'Content-Type': 'application/json'}
    data = {'text': text, 'prompt': prompt} 
    
    try:
        # config.py で設定したURLとタイムアウト値でリクエスト
        response = requests.post(config.GCP_FUNCTION_URL, json=data, timeout=540)
        # なぜ？: 4xx (認証エラー等) や 5xx (AIサーバーエラー) が発生したら、エラーとして扱います。
        response.raise_for_status() 
        print("  GCPからの要約取得に成功しました。")
        return response.text
    
    except requests.exceptions.Timeout:
        print(f"  エラー: GCPへのリクエストがタイムアウトしました（9分以上かかりました）。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  エラー: GCPへのリクエスト中にエラーが発生しました: {e}")
        return None

def split_text(text, limit):
    """
    長いテキストを、だいたいlimit文字ずつの「断片（チャンク）」に分割する関数
    """
    print(f"  全文 (約{len(text)}文字) をチャンクに分割します...")
    chunks = []
    current_pos = 0
    # なぜ？: text の最後まで limit (CHUNK_SIZE) ずつスライスしてリストに追加します。
    while current_pos < len(text):
        chunks.append(text[current_pos : current_pos + limit])
        current_pos += limit
    print(f"  {len(chunks)}個のチャンクに分割しました。")
    return chunks


def cleanup_note_data_file():
    """
    要約が完了した後、使用済みのノート蓄積ファイルをバックアップ（リネーム）する
    """
    print(f"  クリーンアップ: ノート蓄積ファイルをバックアップします...")
    try:
        if os.path.exists(config.NOTE_DATA_FILE_PATH):
            # なぜ？: 削除(os.remove)するとデータが消えてしまいます。
            # デバッグ用に昨日の日付を付けてリネーム(os.rename)し、過去ログとして残します。
            yesterday = datetime.now() - timedelta(days=1)
            backup_name = config.NOTE_DATA_FILE_PATH + f".bak_{yesterday.strftime('%Y%m%d')}"
            os.rename(config.NOTE_DATA_FILE_PATH, backup_name)
            print(f"  '{config.NOTE_DATA_FILE_PATH}' を '{backup_name}' にバックアップしました。")
    except Exception as e:
        print(f"  ノートファイルのクリーンアップ中にエラー: {e}")

def execute_summarize():
    """
    ノートを読み込み、MapReduce方式で要約を実行するメイン関数
    """
    print("==============================================")
    print(f"Misskey要約ボット【要約バッチ】開始: {datetime.now()}")
    print("==============================================")
    
    final_summary = None # 成功したか判定するために、先んじて変数を定義
    try:
        # 1. 蓄積されたノートテキストを読み込む
        # なぜ？: config.py のパス設定を読み込みます。'bot/data/daily_notes.txt' を探します。
        if not os.path.exists(config.NOTE_DATA_FILE_PATH):
            print(f"  エラー: ノートファイル '{config.NOTE_DATA_FILE_PATH}' が見つかりません。")
            return False

        with open(config.NOTE_DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            notes_text = f.read()

        # なぜ？: 中身が空のファイルをAIに送っても無駄なため、ここで終了します。
        if not notes_text.strip():
            print(f"  エラー: ノートファイルは空でした。")
            return False

        # 2. [Map] チャンクに分割し、それぞれを「部分要約」
        chunks = split_text(notes_text, config.CHUNK_SIZE)
        partial_summaries = []
        
        for i, chunk in enumerate(chunks):
            print(f"  チャンク {i+1}/{len(chunks)} を要約中...")
            partial_summary = get_summary_from_gcp(chunk, PROMPT_FOR_CHUNK)
            if partial_summary:
                partial_summaries.append(partial_summary)

        # なぜ？: AIが全チャンクの要約に失敗した場合、最終要約が作れないため中断します。
        if not partial_summaries:
            print(f"  エラー: 全てのチャンクの要約に失敗したため、処理を中断します。")
            return False

        # 3. [Reduce] 「部分要約」を結合し、「最終要約」を生成
        print(f"  全ての断片を結合して、最終的な要約を生成します...")
        combined_summary_text = "\n\n--- (次の断片の要約) ---\n\n".join(partial_summaries)
        final_summary = get_summary_from_gcp(combined_summary_text, PROMPT_FOR_FINAL)

        # なぜ？: AIが最終要約の生成に失敗した場合、投稿するファイルが作れないため中断します。
        if not final_summary:
            print(f"  エラー: 最終的な要約の生成に失敗しました。")
            return False

        # 4. 最終要約をファイルに保存する
        # なぜ？: このファイルを、朝8時の post_note.py が読み取って投稿するためです。
        with open(config.SUMMARY_DATA_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(final_summary)
        
        print(f"[{datetime.now()}] 最終要約をファイルに保存しました。")
        return True # 成功を返す

    except Exception as e:
        print(f"[{datetime.now()}] 要約処理中に予期せぬエラーが発生しました: {e}")
        return False # 失敗を返す
    
    finally:
        # 5. 後片付け
        # なぜ？: 'final_summary' に中身がある ＝ 処理が成功した場合のみ、
        # 収集ファイルをバックアップし、次の日の収集に備えます。
        if final_summary:
            cleanup_note_data_file()
            print(f"[{datetime.now()}] 要約処理がすべて完了しました。")
        else:
            print(f"[{datetime.now()}] 要約処理は失敗しました。収集ファイルはバックアップされません。")
        
        print("==============================================")


if __name__ == "__main__":
    
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    # 要約処理を実行
    execute_summarize()
