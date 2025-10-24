# 【ファイル名: bot/collect_notes.py】
# (最終確定版 v13: 書き込みループ詳細ログ + requests + 時間指定 + ...)

import os
import requests
from datetime import datetime, timedelta, timezone
import config
import sys
from zoneinfo import ZoneInfo
import time
import traceback
# import json # 不要

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
        # mk = Misskey(...) # 不要

        # 1. 時間範囲計算 (変更なし)
        now_utc = datetime.now(timezone.utc)
        since_dt_utc = now_utc - timedelta(minutes=30)
        until_dt_utc = now_utc - timedelta(minutes=15)
        since_date_ms = int(since_dt_utc.timestamp() * 1000)
        until_date_ms = int(until_dt_utc.timestamp() * 1000)
        print(f"  収集範囲: {since_dt_utc.strftime('%Y/%m/%d %H:%M:%S')} UTC から {until_dt_utc.strftime('%Y/%m/%d %H:%M:%S')} UTC まで")

        # 2. requests で API 呼び出し (変更なし)
        print(f"  上記時間範囲のローカルタイムラインを取得します...")
        all_notes_raw = []
        current_until_id = None
        api_url = f"{config.MISSKEY_URL}/api/notes/local-timeline"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {config.MISSKEY_TOKEN}'
        }
        # (リトライ・ページネーションループ...)
        for page in range(5):
            notes_data = None
            payload = {
                'limit': 100,
                'sinceDate': since_date_ms,
                'untilDate': until_date_ms,
            }
            if current_until_id:
                payload['untilId'] = current_until_id
            for attempt in range(MAX_API_RETRIES):
                try:
                    # ...(API呼び出しログ)...
                    response = requests.post(api_url, headers=headers, json=payload, timeout=30)
                    response.raise_for_status()
                    notes_data = response.json()
                    # ...(API成功ログ)...
                    break
                except requests.exceptions.RequestException as api_e:
                    # ...(APIエラー・リトライログ)...
                    if attempt < MAX_API_RETRIES - 1:
                        time.sleep(RETRY_WAIT_SECONDS)
                    else:
                        print(f"    最大リトライ回数 ({MAX_API_RETRIES}) に達しました。")

            if notes_data is None or not isinstance(notes_data, list) or len(notes_data) == 0:
                print("    このページではノートが取得できませんでした。")
                break
            all_notes_raw.extend(notes_data)
            current_until_id = notes_data[-1]['id']

        if not all_notes_raw:
            print(f"[{datetime.now()}] 指定時間範囲に新しいノートはありませんでした。")
            return

        print(f"  合計 {len(all_notes_raw)} 件のノートを指定時間範囲から取得しました。")
        all_notes_raw.reverse()

        # 3. フィルタリング (変更なし)
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

        # --- ★★★ ここからが修正箇所 (詳細ログ出力) ★★★ ---
        # 4. ファイルに追記 (詳細ログ付き)
        print(f"  {len(valid_notes)} 件のノートのファイル追記処理を開始します...")

        formatted_entries = []
        processed_count = 0 # 実際に処理したノート数をカウント
        for i, note in enumerate(valid_notes):
            note_id_log = note.get('id', 'ID不明') # ログ用ID
            print(f"\n    処理中ノート {i+1}/{len(valid_notes)} (ID: {note_id_log})") # ★ ループ開始ログ
            try:
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
                print(f"      -> entry 作成成功。") # ★ entry 作成成功ログ
                formatted_entries.append(entry)
                processed_count += 1 # 処理成功カウント

            except Exception as loop_e:
                # ループ内で予期せぬエラーが発生した場合
                print(f"    ★★★ エラー: ノート {note_id_log} の処理中にエラーが発生しました ★★★")
                print(traceback.format_exc())
                print(f"    ★★★ このノートをスキップして処理を続行します ★★★")
                continue # 次のノートへ

        # --- ★★★ 詳細ログ修正ここまで ★★★ ---

        if not formatted_entries:
             print(f"[{datetime.now()}] entry 文字列を作成できたノートがありませんでした。")
             return

        print(f"\n  {len(formatted_entries)} 件の entry 文字列を作成しました。ファイルに書き込みます...") # ★ 書き込み直前ログ
        output_string = "\n\n".join(formatted_entries)

        with open(config.NOTE_DATA_FILE_PATH, 'a', encoding='utf-8') as f:
            f.seek(0, os.SEEK_END)
            file_is_empty = f.tell() == 0
            if not file_is_empty:
                f.write("\n\n")
            f.write(output_string)

        # 実際に処理・追記できた件数をログに出力
        print(f"[{datetime.now()}] {processed_count} 件のノートをファイルに追記しました。") # ★ processed_count を使用

    except Exception as e:
        print(f"[{datetime.now()}] 定期収集中に予期せぬエラーが発生しました:")
        print(traceback.format_exc())

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    execute_periodic_collection()
