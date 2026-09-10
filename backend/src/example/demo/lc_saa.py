from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()

# 定义模板
template = """
问题：{question}
请将这个问题分解成需要回答的子问题，用'子问题1：'、'子问题2：'等格式列出。
然后依次回答每个子问题，最后给出最终答案。

格式：
子问题1：...
答案1：...
子问题2：...
答案2：...
最终答案：...
"""

# 初始化模型和提示
model = ChatOpenAI(model="gpt-4", temperature=0)
prompt = PromptTemplate.from_template(template)

# 新版写法：使用管道符 | 组合链
chain = prompt | model

# 执行
question = "北京和上海哪个城市人口更多？"
result = chain.invoke({"question": question})

# 打印结果
print(result.content)
