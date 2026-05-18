import urllib.request
import json
# OllamaのローカルAPIエンドポイントを指定します
url = "http://localhost:11434/api/generate"
# リクエストで送るデータ（対象モデルとプロンプト）を定義します
data = {
    "model": "qwen2.5-coder:latest",
    "prompt": "こんにちは、テスト通信です。短い挨拶を返してください。",
    "stream": False
}
# データをJSON形式に変換し、UTF-8でエンコードします
json_data = json.dumps(data).encode("utf-8")
# POSTリクエストを作成します
req = urllib.request.Request(url, data=json_data, headers={"Content-Type": "application/json"})
try:
    # サーバーにリクエストを送信し、レスポンスを受け取ります
    with urllib.request.urlopen(req) as response:
        # ステータスコードが200（成功）か確認します
        if response.status == 200:
            print("導通テスト成功！")
            # レスポンスデータを読み込み、JSONとしてパースします
            result = json.loads(response.read().decode("utf-8"))
            # モデルからの回答部分を出力します
            print("モデルからの回答: " + result["response"])
        else:
            print(f"サーバーからエラーが返されました。ステータスコード: {response.status}")
except Exception as e:
    # 通信エラーなどが発生した場合の処理です
    print(f"通信エラーが発生しました。詳細: {e}")
