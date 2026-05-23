import os
import random

MODEL_NAME = "qwen3.5:4b"
def get_random_answers(filename="labeled_entities.txt", num_questions=3):
    """テキストファイルからランダムに指定数の単語を抽出する"""
    if not os.path.exists(filename):
        # ファイルが配置されていない場合の安全装置
        print(f"⚠️ {filename} が見つかりません。デフォルトの単語を使用します。")
        return ["ウィーン会議"]
        
    with open(filename, "r", encoding="utf-8") as f:
        # 空行を無視して、92万語の単語をすべてリスト化する
        words = [line.strip() for line in f if line.strip()]
    
    # リストの中からランダムに num_questions 個選ぶ
    return random.sample(words, num_questions)
TARGET_ANSWERS = get_random_answers("labeled_entities.txt", 3)
CSV_FILENAME = "quiz_results_evaluated.csv"
MAX_RETRIES = 3

EVALUATION_SYSTEM_PROMPT = """
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

QUESTION_SYSTEM_PROMPT = """
あなたはプロのクイズ作家です。提供された【参考情報】のみを使って問題文を作成し、必ず以下のJSON形式のみを出力してください。
{
  "category": "1〜8のカテゴリ番号",
  "difficult": "0〜3の難易度",
  "answer": "正解キーワード",
  "question": "「〜は何でしょう？」「〜は誰でしょう？」で終わる問題文"
}

カテゴリは次から選んでください。
1: 自然科学 2: 歴史 3: 地理 4: 社会 5: 芸術 6: 言葉 7: 生活・文化 8: その他

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