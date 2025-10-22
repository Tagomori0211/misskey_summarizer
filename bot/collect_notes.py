# 【ファイル名: bot/collect_notes.py】
# (完全版: 重複排除 ＆ Bot除外 ＆ 新フォーマット ＆ メディア検出)

import os
from misskey import Misskey
from datetime import datetime
import config # config.py から秘密情報を読み込む
import sys
from zoneinfo import ZoneInfo # Python 3.9+ が必要

# JST（日本標準時）のタイムゾーンオブジェクトを定義
try:
    JST = ZoneInfo("Asia/Tokyo")
except Exception:
    print("エラー: 'zoneinfo' ライブラリが使用できません。Python 3.9 以上が必要か、'tzdata' パッケージ (pip install tzdata) が必要かもしれません。")
    sys.exit(1)

def convert_to_jst(utc_str):
    """
    UTCのISO文字列を 'YYYY/MM/DD HH:MM:SS' 形式のJST文字列に変換
    """
    try:
        # 'Z' (UTCを示す) を '+00:00' に置換して fromisoformat でパース
        utc_dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        # JSTに変換
        jst_dt = utc_dt.astimezone(JST)
        return jst_dt.strftime('%Y/%m/%d %H:%M:%S')
    except Exception as e:
        print(f"  日付変換エラー: {e} (入力: {utc_str})")
        return "不明な時間" # エラー時はフォールバック

def read_last_id():
    """
    「しおり」ファイルから、最後に取得したノートIDを読み込む
    """
    try:
        if os.path.exists(config.LAST_ID_FILE_PATH):
            with open(config.LAST_ID_FILE_PATH, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception as e:
        print(f"  警告: last_id ファイルの読み込みに失敗: {e}")
    return None # ファイルがないか、読めなければ None を返す

def write_last_id(note_id):
    """
    「しおり」ファイルに、最新のノートIDを書き込む
    """
    try:
        with open(config.LAST_ID_FILE_PATH, 'w', encoding='utf-8') as f:
            f.write(str(note_id))
    except Exception as e:
        print(f"  エラー: last_id ファイルの書き込みに失敗: {e}")


def execute_periodic_collection():
    """
    Misskeyサーバーから「前回の続き」のノートを収集し、ファイルに「追記」する
    """
    print(f"[{datetime.now()}] 定期ノート収集処理を開始します...")
    
    try:
        # dataフォルダがなければ作成
        os.makedirs(config.DATA_DIR, exist_ok=True)
        
        # config.py の情報を使ってMisskeyインスタンスを作成
        mk = Misskey(config.MISSKEY_URL, i=config.MISSKEY_TOKEN)
        
        # 1. 「しおり」ファイルから前回のIDを読み込む
        last_id = read_last_id()
        
        # 2. 初回実行時の処理
        if not last_id:
            print("  初回実行: 最新のノートIDをしおりとして保存します。")
            # タイムラインから最新のノートを1件だけ取得
            notes = mk.notes_local_timeline(limit=1)
            if notes:
                # そのIDを「しおり」として保存し、今回の収集はこれで終わる
                write_last_id(notes[0]['id'])
                print(f"  最新ID ({notes[0]['id']}) を保存しました。次回の実行から収集を開始します。")
            else:
                print("  ノートが1件も見つかりませんでした。")
            return

        # 3. 2回目以降の通常実行
        print(f"  前回のID [{last_id}] 以降のノートを取得します...")
        all_notes = []
        
        # since_id を使うと、APIは古い順（昇順）で返す
        for _ in range(5): # 最大500件 (100件 * 5回)
            # since_id は固定し、取得した最後のIDを last_id として更新し続ける
            notes = mk.notes_local_timeline(
                limit=100,
                since_id=last_id
            )
            
            if not notes:
                break # 新しいノートがなければループ終了
            
            all_notes.extend(notes) # [old...new] の順で溜まっていく
            last_id = notes[-1]['id'] # 次のループのために「今回取得した最新のID」をセット
        
        if not all_notes:
            print(f"[{datetime.now()}] 新しいノートはありませんでした。")
            return

        print(f"  合計 {len(all_notes)} 件の新しいノートを取得しました。")
        
        # 4. Bot自身を除外するフィルタリング
        filtered_notes = [
            note for note in all_notes
            if (
                note.get('text') and
                not note.get('renote') and
                not note.get('cw') and
                note['user']['id'] != config.EXCLUDE_USER_ID # BotのIDを除外
            )
        ]
        
        # 5. しおりの更新 (Botを除外する前に、取得した最新IDで更新)
        newest_id = all_notes[-1]['id'] # all_notes の末尾が取得した中で一番新しい
        write_last_id(newest_id)
        print(f"  しおり（last_id）を {newest_id} に更新しました。")

        if not filtered_notes:
            print(f"[{datetime.now()}] Botの投稿を除外した結果、新しいテキストノートはありませんでした。")
            return # 書き込むノートがないので終了

        # 6. ファイルに「追記」（新フォーマット ＆ メディア検出）
        print(f"  {len(filtered_notes)} 件のノートを新しい形式でファイルに追記します...")
        
        formatted_entries = []
        # filtered_notes は古い順（昇順）になっている
        for note in filtered_notes:
            # ユーザー名を取得 (表示名 or ユーザー名)
            user_name = note['user'].get('name', note['user']['username'])
            # JSTに変換
            post_time_jst = convert_to_jst(note['createdAt'])
            # 投稿内容 (前後の空白を除去)
            post_content = note['text'].strip()
            
            # --- メディア検出ロジック ---
            media_marker = "" # デフォルトは空
            # 'files' リストが存在し、かつ中身が0件より多いかチェック
            if note.get('files') and len(note['files']) > 0:
                media_marker = "\n[メディア付きノート]"
            # --- メディア検出ロジックここまで ---
            
            # しなりさん指定の形式で文字列を組み立てる
            entry = (
                "=========\n"
                f"[{user_name}]\n"
                f"[{post_time_jst}]\n"
                f"[{post_content}]"
                f"{media_marker}\n"  # メディアマーカー（改行含む）を追加
                "========="
            )
            formatted_entries.append(entry)

        # 結合する文字列を作成 (各エントリを空行1行 = \n\n で区切る)
        output_string = "\n\n".join(formatted_entries)

        with open(config.NOTE_DATA_FILE_PATH, 'a', encoding='utf-8') as f:
            # ファイルが空でないか（既に追記済みか）をチェック
            f.seek(0, os.SEEK_END) # ファイルポインタを末尾に
            file_is_empty = f.tell() == 0 # ポインタ位置が0なら空

            if not file_is_empty:
                # ファイルが空でないなら、追記する前に空行を入れる
                f.write("\n\n")
                
            f.write(output_string)

        print(f"[{datetime.now()}] {len(filtered_notes)} 件のノートをファイルに追記しました。")

    except Exception as e:
        print(f"[{datetime.now()}] 定期収集中にエラーが発生しました: {e}")

if __name__ == "__main__":
    # このスクリプトがあるディレクトリを import パスに追加
    # (cronで実行されたときに 'config' が見つかるようにするため)
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    execute_periodic_collection()
