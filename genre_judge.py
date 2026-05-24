import json
import re

import ollama

MODEL_NAME = "qwen3.5:4b"

CATEGORY_MAP = {
    "1": "歴史・地理",
    "2": "科学・数学",
    "3": "文学・言葉",
    "4": "アニメ・ゲーム",
    "5": "芸能・音楽",
    "6": "スポーツ",
    "7": "生活・グルメ",
    "8": "政治・経済",
    "9": "オールジャンル（判定なし）",
}

CATEGORY_HINTS = {
    "1": [
        "歴史", "地理", "日本史", "世界史", "戦国", "幕末", "江戸", "明治", "古代", "中世",
        "都道府県", "国", "首都", "地形", "山", "川", "海", "島", "大陸", "地名",
    ],
    "2": [
        "科学", "数学", "物理", "化学", "生物", "地学", "数学者", "公式", "定理", "関数",
        "数列", "確率", "微分", "積分", "原子", "分子", "元素",
    ],
    "3": [
        "文学", "言葉", "国語", "英語", "作者", "小説", "詩", "俳句", "短歌", "漢字",
        "慣用句", "ことわざ", "語源", "助詞", "文法",
    ],
    "4": [
        "アニメ", "ゲーム", "漫画", "キャラ", "キャラクター", "RPG", "FPS", "任天堂", "ソニー",
        "ポケモン", "マリオ", "ゼルダ", "ガンダム", "エヴァ", "作品",
    ],
    "5": [
        "芸能", "音楽", "歌手", "俳優", "女優", "アイドル", "バンド", "曲", "歌", "映画",
        "演歌", "J-POP", "クラシック", "ライブ", "アルバム", "テレビ",
    ],
    "6": [
        "スポーツ", "野球", "サッカー", "バスケット", "バレー", "テニス", "ゴルフ", "陸上",
        "相撲", "オリンピック", "大会", "選手", "監督", "リーグ", "記録",
    ],
    "7": [
        "生活", "グルメ", "料理", "食べ物", "飲み物", "レシピ", "食材", "和食", "洋食",
        "中華", "ファッション", "宗教", "暮らし", "家庭", "日用品",
    ],
    "8": [
        "政治", "経済", "法律", "社会", "政府", "議会", "選挙", "税", "景気", "会社",
        "金融", "株", "経済学", "外交", "制度", "政策",
    ],
}

GENRE_JUDGE_SYSTEM_PROMPT = """
あなたはクイズのジャンル判定AIです。
判定精度を最優先し、曖昧なら必ず false にしてください。

ルール:
- 与えられた単語が指定ジャンルに明確に属する場合のみ true
- 少しでも迷う場合は false
- 他ジャンル要素が強い、または一般名詞が広すぎる場合は false
- 連想でなく、直接の所属だけを判定する
- 出力は JSON のみ

出力形式:
{
  "is_match": true or false,
  "reason": "短い理由"
}
"""

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

def _chat_json(messages, temperature=0.0, max_tokens=120):
    response = ollama.chat(
        model=MODEL_NAME,
        messages=messages,
        format="json",
        think=False,
        options={
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    )
    return _normalize_content(response.message.content)

def _keyword_prefilter(target_answer, target_category_num):
    if target_category_num == "9":
        return None

    hints = CATEGORY_HINTS.get(target_category_num, [])
    if not hints:
        return None

    answer = target_answer.lower()
    for hint in hints:
        if hint.lower() in answer:
            return True, f"単語内にヒント語 '{hint}' を含むため"
    return None

def judge_genre(target_answer, target_category_name):
    target_category_num = None
    for key, value in CATEGORY_MAP.items():
        if value == target_category_name:
            target_category_num = key
            break

    prefilter = _keyword_prefilter(target_answer, target_category_num)
    if prefilter is not None:
        return prefilter[0], prefilter[1]

    user_prompt = f"""【単語】
{target_answer}

【判定ジャンル】
{target_category_name}

次の条件で判定してください。
- 直接そのジャンルに属する場合のみ true
- 迷ったら false
- 連想だけでは false
- 事実上別ジャンルなら false

出力は JSON のみ。
"""

    raw_text = _chat_json(
        messages=[
            {"role": "system", "content": GENRE_JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=120,
    )

    json_text = extract_json_text(raw_text)
    if json_text is None:
        return False, "JSONが取得できませんでした。"

    try:
        result = json.loads(json_text)
        is_match = bool(result.get("is_match", False))
        reason = str(result.get("reason", ""))
        return is_match, reason
    except json.JSONDecodeError:
        return False, "JSONパースに失敗しました。"