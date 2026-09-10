from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()

model = ChatOpenAI(model="gpt-4", temperature=0.7)
generate_prompt = PromptTemplate.from_template("写一段关于{topic}的简短介绍，不超过50字。")
generate_chain = generate_prompt | model

topic = "人工智能"
first_draft = generate_chain.invoke({"topic": topic}).content
print("初稿：", first_draft)
reflect_prompt = PromptTemplate.from_template("""评估以下文本的质量，指出不足之处，并提出修改建议。
文本：{text}
不足：""")
reflect_chain = reflect_prompt | model
feedback = reflect_chain.invoke({"text": first_draft}).content
print("反馈：", feedback)
improve_prompt = PromptTemplate.from_template("""根据以下反馈修改原文。
原文：{text}
反馈：{feedback}
修改后的版本：""")
improve_chain = improve_prompt | model
final_draft = improve_chain.invoke({"text": first_draft, "feedback": feedback}).content
print("终稿：", final_draft)
