# -*- coding: utf-8 -*-
"""
llm_client.py — LLM 推理层：统一封装不同大模型的 API 接口

支持三类 provider（在 config.yaml 中配置）：
  - openai            : OpenAI 官方（gpt-4o、gpt-3.5-turbo 等）
  - anthropic         : Anthropic 官方（Claude 系列）
  - openai_compatible : 任何 OpenAI 兼容端点，含：
      * 阿里云百炼 DashScope（Qwen 系列）base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
      * Together AI / Groq 等托管开源模型（Llama 3 70B）
      * 本地 Ollama（base_url=http://localhost:11434/v1，api_key 任意填）
"""
import os
import time


class LLMClient:
    def __init__(self, name: str, cfg: dict, gen_cfg: dict):
        self.name = name
        self.provider = cfg["provider"]
        self.model = cfg["model"]
        self.temperature = gen_cfg.get("temperature", 0)
        self.max_tokens = gen_cfg.get("max_tokens", 1024)

        api_key = os.environ.get(cfg.get("api_key_env", ""), "")
        if not api_key and self.provider != "openai_compatible":
            raise RuntimeError(f"环境变量 {cfg.get('api_key_env')} 未设置（模型 {name}）")

        if self.provider == "anthropic":
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        elif self.provider in ("openai", "openai_compatible"):
            from openai import OpenAI
            kwargs = {"api_key": api_key or "not-needed"}
            if cfg.get("base_url"):
                kwargs["base_url"] = cfg["base_url"]
            self._client = OpenAI(**kwargs)
        else:
            raise ValueError(f"未知 provider: {self.provider}")

    def generate(self, prompt: str, max_retries: int = 3) -> dict:
        """
        调用模型，返回:
        {'text': str, 'input_tokens': int, 'output_tokens': int,
         'latency': float, 'error': str|None}
        """
        last_err = None
        for attempt in range(max_retries):
            t0 = time.perf_counter()
            try:
                if self.provider == "anthropic":
                    resp = self._client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    latency = time.perf_counter() - t0
                    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
                    return {"text": text,
                            "input_tokens": resp.usage.input_tokens,
                            "output_tokens": resp.usage.output_tokens,
                            "latency": latency, "error": None}
                else:
                    resp = self._client.chat.completions.create(
                        model=self.model,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    latency = time.perf_counter() - t0
                    usage = getattr(resp, "usage", None)
                    return {"text": resp.choices[0].message.content or "",
                            "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                            "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                            "latency": latency, "error": None}
            except Exception as e:  # 网络/限流等错误：指数退避后重试
                last_err = str(e)
                wait = 2 ** attempt * 2
                print(f"    [{self.name}] 调用失败({attempt+1}/{max_retries}): {last_err[:120]} — {wait}s 后重试")
                time.sleep(wait)
        return {"text": "", "input_tokens": 0, "output_tokens": 0,
                "latency": 0.0, "error": last_err}
