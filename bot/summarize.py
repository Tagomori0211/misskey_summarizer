import os
import requests
from datetime import datetime
import config # config.py から秘密情報を読み込む

# --- AIに指示するプロンプト（指示書） ---

# 1. 部分要約（Map）のためのプロンプト
PROMPT_FOR_CHUNK = """
あなたはMisskeyタイムラインの分析アシスタントです。
以下は、あるコミュニティの1日の投稿の一部（断片）です。
この断片から、特に重要と思われるトピックや会話を箇条書きで簡潔に抽出してください。
後で他の断片と結合されることを意識してください。

---
[テキスト]
"""

# 2. 最終要約（Reduce）のためのプロンプト
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

def get_summary_from_gcp(text, prompt):
    """
    GCPのAIサーバーに「テキスト」と「プロンプト」を送って、要約結果をもらう関数
    """
    if not text or not text.strip():
        print("  GCPリクエスト: テキストが空のためスキップします。")
        return None
    
    print(f"  GCPのAIにリクエストを送信します... (文字数: {len(text)})")
    headers = {'Content-Type': 'application/json'}
    
    # cloud_function/main.py が要求する 'text' と 'prompt' の両方をJSONで送る
    data = {'text': text, 'prompt': prompt} 
    
    try:
        # config.py のURLに、タイムアウト540秒（9分）でリクエスト
        response = requests.post(config.GCP_FUNCTION_URL, json=data, timeout=540)
        
        # なぜ？: 4xx (クライアントエラー) や 5xx (サーバーエラー) が発生したら、
        # ここでエラーを発生させて 'except' ブロックにジャンプさせます。
        response.raise_for_status() 
        
        print("  GCPからの要約取得に成功しました。")
        return response.text # AIが作った要約テキストを返す
    
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
    while current_pos < len(text):
        chunks.append(text[current_pos : current_pos + limit])
        current_pos += limit
    print(f"  {len(chunks)}個のチャンクに分割しました。")
    return chunks

def execute_summarize():
    """
    ノートを読み込み、MapReduce方式で要約を実行するメイン関数
    """
    print(f"[{datetime.now()}] 要約処理を開始します...")
    
    try:
        # 1. collect_notes.py が保存したノートテキストを読み込む
        if not os.path.exists(config.NOTE_DATA_FILE_PATH):
            print(f"  エラー: ノートファイル '{config.NOTE_DATA_FILE_PATH}' が見つかりません。")
            return False

        with open(config.NOTE_DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            notes_text = f.read()

        if not notes_text.strip():
            print(f"  エラー: ノートファイルは空でした。")
            return False

        # --- ここからが「Map-Reduce」ロジック ---

        # 2. [Map] テキストをチャンクに分割し、それぞれを「部分要約」する
        chunks = split_text(notes_text, config.CHUNK_SIZE)
        partial_summaries = [] # 部分要約を入れるリスト
        
        for i, chunk in enumerate(chunks):
            print(f"  チャンク {i+1}/{len(chunks)} を要約中...")
            
            # GCPに「部分要約プロンプト」でリクエスト
            partial_summary = get_summary_from_gcp(chunk, PROMPT_FOR_CHUNK)
            
            if partial_summary:
                partial_summaries.append(partial_summary)
            else:
                print(f"  チャンク {i+1} の要約に失敗しました。スキップします。")

        if not partial_summaries:
            print(f"  エラー: 全てのチャンクの要約に失敗したため、処理を中断します。")
            return False

        # 3. [Reduce] 全ての「部分要約」を一つにまとめ、それを「最終要約」する
        print(f"  全ての断片を結合して、最終的な要約を生成します...")
        
        # 部分要約同士も区切り文字でつなげる
        combined_summary_text = "\n\n--- (次の断片の要約) ---\n\n".join(partial_summaries)
        
        # GCPに「最終要約プロンプト」でリクエスト
        final_summary = get_summary_from_gcp(combined_summary_text, PROMPT_FOR_FINAL)

        if not final_summary:
            print(f"  エラー: 最終的な要約の生成に失敗しました。")
            return False

        # 4. 最終要約をファイルに保存する
        # なぜ？: post_note.py がこのファイルを読み込んで投稿するためです。
        with open(config.SUMMARY_DATA_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(final_summary)
        
        print(f"[{datetime.now()}] 最終要約をファイルに保存しました。")
        return True # 成功を伝える

    except Exception as e:
        print(f"[{datetime.now()}] 要約処理中に予期せぬエラーが発生しました: {e}")
        return False
