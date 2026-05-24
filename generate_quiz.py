import time
import csv
from quiz_config import TARGET_ANSWERS, CSV_FILENAME, MAX_RETRIES
from quiz_score import search_searxng, create_question, evaluate_question


with open(CSV_FILENAME, mode='w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["正解", "問題文", "カテゴリ", "難易度"])

for target_answer in TARGET_ANSWERS:
    print(f"\n=======================================")
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

        score = eval_data.get("score", 0)
        reason = eval_data.get("reason", "")
        is_passed = eval_data.get("is_passed", False)

        print(f"問題文: {quiz_data.get('question', '')}")
        print(f"【スコア】 {score} / 200点")
        print(f"【理　由】 {reason}")

        # --- 3. 合格・不合格の判定 ---
        if is_passed:
            print("=> ✨合格！CSVに保存します。")
            with open(CSV_FILENAME, mode='a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    quiz_data.get("answer", ""),
                    quiz_data.get("question", ""),
                    quiz_data.get("category", ""),
                    quiz_data.get("difficult", ""),
                ])
            break
        else:
            if attempt < MAX_RETRIES:
                print("=> ❌不合格。理由を元に再生成します...")
                feedback = f"\n【修正の指示】\n前回の問題は以下の理由で不合格でした。これを改善した新しい問題を作ってください。\n理由：{reason}"
            else:
                print("=> ⚠️不合格。最大試行回数に達したためスキップします。")

    time.sleep(2)

print(f"\nすべての処理が完了しました！")
