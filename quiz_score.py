import json
import os
import re
import time
import urllib.parse
import urllib.request
import ollama
from quiz_config import MODEL_NAME, QUESTION_SYSTEM_PROMPT, EVALUATION_SYSTEM_PROMPT


EMPTY_RESPONSE_RETRIES = 3
EMPTY_RESPONSE_RETRY_DELAY = 1.0
DEBUG_RAW_RESPONSE = os.getenv("QUIZ_DEBUG", "0") == "1"
SEARCH_RESULT_MAX_CHARS = 250
QUESTION_MAX_TOKENS = 800
EVALUATION_MAX_TOKENS = 800


def search_searxng(keyword):
    instance_url = "https://searx.be"
    safe_keyword = urllib.parse.quote(keyword)
    url = f"{instance_url}/search?q={safe_keyword}&format=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        if "results" in data and len(data["results"]) > 0:
            extract = data["results"][0].get("content", "") or data["results"][0].get("snippet", "")
            return extract[:400] if extract else "情報が見つかりませんでした。"
        return "情報が見つかりませんでした。"
    except Exception as e:
        return f"検索エラー: {e}"


def _normalize_content(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", "") or item.get("content", ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    if isinstance(value, dict):
        return value.get("text", "") or value.get("content", "") or json.dumps(value, ensure_ascii=False)
    return str(value)


def _response_as_dict(resp):
    try:
        return resp.model_dump()
    except Exception:
        try:
            if isinstance(resp, dict):
                return resp
        except Exception:
            pass
    return None


def _debug_response_summary(resp):
    if not DEBUG_RAW_RESPONSE:
        return

    data = _response_as_dict(resp)
    if data is None:
        print(f"[DEBUG] raw_response_type={type(resp).__name__}")
        return

    top_keys = sorted(list(data.keys()))
    choices_len = len(data.get("choices", [])) if isinstance(data.get("choices"), list) else "N/A"
    finish_reason = None
    if isinstance(data.get("choices"), list) and data["choices"]:
        finish_reason = data["choices"][0].get("finish_reason")

    print(f"[DEBUG] response_keys={top_keys}")
    print(f"[DEBUG] choices_len={choices_len}, finish_reason={finish_reason}")


def extract_message_content(resp):
    data = _response_as_dict(resp)

    if data:
        choices = data.get("choices", [])
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message", {})
                if isinstance(msg, dict):
                    content = _normalize_content(msg.get("content"))
                    if content.strip():
                        return content
                text = _normalize_content(first.get("text"))
                if text.strip():
                    return text

        direct_candidates = [
            data.get("output_text"),
            data.get("response"),
            data.get("text"),
            data.get("content"),
        ]
        for candidate in direct_candidates:
            content = _normalize_content(candidate)
            if content.strip():
                return content

    try:
        content = _normalize_content(resp.choices[0].message.content)
        if content.strip():
            return content
    except Exception:
        pass

    return ""


def extract_json_text(raw_text):
    if not raw_text:
        return None

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

    match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if not match:
        return None
    return match.group(0)


def _chat_with_retry(messages, temperature, max_tokens, frequency_penalty=0.5, presence_penalty=1.4):
    """
    OpenAI互換クライアントからOllamaネイティブAPIに切り替え、
    沈黙エラーを回避しつつJSON出力とループ対策を行います。
    """
    for attempt in range(1, EMPTY_RESPONSE_RETRIES + 1):
        try:
            response = ollama.chat(
                model=MODEL_NAME, # quiz_config.py で定義しているモデル名
                messages=messages,
                format="json",  # ネイティブAPIでの正しいJSON強制方法

                # Ollama v0.9.0以降の公式な思考無効化パラメータ（※必要に応じてコメントアウトを外してください）
                think=False,

                # 教授提案のループ対策をOllama用のオプションに変換
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,  # max_tokens は num_predict として設定
                    "frequency_penalty": frequency_penalty,
                    "presence_penalty": presence_penalty,
                    "stop": ["\n\n\n", "Thought:"]
                }
            )
            content = response.message.content or ""
            if content.strip():
                return content, None

            if attempt < EMPTY_RESPONSE_RETRIES:
                time.sleep(EMPTY_RESPONSE_RETRY_DELAY)
        except Exception as e:
            if attempt >= EMPTY_RESPONSE_RETRIES:
                print(f"APIエラーが発生しました: {e}")
                return None, str(e)
            time.sleep(EMPTY_RESPONSE_RETRY_DELAY)

    return None, "空の応答が続いたため中断しました。"


def _shorten_search_result(search_result):
    if not search_result:
        return ""
    if len(search_result) <= SEARCH_RESULT_MAX_CHARS:
        return search_result
    return search_result[:SEARCH_RESULT_MAX_CHARS]


def create_question(search_result, target_answer, feedback=""):
    short_search_result = _shorten_search_result(search_result)
    user_prompt = f"""以下の入力内容をもとに、指定形式のJSONで問題を作成してください。

【参考情報】
{short_search_result}

【正解キーワード】
{target_answer}

【修正指示】
{feedback if feedback else "なし"}

【出力条件】
- 参考情報のみを使ってください。
- 出力はJSONのみとしてください。
- category, difficult, answer, question を必ず含めてください。
"""

    raw_text, err = _chat_with_retry(
        messages=[
            {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
        max_tokens=QUESTION_MAX_TOKENS,
        frequency_penalty=0.5,
        presence_penalty=1.4,
    )
    if err:
        return None, err

    json_text = extract_json_text(raw_text)
    if json_text is None:
        return None, "出力の中にJSONが見つかりませんでした。"

    try:
        quiz_data = json.loads(json_text)
        return quiz_data, None
    except json.JSONDecodeError:
        return None, "抽出した文字列のJSONパースに失敗しました。"


def evaluate_question(search_result, target_answer, question_text):
    short_search_result = _shorten_search_result(search_result)
    user_prompt = f"【参考情報】\n{short_search_result}\n【正解】\n{target_answer}\n【評価対象の問題文】\n{question_text}"

    raw_text, err = _chat_with_retry(
        messages=[
            {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=EVALUATION_MAX_TOKENS,
    )
    if err:
        return None, err

    json_text = extract_json_text(raw_text)
    if json_text is None:
        return None, "出力の中にJSONが見つかりませんでした。"

    try:
        eval_data = json.loads(json_text)
        return eval_data, None
    except json.JSONDecodeError:
        return None, "抽出した文字列のJSONパースに失敗しました。"