import os
from misskey import Misskey
from datetime import datetime, timedelta
import config # config.py から秘密情報を読み込む

def execute_post():
    """
    要約ファイル読み込み、Misskeyに投稿するメイン関数
    """
    print(f"[{datetime.now()}] 投稿処理を開始します...")

    try:
        # 1. summarize.py が作った要約ファイルを読み込む
        if not os.path.exists(config.SUMMARY_DATA_FILE_PATH):
            print(f"  エラー: 要約ファイル '{config.SUMMARY_DATA_FILE_PATH}' が見つかりません。")
            return False

        with open(config.SUMMARY_DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            summary_text = f.read()

        # なぜ？: AIが空の要約を返した場合、投稿する意味がないためチェックします。
        if not summary_text or not summary_text.strip():
            print(f"  エラー: 要約ファイルが空のため、投稿をスキップしました。")
            return False
            
        print("  要約ファイルの読み込みに成功しました。")

        # 2. Misskeyに投稿する
        mk = Misskey(config.MISSKEY_URL, i=config.MISSKEY_TOKEN)
        
        # 昨日の日付を "2025/10/21" のような形式で取得
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y/%m/%d')
        
        # 投稿する本文を作成
        post_text = f"$[x2 昨日のタイムライン ({date_str})]\n\n{summary_text}"

        # なぜ？: Misskeyのノート本文は10000文字などの制限があるため、
        # 念のため長すぎる場合はエラーを出して投稿を中止します。
        if len(post_text) > 2900: # (安全マージンを見て3000文字弱)
             print(f"  エラー: 生成された投稿が長すぎます ({len(post_text)}文字)。投稿を中止しました。")
             return False

        print("  Misskeyに要約を投稿します...")
        mk.notes_create(text=post_text, visibility='home') # LTLではなくHTLに投稿

        print(f"[{datetime.now()}] 投稿に成功しました！")
        return True

    except Exception as e:
        print(f"[{datetime.now()}] 投稿処理中にエラーが発生しました: {e}")
        return False
