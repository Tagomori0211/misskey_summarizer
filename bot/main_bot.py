import os
import sys
from datetime import datetime
import config # config.py から秘密情報を読み込む

# このスクリプトがあるディレクトリのパスを取得
# なぜ？: cronなどで実行された場合でも、他の .py ファイルを
# 正しく import (collect_notes など) できるようにするためのおまじないです。
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import collect_notes
import summarize
import post_note

def cleanup_files():
    """
    処理が終わった後、古いデータファイルを削除する関数
    """
    print(f"[{datetime.now()}] 古いデータファイルをクリーンアップします...")
    try:
        if os.path.exists(config.NOTE_DATA_FILE_PATH):
            os.remove(config.NOTE_DATA_FILE_PATH)
            print(f"  '{config.NOTE_DATA_FILE_PATH}' を削除しました。")
            
        if os.path.exists(config.SUMMARY_DATA_FILE_PATH):
            os.remove(config.SUMMARY_DATA_FILE_PATH)
            print(f"  '{config.SUMMARY_DATA_FILE_PATH}' を削除しました。")
            
    except Exception as e:
        print(f"  クリーンアップ中にエラーが発生しました: {e}")

def main():
    """
    ボットの全処理を順番に実行するメイン関数
    """
    print("==============================================")
    print(f"Misskey要約ボット処理開始: {datetime.now()}")
    print("==============================================")
    
    # 処理済みの古いファイルを先に削除する
    cleanup_files()
    
    # ステップ1: ノート収集
    if not collect_notes.execute_collection():
        print(f"[{datetime.now()}] ノート収集に失敗したため、処理を中断します。")
        return # 収集失敗ならここで終わり

    # ステップ2: 要約実行
    if not summarize.execute_summarize():
        print(f"[{datetime.now()}] 要約処理に失敗したため、処理を中断します。")
        return # 要約失敗ならここで終わり

    # ステップ3: Misskey投稿
    if not post_note.execute_post():
        print(f"[{datetime.now()}] 投稿処理に失敗しました。")
        return # 投稿失敗

    # ステップ4: すべて成功したら後片付け
    print(f"[{datetime.now()}] 全ての処理が正常に完了しました！")
    cleanup_files()
    print("==============================================")


if __name__ == "__main__":
    main()
