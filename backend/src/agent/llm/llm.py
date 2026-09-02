from openai import OpenAI
import os

from agent.post import Post


class OpenAICompatibleLLM:

    def __init__(self, model_id=""):
        self.model_id = model_id

    def generate_response(self, query):
        client = OpenAI(
            api_key=os.getenv('APP_TOKEN'),
            base_url=os.getenv("LLM_BASE_URL"),
        )

        response = client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": query
                }
            ],
            extra_body={"enable_thinking": False},
        )
        # 去除 <think> 推理块,避免 thinking 模型把过程文本带出来
        return Post.strip_think_tags(response.choices[0].message.content)