import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_agent

load_dotenv()

@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气。参数city为城市名。"""
    weather_db = {"北京": "晴 5-15℃", "上海": "阴 8-18℃"}
    return weather_db.get(city, "未知城市")

@tool
def calculate(expression: str) -> str:
    """计算数学表达式，如'2+3*4'。"""
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except:
        return "计算错误"

@tool
def search_wiki(query: str) -> str:
    """搜索维基百科获取信息。参数query为搜索词。"""
    wiki_db = {"北京": "北京是中国的首都", "上海": "上海是中国的经济中心"}
    return wiki_db.get(query, "未找到相关信息")

model = ChatOpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat", temperature=0)

agent = create_agent(
    model=model,
    tools=[get_weather, calculate, search_wiki],
    system_prompt="你是一个助手，可以使用工具。回答要简洁。"
)

response = agent.invoke({
    "messages": [{"role": "user", "content": "北京天气怎么样？然后帮我算一下15*8+20，最后查一下上海的信息。"}]
})

print("\n" + "="*50)
print("最终回答:")
final_message = response["messages"][-1]
print(final_message.content)
