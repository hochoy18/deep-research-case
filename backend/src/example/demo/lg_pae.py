from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, List

# ========== Mock 工具函数 ==========
def get_weather(city: str) -> str:
    """Mock 查天气"""
    weather_db = {"北京": "晴 25℃", "上海": "阴 22℃"}
    return weather_db.get(city, "未知城市")

def calculate(expression: str) -> str:
    """Mock 计算"""
    try:
        # 安全计算
        allowed = {"__builtins__": {}}
        result = eval(expression, allowed, {})
        return str(result)
    except:
        return "计算错误"

# 工具映射表
TOOLS = {
    "查天气": get_weather,
    "计算": calculate,
}

# ========== State 定义 ==========
class PlanExecuteState(TypedDict):
    input: str
    plan: List[str]
    past_steps: List[tuple]
    response: str

# ========== 节点函数 ==========
def plan_step(state: PlanExecuteState):
    """规划节点：用模型生成步骤，但要求使用工具"""
    prompt = f"""分析以下任务，生成具体步骤。每个步骤必须是以下格式之一：
- "查天气:城市名" （如：查天气:北京）
- "计算:表达式" （如：计算:15*8+20）
任务：{state['input']}
只输出步骤列表，每行一个，不要解释。"""
    
    # 帮我查北京天气，然后计算15*8+20，最后总结
    # 1. 查询北京天气
    # 2. 计算15*8+20
    # 3. 总结以上结果
    response = model.invoke(prompt)
    lines = response.content.strip().split('\n')
    # 清理步骤
    plan = [line.strip().lstrip('0123456789.- ') for line in lines if line.strip()]
    return {"plan": plan}

def execute_step(state: PlanExecuteState):
    """执行节点：解析步骤并调用真实工具"""
    plan = state["plan"]
    past_steps = state.get("past_steps", [])
    
    if not plan:
        return {"response": "所有步骤执行完成"}
    
    step = plan[0]
    print(f"🛠️  执行步骤: {step}")
    
    # 解析步骤并调用对应工具
    result = ""
    if "查天气" in step or "天气" in step:
        # 提取城市名（简单解析）
        city = step.split(":")[-1] if ":" in step else "北京"
        result = get_weather(city)
        print(f"   结果: {city}天气 = {result}")
        
    elif "计算" in step:
        # 提取表达式
        expr = step.split(":")[-1] if ":" in step else step.replace("计算", "")
        result = calculate(expr)
        print(f"   结果: {expr} = {result}")
        
    else:
        # 其他步骤用模型处理
        resp = model.invoke(f"完成任务: {step}")
        result = resp.content
    
    past_steps.append((step, result))
    return {"past_steps": past_steps, "plan": plan[1:]}

def should_continue(state: PlanExecuteState):
    if state["plan"]:
        return "execute"
    return "finalize"

def finalize(state: PlanExecuteState):
    """总结节点"""
    summary = "执行结果：\n" + "\n".join([
        f"{i+1}. {step} -> {result}" 
        for i, (step, result) in enumerate(state["past_steps"])
    ])
    return {"response": summary}

# ========== 构建图 ==========
load_dotenv()
model = ChatOpenAI(model="gpt-4", temperature=0)

graph = StateGraph(PlanExecuteState)
graph.add_node("planner", plan_step)
graph.add_node("executor", execute_step)
graph.add_node("finalizer", finalize)

graph.set_entry_point("planner")
graph.add_edge("planner", "executor")
graph.add_conditional_edges("executor", should_continue, {
    "execute": "executor",
    "finalize": "finalizer"
})
graph.add_edge("finalizer", END)

app = graph.compile()

# ========== 运行 ==========
result = app.invoke({"input": "帮我查北京天气，然后计算15*8+20，最后总结"})
print("\n" + "="*50)
print(result["response"])
