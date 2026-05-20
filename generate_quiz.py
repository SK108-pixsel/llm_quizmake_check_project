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
evaluation_schema = {
    "type": "object",
    "properties": {
        "score": {
            "type": "integer",
            "description": "200点満点での総合点数"
        },
        "reason": {
            "type": "string",
            "description": "その点数をつけた具体的な理由と改善点"
        },
        "is_passed": {
            "type": "boolean",
            "description": "140点以上ならtrue、それ未満ならfalse"
        }
    },
    "required": ["score", "reason", "is_passed"]
}
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
          "category" : "カテゴリーを選択します。
          1:自然科学:物理・化学・生物・地学
          2:歴史:日本史・世界史・地理歴史以外の歴史
          3:地理:地理・地誌
          4:社会:政治・経済・法律・社会問題
          5:芸術:文学・音楽・美術・映画・演劇
          6:言葉:国語・英語・その他の言語
          7:生活・文化:料理・スポーツ・ファッション・宗教・その他の文化
          8:その他" : "時事問題や雑学など、上記のどれにも当てはまらない問題はこちらに分類してください。",
          "difficult": "難易度を設定する。0~3の入力を求めます。
          0:小学6年生が分かるような答え
          1:中学3年生が分かるような答え
          2:高校3年生が分かるような答え
          3:大学卒業及び社会人が分かるような答え"
          "answer": "正解キーワード",
          "question": "「〜は何でしょう？」「〜は誰でしょう？」で終わる問題文"
          "example1" : "問題文と正解の例「大根やなた豆などの 7 種類の野菜を原料にして作られる、よくカレー
          の付け合わせとして食べられている漬物の一種は何でしょう？」正解「福神漬け」",
          "example2" : "問題文と正解の例「チャップリンら映画人も排除の対象とな/った、1950 年代前半のアメリ
          カでおこなわれた共産主義者を弾圧する運動を何というでしょう？正解「赤狩り」"
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
            think = False, # ★思考時間をカットして高速化
            format=evaluation_schema, # ★Ollamaネイティブの機能でJSON形式を強制
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
        print(f"【スコア】 {eval_data.get('score', 0)} / 200点")
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
