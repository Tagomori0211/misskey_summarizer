import os
from misskey import Misskey
from datetime import datetime, timedelta, timezone
import config # config.py から秘密情報を読み込む

def execute_collection():
    """
    Misskeyサーバーからノートを収集し、ファイルに保存するメイン関数
    """
    print(f"[{datetime.now()}] ノート収集処理を開始します...")
    
    try:
        # なぜ？: dataフォルダがないとファイル保存に失敗するため、先に確認・作成します。
        os.makedirs(config.DATA_DIR, exist_ok=True)
        
        # config.py の情報を使ってMisskeyインスタンスを作成
        mk = Misskey(config.MISSKEY_URL, i=config.MISSKEY_TOKEN)
        
        # 24時間前の時刻を計算
        since_dt = datetime.now(timezone.utc) - timedelta(days=1)
        
        # ページネーション（複数回APIを叩いて全件取得）のための準備
        all_notes = []
        until_id = None # 取得する投稿の終点ID（最初は指定なし）
        
        print("ローカルタイムライン（LTL）の取得を開始します (最大500件)...")

        # なぜ？: 1回のAPI呼び出しは最大100件までのため、5回ループして最大500件を取得します。
        for _ in range(5): # 最大500件 (100件 * 5回)
            notes = mk.notes_local_timeline(
                limit=100,
                since_date=since_dt,
                until_id=until_id
            )
            
            if not notes:
                break # もう取得できるノートがなければループを抜ける

            all_notes.extend(notes) # 取得したノートをリストに追加
            until_id = notes[-1]['id'] # 次回取得時の開始地点をセット
            
            print(f"...現在 {len(all_notes)} 件取得")

        if not all_notes:
            print(f"[{datetime.now()}] 収集対象のノートはありませんでした。")
            return False # 失敗（ノート0件）を呼び出し元に伝える

        print(f"合計 {len(all_notes)} 件のノートを取得しました。")
        
        # 収集したノートからテキストだけを抽出
        # なぜ？: AIにはテキストだけ渡せばよく、リノート(RN)やCWは不要なため除外します。
        note_texts = [
            note['text'] 
            for note in all_notes 
            if note.get('text') and not note.get('renote') and not note.get('cw')
        ]

        if not note_texts:
            print(f"[{datetime.now()}] テキストを含むノートはありませんでした。")
            return False

        # 収集した全テキストを1つのファイルに書き出す
        # なぜ？: 'a' (追記) モードではなく 'w' (上書き) モードを使い、
        # 実行のたびにファイルが新しくなるようにします。
        with open(config.NOTE_DATA_FILE_PATH, 'w', encoding='utf-8') as f:
            # 投稿と投稿の間に区切り文字を入れて、AIが区別できるようにする
            f.write("\n\n--- (次のノート) ---\n\n".join(note_texts))

        print(f"[{datetime.now()}] {len(note_texts)} 件のノートテキストをファイルに保存しました。")
        return True # 成功を呼び出し元に伝える

    except Exception as e:
        print(f"[{datetime.now()}] ノート収集中にエラーが発生しました: {e}")
        return False # 失敗を呼び出し元に伝える
