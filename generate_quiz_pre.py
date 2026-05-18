import urllib.request
import urllib.parse
import json
import time
import csv
import ollama # ★変更1: openai から ollama に変更

def search_wikipedia(keyword):
    safe_keyword = urllib.parse.quote(keyword)
    url = f"https://ja.wikipedia.org/w/api.php?format=json&action=query&prop=extracts&exintro&explaintext&titles={safe_keyword}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        response = urllib.request.urlopen(req)
        data = json.loads(response.read())
        pages = data['query']['pages']
        for page_id in pages:
            if 'extract' in pages[page_id]:
                return pages[page_id]['extract'][:400]
        return "情報が見つかりませんでした。"
    except Exception as e:
        return f"検索エラー: {e}"

# ★変更2: client = OpenAI(...) の接続設定は不要になるため削除

target_answers = ["夏目漱石", "ウィーン会議", "徳川家康"]

csv_filename = "quiz_results_evaluated.csv"
with open(csv_filename, mode='w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["正解", "問題文"]) 

evaluation_system_prompt = """
あなたはプロのクイズ校閲者です。
生成された問題文が、競技クイズとして高品質か評価してください。
以下の3つの【評価基準】に従って10点満点で採点し、必ず指定されたJSON形式のみを出力してください。
【評価基準】1. 事実の正確性(4点) 2. 構成の美しさ(3点) 3. 難易度の適切さ(3点)
{
  "score": 総合点数,
  "reason": "その点数をつけた具体的な理由と改善点",
  "is_passed": trueかfalse（8点以上ならtrue）
}
"""

MAX_RETRIES = 3

for target_answer in target_answers:
    print(f"\n=======================================")
    print(f"【検索中】Wikipediaで「{target_answer}」を調べています...")
    search_result = search_wikipedia(target_answer)
    
    feedback = ""
    
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n--- 試行 {attempt}/{MAX_RETRIES} 回目 ---")
        
        # --- 1. 作問フェーズ ---
        system_prompt = """
        あなたはプロのクイズ作家です。提供された【参考情報】のみを使って問題文を作成し、必ず以下のJSON形式のみを出力してください。
        {
          "answer": "正解キーワード",
          "question": "「〜は何でしょう？」「〜は誰でしょう？」で終わる問題文"
        }
        """
        user_prompt = f"【参考情報】\n{search_result}\n\n「{target_answer}」を答えとする早押しクイズを作ってください。\n{feedback}"
        
        # ★変更3: ollama.chat を使い、options で num_ctx を 1024 に半減させる
        response = ollama.chat(
            model="qwen3.5:4b", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            format="json", # ★Ollamaネイティブの機能でJSON形式を強制
            options={
                "temperature": 0.6,
                "num_ctx": 1024 # ★ここが最適化の要！不要な記憶領域をカット
            }
        )
        
        # ★変更4: ollamaライブラリの形式に合わせて結果を取り出す
        raw_text = response['message']['content']
        
        try:
            quiz_data = json.loads(raw_text)
        except json.decoder.JSONDecodeError:
            print("=> ⚠️AIが無言、または形式エラーを起こしました。再生成します...")
            feedback = "\n【修正の指示】\n前回は正しいJSONが出力されませんでした。必ず指定したJSON形式のみを出力してください。"
            continue
        
        # --- 2. 評価フェーズ ---
        evaluation_user_prompt = f"【参考情報】\n{search_result}\n【正解】\n{target_answer}\n【評価対象の問題文】\n{quiz_data.get('question', '')}"
        
        # ★変更5: 評価用AIも同様に最適化する
        eval_response = ollama.chat(
            model="qwen3.5:4b", 
            messages=[
                {"role": "system", "content": evaluation_system_prompt},
                {"role": "user", "content": evaluation_user_prompt}
            ],
            format="json",
            options={
                "temperature": 0.1,
                "num_ctx": 1024 # ★評価時もメモリを節約
            }
        )
        
        eval_raw_text = eval_response['message']['content']
        
        try:
            eval_data = json.loads(eval_raw_text)
        except json.decoder.JSONDecodeError:
            print("=> ⚠️評価AIが形式エラーを起こしました。再生成します...")
            feedback = "\n【修正の指示】\n評価AIが判定に失敗しました。もう少し一般的なクイズらしい問題文にしてください。"
            continue
        
        print(f"問題文: {quiz_data.get('question', '')}")
        print(f"【スコア】 {eval_data.get('score', 0)} / 10点")
        print(f"【理　由】 {eval_data.get('reason', '')}")
        
        # --- 3. 合格・不合格の判定 ---
        if eval_data.get("is_passed"):
            print("=> ✨合格！CSVに保存します。")
            with open(csv_filename, mode='a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([quiz_data.get("answer", ""), quiz_data.get("question", "")])
            break 
            
        else:
            if attempt < MAX_RETRIES:
                print("=> ❌不合格。理由を元に再生成します...")
                feedback = f"\n【修正の指示】\n前回の問題は以下の理由で不合格でした。これを改善した新しい問題を作ってください。\n理由：{eval_data.get('reason', '')}"
            else:
                print("=> ⚠️不合格。最大試行回数に達したためスキップします。")
    
    time.sleep(2)

print(f"\nすべての処理が完了しました！")
