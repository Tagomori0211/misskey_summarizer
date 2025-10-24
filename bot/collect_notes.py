# 【ファイル名: bot/collect_notes.py】
# (最終確定版 v12: requestsで直接API呼び出し + 時間指定 + リアクション + メディア + リトライ)

import os
# ★ misskey ライブラリはもう使わない
import requests # ★ requests を使用
from datetime import datetime, timedelta, timezone
import config
import sys
from zoneinfo import ZoneInfo
import time
import traceback
# import json # json は requests が内部で使うので不要

# --- (JST, convert_to_jst は変更なし) ---
try:
    JST = ZoneInfo("Asia/Tokyo")
except Exception:
    print("エラー: 'zoneinfo' ライブラリ...")
    sys.exit(1)

def convert_to_jst(utc_str):
    if not utc_str: return None
    try:
        utc_dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
        jst_dt = utc_dt.astimezone(JST)
        return jst_dt.strftime('%Y/%m/%d %H:%M:%S')
    except Exception as e:
        print(f"  日付変換エラー: {e} (入力: {utc_str})")
        return None

# --- (リトライ関連の定数も変更なし) ---
MAX_API_RETRIES = 3
RETRY_WAIT_SECONDS = 5

def execute_periodic_collection():
    print(f"[{datetime.now()}] 定期ノート収集処理を開始します...")

    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        # ★ Misskey インスタンス作成は不要に

        # 1. 時間範囲計算 (変更なし)
        now_utc = datetime.now(timezone.utc)
        since_dt_utc = now_utc - timedelta(minutes=30)
        until_dt_utc = now_utc - timedelta(minutes=15)
        since_date_ms = int(since_dt_utc.timestamp() * 1000)
        until_date_ms = int(until_dt_utc.timestamp() * 1000)
        print(f"  収集範囲: {since_dt_utc.strftime('%Y/%m/%d %H:%M:%S')} UTC から {until_dt_utc.strftime('%Y/%m/%d %H:%M:%S')} UTC まで")

        # --- ★★★ ここからが修正箇所 (requests を使用) ★★★ ---
        # 2. requests で API を直接呼び出し (ページネーション対応)
        print(f"  上記時間範囲のローカルタイムラインを取得します...")
        all_notes_raw = []
        current_until_id = None
        api_url = f"{config.MISSKEY_URL}/api/notes/local-timeline" # APIエンドポイント
        headers = { # ヘッダー (認証トークン含む)
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.MISSKEY_TOKEN}'
        }

        for page in range(5): # 最大500件取得試行
            notes_data = None # ループごとにリセット
            payload = { # 送信するデータ
                'limit': 100,
                'sinceDate': since_date_ms,
                'untilDate': until_date_ms,
            }
            # 2ページ目以降は untilId を追加
            if current_until_id:
                payload['untilId'] = current_until_id

            for attempt in range(MAX_API_RETRIES):
                try:
                    print(f"    ページ {page+1}, 試行 {attempt+1}/{MAX_API_RETRIES}: API呼び出し...")
                    response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                    response.raise_for_status() # エラーチェック
                    notes_data = response.json() # JSONで結果を取得
                    print(f"    API呼び出し成功。{len(notes_data) if notes_data is not None else 0} 件取得。")
                    break
                except requests.exceptions.RequestException as api_e:
                    print(f"    エラー: API呼び出し中にエラー発生: {api_e}")
                    if attempt < MAX_API_RETRIES - 1:
                        print(f"    {RETRY_WAIT_SECONDS}秒待機してリトライします...")
                        time.sleep(RETRY_WAIT_SECONDS)
                    else:
                        print(f"    最大リトライ回数 ({MAX_API_RETRIES}) に達しました。")

            # API失敗 or データ0件 or リストでない場合はループ終了
            if notes_data is None or not isinstance(notes_data, list) or len(notes_data) == 0:
                print("    このページではノートが取得できませんでした。")
                break

            all_notes_raw.extend(notes_data)
            current_until_id = notes_data[-1]['id'] # 次のページ用にID更新
        # --- ★★★ requests 使用箇所ここまで ★★★ ---

        if not all_notes_raw:
            print(f"[{datetime.now()}] 指定時間範囲に新しいノートはありませんでした。")
            return

        print(f"  合計 {len(all_notes_raw)} 件のノートを指定時間範囲から取得しました。")
        all_notes_raw.reverse() # 古い順に並び替え

        # 3. フィルタリング (変更なし、安全アクセス版)
        print("  必要な情報を持つノートをフィルタリングします...")
        valid_notes = []
        for note in all_notes_raw:
            user_info = note.get('user')
            user_id = user_info.get('id') if user_info else None
            created_at = note.get('createdAt')
            note_id = note.get('id')

            if not user_id or not created_at or not note_id: continue
            if user_id == config.EXCLUDE_USER_ID: continue
            if note.get('renote'): continue
            valid_notes.append(note)

        if not valid_notes:
            print(f"[{datetime.now()}] フィルタリングの結果、追記するノートはありませんでした。")
            return

        # 4. ファイルに追記 (変更なし、安全アクセス版)
        print(f"  {len(valid_notes)} 件のノートをファイルに追記します...")
        formatted_entries = []
        for note in valid_notes:
            # (安全なデータ抽出...)
            user_info = note.get('user', {})
            user_name = user_info.get('name', user_info.get('username', '不明なユーザー'))
            post_time_jst = convert_to_jst(note.get('createdAt'))
            if not post_time_jst: post_time_jst = "不明な時間"
            text_value = note.get('text')
            post_content = text_value.strip() if isinstance(text_value, str) else ''
            reaction_count = note.get('reactionCount', 0)
            media_marker = ""
            files_list = note.get('files', [])
            if isinstance(files_list, list) and len(files_list) > 0:
                 media_marker = "\n[メディア付きノート]"

            # (entry 文字列作成...)
            entry = (
                "=========\n"
                f"[{user_name}]\n"
                f"[{post_time_jst}]\n"
                f"[{post_content if post_content else '(本文なし)'}]\n"
                f"[リアクション数: {reaction_count}]"
                f"{media_marker}\n"
                "========="
            )
            formatted_entries.append(entry)

        output_string = "\n\n".join(formatted_entries)
        # (ファイル書き込み...)
        with open(config.NOTE_DATA_FILE_PATH, 'a', encoding='utf-8') as f:
            f.seek(0, os.SEEK_END)
            file_is_empty = f.tell() == 0
            if not file_is_empty:
                f.write("\n\n")
            f.write(output_string)

        print(f"[{datetime.now()}] {len(valid_notes)} 件のノートをファイルに追記しました。")

    except Exception as e:
        print(f"[{datetime.now()}] 定期収集中に予期せぬエラーが発生しました:")
        print(traceback.format_exc())

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    execute_periodic_collection()
