import re
from loguru import logger

# 常见推理/思考模型会输出 <think>...</think> 这类标签,本项目统一剥离。
# 支持: think / thinking / reasoning / reflection,大小写不敏感,跨多行。
_THINK_PATTERN = re.compile(
    r"<(?:think|thinking|reasoning|reflection)>.*?</(?:think|thinking|reasoning|reflection)>",
    re.DOTALL | re.IGNORECASE,
)


class Post:
    @staticmethod
    def strip_think_tags(text: str) -> str:
        """
        移除 LLM 输出中的 <think>...</think> 类推理块。

        支持大小写、跨多行、多处成对出现;若 text 为空则原样返回。

        适用模型示例:
            - Qwen3 / QwQ / DeepSeek-R1 / GLM-Z1 / Doubao-1.5-thinking / MiniMax-Text-01(思考模式) 等
        """
        if not text:
            return text
        cleaned = _THINK_PATTERN.sub("", text)
        # 把 strip 后的多余空行压一下,避免产生双空行
        return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    @staticmethod
    def extract_pattern(text, pattern):
        # 先剥离 <think> 块,防止 JSON 边缘 case 失败
        text = Post.strip_think_tags(text)
        pattern = re.compile(rf"```{pattern}\s(.*?)```", re.DOTALL)
        matches = pattern.findall(text)
        return matches[0] if matches else text

