from __future__ import annotations

import ollama
from ollama import ResponseError

MODEL = "qwen2.5:7b-instruct"  # 换成你本地 `ollama list` 里已有的模型名

def chat_once(prompt: str) -> str:
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp["message"]["content"]
    except ResponseError as e:
        # 模型不存在时通常是 404，可自动拉取
        if getattr(e, "status_code", None) == 404:
            ollama.pull(MODEL)
            resp = ollama.chat(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp["message"]["content"]
        raise

def chat_stream(prompt: str) -> None:
    stream = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        print(chunk["message"]["content"], end="", flush=True)
    print()

if __name__ == "__main__":
    print(chat_once("用一句话解释什么是递归。"))
    chat_stream("给我一个 5 行以内的 Python 递归示例。")
