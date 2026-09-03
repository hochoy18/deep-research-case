import json

from agent.tools_and_schemas import SearchQueryList, Reflection, PlanReflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
    plan_instructions,
    plan_reflection_instructions
)
from agent.post import Post
from agent.utils import (
    get_research_topic,
    get_last_user_response,
    resolve_urls,
)
from agent.base_agent import Agent, JsonAgent, WebSearchAgent
from loguru import logger
load_dotenv()

GENERATE_PLAN_NODE = "generate_plan"
GENERATE_SEARCH_NODE = "generate_search"
WEB_SEARCH_NODE = "web_search"
CRITIQUE_NODE = "critique"
FINAL_ANSWER_NODE = "final_answer"

# 节点定义
def generate_plan(state: OverallState, config: RunnableConfig)-> OverallState:
    """
    生成研究计划的LangGraph节点
    
    基于用户的问题和需求，使用LLM生成一个详细的研究计划。
    
    Args:
        state: 包含用户问题的当前图状态
        config: 可运行配置，包括LLM提供商设置
        
    Returns:
        包含计划状态更新的字典，包括plan和plan_status键
    """
    logger.info("正在生成计划...")
    if state.get("plan_status", "unconfirmed") != "unconfirmed":
        return {}

    configurable = Configuration.from_runnable_config(config)
    agent = Agent(model_id=configurable.query_generator_model)
    agent.set_step_prompt(plan_instructions)
    response = agent.step(
        current_date=get_current_date(),
        research_topic=get_research_topic(state.get("messages",[]), [msg.content for msg in state.get('plan_messages',[])]),
        research_proposal=state.get("plan", "")
    )
    response = Post.extract_pattern(response, pattern="markdown")
    logger.info(state)
    logger.info(response)

    return {"messages": [AIMessage(content=response)],
            "plan": response,
            "plan_status": "unconfirmed",
            "plan_messages": [AIMessage(content=response)]}

def evaluate_plan(state: OverallState, config: RunnableConfig)-> ReflectionState:
    """
    评估研究计划的LangGraph节点
    
    分析当前计划并根据用户反馈决定下一步行动：
    - 如果用户确认计划，继续生成查询
    - 如果用户需要修改计划，重新生成
    - 如果用户未确认，等待确认
    
    Args:
        state: 包含计划信息的当前图状态
        config: 可运行配置
        
    Returns:
        字符串字面量，指示下一个要访问的节点
    """
    configurable = Configuration.from_runnable_config(config)
    plan = state.get("plan", None)
    if state.get("plan_status", "unconfirmed") == "unconfirmed":
        logger.info("等待用户确认...")
        return "awaiting_plan_confirmation"

    if not plan:
        logger.info("没有计划需要评估。")
        return "replan"
    else:
        context = get_last_user_response(state["messages"])
        if "开始研究" in context:
            return GENERATE_SEARCH_NODE
        if "需求确认" in context:
            return GENERATE_SEARCH_NODE

        agent = JsonAgent(model_id=configurable.query_generator_model, keys=PlanReflection)
        agent.set_step_prompt(plan_reflection_instructions)
        result = agent.step(
            research_proposal=state.get("plan", ""),
            context=context,
        )
        if result.satisfy:
            return GENERATE_SEARCH_NODE
        return "replan"


def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """
    基于用户问题生成搜索查询的LangGraph节点
    
    使用LLM为用户的问题创建优化的网络搜索查询，用于网络研究。
    
    Args:
        state: 包含用户问题的当前图状态
        config: 可运行配置，包括LLM提供商设置
        
    Returns:
        包含状态更新的字典，包括search_query键，包含生成的查询
    """
    configurable = Configuration.from_runnable_config(config)
    logger.info(f"LangGraph节点开始运行.....，配置：[{config}]")
    # 检查自定义初始搜索查询数量
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    agent = JsonAgent(model_id=configurable.query_generator_model, keys=SearchQueryList)
    agent.set_step_prompt(query_writer_instructions)
    result = agent.step(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
        research_proposal=state.get("plan", "")
    )
    logger.info(f"生成待搜索内容.....{state}")
    logger.info(f"待搜索内容生成结果: {result}")
    return {"search_query": result.query}


def send_to_web_search(state: QueryGenerationState):
    """
    将搜索查询发送到web_search节点的LangGraph节点

    用于为每个搜索查询生成n个网络研究节点，实现并行搜索。

    Args:
        state: 包含搜索查询的查询生成状态

    Returns:
        发送到web_search节点的消息列表
    """
    logger.info(f"准备发送请求给网络搜索节点......")
    return [
        Send(WEB_SEARCH_NODE, {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["search_query"])
    ]


def web_search(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """
    使用web search agent执行网络搜索的节点
    Args:
        state: 包含搜索查询和研究循环计数的当前图状态
        config: 可运行配置，包括搜索API设置

    Returns:
        包含状态更新的字典，包括sources_gathered、research_loop_count和web_search_results
    """
    logger.info(f"开始网络搜索......")
    # 配置
    configurable = Configuration.from_runnable_config(config)
    web_searcher = WebSearchAgent()

    # 执行搜索
    response = web_searcher.step(prompt=state["search_query"],
                                 count=10)
    
    # 检查搜索结果是否为空或None
    if not response or response is None:
        logger.error(f"网络搜索返回为空: {state['search_query']}")
        return {
            "sources_gathered": [],
            "search_query": [state["search_query"]],
            "web_search_result": [f"未找到关于 '{state['search_query']}' 的搜索结果"],
        }
    
    # 长URL到短URL的映射
    long2short_url_mappings = resolve_urls(response, state["id"])
    sources_gathered = [{"short_url": long2short_url_mappings[item["url"]], "value": item["url"], "label": item["title"]} for item in response]
    web_search_result = [{"snippet": item["snippet"], "title": item["title"], "url": long2short_url_mappings[item["url"]]} for item in response]
    web_search_result = json.dumps(web_search_result, ensure_ascii=False, indent=4)

    agent = Agent(model_id=configurable.query_generator_model)
    agent.set_step_prompt(web_searcher_instructions)
    modified_text = agent.step(query=state["search_query"], current_date=get_current_date(), web_search_result=web_search_result)
    modified_text = Post.extract_pattern(modified_text, pattern="text")

    logger.info(f"搜索标题: {state['search_query']}")
    logger.debug(f"网络搜索结果: {modified_text}")
    return {
        "sources_gathered": sources_gathered,
        "search_query": [state["search_query"]],
        "web_search_result": [modified_text],
    }


def critique(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """
    识别知识差距并生成潜在后续查询的节点

    分析当前摘要以识别需要进一步研究的领域，并生成潜在的后续查询。
    使用结构化输出来提取JSON格式的后续查询。

    Args:
        state: 包含运行摘要和研究主题的当前图状态
        config: 可运行配置，包括LLM提供商设置

    Returns:
        包含状态更新的字典，包括search_query键，包含生成的后续查询
    """
    logger.info(f"反思分析识别知识差距并生成潜在后续查询的节点工作......")
    configurable = Configuration.from_runnable_config(config)
    # 增加研究循环计数并获取推理模型
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model", configurable.reflection_model)
    logger.info(f"critique反思节点模型：{reasoning_model}")

    # 格式化提示
    agent = JsonAgent(model_id=reasoning_model, keys=Reflection)
    agent.set_step_prompt(reflection_instructions)
    result = agent.step(
        current_date=get_current_date(),
        number_queries=state["initial_search_query_count"],
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_search_result"]),
        research_proposal=state.get("plan", "")
    )

    logger.info(f"反思分析：{result}")
    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
        "max_research_loops": state.get("max_research_loops", configurable.max_research_loops),
    }


def route_evaluate(
    state: ReflectionState,
    config: RunnableConfig,
) -> OverallState:
    """
    确定research中下一步的路由函数

    通过决定是否继续收集信息状态"is_sufficient"或基于配置的最大research循环次数来最终确定摘要，
    从而控制research循环。

    Args:
        state: 包含研究循环计数的当前图状态
        config: 可运行配置，包括max_research_loops设置

    Returns:
        字符串字面量，指示下一个要访问的节点（"web_research"或"finalize_summary"）
    """
    logger.info("准备评估当前研究......")
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )

    logger.info(state)
    logger.info(f"最大研究循环数: {max_research_loops}")
    logger.info(f"当前已研究次数: {state['research_loop_count']}")
    if state["is_sufficient"] or state["research_loop_count"] >= max_research_loops:
        return FINAL_ANSWER_NODE
    else:
        return [
            Send(
                WEB_SEARCH_NODE,
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


def final_answer(state: OverallState, config: RunnableConfig):
    """
    最终确定research摘要的节点

    通过去重和格式化源，然后将它们与运行摘要结合，
    创建结构良好的研究报告，包含适当的引用。

    Args:
        state: 包含运行摘要和收集源的当前图状态

    Returns:
        包含状态更新的字典，包括running_summary键，包含格式化的最终摘要和源
    """
    logger.info("最终答案准备生成........")
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.answer_model
    logger.info(f"final_answer最终答案节点模型：{reasoning_model}")

    # 格式化提示
    agent = Agent(model_id=reasoning_model)
    agent.set_step_prompt(answer_instructions)
    content = agent.step(
        current_date=get_current_date(),
        research_topic=get_research_topic(state["messages"]),
        summaries="\n---\n\n".join(state["web_search_result"]),
        research_proposal=state.get("plan", "")
    )

    # 用原始URL替换短URL，并将所有使用的URL添加到sources_gathered
    unique_sources = []
    for source in state["sources_gathered"]:
        if source["short_url"] in content:
            content= content.replace(
                source["short_url"], source["value"]
            )
            unique_sources.append(source)


    logger.info(f"最终确定答案：{content}")
    return {
        "messages": [AIMessage(content=content)],
        "sources_gathered": unique_sources,
    }


# 创建我们的Agent图
builder = StateGraph(OverallState, config_schema=Configuration)



# 定义图中的节点
builder.add_node(GENERATE_PLAN_NODE, generate_plan)
builder.add_node(GENERATE_SEARCH_NODE, generate_query)
builder.add_node(WEB_SEARCH_NODE, web_search)
builder.add_node(CRITIQUE_NODE, critique)
builder.add_node(FINAL_ANSWER_NODE, final_answer)
builder.add_node("awaiting_plan_confirmation", lambda state, config: state)
builder.add_node("replan", lambda state, config: {"plan_status": "unconfirmed"})

# 将入口点设置为`GENERATE_PLAN_NODE`
# 这意味着这个节点是第一个被调用的
builder.add_edge(START, GENERATE_PLAN_NODE)
builder.add_conditional_edges(
    GENERATE_PLAN_NODE, evaluate_plan, [GENERATE_SEARCH_NODE, "replan", "awaiting_plan_confirmation"]
)
builder.add_edge("replan", GENERATE_PLAN_NODE)
# 添加条件边以在并行分支中继续搜索查询
builder.add_conditional_edges(
    GENERATE_SEARCH_NODE, send_to_web_search, [WEB_SEARCH_NODE]
)
# 对进度进行评估
builder.add_edge(WEB_SEARCH_NODE, CRITIQUE_NODE)
# 评估后决定下一步如何做
builder.add_conditional_edges(
    CRITIQUE_NODE, route_evaluate, [WEB_SEARCH_NODE, FINAL_ANSWER_NODE]
)
# 最终确定答案
builder.add_edge(FINAL_ANSWER_NODE, END)

# 编译图
graph = builder.compile(name="pro-research-agent")

