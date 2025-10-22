
import os
from misskey import Misskey
from datetime import datetime, timedelta
import config # config.py から秘密情報を読み込む
import sys

def save_last_post_id(note_id):
    """
    投稿したNote IDを、夜のリノート用にファイルに保存する
    """
    print(f"  リノート用: Note ID ({note_id}) をファイルに保存します...")
    try:
        if os.path.exists(config.LAST_POST_ID_FILE_PATH):
            os.remove(config.LAST_POST_ID_FILE_PATH)
            
        with open(config.LAST_POST_ID_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(str(note_id))
        print(f"  Note IDの保存に成功しました。")
        
    except Exception as e:
        print(f"  エラー: Note IDの保存に失敗しました: {e}")

def cleanup_summary_file():
    """
    投稿が完了した後、使用済みの要約ファイルを削除する
    """
    print(f"  クリーンアップ: 要約ファイルを削除します...")
    try:
        if os.path.exists(config.SUMMARY_DATA_FILE_PATH):
            os.remove(config.SUMMARY_DATA_FILE_PATH)
            print(f"  '{config.SUMMARY_DATA_FILE_PATH}' を削除しました。")
    except Exception as e:
        print(f"  要約ファイルのクリーンアップ中にエラー: {e}")

def execute_post():
    """
    要約ファイル読み込み、MisskeyにCWでローカル投稿するメイン関数
    """
    print("==============================================")
    print(f"Misskey要約ボット【投稿バッチ】開始: {datetime.now()}")
    print("==============================================")
    
    post_success = False
    new_note_id = None
    
    try:
        # 1. 要約ファイルを読み込む
        if not os.path.exists(config.SUMMARY_DATA_FILE_PATH):
            print(f"  エラー: 要約ファイル '{config.SUMMARY_DATA_FILE_PATH}' が見つかりません。")
            return False

        with open(config.SUMMARY_DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            summary_text = f.read()

        if not summary_text or not summary_text.strip():
            print(f"  エラー: 要約ファイルが空のため、投稿をスキップしました。")
            return False
            
        print("  要約ファイルの読み込みに成功しました。")

        # 2. Misskeyに投稿する
        mk = Misskey(config.MISSKEY_URL, i=config.MISSKEY_TOKEN)
        
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y/%m/%d')
        
        post_text = f"昨日のタイムライン ({date_str}) のまとめです。\n\n{summary_text}"
        cw_title = "$[tada.speed=0s :sushiski_news_sokuhou:]"

        if len(post_text) > 2900: 
             print(f"  エラー: 生成された投稿が長すぎます ({len(post_text)}文字)。投稿を中止しました。")
             return False

        print("  Misskeyに要約をCW（LTL/Public）投稿します...")
        
        created_note_response = mk.notes_create(
            text=post_text,
            visibility='public',
            cw=cw_title
        )
        
        
        new_note_id = created_note_response['createdNote']['id']
        
        
        print(f"[{datetime.now()}] 投稿に成功しました！ (Note ID: {new_note_id})")
        post_success = True
        return True

    except Exception as e:
        print(f"[{datetime.now()}] 投稿処理中にエラーが発生しました: {e}")
        return False

    finally:
        # 3. 後片付け
        if post_success and new_note_id:
            cleanup_summary_file()
            save_last_post_id(new_note_id)
            print(f"[{datetime.now()}] 投稿処理がすべて完了しました。")
        else:
            print(f"[{datetime.now()}] 投稿処理は失敗しました。")
        
        print("==============================================")


if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    execute_post()
