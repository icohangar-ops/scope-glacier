"""
Bedrock Client — Native Amazon Bedrock Runtime Converse API for Claude Haiku.
https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
"""
from __future__ import annotations
import json, logging, os, time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
logger = logging.getLogger(__name__)

@dataclass
class BedrockClient:
    """Thin wrapper around boto3 Bedrock Runtime Converse API."""
    model_id: str = field(default_factory=lambda: os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"))
    region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-east-1"))
    max_tokens: int = 1500
    temperature: float = 0.3
    max_retries: int = 3
    base_delay: float = 1.0
    _client: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._client = boto3.client("bedrock-runtime", region_name=self.region)

    def converse(self, messages: List[Dict[str, Any]], system: Optional[str] = None,
                 temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        inference_config = {"maxTokens": max_tokens or self.max_tokens,
                            "temperature": temperature if temperature is not None else self.temperature}
        for attempt in range(self.max_retries):
            try:
                kwargs: Dict[str, Any] = {"modelId": self.model_id, "messages": messages, "inferenceConfig": inference_config}
                if system:
                    kwargs["system"] = [{"text": system}]
                response = self._client.converse(**kwargs)
                output = response.get("output", {})
                message = output.get("message", {})
                text = "".join(cb.get("text", "") for cb in message.get("content", []))
                usage = response.get("usage", {})
                return {"content": text, "input_tokens": usage.get("inputTokens", 0),
                        "output_tokens": usage.get("outputTokens", 0), "model": self.model_id,
                        "stop_reason": message.get("stopReason")}
            except ClientError as e:
                if e.response.get("Error", {}).get("Code", "") in ("ThrottlingException", "ServiceUnavailable") and attempt < self.max_retries - 1:
                    time.sleep(self.base_delay * (2 ** attempt)); continue
                raise
        raise RuntimeError(f"Bedrock converse failed after {self.max_retries} retries")

    def chat(self, prompt: str, system: Optional[str] = None, **kw) -> str:
        return self.converse(messages=[{"role": "user", "content": [{"text": prompt}]}], system=system, **kw)["content"]

    def multi_turn(self, messages: List[Dict[str, str]], system: Optional[str] = None, **kw) -> str:
        return self.converse(messages=[{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages], system=system, **kw)["content"]
