import os
import pandas as pd
import matplotlib  # 先导入 matplotlib
matplotlib.use('Agg')  # 使用 matplotlib.use()，不是 plt.use()
import matplotlib.pyplot as plt  # 然后再导入 pyplot
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent
from langgraph.graph import StateGraph, END, add_messages
from langgraph.checkpoint.memory import InMemorySaver
from typing import TypedDict, Annotated, List, Tuple

load_dotenv()

# 加载数据（全局变量，实际应用可改为动态加载）
df = pd.read_csv("sales.csv")

@tool
def query_sales_data(question: str) -> str:
    """
    对销售数据执行分析查询。支持以下类型的问题：
    - 最高/最低值查询：如'销售额最高的月份'、'利润最低的地区'
    - 总和/平均值：如'总销售额'、'平均利润'
    - 分组统计：如'各地区的销售额'、'各月份的总利润'
    - 条件筛选：如'产品A在3月的销量'
    
    参数:
        question: 用户的分析问题
    
    返回:
        分析结果的字符串描述
    """
    global df
    q = question.lower()
    
    # 最高值查询
    if "最高" in q or "最大" in q:
        if "销售额" in q:
            max_row = df.loc[df['sales'].idxmax()]
            return f"销售额最高的记录是{max_row['month']}月，{max_row['region']}地区，{max_row['product']}产品，销售额为{max_row['sales']}"
        elif "利润" in q:
            max_row = df.loc[df['profit'].idxmax()]
            return f"利润最高的记录是{max_row['month']}月，{max_row['region']}地区，利润为{max_row['profit']}"
    
    # 总和查询
    if "总销售额" in q:
        total = df['sales'].sum()
        return f"总销售额为{total}"
    if "总利润" in q:
        total = df['profit'].sum()
        return f"总利润为{total}"
    
    # 分组统计
    if "各地区" in q and "销售额" in q:
        result = df.groupby('region')['sales'].sum().to_dict()
        return f"各地区销售额：{result}"
    if "各月份" in q and "利润" in q:
        result = df.groupby('month')['profit'].sum().to_dict()
        return f"各月份利润：{result}"
    
    # 条件筛选
    if "产品" in q and "销量" in q:
        # 提取产品名（简单处理）
        for product in df['product'].unique():
            if product in q:
                result = df[df['product'] == product]['quantity'].sum()
                return f"{product}产品总销量为{result}"
    
    return f"无法理解问题：{question}。请尝试其他表述方式。"


@tool
def plot_sales_data(chart_type: str = "line", metric: str = "sales") -> str:
    """
    生成销售数据可视化图表。
    
    参数:
        chart_type: 图表类型，可选'line'（折线图）或'bar'（柱状图）
        metric: 要绘制的指标，可选'sales'（销售额）或'profit'（利润）
    
    返回:
        图表保存路径
    """
    global df
    plt.figure(figsize=(10, 6))
    
    if chart_type == "line":
        # 按月聚合销售额/利润
        monthly = df.groupby('month')[metric].sum()
        monthly.plot(kind='line', marker='o')
        plt.title(f"Monthly {metric.capitalize()} Trend")
        plt.xlabel("Month")
        plt.ylabel(metric.capitalize())
    elif chart_type == "bar":
        # 按地区聚合
        regional = df.groupby('region')[metric].sum()
        regional.plot(kind='bar')
        plt.title(f"{metric.capitalize()} by Region")
        plt.xlabel("Region")
        plt.ylabel(metric.capitalize())
    else:
        return f"不支持的图表类型：{chart_type}"
    
    img_path = f"sales_{metric}_{chart_type}.png"
    plt.savefig(img_path)
    plt.close()
    return f"图表已保存为{img_path}"

@tool
def analyze_sales_trend(question: str) -> str:
    """
    对销售数据进行深度分析，生成业务洞察。
    
    参数:
        question: 分析问题，如'为什么利润下降了？'
    
    返回:
        分析结果
    """
    global df
    q = question.lower()
    
    if "利润下降" in q or "利润为什么" in q:
        # 按月份计算利润变化
        monthly_profit = df.groupby('month')['profit'].sum()
        if len(monthly_profit) >= 2:
            months = list(monthly_profit.index)
            changes = []
            for i in range(1, len(months)):
                change = monthly_profit.iloc[i] - monthly_profit.iloc[i-1]
                changes.append(f"{months[i]}月相比{months[i-1]}月：{change}")
            return f"利润变化趋势：\n" + "\n".join(changes)
    
    return f"请提供更具体的分析问题。"


# 初始化模型
model = ChatOpenAI(model="gpt-4", temperature=0)

# 创建带工具的Agent
agent = create_agent(
    model=model,
    tools=[query_sales_data, plot_sales_data, analyze_sales_trend],
    system_prompt="""你是一个专业的数据分析助手。你可以：
1. 使用 query_sales_data 回答数据查询问题
2. 使用 plot_sales_data 生成图表
3. 使用 analyze_sales_trend 进行深度分析

回答要简洁、专业。"""
)

class PlanState(TypedDict):
    input: str                      # 用户原始输入
    plan: List[str]                 # 步骤列表，如['计算总销售额', '查找最高利润月份', '画利润趋势图']
    past_steps: List[Tuple[str, str]]  # 已执行步骤及结果
    final_answer: str               # 最终答案

def planner(state: PlanState):
    """规划节点：生成执行计划"""
    prompt = f"为以下任务生成步骤列表：{state['input']}"
    response = model.invoke(prompt)
    lines = response.content.strip().split('\n')
    # 过滤空行和标题行，保留步骤
    plan = [line.strip() for line in lines if line.strip() and not line.startswith('步骤')]
    return {"plan": plan}


def executor(state: PlanState):
    """执行节点：按顺序执行步骤"""
    if not state["plan"]:
        return {}
    
    step = state["plan"][0]
    # 调用Agent执行当前步骤
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"执行：{step}"}]
    })
    result_content = result["messages"][-1].content
    
    # 安全更新 past_steps（创建新列表，避免副作用）
    new_past_steps = state.get("past_steps", []) + [(step, result_content)]
    remaining_plan = state["plan"][1:]
        
    # 关键修复：最后一步时综合所有步骤结果
    if not remaining_plan:
        # 生成完整总结
        summary_lines = []
        for s, r in new_past_steps:
            summary_lines.append(f"{s}: {r}")
        final_answer = "\n".join(summary_lines)
        print(f"🎯 生成最终答案")
    else:
        final_answer = ""
    
    return {
        "plan": remaining_plan,
        "past_steps": new_past_steps,
        "final_answer": final_answer
    }






# 添加条件判断函数
def should_continue(state: PlanState) -> str:
    """判断是否需要继续执行"""
    if state.get("plan"):  # 还有剩余步骤
        return "continue"
    return "end"


# 构建图
plan_graph = StateGraph(PlanState)
# # 添加节点
plan_graph.add_node("planner", planner)
plan_graph.add_node("executor", executor)

# 设置入口
plan_graph.set_entry_point("planner")

# 设置边：从计划器 → 执行器，再从执行器到结束节点
plan_graph.add_edge("planner", "executor")

# 关键修改：添加条件循环边
plan_graph.add_conditional_edges(
    "executor",
    should_continue,
    {
        "continue": "executor",  # 还有步骤，回到 executor 继续
        "end": END  # 没步骤了，结束
    }
)

plan_app = plan_graph.compile()


result = plan_app.invoke({
    "input": "帮我分析销售数据，包括总销售额、最高利润月份，并画一张利润趋势图",
    "plan": [],
    "past_steps": [],
    "final_answer": ""
})

print(f"\n{'='*50}")
print(f"🎯 最终结果：")
print(result['final_answer'])
