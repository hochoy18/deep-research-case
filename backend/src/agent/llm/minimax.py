from openai import OpenAI
import os

from agent.post import Post


class MiniMaxLLM:
    """
    MiniMax / MiniMax (OpenAI 兼容模式) LLM 客户端封装。

    MiniMax 的 chat/completions 接口与 OpenAI 完全兼容,
    因此直接复用 openai SDK,只换 base_url 与 model_id 即可。

    环境变量:
        MINIMAX_API_KEY   MiniMax API 访问密钥 (必填)
        MINIMAX_BASE_URL  MiniMax OpenAI 兼容模式入口,
                          默认 "https://api.MiniMax.chat/v1"

    模型示例 (按需替换 model_id):
        - MiniMax-Text-01            (通用文本)
        - abab6.5s-chat              (旧版对话)
        - MiniMax-Text-01-250528     (指定快照)
        ... 具体参考 MiniMax 官方文档

    使用示例:
        llm = MiniMaxLLM(model_id="MiniMax-Text-01")
        answer = llm.generate_response("你好,请你介绍一下自己。")
    """

    def __init__(self, model_id: str = "MiniMax-Text-01"):
        self.model_id = model_id

    def generate_response(self, query: str) -> str:
        client = OpenAI(
            api_key=os.getenv("MINIMAX_API_KEY"),
            base_url=os.getenv(
                "MINIMAX_BASE_URL", "https://api.MiniMax.chat/v1"
            ),
        )

        response = client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query},
            ],
        )
        # 去除 <think> 推理块,MiniMax 部分思考模型会输出此类标签
        return Post.strip_think_tags(response.choices[0].message.content)


if __name__ == "__main__":
    # 简单冒烟测试
    llm = MiniMaxLLM(model_id="MiniMax-Text-01")
    print(llm.generate_response("用一句话介绍 MiniMax 公司。"))
