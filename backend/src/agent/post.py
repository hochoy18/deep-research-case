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
        pattern = re.compile(f"```{pattern}\s(.*?)```", re.DOTALL)
        matches = pattern.findall(text)
        return matches[0] if matches else text


if __name__ == "__main__":
    # ① 原 markdown 提取 case
    text = """```markdown
# 需求清晰度进度条: 60%

## 核心需求理解：
1. **核心目标**: 分析近一周（2025年6月10日-2025年6月17日）台湾媒体及国际舆论对第16届海峡论坛的报道观点，重点关注以下内容
- 台湾参加论坛的"热点人物"在岛内的舆论反应（如政治人物，团体代表）
- 民进党在舆论场中的斗争策略（如抹黑、限制、认知作战等）
- 论坛的潜在风险点（如两岸冲突、政治敏感性等）

2. **需求边界**
- **时间范围**：近一周（2025年6月10日-2025年6月17日）
- **主题范围**：台湾媒体（如TVBS、联合新闻网、中央社）及国际英文媒体（如Reuters、BBC）
- **分析重点**：舆论观点、政党观点、风险研判（非执行落地）。

## 待确认问题：
1. **时间范围**：是否严格限定为"近一周"，或可扩展至论坛前后两周（6月1日-6月17日）？
2. **热点人物**：是否有具体关注对象（如国民党代表团、民间团体领袖）？
3. **国际舆论**：需明确以英文为主，或包含其他语种（如日语、东南亚媒体）？
4. **风险点优先级**：需侧重政治风险、社会反应，还是舆情传播风险？

## 下一步：
请用户确认上述问题，或补充其他需求细节。若需求无调整，请基于当前理解开展分析。

（如需调整关键词或者范围，请直接告知），如需求清晰明了，请回复【需求确认】，我将进行报告生成任务，如果还存在问题，请直接说明。
```
"""
    output = Post.extract_pattern(text, "markdown")
    logger.info(output)

    # ② think 标签剥离 case
    samples = [
        "<think>推理内容...</think>真实答案",
        "<thinking>reasoning...</thinking>\n```json\n{\"answer\":42}\n```",
        "<Reasoning>跨行\n第二行\n第二行</Reasoning>正文",
        "<think>A</think><think>B</think>只有 A<think>中间</think>B 没了",
        "",
        "没有 think 标签就原样返回",
    ]
    for i, s in enumerate(samples, 1):
        print(f"\n[{i}] IN : {repr(s[:80])}...")
        print(f"[{i}] OUT: {repr(Post.strip_think_tags(s))[:120]}...")