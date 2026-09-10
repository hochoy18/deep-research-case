from datetime import datetime, timedelta
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END, START
from typing import TypedDict, List, Annotated, Literal
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv
import random
import re

load_dotenv()

# ========== 工具定义 ==========
@tool
def get_zodiac(birth_date: str) -> str:
    """根据出生日期（YYYY-MM-DD）返回星座"""
    try:
        date = datetime.strptime(birth_date, "%Y-%m-%d")
        month, day = date.month, date.day
        zodiac_dates = [
            ((3, 21), (4, 19), "白羊座"), ((4, 20), (5, 20), "金牛座"),
            ((5, 21), (6, 21), "双子座"), ((6, 22), (7, 22), "巨蟹座"),
            ((7, 23), (8, 22), "狮子座"), ((8, 23), (9, 22), "处女座"),
            ((9, 23), (10, 23), "天秤座"), ((10, 24), (11, 22), "天蝎座"),
            ((11, 23), (12, 21), "射手座"), ((12, 22), (1, 19), "摩羯座"),
            ((1, 20), (2, 18), "水瓶座"), ((2, 19), (3, 20), "双鱼座")
        ]
        for (start_m, start_d), (end_m, end_d), name in zodiac_dates:
            if (month == start_m and day >= start_d) or (month == end_m and day <= end_d):
                return name
        return "摩羯座"
    except:
        return "未知"

@tool
def get_chinese_zodiac(birth_date: str) -> str:
    """根据出生日期返回生肖"""
    try:
        year = datetime.strptime(birth_date, "%Y-%m-%d").year
        zodiacs = ["猴", "鸡", "狗", "猪", "鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊"]
        return zodiacs[year % 12]
    except:
        return "未知"

@tool
def get_daily_luck(zodiac: str, day_offset: int = 0) -> str:
    """根据星座返回运势（day_offset=0今天，1明天）"""
    luck_options = ["大吉", "中吉", "小吉", "平"]
    # 用日期做种子，保证同一天结果一致，不同天不同
    base_date = datetime.now().date()
    target_date = base_date + timedelta(days=day_offset)
    random.seed(f"{zodiac}_{target_date}")
    luck = random.choice(luck_options)
    random.seed()  # 重置种子
    day_str = "今日" if day_offset == 0 else "明日"
    return f"{day_str}运势：{luck}"

@tool
def generate_advice(zodiac: str, chinese_zodiac: str, luck: str) -> str:
    """生成个性化建议"""
    prompt = f"用户星座{zodiac}，生肖{chinese_zodiac}，{luck}。给一条20字内的运势建议："
    try:
        advice = model.invoke(prompt).content.strip()
        return advice
    except:
        return "保持好心情，好运自然来"


# ========== State 定义 ==========
class FortuneState(TypedDict):
    messages: Annotated[list, add_messages]
    user_info: dict           # birth_date, zodiac, chinese_zodiac, luck, advice
    plan: List[str]           # 待执行计划
    past_steps: List[tuple]   # 已执行步骤
    final_answer: str
    needs_replan: bool        # 是否需要重新规划


# ========== 辅助函数 ==========
def extract_birth_date(text: str) -> str:
    """提取日期，支持：1995年8月23日 / 1995-08-23 / 1995/8/23"""
    # 中文格式：1995年8月23日
    chinese_pattern = r'(\d{4})年(\d{1,2})月(\d{1,2})日'
    match = re.search(chinese_pattern, text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    # 标准格式：1995-08-23 或 1995/8/23
    standard_pattern = r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})'
    match = re.search(standard_pattern, text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    
    return ""

def is_asking_tomorrow(text: str) -> bool:
    """判断是否询问明天运势"""
    keywords = ["明天", "明日", "后天", "未来", "下次", "再算"]
    return any(kw in text for kw in keywords)


# ========== 节点函数 ==========

def collect_info(state: FortuneState):
    """
    信息收集节点
    - 提取生日，存入 user_info
    - 如果已有生日，检查是否问明天
    """
    messages = state.get("messages", [])
    user_info = state.get("user_info", {}).copy()
    last_msg = messages[-1].content if messages else ""
    
    # 尝试提取新生日
    birth_date = extract_birth_date(last_msg)
    if birth_date:
        user_info["birth_date"] = birth_date
        print(f"   [收集] 提取到生日: {birth_date}")
    
    # 检查是否询问明天（且已有生日）
    ask_tomorrow = is_asking_tomorrow(last_msg)
    
    # 判断是否有足够信息
    if not user_info.get("birth_date"):
        return {
            "user_info": user_info,
            "final_answer": "请提供您的出生日期（格式：YYYY-MM-DD），以便为您推算运势。",
            "needs_replan": False
        }
    
    # 已有生日，进入规划阶段
    return {
        "user_info": user_info,
        "ask_tomorrow": ask_tomorrow,
        "needs_replan": True
    }

def planner(state: FortuneState):
    """
    规划节点：根据已有信息动态生成计划
    - 第一次：计算所有
    - 以后：只重新算运势和建议
    """
    user_info = state.get("user_info", {})
    ask_tomorrow = state.get("ask_tomorrow", False)
    
    plan = []
    
    # 只有没有星座时才计算（避免重复）
    if not user_info.get("zodiac"):
        plan.append("get_zodiac")
        print("   [规划] 添加: get_zodiac")
    
    if not user_info.get("chinese_zodiac"):
        plan.append("get_chinese_zodiac")
        print("   [规划] 添加: get_chinese_zodiac")
    
    # 运势和建议每次都重新计算（支持今天/明天）
    plan.append("get_daily_luck")
    plan.append("generate_advice")
    print(f"   [规划] 添加: get_daily_luck (明天={ask_tomorrow})")
    print(f"   [规划] 添加: generate_advice")
    
    return {
        "plan": plan,
        "ask_tomorrow": ask_tomorrow,
        "past_steps": [],
        "needs_replan": False
    }

def executor(state: FortuneState):
    """执行节点：单步执行"""
    plan = state.get("plan", [])
    user_info = state.get("user_info", {}).copy()
    past_steps = state.get("past_steps", []).copy()
    ask_tomorrow = state.get("ask_tomorrow", False)
    
    if not plan:
        return {"needs_replan": True}  # 触发反思
    
    step = plan[0]
    result = ""
    
    print(f"   [执行] {step}")
    
    if step == "get_zodiac":
        birth_date = user_info.get("birth_date")
        result = get_zodiac.invoke({"birth_date": birth_date})
        user_info["zodiac"] = result
        print(f"   [结果] 星座: {result}")
        
    elif step == "get_chinese_zodiac":
        birth_date = user_info.get("birth_date")
        result = get_chinese_zodiac.invoke({"birth_date": birth_date})
        user_info["chinese_zodiac"] = result
        print(f"   [结果] 生肖: {result}")
        
    elif step == "get_daily_luck":
        zodiac = user_info.get("zodiac", "未知")
        day_offset = 1 if ask_tomorrow else 0
        result = get_daily_luck.invoke({"zodiac": zodiac, "day_offset": day_offset})
        user_info["luck"] = result
        print(f"   [结果] {result}")
        
    elif step == "generate_advice":
        zodiac = user_info.get("zodiac", "未知")
        chinese_zodiac = user_info.get("chinese_zodiac", "未知")
        luck = user_info.get("luck", "未知")
        result = generate_advice.invoke({
            "zodiac": zodiac,
            "chinese_zodiac": chinese_zodiac,
            "luck": luck
        })
        user_info["advice"] = result
        print(f"   [结果] 建议: {result}")
    
    past_steps.append((step, result))
    
    return {
        "plan": plan[1:],
        "user_info": user_info,
        "past_steps": past_steps,
        "needs_replan": False
    }

def reflector(state: FortuneState):
    """
    反思节点：检查结果完整性
    - 如果缺少关键字段，重新规划补充
    """
    user_info = state.get("user_info", {})
    past_steps = state.get("past_steps", [])
    
    print(f"   [反思] 检查完整性...")
    
    # 检查必备字段
    missing = []
    if not user_info.get("zodiac"):
        missing.append("get_zodiac")
    if not user_info.get("chinese_zodiac"):
        missing.append("get_chinese_zodiac")
    if not user_info.get("luck"):
        missing.append("get_daily_luck")
    if not user_info.get("advice"):
        missing.append("generate_advice")
    
    if missing:
        print(f"   [反思] 发现缺失: {missing}，重新规划")
        return {
            "plan": missing,
            "needs_replan": False  # 补充执行，不结束
        }
    
    print(f"   [反思] 检查通过，结果完整")
    return {"needs_replan": True}  # 进入总结

def finalizer(state: FortuneState):
    """总结节点：生成最终回答"""
    user_info = state.get("user_info", {})
    
    birth = user_info.get("birth_date", "未知")
    zodiac = user_info.get("zodiac", "未知")
    chinese = user_info.get("chinese_zodiac", "未知")
    luck = user_info.get("luck", "未知")
    advice = user_info.get("advice", "保持好心情")
    
    # 提取运势中的"今日/明日"
    day_desc = "今日" if "今日" in luck else "明日"
    luck_level = luck.replace("今日运势：", "").replace("明日运势：", "")
    
    answer = f"根据您的出生日期{birth}，您的星座是{zodiac}，生肖是{chinese}。{day_desc}运势：{luck_level}。建议：{advice}"
    
    print(f"   [总结] 生成最终回答")
    return {"final_answer": answer}


# ========== 条件路由 ==========

def route_after_collect(state: FortuneState) -> Literal["plan", "end"]:
    """收集后路由：有生日则规划，否则结束等待"""
    if state.get("final_answer"):  # 缺少信息，直接返回答案
        return "end"
    return "plan"

def route_after_executor(state: FortuneState) -> Literal["execute", "reflect"]:
    """执行后路由：还有步骤则继续，否则反思"""
    if state.get("plan"):
        return "execute"
    return "reflect"

def route_after_reflector(state: FortuneState) -> Literal["execute", "finalize"]:
    """反思后路由：需要补充则执行，否则总结"""
    if state.get("plan"):  # 反思后发现缺失，补充执行
        return "execute"
    return "finalize"


# ========== 构建图 ==========
model = ChatOpenAI(model="gpt-4", temperature=0.7)

graph = StateGraph(FortuneState)

# 添加节点
graph.add_node("collect", collect_info)
graph.add_node("planner", planner)
graph.add_node("executor", executor)
graph.add_node("reflector", reflector)
graph.add_node("finalizer", finalizer)

# 边
graph.add_edge(START, "collect")

graph.add_conditional_edges(
    "collect",
    route_after_collect,
    {"plan": "planner", "end": END}
)

graph.add_edge("planner", "executor")

graph.add_conditional_edges(
    "executor",
    route_after_executor,
    {"execute": "executor", "reflect": "reflector"}
)

graph.add_conditional_edges(
    "reflector",
    route_after_reflector,
    {"execute": "executor", "finalize": "finalizer"}
)

graph.add_edge("finalizer", END)

# 编译
checkpointer = InMemorySaver()
app = graph.compile(checkpointer=checkpointer)


# ========== 演示交互 ==========

def demo_chat():
    """模拟对话演示"""
    print("=" * 60)
    print("🔮 智能命理机器人 - 演示模式")
    print("=" * 60)
    
    thread_id = "demo_user_001"
    config = {"configurable": {"thread_id": thread_id}}
    
    # 场景1：第一次询问（完整流程）
    print("\n【场景1】第一次询问，完整推算")
    print("-" * 40)
    
    user_input = "我1995年8月23日出生，今天运势如何？"
    print(f"👤 你: {user_input}")
    
    result = app.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config
    )
    print(f"\n🤖 助手: {result['final_answer']}")
    
    # 场景2：多轮对话，问明天
    print("\n【场景2】多轮对话，询问明天运势")
    print("-" * 40)
    
    user_input = "那明天的运势呢？"
    print(f"👤 你: {user_input}")
    
    result = app.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config
    )
    print(f"\n🤖 助手: {result['final_answer']}")
    
    # 显示记忆
    print("\n【记忆状态】")
    final_state = app.get_state(config)
    if final_state:
        info = final_state.values.get("user_info", {})
        print(f"   生日: {info.get('birth_date')}")
        print(f"   星座: {info.get('zodiac')}（已记忆，下次不再计算）")
        print(f"   生肖: {info.get('chinese_zodiac')}（已记忆，下次不再计算）")
    
    # 场景3：缺少信息
    print("\n【场景3】缺少信息，主动询问")
    print("-" * 40)
    
    # 新用户，没有thread_id
    new_config = {"configurable": {"thread_id": "new_user_002"}}
    user_input = "帮我算算运势"
    print(f"👤 你: {user_input}")
    
    result = app.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=new_config
    )
    print(f"\n🤖 助手: {result['final_answer']}")
    
    # 补充信息
    print(f"\n👤 你: 2000年1月1日")
    result = app.invoke(
        {"messages": [{"role": "user", "content": "2000年1月1日"}]},
        config=new_config
    )
    print(f"\n🤖 助手: {result['final_answer']}")


if __name__ == "__main__":
    demo_chat()
