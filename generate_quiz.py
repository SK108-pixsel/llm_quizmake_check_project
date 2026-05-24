import os
import csv
import random
import time

from quiz_config import ALL_ENTITIES, CSV_FILENAME, MAX_RETRIES, TARGET_QUESTION_COUNT
from quiz_score import create_question, evaluate_question, search_searxng
from genre_judge import judge_genre, CATEGORY_MAP


def ensure_csv_file():
    if not os.path.exists(CSV_FILENAME) or os.path.getsize(CSV_FILENAME) == 0:
        with open(CSV_FILENAME, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["正解", "問題文", "カテゴリ", "難易度", "点数(200点満点)", "評価理由", "合格判定"])


ensure_csv_file()

print("=======================================")
print("作成したいクイズのジャンルを選択してください")
for key, value in CATEGORY_MAP.items():
    print(f" {key}: {value}")
print("=======================================")

selected_num = input("番号を入力 (1-9): ").strip()
target_category_name = CATEGORY_MAP.get(selected_num, "オールジャンル（判定なし）")
target_category_num = selected_num if selected_num in CATEGORY_MAP else "9"

print(f"\n→ カテゴリー【{target_category_num}: {target_category_name}】のクイズを作成します！\n")

questions_created = 0
attempts = 0
max_attempts = max(1, TARGET_QUESTION_COUNT * 20)

while questions_created < TARGET_QUESTION_COUNT and attempts < max_attempts:
    attempts += 1
    target_answer = random.choice(ALL_ENTITIES)

    if target_category_num == "9":
        is_match = True
        judge_reason = ""
    else:
        print(f"【判定中】単語ガチャ「{target_answer}」は「{target_category_name}」ですか？")
        is_match, judge_reason = judge_genre(target_answer, target_category_name)
        if not is_match:
            print(f"→ 判定NG: {judge_reason}")
            continue

    print("→ ✓ ジャンル一致！ クイズ作成を開始します。")
    print("\n=======================================")
    print(f"【検索中】SearXNGで「{target_answer}」を調べています...")
    search_result = search_searxng(target_answer)

    feedback = ""

    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- 試行 {attempt}/{MAX_RETRIES} 回目 ---")

        quiz_data, create_error = create_question(
            search_result,
            target_answer,
            feedback,
            target_category_num,
        )
        if create_error:
            print(f"=> ⚠️{create_error} 再生成します...")
            feedback = "\n【修正の指示】\n前回は正しいJSONが出力されませんでした。必ず指定したJSON形式のみを出力してください。"
            continue

        eval_data, eval_error = evaluate_question(
            search_result,
            target_answer,
            quiz_data.get("question", ""),
        )
        if eval_error:
            print(f"=> ⚠️{eval_error} 再生成します...")
            feedback = "\n【修正の指示】\n評価AIが判定に失敗しました。もう少し一般的なクイズらしい問題文にしてください。"
            continue

        question_text = quiz_data.get("question", "")
        category = quiz_data.get("category", "")
        difficult = quiz_data.get("difficult", "")
        score = eval_data.get("score", 0)
        reason = eval_data.get("reason", "")
        is_passed = eval_data.get("is_passed", False)

        print(f"問題文: {question_text}")
        print(f"【スコア】 {score} / 200点")
        print(f"【理　由】 {reason}")

        with open(CSV_FILENAME, mode="a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                target_answer,
                question_text,
                category,
                difficult,
                score,
                reason,
                is_passed,
            ])

        print(f"✓ CSVに保存しました。点数: {score}点 / 難易度: {difficult}")

        if is_passed:
            print("=> ✨合格！次の問題へ進みます。")
            questions_created += 1
            break
        else:
            if attempt < MAX_RETRIES:
                print("=> ❌不合格。理由を元に再生成します...")
                feedback = f"\n【修正の指示】\n前回の問題は以下の理由で不合格でした。これを改善した新しい問題を作ってください。\n理由：{reason}"
            else:
                print("=> ⚠️不合格。最大試行回数に達したためスキップします。")

    time.sleep(2)

print("\nすべての処理が完了しました！")