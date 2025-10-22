import os
import google.generativeai as genai
import functions_framework

# --- グローバル変数としてAIモデルを初期化 ---
# サーバー起動時に一度だけモデルを準備（ウォームアップ）しておきます。
try:
    # APIキーはコードに直書きせず、「環境変数」から読み込みます。
    # GCPデプロイ時に 'GEMINI_API_KEY' という名前でキーを設定します。
    API_KEY = os.environ.get("GEMINI_API_KEY")
    if not API_KEY:
        print("エラー: 環境変数 'GEMINI_API_KEY' が設定されていません。")
        raise ValueError("APIキーがありません")

    genai.configure(api_key=API_KEY)
    
    # 使用するAIモデルを指定
    generation_config = {
      "temperature": 0.7, # 創造性 (0.0-1.0)
      "top_p": 1,
      "top_k": 1,
      "max_output_tokens": 8192, # 最大出力トークン数
    }
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-001",
        generation_config=generation_config
    )
    print("AIモデル (gemini-1.5-flash-001) の初期化に成功しました。")

except Exception as e:
    print(f"AIモデルの初期化中に致命的なエラーが発生: {e}")
    model = None # エラーが発生したらモデルをNoneにしておく

@functions_framework.http
def summarize_text_handler(request):
    """
    HTTPリクエストを受け取って要約を実行するメインの関数
    """
    #  起動時の初期化に失敗した場合、関数が呼ばれても動かないようにします。
    if model is None:
        print("エラー: AIモデルが初期化されていないため、処理を実行できません。")
        return "AIモデルが利用不可能です。", 500

    try:
        # ボットサーバーから送られてくるJSONデータを取得
        request_json = request.get_json(silent=True)

        if not request_json:
            print("エラー: リクエストがJSONではありません。")
            return "JSONデータがありません。", 400

        # ボットから「テキスト」と「プロンプト」の2つを受け取る
        notes_text = request_json.get('text')
        prompt = request_json.get('prompt')

        #  どちらか一方でも欠けていたら、AIに何を指示すればいいか分からないためです。
        if not notes_text or not prompt:
            print("エラー: 'text' または 'prompt' がリクエストに含まれていません。")
            return "textとpromptの両方が必要です。", 400
        
        # 受け取ったプロンプトとテキストを組み合わせて、AIへの最終指示を作成
        final_prompt = f"{prompt}\n\n{notes_text}"

        # AIに要約を実行させる
        print(f"AI要約を開始します... (入力文字数: {len(final_prompt)}文字)")
        response = model.generate_content(final_prompt)
        
        print("AI要約が正常に完了しました。")
        # 要約結果（テキスト）だけをボットサーバーに返す
        return response.text, 200

    except Exception as e:
        #  AIの生成中 (generate_content) にエラーが起きる可能性があるためです。
        print(f"要約生成中にエラーが発生: {e}")
        return "要約の生成に失敗しました。", 500
