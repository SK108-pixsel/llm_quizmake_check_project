import urllib.request
import urllib.parse
import json
import time
import csv
import re
from openai import OpenAI


def search_searxng(keyword):
    instance_url = "https://searx.be"
    safe_keyword = urllib.parse.quote(keyword)
    url = f"{instance_url}/search?q={safe_keyword}&format=json"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        if 'results' in data and len(data['results']) > 0:
            extract = data['results'][0].get('content', '') or data['results'][0].get('snippet', '')
            return extract[:400] if extract else "情報が見つかりませんでした。"
        else:
            return "情報が見つかりませんでした。"
    except Exception as e:
        return f"検索エラー: {e}"


# OpenAI互換クライアント（OllamaのOpenAI互換エンドポイント向け）
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama",
)

target_answers = ["ウィーン会議"]

csv_filename = "quiz_results_evaluated.csv"
with open(csv_filename, mode='w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["正解", "問題文"])

evaluation_system_prompt = """
あなたはプロのクイズ校閲者です。
生成された問題文が、競技クイズとして高品質か評価してください。
以下の3つの【評価基準】に従って200点満点で採点し、必ず指定されたJSON形式のみを出力してください。
【評価基準】1. 事実の正確性(120点) 2. 構成の美しさ(30点) 3. 難易度の適切さ(50点)
{
  "score": 総合点数,
  "reason": "その点数をつけた具体的な理由と改善点",
  "is_passed": trueかfalse（140点以上ならtrue）
}
"""

MAX_RETRIES = 3


def _extract_message_content(resp):
    try:
        return resp.choices[0].message.content
    except Exception:
        try:
            return resp['choices'][0]['message']['content']
        except Exception:
            try:
                return resp.choices[0].message['content']
            except Exception:
                return str(resp)


for target_answer in target_answers:
    print(f"\n=======================================")
    print(f"【検索中】SearXNGで「{target_answer}」を調べています...")
    search_result = search_searxng(target_answer)

    feedback = ""

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- 試行 {attempt}/{MAX_RETRIES} 回目 ---")

        # --- 1. 作問フェーズ ---
        system_prompt = """
        あなたはプロのクイズ作家です。提供された【参考情報】のみを使って問題文を作成し、必ず以下のJSON形式のみを出力してください。
        {
          "category" : "カテゴリー番号",
          "difficult": "0~3",
          "answer": "正解キーワード",
          "question": "「〜は何でしょう？」等で終わる問題文"
        }
        """
        user_prompt = f"【参考情報】\n{search_result}\n\n「{target_answer}」を答えとする早押しクイズを作ってください。\n{feedback}"

        response = client.chat.completions.create(
            model="qwen3.5:4b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            frequency_penalty=0.5,
            presence_penalty=1.4,
            temperature=0.6,
            stop=["\n\n\n", "Thought:"],
            max_tokens=500,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": False}
            }
        )

        raw_text = _extract_message_content(response)

        try:
            quiz_data = json.loads(raw_text)
        except json.decoder.JSONDecodeError:
            print("=> ⚠️AIが無言、または形式エラーを起こしました。再生成します...")
            feedback = "\n【修正の指示】\n前回は正しいJSONが出力されませんでした。必ず指定したJSON形式のみを出力してください。"
            continue

        # --- 2. 評価フェーズ ---
        evaluation_user_prompt = f"【参考情報】\n{search_result}\n【正解】\n{target_answer}\n【評価対象の問題文】\n{quiz_data.get('question', '')}"

        eval_response = client.chat.completions.create(
            model="qwen3.5:4b",
            messages=[
                {"role": "system", "content": evaluation_system_prompt},
                {"role": "user", "content": evaluation_user_prompt}
            ],
            temperature=0.1,
            max_tokens=400,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": False}
            }
        )

        eval_raw_text = _extract_message_content(eval_response)

        # APIからの生テキストを取得
        raw_response = eval_raw_text

        # 正規表現で { から } までを抽出する安全装置
        match = re.search(r'\{.*\}', raw_response, re.DOTALL)

        if match:
            json_str = match.group(0)
            try:
                # 文字列をPythonの辞書に変換
                eval_data = json.loads(json_str)

                # 成功した場合の処理
                score = eval_data.get("score", 0)
                reason = eval_data.get("reason", "")
                is_passed = eval_data.get("is_passed", False)

            except json.JSONDecodeError:
                print("抽出した文字列のJSONパースに失敗しました。再生成します。")
                feedback = "\n【修正の指示】\n評価AIが判定に失敗しました。もう少し一般的なクイズらしい問題文にしてください。"
                continue
        else:
            print("出力の中にJSONが見つかりませんでした。再生成します。")
            feedback = "\n【修正の指示】\n評価AIが判定に失敗しました。もう少し一般的なクイズらしい問題文にしてください。"
            continue

        print(f"問題文: {quiz_data.get('question', '')}")
        print(f"【スコア】 {score} / 200点")
        print(f"【理　由】 {reason}")

        # --- 3. 合格・不合格の判定 ---
        if is_passed:
            print("=> ✨合格！CSVに保存します。")
            with open(csv_filename, mode='a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([quiz_data.get("answer", ""), quiz_data.get("question", "")])
            break
        else:
            if attempt < MAX_RETRIES:
                print("=> ❌不合格。理由を元に再生成します...")
                feedback = f"\n【修正の指示】\n前回の問題は以下の理由で不合格でした。これを改善した新しい問題を作ってください。\n理由：{reason}"
            else:
                print("=> ⚠️不合格。最大試行回数に達したためスキップします。")

    time.sleep(2)

print(f"\nすべての処理が完了しました！")
