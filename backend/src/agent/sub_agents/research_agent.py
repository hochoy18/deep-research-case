"""ResearchAgent 子图。

封装了核心研究循环：

1. generate_queries — 将主题分解为搜索查询

2. web_search（并行扇出）— 搜索并汇总每个查询

3. critique — 评估信息是否充分；如有必要，则循环返回步骤 (1)

当评估认为信息充分或达到 max_research_loops 时，循环终止。
"""

from __future__ import annotations

import json

from dotenv import load_dotenv
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from loguru import logger

from agent.base_agent import Agent, JsonAgent, WebSearchAgent
from agent.configuration import Configuration
from agent.post import Post
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    reflection_instructions,
    web_searcher_instructions,
)
from agent.state import OverallState, QueryGenerationState, WebSearchState
from agent.tools_and_schemas import Reflection, SearchQueryList
from agent.utils import get_research_topic, resolve_urls

load_dotenv()

_GENERATE_QUERIES = "generate_queries"
_WEB_SEARCH = "web_search"
_CRITIQUE = "critique"


def _generate_queries(state: OverallState, config: RunnableConfig) -> dict:
    """将研究主题分解为独立的搜索查询。"""
    configurable = Configuration.from_runnable_config(config)
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries
    logger.info(f"[ResearchAgent] _generate_queries使用模型: {configurable.query_generator_model}")
    agent = JsonAgent(model_id=configurable.query_generator_model, keys=SearchQueryList)
    agent.set_step_prompt(query_writer_instructions)
    result = agent.step(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
        research_proposal=state.get("plan", ""),
    )
    logger.info(f"[ResearchAgent] 生成 {len(result.query)} 个查询: {result.query}")
    return {"search_query": result.query}


def _fan_out_to_web_search(state: QueryGenerationState) -> list[Send]:
    """Fan-out: 每个查询调用一次 web_search。"""
    return [
        Send(_WEB_SEARCH, {"search_query": q, "id": int(idx)})
        for idx, q in enumerate(state["search_query"])
    ]


def _web_search(state: WebSearchState, config: RunnableConfig) -> dict:
    """搜索单个查询并汇总结果。"""
    configurable = Configuration.from_runnable_config(config)
    searcher = WebSearchAgent()
    response = searcher.step(prompt=state["search_query"], count=10)

    if not response:
        logger.error(f"[ResearchAgent] 搜索结果为空： '{state['search_query']}'")
        return {
            "sources_gathered": [],
            "search_query": [state["search_query"]],
            "web_search_result": [f"未找到关于 '{state['search_query']}' 的搜索结果"],
        }

    # URL shortening
    long2short = resolve_urls(response, state["id"])
    sources = [
        {"short_url": long2short[item["url"]], "value": item["url"], "label": item["title"]}
        for item in response
    ]
    raw_results = json.dumps(
        [{"snippet": i["snippet"], "title": i["title"], "url": long2short[i["url"]]}
         for i in response],
        ensure_ascii=False, indent=4,
    )
    logger.info(f"[ResearchAgent] _web_search 使用模型: {configurable.query_generator_model}")
    agent = Agent(model_id=configurable.query_generator_model)
    agent.set_step_prompt(web_searcher_instructions)
    summary = agent.step(
        query=state["search_query"],
        current_date=get_current_date(),
        web_search_result=raw_results,
    )
    summary = Post.extract_pattern(summary, pattern="text")
    logger.info(f"[ResearchAgent] 已搜索： '{state['search_query']}'")

    return {
        "sources_gathered": sources,
        "search_query": [state["search_query"]],
        "web_search_result": [summary],
    }


def _critique(state: OverallState, config: RunnableConfig) -> dict:
    """评估收集到的信息是否充足。"""
    configurable = Configuration.from_runnable_config(config)
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model", '')  if state.get("reasoning_model",'') == '' else configurable.reflection_model
    logger.info(f"[ResearchAgent] _critique评估使用模型: {reasoning_model}")
    agent = JsonAgent(model_id=reasoning_model, keys=Reflection)
    agent.set_step_prompt(reflection_instructions)
    result = agent.step(
        current_date=get_current_date(),
        number_queries=state["initial_search_query_count"],
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_search_result"]),
        research_proposal=state.get("plan", ""),
    )
    logger.info(
        f"[ResearchAgent] 评估是否充足结果：{result.is_sufficient}, "
        f"gap='{result.knowledge_gap[:80]}...'"
    )
    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
        "max_research_loops": state.get("max_research_loops", configurable.max_research_loops),
    }


def _route_after_critique(state: OverallState, config: RunnableConfig):
    """Decide: loop back for more searches, or exit the sub-graph."""
    configurable = Configuration.from_runnable_config(config)
    max_loops = state.get("max_research_loops") or configurable.max_research_loops

    if state["is_sufficient"] or state["research_loop_count"] >= max_loops:
        logger.info(f"[ResearchAgent] 退出循环，已执行 {state['research_loop_count']} 次")
        return END  # ← exits sub-graph, parent takes over
    else:
        logger.info(f"[ResearchAgent] 继续循环 ({state['research_loop_count']}/{max_loops})")
        return [
            Send(_WEB_SEARCH,
                 {"search_query": q, "id": state["number_of_ran_queries"] + int(idx)})
            for idx, q in enumerate(state["follow_up_queries"])
        ]


_builder = StateGraph(OverallState, config_schema=Configuration)

_builder.add_node(_GENERATE_QUERIES, _generate_queries)
_builder.add_node(_WEB_SEARCH, _web_search)
_builder.add_node(_CRITIQUE, _critique)

_builder.add_edge(START, _GENERATE_QUERIES)
_builder.add_conditional_edges(_GENERATE_QUERIES, _fan_out_to_web_search, [_WEB_SEARCH])
_builder.add_edge(_WEB_SEARCH, _CRITIQUE)
_builder.add_conditional_edges(_CRITIQUE, _route_after_critique, [_WEB_SEARCH, END])

research_agent_graph = _builder.compile(name="ResearchAgent")

# if __name__ == "__main__":
#     from IPython.display import Image, display
#     try:
#         display(Image(research_agent_graph.get_graph().draw_mermaid_png(output_file_path="./ResearchAgent子图.png")))
#     except Exception:
#         pass