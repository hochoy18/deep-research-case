可以。下面给你整理一份偏 **Redis CLI 实战手册** 风格的说明，重点覆盖 **String、Hash、Stream、Consumer Group（XGROUP）**，可以直接拿去当日常排查/操作速查表。

# Redis CLI 命令操作说明

## 1. 连接 Redis

```bash
redis-cli
```

指定地址、端口：

```bash
redis-cli -h 127.0.0.1 -p 6379
```

带密码：

```bash
redis-cli -h 127.0.0.1 -p 6379 -a 'password'
```

进入后：

```redis
PING
```

返回：

```text
PONG
```

查看 Redis 版本：

```redis
INFO server
```

---

# 2. String

String 是 Redis 最基础的数据类型，可以存字符串、数字、JSON 等。

## 2.1 SET / GET

设置：

```redis
SET user:name "zhangsan"
```

查询：

```redis
GET user:name
```

判断是否存在：

```redis
EXISTS user:name
```

删除：

```redis
DEL user:name
```

---

## 2.2 设置过期时间

设置 60 秒后过期：

```redis
SET user:token "abc123" EX 60
```

毫秒：

```redis
SET user:token "abc123" PX 60000
```

查看 TTL：

```redis
TTL user:token
```

查看毫秒 TTL：

```redis
PTTL user:token
```

永久删除过期时间：

```redis
PERSIST user:token
```

---

## 2.3 SETNX

只有 Key 不存在时才设置：

```redis
SETNX lock:order "1"
```

推荐分布式锁通常直接：

```redis
SET lock:order "request-id" NX EX 30
```

其中：

* `NX`：Key 不存在才设置
* `EX 30`：30 秒过期

---

## 2.4 数字自增

```redis
SET counter 10
```

增加：

```redis
INCR counter
```

增加指定数值：

```redis
INCRBY counter 5
```

减少：

```redis
DECR counter
```

减少指定数值：

```redis
DECRBY counter 5
```

查看：

```redis
GET counter
```

---

## 2.5 MGET / MSET

一次设置多个：

```redis
MSET user:1:name zhangsan user:2:name lisi
```

一次查询多个：

```redis
MGET user:1:name user:2:name
```

---

# 3. Hash

Hash 非常适合存储对象。

例如：

```text
user:1001
 ├── name = zhangsan
 ├── age = 20
 └── city = shanghai
```

---

## 3.1 HSET

设置字段：

```redis
HSET user:1001 name zhangsan
```

设置多个字段：

```redis
HSET user:1001 name zhangsan age 20 city shanghai
```

---

## 3.2 HGET

获取指定字段：

```redis
HGET user:1001 name
```

获取所有字段和值：

```redis
HGETALL user:1001
```

只获取 Field：

```redis
HKEYS user:1001
```

只获取 Value：

```redis
HVALS user:1001
```

---

## 3.3 判断 Field 是否存在

```redis
HEXISTS user:1001 name
```

返回：

```text
1
```

表示存在。

```text
0
```

表示不存在。

---

## 3.4 删除 Hash Field

删除一个：

```redis
HDEL user:1001 city
```

删除多个：

```redis
HDEL user:1001 age city
```

---

## 3.5 Hash 数值操作

例如：

```redis
HSET user:1001 balance 100
```

增加：

```redis
HINCRBY user:1001 balance 50
```

结果：

```text
150
```

浮点数：

```redis
HINCRBYFLOAT user:1001 balance 1.5
```

---

## 3.6 Hash Field 数量

```redis
HLEN user:1001
```

---

## 3.7 查看 Key 类型

非常实用：

```redis
TYPE user:1001
```

如果是 Hash：

```text
hash
```

String：

```text
string
```

Stream：

```text
stream
```

---

# 4. Stream

Redis Stream 主要用于：

* 消息队列
* 事件流
* 日志/事件记录
* 消费者组
* ACK
* Pending 消息处理

假设我们使用：

```text
stream.orders
```

---

# 5. XADD —— 写入 Stream

最基本：

```redis
XADD stream.orders * user_id 1001 amount 99
```

这里的 `*` 表示让 Redis 自动生成消息 ID。

例如返回：

```text
1757400000000-0
```

完整消息类似：

```text
1757400000000-0
    user_id
    1001
    amount
    99
```

---

## 5.1 指定 Message ID

也可以自己指定：

```redis
XADD stream.orders 1-0 user_id 1001
```

不过实际生产中通常使用：

```redis
XADD stream.orders * ...
```

---

# 6. XRANGE —— 查看 Stream 消息

查看全部：

```redis
XRANGE stream.orders - +
```

其中：

* `-`：最小 ID
* `+`：最大 ID

查看最近几条：

```redis
XREVRANGE stream.orders + - COUNT 10
```

---

## 6.1 根据 ID 查询

例如：

```redis
XRANGE stream.orders 1757400000000-0 +
```

表示查询从指定 ID 开始的数据。

---

# 7. XLEN —— Stream 长度

```redis
XLEN stream.orders
```

例如：

```text
(integer) 100
```

表示 Stream 当前有 100 条消息。

---

# 8. XTRIM —— 裁剪 Stream

保留最多 1000 条：

```redis
XTRIM stream.orders MAXLEN 1000
```

近似裁剪：

```redis
XTRIM stream.orders MAXLEN ~ 1000
```

一般推荐：

```redis
XTRIM stream.orders MAXLEN ~ 1000
```

`~` 表示允许 Redis 做近似裁剪，性能通常更好。

---

# 9. Consumer Group

Consumer Group 是 Stream 最重要的一部分。

例如：

```text
Stream
  |
  +--- order-group
          |
          +--- consumer-1
          +--- consumer-2
          +--- consumer-3
```

多个 Consumer 可以共同消费一个 Stream。

---

# 10. XGROUP CREATE —— 创建消费组

创建：

```redis
XGROUP CREATE stream.orders order-group 0
```

这里：

```text
stream.orders   Stream 名称
order-group     Consumer Group
0               从哪个 ID 开始消费
```

常见的两个选择：

### 从头开始消费

```redis
XGROUP CREATE stream.orders order-group 0
```

### 只消费创建 Group 之后的新消息

```redis
XGROUP CREATE stream.orders order-group $
```

`$` 表示当前 Stream 最新 ID。

---

## 10.1 Stream 不存在时创建

如果 Stream 还不存在：

```redis
XGROUP CREATE stream.orders order-group $ MKSTREAM
```

`MKSTREAM` 会自动创建 Stream。

这是实际项目里比较常用的写法：

```redis
XGROUP CREATE stream.orders order-group $ MKSTREAM
```

---

# 11. XREADGROUP —— Consumer 消费消息

假设：

```text
Stream: stream.orders
Group:  order-group
Consumer: consumer-1
```

消费：

```redis
XREADGROUP GROUP order-group consumer-1 COUNT 10 STREAMS stream.orders >
```

这里最关键的是：

```text
>
```

表示：

> 获取这个 Consumer Group 中，当前还没有被其他 Consumer 投递过的新消息。

---

## 11.1 阻塞等待消息

实际消息消费通常会使用：

```redis
XREADGROUP GROUP order-group consumer-1 COUNT 10 BLOCK 5000 STREAMS stream.orders >
```

含义：

```text
COUNT 10
最多取 10 条

BLOCK 5000
最多阻塞 5000ms

>
读取尚未分配给 Consumer 的新消息
```

例如：

```redis
XREADGROUP GROUP order-group consumer-1 COUNT 10 BLOCK 0 STREAMS stream.orders >
```

`BLOCK 0` 表示一直阻塞等待。

---

# 12. XACK —— ACK 消息

消费成功以后：

```redis
XACK stream.orders order-group 1757400000000-0
```

多个消息：

```redis
XACK stream.orders order-group \
1757400000000-0 \
1757400000001-0
```

ACK 的作用是：

> 告诉 Consumer Group：这条消息我已经处理成功了。

---

# 13. Pending 消息

这是 Stream 排查问题时非常重要的一部分。

如果：

```text
XREADGROUP
```

读取到了消息，但是没有：

```redis
XACK
```

那么消息就会进入 **Pending Entries List（PEL）**。

可以理解为：

```text
Stream
   |
   +--- 已消费 + ACK
   |
   +--- 已投递但未 ACK
              ↓
           Pending
```

---

# 14. XPENDING —— 查看 Pending

最基本：

```redis
XPENDING stream.orders order-group
```

例如：

```text
1) (integer) 3
2) 1757400000000-0
3) 1757400000002-0
4) 1) 1) consumer-1
      2) (integer) 3
```

主要表示：

```text
Pending 总数
最小 Pending ID
最大 Pending ID
各 Consumer 的 Pending 数量
```

---

## 14.1 查看详细 Pending

```redis
XPENDING stream.orders order-group - + 10
```

可以看到：

```text
消息 ID
Consumer
空闲时间
Delivery 次数
```

这个命令特别适合排查：

> 为什么消息一直没有 ACK？

---

# 15. XCLAIM —— 抢回超时消息

假设：

```text
consumer-1
```

消费了一条消息，但是程序挂掉了。

消息就可能一直 Pending。

这时候可以让：

```text
consumer-2
```

接管。

例如：

```redis
XCLAIM stream.orders order-group consumer-2 60000 1757400000000-0
```

其中：

```text
60000
```

表示消息至少空闲 60 秒才允许被 Claim。

---

# 16. XAUTOCLAIM —— 自动接管 Pending

Redis 新版本更推荐：

```redis
XAUTOCLAIM stream.orders order-group consumer-2 60000 0-0 COUNT 10
```

含义：

```text
stream.orders
    ↓
order-group
    ↓
consumer-2 接管
    ↓
空闲超过 60000ms 的消息
    ↓
从 0-0 开始找
    ↓
最多 10 条
```

这对于实现：

> Consumer 宕机后的消息重新消费

非常有用。

---

# 17. XGROUP 常用管理命令

## 查看 Consumer Group

```redis
XINFO GROUPS stream.orders
```

可以看到：

```text
name
consumers
pending
last-delivered-id
```

---

## 查看 Consumer

```redis
XINFO CONSUMERS stream.orders order-group
```

可以看到：

```text
name
pending
idle
inactive
```

例如：

```redis
XINFO CONSUMERS stream.orders order-group
```

可以帮助判断：

> 哪个 Consumer 很久没消费？

---

## 查看 Stream 信息

```redis
XINFO STREAM stream.orders
```

可以查看：

```text
length
radix-tree-keys
first-entry
last-entry
groups
```

---

# 18. XGROUP SETID

修改 Consumer Group 当前的消费位置。

例如：

```redis
XGROUP SETID stream.orders order-group 0
```

让 Group 从头开始。

或者：

```redis
XGROUP SETID stream.orders order-group $
```

让 Group 从当前最新位置开始。

**注意：** 这个操作会改变整个 Consumer Group 的消费游标，生产环境操作前要特别谨慎。

---

# 19. XGROUP DESTROY

删除 Consumer Group：

```redis
XGROUP DESTROY stream.orders order-group
```

删除前建议：

```redis
XINFO GROUPS stream.orders
```

确认 Group 名称。

---

# 20. XGROUP DELCONSUMER

删除 Consumer：

```redis
XGROUP DELCONSUMER stream.orders order-group consumer-1
```

通常用于清理已经废弃的 Consumer。

---

# 21. Stream + Group 完整操作示例

假设我们做一个订单消息队列。

### ① 创建 Stream + Group

```redis
XGROUP CREATE stream.orders order-group $ MKSTREAM
```

---

### ② 生产消息

```redis
XADD stream.orders * order_id 10001 user_id 888 amount 99
```

再来一条：

```redis
XADD stream.orders * order_id 10002 user_id 999 amount 199
```

---

### ③ Consumer 1 消费

```redis
XREADGROUP GROUP order-group consumer-1 COUNT 10 STREAMS stream.orders >
```

---

### ④ Consumer 2 消费

```redis
XREADGROUP GROUP order-group consumer-2 COUNT 10 STREAMS stream.orders >
```

此时 Group 会把不同消息分配给不同 Consumer。

---

### ⑤ Consumer 处理成功

```redis
XACK stream.orders order-group 1757400000000-0
```

---

### ⑥ 查看还有多少 Pending

```redis
XPENDING stream.orders order-group
```

---

### ⑦ 查看详细 Pending

```redis
XPENDING stream.orders order-group - + 20
```

---

### ⑧ Consumer 宕机，其他 Consumer 接管

```redis
XAUTOCLAIM stream.orders order-group consumer-2 60000 0-0 COUNT 10
```

---

# 22. Stream 消费的几个 ID 特别容易搞混

这是使用 `XREADGROUP` 时最需要注意的地方。

| ID    | 含义                         |
| ----- | -------------------------- |
| `0`   | 从 Stream 开头                |
| `$`   | Stream 当前最新 ID             |
| `>`   | Group 中尚未投递给 Consumer 的新消息 |
| `0-0` | Pending 中从最早消息开始查          |

尤其是：

```redis
XREADGROUP GROUP order-group consumer-1 STREAMS stream.orders >
```

和：

```redis
XREADGROUP GROUP order-group consumer-1 STREAMS stream.orders 0
```

**不是一回事。**

`>`：

> 获取新的、尚未分配的消息。

`0`：

> 查看这个 Consumer 自己 Pending 的消息。

所以故障恢复/重新处理 Pending 时，经常会看到：

```redis
XREADGROUP GROUP order-group consumer-1 COUNT 10 STREAMS stream.orders 0
```

---

# 23. 一张速查表

## String

| 操作    | CLI                   |
| ----- | --------------------- |
| 设置    | `SET key value`       |
| 获取    | `GET key`             |
| 删除    | `DEL key`             |
| 判断存在  | `EXISTS key`          |
| 设置过期  | `SET key value EX 60` |
| TTL   | `TTL key`             |
| 自增    | `INCR key`            |
| 自增指定值 | `INCRBY key 10`       |
| 批量设置  | `MSET k1 v1 k2 v2`    |
| 批量获取  | `MGET k1 k2`          |

## Hash

| 操作       | CLI                    |
| -------- | ---------------------- |
| 设置       | `HSET key field value` |
| 获取       | `HGET key field`       |
| 全部       | `HGETALL key`          |
| Field 列表 | `HKEYS key`            |
| Value 列表 | `HVALS key`            |
| 判断 Field | `HEXISTS key field`    |
| 删除 Field | `HDEL key field`       |
| Field 数量 | `HLEN key`             |
| 数值增加     | `HINCRBY key field 10` |

## Stream

| 操作        | CLI                             |
| --------- | ------------------------------- |
| 写消息       | `XADD stream * field value`     |
| 查看消息      | `XRANGE stream - +`             |
| 倒序查看      | `XREVRANGE stream + - COUNT 10` |
| 长度        | `XLEN stream`                   |
| 裁剪        | `XTRIM stream MAXLEN ~ 1000`    |
| Stream 信息 | `XINFO STREAM stream`           |

## XGROUP

| 操作          | CLI                                                |
| ----------- | -------------------------------------------------- |
| 创建 Group    | `XGROUP CREATE stream group $ MKSTREAM`            |
| 消费新消息       | `XREADGROUP GROUP group consumer STREAMS stream >` |
| ACK         | `XACK stream group message-id`                     |
| 查看 Pending  | `XPENDING stream group`                            |
| Pending 详情  | `XPENDING stream group - + 10`                     |
| 抢消息         | `XCLAIM ...`                                       |
| 自动抢消息       | `XAUTOCLAIM ...`                                   |
| Group 信息    | `XINFO GROUPS stream`                              |
| Consumer 信息 | `XINFO CONSUMERS stream group`                     |
| 修改 Group ID | `XGROUP SETID stream group id`                     |
| 删除 Group    | `XGROUP DESTROY stream group`                      |
| 删除 Consumer | `XGROUP DELCONSUMER stream group consumer`         |

---

# 24. 生产环境排查 Stream，我建议记住这 8 个命令

```redis
# 1. Stream 有多少消息
XLEN stream.orders

# 2. 看最近消息
XREVRANGE stream.orders + - COUNT 10

# 3. Stream 状态
XINFO STREAM stream.orders

# 4. Group 状态
XINFO GROUPS stream.orders

# 5. Consumer 状态
XINFO CONSUMERS stream.orders order-group

# 6. Pending 总览
XPENDING stream.orders order-group

# 7. Pending 详情
XPENDING stream.orders order-group - + 20

# 8. 接管超时 Pending
XAUTOCLAIM stream.orders order-group consumer-2 60000 0-0 COUNT 10
```

**核心链路可以记成：**

```text
XADD
  ↓
Stream
  ↓
XGROUP CREATE
  ↓
XREADGROUP
  ↓
Consumer 处理
  ↓
XACK
  ↓
成功结束

如果 Consumer 挂了
  ↓
XPENDING
  ↓
XAUTOCLAIM
  ↓
其他 Consumer 接管
  ↓
重新处理
  ↓
XACK
```

如果你是拿这个做**后端开发/Redis 运维**，我还可以进一步给你整理成一份「**Redis CLI 实战速查手册**」，把 **List / Set / ZSet / Bitmap / HyperLogLog / GEO / Lua / 发布订阅 / Stream** 全部放进去，并重点标注**生产环境最常用命令、危险命令和排障命令**。
