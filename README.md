# AI Quiz Generator
## 概要
競技クイズ用の高品質な問題文を自動生成し、AIによる校閲・評価を行うPythonスクリプトです。
ローカルLLM環境 (Ollama) とメタ検索エンジン (SearXNG) を活用し、指定したキーワードに関する事実に基づいたクイズを作成・厳選します。
## 特徴
- **検索連動**: SearXNGを用いて最新の情報を取得し、事実に基づいた精度の高いクイズを生成します。
- **ローカルLLM活用**: Ollama (`qwen3.5:4b`) を使用することで、APIコストをかけずに作問と評価をローカルで完結します。
- **自動評価システム**: 生成された問題を「事実の正確性」「構成の美しさ」「難易度の適切さ」の3つの基準で評価し、合格基準（140点以上/200点満点）を満たしたものだけをCSVに保存します。
- **メモリ最適化**: Ollamaのコンテキストウィンドウ (`num_ctx`) を調整し、メモリ消費を抑えつつ高速に処理を行います。
## 必要条件
- Python 3.8以上
- [Ollama](https://ollama.com/) がインストールされ、バックグラウンドで起動していること
- 利用モデル: `qwen3.5:4b`
## インストール手順
1. リポジトリをクローンまたはスクリプトをダウンロードします。
```bash
git clone [https://github.com/yourusername/ai-quiz-generator.git](https://github.com/yourusername/ai-quiz-generator.git)
cd ai-quiz-generator
```
2. Pythonライブラリをインストール
```bash
pip install ollama
```
3. Ollamaで必要なモデルをインストール
```bash
ollama pull qwen3.5:4b
```
