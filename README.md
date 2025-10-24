# Misskey LTL Summarizer AI Bot 🤖📈

## 概要

このプロジェクトは、特定のMisskeyインスタンスのローカルタイムライン（LTL）を定期的に収集し、Google Cloud Functions上のAI（Gemini）を利用して内容を要約、指定した時間に自動投稿するPython製のBotです。タイムラインの流れが速いサーバーでも、主要な話題を把握することを目的としています。

---

## 主な機能 ✨

* **LTLノート収集:** 指定した時間間隔でローカルタイムラインからノートを収集し、重複なく蓄積します。
* **AIによる要約:** Google Cloud Functions (Gen 2) 上の Gemini AI (例: `gemini-2.5-flash`) を利用し、収集したノート群を要約します。長文テキストに対応するため、MapReduce方式（チャンク分割・要約）を採用しています。
* **定時投稿:** cron等を利用し、指定した時間に要約結果をMisskeyに投稿します。
* **CW（コンテンツワーニング）投稿:** タイムラインへの配慮として、要約本文をCWで隠して投稿します。
* **自動リノート:** 投稿した要約ノートを、指定した時間に自動でリノート（自己RN）し、再度注目を集めます。
* **柔軟な設定:** MisskeyサーバーのURL、APIトークン、GCP FunctionのURL、除外ユーザーID、ファイルパスなどを設定ファイルで管理できます。

---

## 技術スタック 🛠️

* **言語:** Python 3.11+
* **主要ライブラリ:**
    * `requests`: Misskey APIとの直接通信に使用
    * `google-cloud-aiplatform`: Vertex AI (Gemini) との連携
* **プラットフォーム:**
    * Google Cloud Functions (Gen 2)
    * Vertex AI (Gemini Models)
* **その他:** cron (スケジューリング)

---


(cronでの実行例) ⏰
crontab -e 各スクリプトは、プロジェクトのルートディレクトリから実行することを想定しています。

 --- パス設定 (★★★ あなたの環境に合わせて変更してください ★★★) ---
 ログファイルを出力するディレクトリ (絶対パス)
LOG_DIR="/path/to/your/project/misskey_summarizer/logs"
 ボットのスクリプトがあるディレクトリ (絶対パス)
BOT_DIR="/path/to/your/project/misskey_summarizer/bot"
 Python仮想環境のPython実行ファイルのパス (絶対パス)
VENV_PYTHON="/path/to/your/project/misskey_summarizer/venv/bin/python3"

 --- 定期実行ジョブ ---
 1. 【収集】 15分ごと (0分, 15分, 30分, 45分) にノートを収集
*/15 * * * * $VENV_PYTHON $BOT_DIR/collect_notes.py >> $LOG_DIR/collect.log 2>&1

 2. 【要約】 毎日 朝4時00分 にAI要約を実行
0 4 * * * $VENV_PYTHON $BOT_DIR/summarize.py >> $LOG_DIR/summarize.log 2>&1

 3. 【投稿】 毎日 朝8時00分 にMisskeyへ要約を投稿
0 8 * * * $VENV_PYTHON $BOT_DIR/post_note.py >> $LOG_DIR/post.log 2>&1

 4. 【リノート】 毎日 夜20時00分 に朝の投稿を自己リノート
0 20 * * * $VENV_PYTHON $BOT_DIR/renote.py >> $LOG_DIR/renote.log 2>&1
注意: 上記のパス (LOG_DIR, BOT_DIR, VENV_PYTHON) は、ご自身の環境に合わせて必ず変更してください。


 主な実装の工夫点

AI要約 (MapReduce): summarize.py では、収集した大量のノートテキストをそのままAIに送るとエラーになるため、一定の文字数 (CHUNK_SIZE) で分割して個別に「部分要約」させ (Map)、最後にそれらを結合して「最終要約」を生成させる (Reduce) 方式を採用し、長文処理を実現しています。

Misskey API通信: collect_notes.py では、当初利用していた misskey.py ライブラリでノート取得漏れが発生したため、Python標準の requests ライブラリを用いてAPIエンドポイントを直接呼び出す方式に変更し、安定したデータ収集を実現しています。
