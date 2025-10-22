# 【ファイル名: bot/renote.py】
# (cron で 1日1回, 例: 20:00 に実行)
# (朝8時に投稿したノートを自己リノートする)

import os
from misskey import Misskey
from datetime import datetime
import config # config.py から秘密情報を読み込む
import sys

def cleanup_id_file():
    """
    リノートが完了した後、使用済みのIDファイルを削除する
    """
    print(f"  クリーンアップ: Note ID ファイルを削除します...")
    try:
        if os.path.exists(config.LAST_POST_ID_FILE_PATH):
            os.remove(config.LAST_POST_ID_FILE_PATH)
            print(f"  '{config.LAST_POST_ID_FILE_PATH}' を削除しました。")
    except Exception as e:
        print(f"  Note ID ファイルのクリーンアップ中にエラー: {e}")

def execute_renote():
    """
    IDファイルを読み込み、Misskeyにリノートするメイン関数
    """
    print("==============================================")
    print(f"Misskey要約ボット【リノートバッチ】開始: {datetime.now()}")
    print("==============================================")
    
    renote_success = False
    try:
        # 1. 朝8時に保存されたIDファイルを読み込む
        if not os.path.exists(config.LAST_POST_ID_FILE_PATH):
            print(f"  エラー: リノート対象のIDファイル '{config.LAST_POST_ID_FILE_PATH}' が見つかりません。")
            return False

        with open(config.LAST_POST_ID_FILE_PATH, 'r', encoding='utf-8') as f:
            note_id = f.read().strip()

        if not note_id:
            print(f"  エラー: IDファイルが空です。")
            return False
            
        print(f"  リノート対象の Note ID ({note_id}) を読み込みました。")

        # 2. Misskeyにリノート（RN）する
        mk = Misskey(config.MISSKEY_URL, i=config.MISSKEY_TOKEN)
        
        print("  Misskeyに自己リノートを投稿します...")
        
        # renote_id を指定して投稿（本文は空）
        # RNは強制的に 'local' に流れる
        mk.notes_create(renote_id=note_id)

        print(f"[{datetime.now()}] リノートに成功しました！")
        renote_success = True
        return True

    except Exception as e:
        print(f"[{datetime.now()}] リノート処理中にエラーが発生しました: {e}")
        return False

    finally:
        # 3. 後片付け
        if renote_success:
            # ★ 使ったIDファイルを削除する
            cleanup_id_file()
            print(f"[{datetime.now()}] リノート処理がすべて完了しました。")
        else:
            print(f"[{datetime.now()}] リノート処理は失敗しました。IDファイルは削除されません。")
        
        print("==============================================")


if __name__ == "__main__":
    # このスクリプトが 'python3 bot/renote.py' として実行されたときに
    # 'execute_renote()' 関数を呼び出すための「入り口」
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    execute_renote()
