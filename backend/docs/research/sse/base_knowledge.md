当然。SSE（**Server-Sent Events**）可以理解成：

> **客户端发起一次 HTTP 请求，服务器保持这个连接不关闭，然后服务器不断把“事件”推送给客户端。**

它特别适合：**AI 流式输出、实时日志、任务进度、消息通知、股票/监控数据**等。

---

# 1. SSE 到底是什么？

SSE 全称：

**Server-Sent Events**

它是基于 HTTP 的一种**服务器 → 客户端单向实时通信机制**。

传统 HTTP：

```text
Client                    Server
  |                         |
  | ------ HTTP Request ---> |
  | <----- HTTP Response --- |
  |                         |
  X 连接结束
```

SSE：

```text
Client                    Server
  |                         |
  | ------ HTTP Request ---> |
  |                         |
  | <----- event 1 --------- |
  | <----- event 2 --------- |
  | <----- event 3 --------- |
  | <----- event 4 --------- |
  |                         |
  |       连接一直保持       |
  |                         |
```

关键点：

**请求只有一次，但是响应可以持续很久。**

---

# 2. SSE 和普通 HTTP 的区别

普通接口：

```http
GET /api/user
```

服务器返回：

```json
{
  "name": "Tom",
  "age": 20
}
```

返回完连接基本就结束了。

SSE：

```http
GET /events
```

服务器可能持续返回：

```text
data: hello

data: world

data: 123

data: 456
```

每一条都是一个 Event。

所以 SSE 本质上还是 HTTP，只不过：

> **Response 不立即结束，而是持续向客户端写数据。**

---

# 3. SSE 的 HTTP Header

服务器需要返回：

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

最重要的是：

```http
Content-Type: text/event-stream
```

告诉浏览器：

> 这不是普通 HTTP Response，而是 SSE 流。

---

# 4. SSE 数据格式

SSE 有自己规定的数据格式。

最简单：

```text
data: hello

```

注意：

**最后必须有一个空行。**

也就是：

```text
data: hello
\n
\n
```

一个完整事件通常长这样：

```text
data: hello
data: world

```

客户端收到后，得到：

```text
hello
world
```

---

# 5. 为什么 `data:` 后面有两行？

因为 SSE 的协议格式是：

```text
field: value
field: value

```

**空行表示一个 Event 结束。**

例如：

```text
data: hello

data: world

```

实际上是两个事件：

```text
Event 1
data: hello
↑
空行

Event 2
data: world
↑
空行
```

---

# 6. SSE 支持哪些字段？

常见的有：

```text
event:
data:
id:
retry:
```

例如：

```text
event: message
id: 100
data: hello
retry: 5000

```

分别代表：

| 字段      | 作用        |
| ------- | --------- |
| `event` | 事件类型      |
| `data`  | 数据        |
| `id`    | 事件 ID     |
| `retry` | 浏览器重连等待时间 |

最常用的其实就是：

```text
event:
data:
id:
```

---

# 7. `data` 可以放 JSON

实际开发中非常常见：

```text
data: {"id":123,"name":"Tom"}

```

甚至：

```text
data: {"type":"message","content":"hello"}

```

客户端：

```javascript
const eventSource = new EventSource("/events");

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    console.log(data);
};
```

---

# 8. `event` 是干什么的？

假设服务器发送：

```text
event: message
data: hello

event: notification
data: new message

```

客户端可以分别监听：

```javascript
const es = new EventSource("/events");

es.addEventListener("message", (event) => {
    console.log("message:", event.data);
});

es.addEventListener("notification", (event) => {
    console.log("notification:", event.data);
});
```

所以 SSE 可以理解成：

```text
一个 HTTP 长连接
        │
        ├── message
        ├── notification
        ├── progress
        └── heartbeat
```

---

# 9. 浏览器端怎么使用？

浏览器原生提供：

```javascript
EventSource
```

最简单：

```javascript
const es = new EventSource("/events");

es.onmessage = (event) => {
    console.log(event.data);
};

es.onerror = (error) => {
    console.error(error);
};
```

服务器：

```text
data: hello

data: world

data: SSE

```

客户端会依次收到：

```text
hello
world
SSE
```

---

# 10. SSE 最大的一个特点：自动重连

这是 SSE 非常舒服的一点。

假设：

```text
Client -------- SSE -------- Server
```

网络断了：

```text
Client ----X---- Server
```

浏览器的 `EventSource` 默认会尝试重新连接。

例如：

```javascript
const es = new EventSource("/events");
```

连接断开以后，它会自动 reconnect。

这也是 SSE 相比自己实现 WebSocket 重连逻辑比较方便的地方。

---

# 11. `retry` 是干嘛的？

服务器可以发送：

```text
retry: 5000
data: hello

```

意思是：

> 如果连接断了，客户端 5 秒后尝试重新连接。

单位是毫秒。

```text
retry: 1000
```

就是 1 秒。

---

# 12. SSE 的 `id` 非常重要

例如：

```text
id: 101
data: hello

id: 102
data: world

id: 103
data: SSE

```

浏览器会记录最后收到的 ID。

假设收到：

```text
id: 103
data: SSE
```

然后网络断了。

重新连接时，浏览器可能发送：

```http
Last-Event-ID: 103
```

服务器就知道：

> 客户端已经收到 103 了。

于是服务器可以从：

```text
104
```

继续发送。

这可以解决：

**网络断开导致事件丢失的问题。**

---

# 13. 一个完整的 SSE 流程

假设服务器有：

```text
1
2
3
4
5
```

服务器发送：

```text
id: 1
data: 1

id: 2
data: 2

id: 3
data: 3

```

客户端收到 3 后断网。

重新连接：

```http
GET /events HTTP/1.1
Last-Event-ID: 3
```

服务器：

```text
id: 4
data: 4

id: 5
data: 5

```

于是客户端不会重复收到 1、2、3。

---

# 14. 后端怎么实现？

以 Node.js 为例。

```javascript
const http = require("http");

const server = http.createServer((req, res) => {
    if (req.url === "/events") {

        res.writeHead(200, {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        });

        let count = 0;

        const timer = setInterval(() => {
            count++;

            res.write(`data: ${count}\n\n`);

            if (count === 10) {
                clearInterval(timer);
                res.end();
            }
        }, 1000);

        req.on("close", () => {
            clearInterval(timer);
        });
    }
});

server.listen(3000);
```

客户端：

```javascript
const es = new EventSource("http://localhost:3000/events");

es.onmessage = (event) => {
    console.log(event.data);
};
```

结果：

```text
1
2
3
4
5
6
7
8
9
10
```

每秒一个。

---

# 15. SSE 和 WebSocket 的区别

这是最容易混淆的地方。

|          | SSE           | WebSocket |
| -------- | ------------- | --------- |
| 通信方向     | **服务器 → 客户端** | **双向**    |
| 基于       | HTTP          | WebSocket |
| 浏览器 API  | EventSource   | WebSocket |
| 自动重连     | ✅             | ❌ 通常自己实现  |
| 数据格式     | 文本            | 文本 / 二进制  |
| 实现复杂度    | 低             | 相对高       |
| 适合服务端推送  | ⭐⭐⭐⭐⭐         | ⭐⭐⭐⭐      |
| 适合实时双向通信 | ❌             | ⭐⭐⭐⭐⭐     |

比如：

### SSE

```text
Client ──────────────> Server
       HTTP Request

Client <────────────── Server
       Event
Client <────────────── Server
       Event
Client <────────────── Server
       Event
```

主要是：

```text
Server → Client
```

---

### WebSocket

```text
Client ──────────────> Server
Client <────────────── Server
Client ──────────────> Server
Client <────────────── Server
```

双方都可以随时发消息。

所以：

**聊天室**

```text
A ←→ Server ←→ B
```

更适合 WebSocket。

而：

**AI 输出**

```text
Server
  ↓
"你"
  ↓
"好"
  ↓
"！"
  ↓
"今"
  ↓
"天"
```

SSE 就非常合适。

---

# 16. SSE 为什么特别适合 AI Streaming？

比如你问 AI：

> 给我解释一下 Redis

传统 API：

```text
POST /chat

              等待……

<----------------

{
    "answer": "Redis 是一个..."
}
```

必须等 AI 全部生成完。

SSE：

```text
POST /chat
       ↓
     Server
       ↓
data: Redis
       ↓
data: 是
       ↓
data: 一个
       ↓
data: 内存
       ↓
data: 数据库
       ↓
data: ...
```

前端可以边收边显示：

```text
Redis
Redis 是
Redis 是一个
Redis 是一个内存
Redis 是一个内存数据库
...
```

这就是大家经常说的：

**Streaming Response / 流式响应。**

---

# 17. 不过 AI API 不一定使用 EventSource

这里有一个很容易踩坑的地方。

浏览器原生：

```javascript
new EventSource("/events")
```

只能很方便地处理：

```http
GET
```

但 AI Chat 通常需要：

```http
POST /chat

{
    "message": "你好"
}
```

这时候不能简单写：

```javascript
new EventSource("/chat")
```

因为你需要 POST body。

所以前端经常会使用：

```javascript
fetch("/chat", {
    method: "POST",
    body: JSON.stringify(...)
});
```

然后：

```javascript
const response = await fetch(...);

const reader = response.body.getReader();

while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    // 处理流
}
```

这时候虽然底层也是：

```text
text/event-stream
```

但前端不一定使用 `EventSource`。

这个区别非常重要：

> **SSE 是一种数据传输格式/机制，而 `EventSource` 是浏览器提供的 SSE 客户端 API。**

---

# 18. SSE 的底层到底发生了什么？

假设：

```javascript
const es = new EventSource("/events");
```

实际上浏览器发送：

```http
GET /events HTTP/1.1
Host: example.com
Accept: text/event-stream
Cache-Control: no-cache
```

服务器：

```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
```

然后服务器**不调用结束 Response 的操作**，而是不断：

```text
write()
write()
write()
write()
```

例如：

```text
data: hello\n\n
```

然后：

```text
data: world\n\n
```

然后：

```text
data: bye\n\n
```

所以你可以把 SSE 想象成：

> **一个永远没有立刻结束的 HTTP Response。**

---

# 19. 为什么必须 `\n\n`？

这是 SSE 最重要的协议细节之一。

错误：

```text
data: hello
data: world
```

没有空行，客户端可能认为：

```text
这是同一个 event
```

正确：

```text
data: hello

data: world

```

即：

```text
data: hello\n\n
data: world\n\n
```

---

# 20. SSE 的多行 data

例如：

```text
data: hello
data: world

```

这是**一个 event**，它的数据相当于：

```text
hello
world
```

而不是两个 event。

所以：

```text
data: A
data: B

```

和：

```text
data: A

data: B

```

完全不同。

前者：

```text
一个 Event
└── data = "A\nB"
```

后者：

```text
Event 1
└── data = "A"

Event 2
└── data = "B"
```

---

# 21. SSE 心跳（Heartbeat）

还有一个实际生产环境非常重要的问题：

**代理服务器可能认为连接太久没有数据，然后把连接断掉。**

所以服务器经常发送：

```text
: heartbeat

```

注意：

```text
:
```

开头的是 SSE comment。

客户端不会触发 message event。

但是它可以让连接保持活跃。

例如每 15 秒：

```text
: ping

```

或者：

```text
: heartbeat 2026-09-11T14:00:00

```

---

# 22. Nginx 是 SSE 的大坑

如果架构是：

```text
Browser
   ↓
Nginx
   ↓
Node / Java / Go
```

Nginx 可能对 Response 做 buffering。

结果：

服务器实际上：

```text
data: 1

data: 2

data: 3

```

但是浏览器：

```text
          等等……
          等等等……
          等等……

一次性收到：

data: 1

data: 2

data: 3
```

SSE 就失去意义了。

通常需要关闭代理缓冲，例如：

```http
X-Accel-Buffering: no
```

或者在 Nginx 配置：

```nginx
proxy_buffering off;
```

这属于 SSE 生产环境非常常见的问题。

---

# 23. SSE 的连接模型

如果有：

```text
10000 users
```

每个人都有一个 SSE：

```text
User 1  ───────┐
User 2  ───────┤
User 3  ───────┤
User 4  ───────┤── Server
...            │
User 10000 ────┘
```

服务器需要维护大量长连接。

所以 SSE 虽然简单，但并不意味着：

> **无限规模下完全没有成本。**

生产环境通常需要考虑：

* connection limit
* event loop
* memory
* load balancer
* reverse proxy
* timeout
* heartbeat
* reconnect
* event replay
* Redis / Kafka 等消息系统

---

# 24. SSE + Redis 是一个非常经典的架构

例如：

```text
                ┌── Server A ── User 1
Redis Pub/Sub ──┼── Server B ── User 2
                ├── Server C ── User 3
                └── Server D ── User 4
```

业务服务：

```text
Order Service
      │
      ↓
Redis Pub/Sub
      │
      ├──── Server A
      ├──── Server B
      └──── Server C
```

然后每个 Server：

```text
Redis Event
    ↓
SSE
    ↓
Browser
```

这样就可以把：

**消息产生**

和

**消息推送**

解耦。

---

# 25. SSE 的认证

通常可以使用 Cookie：

```javascript
new EventSource("/events");
```

浏览器会自动带同源 Cookie。

如果是跨域：

```javascript
new EventSource("https://api.example.com/events", {
    withCredentials: true
});
```

服务器需要正确处理 CORS。

不过这里要特别注意：

**原生 EventSource 对自定义 Authorization Header 的支持很有限。**

所以很多系统会采用：

```text
Cookie
```

或者：

```text
短期 token + URL
```

但把敏感 token 放 URL 有日志泄露风险，因此生产环境要谨慎。

---

# 26. SSE 的优点总结

SSE 最大的优势就是：

### 简单

基于 HTTP：

```text
GET
HTTP Response
```

不需要像 WebSocket 一样处理复杂的协议升级。

### 浏览器原生支持

```javascript
new EventSource()
```

### 自动重连

浏览器帮你做。

### 支持事件类型

```text
event: message
event: notification
event: progress
```

### 支持断线恢复

```text
id: 100
```

配合：

```http
Last-Event-ID: 100
```

### 非常适合流式输出

尤其是：

```text
AI
日志
任务进度
通知
监控
```

---

# 27. SSE 的缺点

最大的缺点：

### 单向

```text
Server → Client
```

客户端不能通过 SSE 通道主动给服务器发送消息。

需要另外：

```text
POST /message
```

例如：

```text
Client
  │
  ├── POST /chat ───────→ Server
  │
  │
  │ ←── SSE streaming ── Server
  │
  │ ←── SSE streaming ── Server
  │
  │ ←── SSE streaming ── Server
```

这其实就是很多 AI Chat 架构的模式。

---

# 28. 一句话理解 SSE

如果让我用一句话概括：

> **SSE = 一个保持打开的 HTTP Response，服务器不断按照 `text/event-stream` 格式往里面写事件，浏览器持续接收，并且支持自动重连。**

你可以把它记成：

```text
HTTP
  +
长连接
  +
text/event-stream
  +
Server → Client
  +
自动重连
  +
事件 ID
```

---

# 29. 最值得掌握的一张图

```text
                    SSE

       ┌─────────────────────────┐
       │                         │
       │       HTTP Request      │
Browser ────────────────────────→ Server
       │                         │
       │    HTTP 200             │
       │    Content-Type:        │
       │    text/event-stream    │
       │ ←───────────────────────│
       │                         │
       │    data: hello          │
       │ ←───────────────────────│
       │                         │
       │    data: world          │
       │ ←───────────────────────│
       │                         │
       │    event: message       │
       │    data: xxx            │
       │ ←───────────────────────│
       │                         │
       │    id: 123              │
       │    data: xxx            │
       │ ←───────────────────────│
       │                         │
       │       长连接保持         │
       │                         │
       └─────────────────────────┘

             Server → Client
```

如果你正在学后端，我建议下一步重点搞懂 **“SSE 在 Java/Spring Boot 中怎么实现 + Nginx 为什么会把 SSE 缓冲住 + SSE 和 WebSocket/HTTP Streaming 的底层区别”**。这三个搞懂以后，SSE 基本就吃透了。
