
# TODO 

## 对于同一个 task，会生成 至少两个 task id 存在 redis 中

- task 1 ： 初始问题，第一次调用 POST /api/research 
- task 2 ： 对初始问题的确认信息，第二次 调用 POST /api/research 

## 哪些问题会 存Redis research:task:{task_id}
- 初始问题
- 对初始问题的确认信息

## 哪些问题会 存 Redis research:event:{task_id}


## LLM 请求超时[Done]
- 超时时间：600秒 timeout=600


## Embedding Model 支持 qwen3.7-text-embedding[[Done]
- base url
- api key
- 权限 

## 事实提取 default model set[Done]

## MiniMax <think> 处理

