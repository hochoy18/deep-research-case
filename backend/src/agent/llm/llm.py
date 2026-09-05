"""
OpenAI 兼容 LLM 客户端封装 —— 内置重试与异常处理。

特性:
    * 指数退避 + 抖动 (exponential backoff with jitter)
    * 区分"可重试"瞬时错误 (网络、限流、超时、5xx) 与"不可重试"客户端错误
      (鉴权、参数错误、配额等 4xx)。后者立即抛出,不浪费重试预算。
    * 客户端显式 timeout,避免请求被挂死。
    * 通过 loguru 输出每次重试的告警/最终失败日志,便于排障。
    * 重试参数全部可由构造器传入,保持默认值的向后兼容。

使用示例::

    llm = OpenAICompatibleLLM(model_id="deepseek-v4-flash")
    text = llm.generate_response("你好")
"""

from __future__ import annotations

import os
import random
import time
from typing import Optional, Tuple, Type

from loguru import logger
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    OpenAI,
    PermissionDeniedError,
    RateLimitError,
)

from agent.post import Post


# ---------------------------------------------------------------------------
# 常量 / 默认值
# ---------------------------------------------------------------------------

DEFAULT_MAX_RETRIES: int = 3
DEFAULT_INITIAL_BACKOFF: float = 1.0      # 秒
DEFAULT_MAX_BACKOFF: float = 30.0        # 秒,防止无限拉长退避
DEFAULT_BACKOFF_MULTIPLIER: float = 2.0  # 1 -> 2 -> 4 -> 8 ...
DEFAULT_JITTER: float = 0.2              # ±20% 的随机扰动,避免雷鸣群
DEFAULT_TIMEOUT: float = 600.0            # SDK 单次请求超时


class LLMRetryExhausted(RuntimeError):
    """LLM 请求在所有重试耗尽后仍然失败时抛出,便于上层捕获与降级。"""


# ---------------------------------------------------------------------------
# 主体类
# ---------------------------------------------------------------------------

class OpenAICompatibleLLM:
    """带重试与异常处理的 OpenAI 兼容 LLM 客户端。"""

    # 这些异常属于"瞬时/服务端问题",应当重试。
    RETRYABLE_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
    )

    # 这些异常属于"客户端/参数问题",重试无意义,立即抛出。
    NON_RETRYABLE_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
        AuthenticationError,
        PermissionDeniedError,
        BadRequestError,
        NotFoundError,
    )

    def __init__(
        self,
        model_id: str = "",
        *,
        max_retries: int = DEFAULT_MAX_RETRIES,
        initial_backoff: float = DEFAULT_INITIAL_BACKOFF,
        max_backoff: float = DEFAULT_MAX_BACKOFF,
        backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER,
        jitter: float = DEFAULT_JITTER,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.model_id = model_id
        self.max_retries = max(0, int(max_retries))
        self.initial_backoff = max(0.0, float(initial_backoff))
        self.max_backoff = max(self.initial_backoff, float(max_backoff))
        self.backoff_multiplier = max(1.0, float(backoff_multiplier))
        self.jitter = max(0.0, float(jitter))
        self.timeout = float(timeout)

    # ------------------------------------------------------------------ utils

    def _calculate_backoff(self, attempt: int) -> float:
        """计算第 ``attempt`` 次失败后的退避时间(秒),带抖动。"""
        backoff = min(
            self.initial_backoff * (self.backoff_multiplier ** attempt),
            self.max_backoff,
        )
        if self.jitter > 0 and backoff > 0:
            jitter_range = backoff * self.jitter
            backoff = backoff + random.uniform(-jitter_range, jitter_range)
        return max(0.0, backoff)

    def _build_client(self) -> OpenAI:
        return OpenAI(
            api_key=os.getenv("APP_TOKEN"),
            base_url=os.getenv("LLM_BASE_URL"),
            timeout=self.timeout,
            # SDK 自带的轻量重试关掉,统一由本类管理,避免双重退避叠加。
            max_retries=0,
        )

    def _do_request(self, query: str) -> str:
        """真正发起一次请求;返回 strip 后的文本。"""
        client = self._build_client()
        response = client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query},
            ],
            extra_body={"enable_thinking": False},
        )
        content = response.choices[0].message.content
        # 去除 <think> 推理块,避免 thinking 模型把过程文本带出来
        return Post.strip_think_tags(content)

    # ----------------------------------------------------------------- public

    def generate_response(self, query: str) -> str:
        """带重试与异常处理的 LLM 调用入口。

        Args:
            query: 用户输入的提示文本。

        Returns:
            模型返回的正文(已剥离 ``<think>`` 标签)。

        Raises:
            LLMRetryExhausted: 重试耗尽后仍失败。
            AuthenticationError / BadRequestError / ...: 不可重试的客户端错误,
                原样向上抛出以便上层针对性处理。
        """
        last_exception: Optional[BaseException] = None
        total_attempts = self.max_retries + 1  # 初次 + 重试

        for attempt in range(total_attempts):
            try:
                return self._do_request(query)

            except self.NON_RETRYABLE_EXCEPTIONS as exc:
                # 鉴权失败 / 配额 / 参数错误等 —— 重试毫无意义,直接抛
                logger.error(
                    f"[LLM] 不可重试错误 model={self.model_id!r} "
                    f"attempt={attempt + 1}/{total_attempts}: "
                    f"{type(exc).__name__}: {exc}"
                )
                raise

            except self.RETRYABLE_EXCEPTIONS as exc:
                last_exception = exc
                if attempt >= self.max_retries:
                    logger.error(
                        f"[LLM] 重试 {self.max_retries} 次后仍失败 "
                        f"model={self.model_id!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    break

                backoff = self._calculate_backoff(attempt)
                logger.warning(
                    f"[LLM] 请求失败 {type(exc).__name__} "
                    f"model={self.model_id!r} "
                    f"attempt={attempt + 1}/{total_attempts}: {exc} "
                    f"-> {backoff:.2f}s 后重试"
                )
                time.sleep(backoff)
                continue

            except APIError as exc:
                # 兜底:OpenAI SDK 其余状态码错误,按 HTTP 状态码决定是否重试。
                status_code = getattr(exc, "status_code", None)
                if isinstance(status_code, int) and 400 <= status_code < 500:
                    logger.error(
                        f"[LLM] 客户端错误 HTTP {status_code} "
                        f"model={self.model_id!r}: {exc}"
                    )
                    raise

                last_exception = exc
                if attempt >= self.max_retries:
                    logger.error(
                        f"[LLM] 重试 {self.max_retries} 次后仍失败 "
                        f"model={self.model_id!r}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    break

                backoff = self._calculate_backoff(attempt)
                logger.warning(
                    f"[LLM] 请求失败 {type(exc).__name__} "
                    f"model={self.model_id!r} "
                    f"attempt={attempt + 1}/{total_attempts}: {exc} "
                    f"-> {backoff:.2f}s 后重试"
                )
                time.sleep(backoff)
                continue

            except Exception as exc:  # noqa: BLE001 —— 保守兜底
                # 未预期的异常(网络层、解析错误等),记堆栈后重试。
                last_exception = exc
                logger.exception(
                    f"[LLM] 未预期异常 model={self.model_id!r} "
                    f"attempt={attempt + 1}/{total_attempts}: "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt >= self.max_retries:
                    break
                time.sleep(self._calculate_backoff(attempt))
                continue

        # 走到这里:重试已耗尽
        raise LLMRetryExhausted(
            f"LLM 请求重试 {self.max_retries} 次后仍失败 "
            f"(model={self.model_id!r}): {last_exception}"
        ) from last_exception


# ---------------------------------------------------------------------------
# 简易自检 (python -m agent.llm.llm)
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    llm = OpenAICompatibleLLM(model_id="deepseek-v4-flash")
    print(llm.generate_response("用一句话介绍你自己。"))
