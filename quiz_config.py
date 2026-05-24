import os
import random

MODEL_NAME = "qwen3.5:4b"


def load_entities(filename="labeled_entities.txt"):
    """テキストファイルから単語一覧を読み込む"""
    if not os.path.exists(filename):
        print(f"⚠️ {filename} が見つかりません。デフォルトの単語を使用します。")
        return ["ウィーン会議"]

    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def get_random_answers(filename="labeled_entities.txt", num_questions=3):
    """テキストファイルからランダムに指定数の単語を抽出する"""
    words = load_entities(filename)
    return random.sample(words, num_questions)


ALL_ENTITIES = load_entities("labeled_entities.txt")
TARGET_QUESTION_COUNT = 3
TARGET_ANSWERS = get_random_answers("labeled_entities.txt", TARGET_QUESTION_COUNT)
CSV_FILENAME = "quiz_results_evaluated.csv"
MAX_RETRIES = 3

EVALUATION_SYSTEM_PROMPT = """
あなたはプロのクイズ作家および校閲者です。
生成された問題文が、早押し競技クイズとして高品質かを評価してください。
以下の3つの【評価基準】に従って200点満点で厳密に採点し、必ず指定されたJSON形式のみを出力してください。

【評価基準】
1. 事実の正確性と限定性 (最高100点)
 - 【事実誤認】事実に反する情報や嘘が含まれていないか。
 - 【限定】他の答えが当てはまってしまう可能性を排除し、答えが完全に一つに確定できる条件が揃っているか。

2. 文章の構造と音声への配慮 (最高60点)
 - 【前フリと後限定】「あまり知られていない情報（前フリ）」から「有名な情報（後限定）」へと滑らかに移行しているか。
 - 【音声的配慮】耳で聞いて理解しやすいか。同音異義語や、音だけで分かりにくい熟語を避けているか。
 - 【簡潔さ】不要な修飾語がなく、情報密度が高くコンパクトにまとまっているか。

3. 難易度と面白さ (最高40点)
 - 【難易度】簡単すぎず難しすぎないか。
 - 【面白さ】前フリが単なる事実の羅列ではなく、後限定の答えを聞いたときに納得感や知的好奇心を刺激する面白さがあるか。

【出力形式（厳守）】
{
  "score": 総合点数（整数）,
  "reason": "1.正確性・限定性、2.文章構造、3.面白さ の各観点に基づいた点数の根拠と、より良くするための具体的な改善案",
  "is_passed": trueかfalse（160点以上ならtrue）
}
"""

QUESTION_SYSTEM_PROMPT = """
あなたはプロのクイズ作家です。提供された【参考情報】のみを使って問題文を作成し、必ず以下のJSON形式のみを出力してください。
{
  "category": "1〜9のカテゴリ番号",
  "difficult": "0〜3の難易度",
  "answer": "正解キーワード",
  "question": "「〜は何でしょう？」「〜は誰でしょう？」で終わる問題文"
}

カテゴリは次から選んでください。
1: 自然科学 2: 歴史 3: 地理 4: 社会 5: 芸術 6: 言葉 7: 生活・文化 8: その他
9: オールジャンル（判定なし）

難易度は次の基準で選んでください。
0: 小学6年生が分かる
1: 中学3年生が分かる
2: 高校3年生が分かる
3: 大学卒業及び社会人が分かる

出力例:
{
  "category": "2",
  "difficult": "1",
  "answer": "福神漬け",
  "question": "大根やなた豆などの7種類の野菜を原料にして作られ、よくカレーの付け合わせとして食べられている漬物の一種は何でしょう？"
}
 
出力例2:
{
  "category": "4",
  "difficult": "2",
  "answer": "バッキンガム宮殿",
  "question": "午前11 時から行われる衛兵交代の儀式/も有名な、イギリス国王がロン
ドンにおける住居として使用する宮殿は何でしょう？？"
}
"""