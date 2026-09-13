import os
from typing import Union, List

import dashscope
from http import HTTPStatus

import dotenv

input_texts = "衣服的质量杠杠的，很漂亮，不枉我等了这么久啊，喜欢，以后还来这里买"

dotenv.load_dotenv(override=True)
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY')

DEFAULT_EMBEDDING_MODEL = 'qwen3.7-text-embedding'

def dashscope_embedded(input: Union[str, List[str]],
                       model:str=DEFAULT_EMBEDDING_MODEL
                       ) -> List[List[float|int]]:
    resp = dashscope.TextEmbedding.call(
        api_key=EMBEDDING_API_KEY,
        model=model,
        input=input
    )
    embeddings = resp.output.get('embeddings', [])
    embeddings.sort(key=lambda x: x.get("text_index", 0) if isinstance(x, dict) else 0)
    result = [item["embedding"] if isinstance(item, dict) else item for item in embeddings]

    return result

#
# embeddings = dashscope_embedded(input_texts)
# for e in embeddings:
#     print(e)
# print('\n\n')
# texts = [
#     '研究欧美酒店旅游行业 AI Agent 在企业如何落地',
#     input_texts
# ]
# embeddings = dashscope_embedded(texts)
# for e in embeddings:
#     print(e)
# print('\n\n')
