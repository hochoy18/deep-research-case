"""WriterAgent 子图。

概括了报告撰写流程：

1. 提纲 — 根据研究计划和材料设计章节结构

2. 草稿 — 为每个部分撰写内容

3. 引用与润色 — 将短链接替换为有效链接，修正格式，去除重复来源

这三步流程取代了原图中的单节点 final_answer，通过迭代改进生成更高质量的报告。
"""

from __future__ import annotations

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from loguru import logger

from agent.base_agent import Agent
from agent.configuration import Configuration
from agent.post import Post
from agent.prompts import (
    draft_instructions,
    get_current_date,
    outline_instructions,
    polish_instructions,
)
from agent.state import OverallState
from agent.utils import get_research_topic

load_dotenv()

_OUTLINE = "outline"
_DRAFT = "draft"
_CITE_AND_POLISH = "cite_and_polish"


def _outline(state: OverallState, config: RunnableConfig) -> dict:
    """根据研究主题和计划，生成结构化的报告大纲。"""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] outline using model={reasoning_model}")

    agent = Agent(
        name="报告大纲撰写Agent",
        model_id=reasoning_model)
    agent.set_step_prompt(outline_instructions)
    raw = agent.step(
        research_topic=get_research_topic(state["messages"]),
        research_proposal=state.get("plan", ""),
        summaries="\n---\n\n".join(state["web_search_result"]),
    )
    outline = Post.extract_pattern(raw, pattern="markdown")
    logger.info(f"[WriterAgent] outline 已生成 ({len(outline)} 字)")
    return {"report_outline": outline}


def _draft(state: OverallState, config: RunnableConfig) -> dict:
    """根据大纲撰写报告正文草稿。"""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] drafting using model={reasoning_model}")

    outline_text = state.get("report_outline", "")

    agent = Agent(
        name="报告草稿撰写Agent",
        model_id=reasoning_model)
    agent.set_step_prompt(draft_instructions)
    raw = agent.step(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        research_proposal=state.get("plan", ""),
        outline=outline_text,
        summaries="\n---\n\n".join(state["web_search_result"]),
    )
    draft = Post.extract_pattern(raw, pattern="markdown")
    logger.info(f"[WriterAgent] draft 已生成 ({len(draft)} 字)")
    return {"report_draft": draft}


def _cite_and_polish(state: OverallState, config: RunnableConfig) -> dict:
    """将短链接替换为真实链接，删除重复来源，润色语言。"""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"[WriterAgent] polishing using model={reasoning_model}")

    draft_text = state.get("report_draft", "")

    # Step A — LLM polish pass
    agent = Agent(
        name="报告润色Agent",
        model_id=reasoning_model)
    agent.set_step_prompt(polish_instructions)
    raw = agent.step(
        research_topic=get_research_topic(state["messages"]),
        draft=draft_text,
        summaries="\n---\n\n".join(state["web_search_result"]),
    )
    polished = Post.extract_pattern(raw, pattern="markdown")

    unique_sources = []
    for source in state.get("sources_gathered", []):
        if source["short_url"] in polished:
            polished = polished.replace(source["short_url"], source["value"])
            unique_sources.append(source)

    logger.info(f"[WriterAgent] 已润色 ({len(polished)} 字), {len(unique_sources)} 个引用来源")
    return {
        "messages": [AIMessage(content=polished)],
        "sources_gathered": unique_sources,
    }

_builder = StateGraph(OverallState, config_schema=Configuration)

_builder.add_node(_OUTLINE, _outline)
_builder.add_node(_DRAFT, _draft)
_builder.add_node(_CITE_AND_POLISH, _cite_and_polish)

_builder.add_edge(START, _OUTLINE)
_builder.add_edge(_OUTLINE, _DRAFT)
_builder.add_edge(_DRAFT, _CITE_AND_POLISH)
_builder.add_edge(_CITE_AND_POLISH, END)

writer_agent_graph = _builder.compile(name="WriterAgent")

if __name__ == "__main__":
    from IPython.display import Image, display
    try:
        display(Image(writer_agent_graph.get_graph().draw_mermaid_png(output_file_path="./WriterAgent子图.png")))
    except Exception:
        pass
