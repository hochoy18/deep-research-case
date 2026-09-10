import os
from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()

# 使用 DeepSeek API（兼容 OpenAI 接口）
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

def get_weather(city: str) -> str:
    weather_db = {"北京": "晴 5-15℃", "上海": "阴 8-18℃"}
    return weather_db.get(city, "未知城市")

def calculate(expression: str) -> str:
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"{expression} = {result}"
    except:
        return "计算错误"

def search_wiki(query: str) -> str:
    wiki_db = {"北京": "北京是中国的首都", "上海": "上海是中国的经济中心"}
    return wiki_db.get(query, "未找到相关信息")

# 定义工具（符合 OpenAI function calling 格式）
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式，如'2+3*4'"}
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_wiki",
            "description": "搜索维基百科信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索词"}
                },
                "required": ["query"]
            }
        }
    }
]

def manual_react_agent(user_input, max_steps=5):
    messages = [{"role": "user", "content": user_input}]
    step = 0
    while step < max_steps:
        response = client.chat.completions.create(
            model="deepseek-chat",          # 使用 DeepSeek 模型
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        message = response.choices[0].message

        # 如果模型想调用工具
        if message.tool_calls:
            # 将 assistant 消息加入对话
            messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in message.tool_calls
                ]
            })

            for tc in message.tool_calls:
                func_name = tc.function.name
                args = json.loads(tc.function.arguments)

                # 执行真实函数
                if func_name == "get_weather":
                    result = get_weather(**args)
                elif func_name == "calculate":
                    result = calculate(**args)
                elif func_name == "search_wiki":
                    result = search_wiki(**args)
                else:
                    result = "未知工具"

                # 添加工具返回结果
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)
                })
        else:
            # 没有工具调用，返回最终答案
            return message.content

        step += 1
    return "达到最大步数，未完成"

print(manual_react_agent("北京天气怎么样？"))