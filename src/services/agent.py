from typing import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)


class AgentService:
    """Claude Agent 서비스 추상화 레이어"""

    def __init__(
        self,
        system_prompt: str | None = None,
        max_turns: int = 10,
        cwd: str | None = None,
        use_bedrock: bool = False,
        model: str | None = None,
    ):
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.cwd = cwd
        self.use_bedrock = use_bedrock
        self.model = model

    def _build_options(self, **kwargs) -> ClaudeAgentOptions:
        """ClaudeAgentOptions 빌드"""
        env = {}
        if self.use_bedrock:
            env["CLAUDE_CODE_USE_BEDROCK"] = "1"
        if self.model:
            env["ANTHROPIC_MODEL"] = self.model

        return ClaudeAgentOptions(
            system_prompt=kwargs.get("system_prompt", self.system_prompt),
            max_turns=kwargs.get("max_turns", self.max_turns),
            cwd=kwargs.get("cwd", self.cwd),
            env=env,
        )

    async def query(
        self,
        prompt: str,
        **kwargs,
    ) -> AsyncIterator[AssistantMessage | ResultMessage]:
        """Claude Agent에 쿼리 전송"""
        options = self._build_options(**kwargs)
        async for message in query(prompt=prompt, options=options):
            yield message

    async def query_text(self, prompt: str, **kwargs) -> str:
        """Claude Agent에 쿼리 전송 후 텍스트만 반환"""
        result_text = ""
        async for message in self.query(prompt, **kwargs):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result_text += block.text
        return result_text

    async def analyze_file(self, file_content: str, filename: str) -> dict:
        """파일 분석 후 메타데이터 반환"""
        import json
        from textwrap import dedent

        prompt = dedent(f"""
            다음 파일을 분석하고 메타데이터를 JSON 형식으로 반환해주세요.

            파일명: {filename}

            파일 내용:
            {file_content}

            다음 형식으로 JSON만 반환해주세요 (다른 텍스트 없이):
            {{
                "summary": "문서 요약 (2-3문장)",
                "categories": ["카테고리1", "카테고리2"],
                "tags": ["태그1", "태그2", "태그3"]
            }}
        """).strip()

        response = await self.query_text(prompt, max_turns=1)

        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            return {
                "summary": response[:200],
                "categories": ["기타"],
                "tags": [],
            }
