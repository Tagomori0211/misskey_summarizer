# 【ファイル名: cloud_function/main.py】
# (最終確定版: Gemini 2.5 Flash @ us-central1)

import os
import functions_framework

# 正しいGemini SDK（GenerativeModel）
import vertexai
from vertexai.generative_models import GenerativeModel

# --- AIモデルの初期化 ---
try:
    # ★ リージョンは、Gemini 2.5 が確実にある「us-central1」を指定
    PROJECT_ID = "sushisuki-summarizer-v2"
    LOCATION = "us-central1"
    vertexai.init(project=PROJECT_ID, location=LOCATION)

    # ★ しなりさんのGCPで利用可能な、最新の「2.5 Flash」を指定
    model = GenerativeModel(
        model_name="gemini-2.5-flash"
    )
    
    print("AIモデル (Gemini SDK: gemini-2.5-flash-latest @ us-central1) の初期化に成功しました。")

except Exception as e:
    print(f"AIモデルの初期化中に致命的なエラーが発生: {e}")
    model = None

@functions_framework.http
def summarize_text_handler(request):
    """
    HTTPリクエストを受け取って要約を実行するメインの関数
    """
    if model is None:
        print("エラー: AIモデルが初期化されていないため、処理を実行できません。")
        return "AIモデルが利用不可能です。", 500

    try:
        request_json = request.get_json(silent=True)
        if not request_json:
            return "JSONデータがありません。", 400

        notes_text = request_json.get('text')
        prompt = request_json.get('prompt')
        if not notes_text or not prompt:
            return "textとpromptの両方が必要です。", 400
        
        final_prompt = f"{prompt}\n\n{notes_text}"

        print(f"AI要約を開始します... (入力文字数: {len(final_prompt)}文字)")
        
        # 正しい .generate_content() 呼び出し
        response = model.generate_content(
            final_prompt,
            generation_config={
              "temperature": 0.7,
              "max_output_tokens": 8192,
              "top_p": 1,
              "top_k": 1
            }
        )
        
        print("AI要約が正常に完了しました。")
        return response.text, 200

    except Exception as e:
        print(f"要約生成中にエラーが発生: {e}")
        return "要約の生成に失敗しました。", 500
