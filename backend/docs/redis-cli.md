
```shell
redis-cli 



```

```redis
## 查看所有键
KEYS * 

# 查看所有以 research 开头的键
KEYS research*

# 查看 research:tasks Stream 的长度
XLEN "research:tasks"

# 查看 research:tasks Stream 最新的 10 条消息
XRANGE "research:tasks" - + COUNT 10

## 查看 research:tasks Stream 所有消息
XRANGE "research:tasks" - + 

```