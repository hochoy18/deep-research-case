"""Unit tests for :mod:`agent.post`.

The original ``__main__`` block in ``post.py`` ran two demos by hand:
    ① ``Post.extract_pattern(text, "markdown")`` over a hard-coded sample
    ② ``Post.strip_think_tags`` over 6 ad-hoc strings
Those scripts are preserved here as module-level constants
(:data:`MARKDOWN_DEMO_TEXT`, :data:`THINK_TAG_SAMPLES`) so the previously
hand-verified behaviour is now regression-protected by pytest.
"""

from agent.post import Post


# ---------------------------------------------------------------------------
# Demo fixtures (lifted from post.py's old __main__ block)
# ---------------------------------------------------------------------------

MARKDOWN_DEMO_TEXT = """```markdown
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

THINK_TAG_SAMPLES = [
    "THINK_TAG0",
    "THINK_TAG1",
    "THINK_TAG2",
    "THINK_TAG3",
    "",
    "没有 think 标签就原样返回",
]

# Each entry corresponds to the real sample in post.py's old __main__ block.
# The literal angle-bracket tags below are why we keep them outside the
# list literal — Python source can't express `<thinking>...</thinking>` cleanly
# alongside the JSON we want, so we patch them in at import time via ``dict``.
THINK_TAG_SAMPLES[0] = "<" + "thinking>推理内容...真实答案"
THINK_TAG_SAMPLES[1] = "<" + "thinking>reasoning...</" + "thinking>\n```json\n{\"answer\":42}\n```"
THINK_TAG_SAMPLES[2] = "<" + "Reasoning>跨行\n第二行\n第二行</" + "Reasoning>正文"
THINK_TAG_SAMPLES[3] = "<" + "think>A<" + "/think><" + "think>B<" + "/think>只有 A<" + "think>中间<" + "/think>B 没了"



# ---------------------------------------------------------------------------
# extract_pattern
# ---------------------------------------------------------------------------


def test_extract_pattern_markdown_demo():
    """Old __main__ demo ①: extract the ``markdown`` fenced block."""
    output = Post.extract_pattern(MARKDOWN_DEMO_TEXT, "markdown")

    assert output.startswith("# 需求清晰度进度条: 60%")
    # Lazy quantifier keeps the trailing ``\n`` that precedes the closing fence.
    assert output.rstrip("\n").endswith("如果还存在问题，请直接说明。")
    assert output.endswith("\n")
    # The surrounding fence must be stripped off.
    assert "```" not in output
    # And the language tag must not leak into the body.
    assert not output.lstrip().startswith("markdown")


def test_extract_pattern_no_match_returns_original_text():
    """When no fenced block matches, the original text is returned untouched."""
    text = "plain text with no fenced block at all"
    assert Post.extract_pattern(text, "python") == text


def test_extract_pattern_multiple_matches_returns_first():
    """If the same fence appears multiple times, only the first body wins."""
    text = (
        "```markdown\nfirst body\n```\n"
        "some narration in between\n"
        "```markdown\nsecond body\n```"
    )

    output = Post.extract_pattern(text, "markdown")

    assert output == "first body\n"


def test_extract_pattern_supports_dotall_multiline_body():
    """``re.DOTALL`` must let ``.`` match newlines inside the body."""
    text = "```json\n{\n  \"a\": 1,\n  \"b\": 2\n}\n```"

    output = Post.extract_pattern(text, "json")

    assert output == '{\n  "a": 1,\n  "b": 2\n}\n'


def test_extract_pattern_only_matches_when_tag_is_followed_by_whitespace():
    """``f'```{tag}\\s...'`` requires whitespace after the language tag."""
    # No space after ``python`` -> pattern must NOT match.
    text = "```pythonprint('hi')\n```"

    output = Post.extract_pattern(text, "python")

    assert output == text


def test_extract_pattern_different_languages_are_isolated():
    """A ``python`` lookup must not accidentally grab a ``markdown`` block."""
    text = "```markdown\n# heading\n```\n```python\nprint('hi')\n```"

    output = Post.extract_pattern(text, "python")

    assert output == "print('hi')\n"


def test_extract_pattern_strips_think_tags_before_extraction():
    """``extract_pattern`` pre-strips think tags so JSON edge cases work.

    This is the integration contract documented inline in ``post.py``:
        "先剥离  块,防止 JSON 边缘 case 失败"
    """
    text = (
        "reasoning...\n"
        "```json\n{\"answer\": 42}\n```"
    )

    output = Post.extract_pattern(text, "json")

    # ``strip_think_tags`` removes the leading reasoning block before matching,
    # so the JSON fence is found cleanly.
    assert "reasoning" not in output
    assert output == '{"answer": 42}\n'


# ---------------------------------------------------------------------------
# strip_think_tags
# ---------------------------------------------------------------------------


def test_strip_think_tags_unpaired_open_tag_is_left_intact():
    """Old __main__ demo ② sample[0]: unpaired ``<think>`` is not stripped.

    The pattern requires a closing tag.  When the model emits only the opening
    half, ``strip_think_tags`` is a no-op — by design, otherwise it would
    silently swallow the rest of the output.
    """
    text = THINK_TAG_SAMPLES[0]

    out = Post.strip_think_tags(text)

    assert out == text
    assert "推理内容...真实答案" in out


def test_strip_think_tags_preserves_fenced_code_after_think():
    """Old __main__ demo ② sample[1]: fenced JSON must survive the strip."""
    text = THINK_TAG_SAMPLES[1]

    out = Post.strip_think_tags(text)

    assert "thinking" not in out
    assert "reasoning" not in out
    # The fenced JSON body is preserved verbatim.
    assert out == "```json\n{\"answer\":42}\n```"


def test_strip_think_tags_is_case_insensitive():
    """Old __main__ demo ② sample[2]: ``<Reasoning>`` must also be stripped."""
    text = THINK_TAG_SAMPLES[2]

    out = Post.strip_think_tags(text)

    assert "reasoning" not in out.lower()
    assert "正文" in out
    assert out == "正文"


def test_strip_think_tags_handles_multiple_pairs():
    """Old __main__ demo ② sample[3]: many pairs in one text."""
    text = THINK_TAG_SAMPLES[3]

    out = Post.strip_think_tags(text)

    # Three ``<think>...</think>`` blocks are eaten: A, B, 中间.
    assert out == "只有 AB 没了"


def test_strip_think_tags_empty_string_returns_empty():
    """Old __main__ demo ② sample[4]: ``""`` short-circuits to ``""``."""
    assert Post.strip_think_tags("") == ""


def test_strip_think_tags_returns_text_unchanged_when_no_think_tags():
    """Old __main__ demo ② sample[5]: no think tags → text passes through."""
    text = "没有 think 标签就原样返回"

    out = Post.strip_think_tags(text)

    assert out == text


def test_strip_think_tags_collapses_excess_blank_lines():
    """``\\n{3,}`` is collapsed to ``\\n\\n`` to avoid double blanks."""
    text = (
        "before"
        "\n\n\n\n\n"
        "after"
    )

    out = Post.strip_think_tags(text)

    # 5 blank lines (6 newlines total) must compress down to one blank line.
    assert out == "before\n\nafter"


def test_strip_think_tags_supports_all_documented_tag_names():
    """The four supported tags are: think, thinking, reasoning, reflection."""
    samples = {
        "think": "a",
        "thinking": "a",
        "reasoning": "a",
        "reflection": "a",
    }

    for tag, tail in samples.items():
        # Tail ``kept`` lives OUTSIDE the closing tag so the assertion is
        # meaningful (anything between <tag>...</tag> is swallowed).
        text = f"prefix<{tag}>swallow me</{tag}>{tail} suffix"
        out = Post.strip_think_tags(text)
        assert f"<{tag}" not in out, f"<{tag}> tag should be stripped, got {out!r}"
        assert "swallow me" not in out
        assert tail in out
