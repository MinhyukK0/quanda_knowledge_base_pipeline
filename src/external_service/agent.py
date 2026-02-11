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

    def _extract_json(self, response: str) -> dict | list:
        """응답에서 JSON 추출"""
        import json

        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]
        return json.loads(response.strip())

    def _generate_directory_name(self, metadata: dict) -> str:
        """메타데이터에서 디렉토리명 생성"""
        import re

        # 카테고리와 태그에서 키워드 추출
        keywords = []

        categories = metadata.get("categories", [])
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(",") if c.strip()]
        if categories:
            keywords.extend(categories[:2])

        tags = metadata.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if tags and len(keywords) < 3:
            keywords.extend(tags[:2])

        if not keywords:
            return "misc-documents"

        # kebab-case로 변환
        dir_name = "-".join(keywords[:3])
        # 영문/숫자/하이픈만 유지, 한글은 제거
        dir_name = re.sub(r"[^a-zA-Z0-9\-]", "", dir_name.lower().replace(" ", "-"))
        # 연속 하이픈 제거
        dir_name = re.sub(r"-+", "-", dir_name).strip("-")

        return dir_name if dir_name else "misc-documents"

    async def find_similar_documents(
        self,
        documents: list[dict],
    ) -> list[list[str]]:
        """유사 문서 그룹 찾기 (내용 기반 의미론적 분석)

        Args:
            documents: [{key, content, metadata}, ...]

        Returns:
            그룹별 key 리스트 [["key1", "key2"], ["key3"], ...]
        """
        from textwrap import dedent

        # 문서 내용 포함하여 생성
        doc_entries = []
        for i, doc in enumerate(documents, 1):
            content = doc.get("content", "")
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")

            doc_entries.append(f"=== 문서 {i}: {doc['key']} ===\n{content}")

        docs_text = "\n\n".join(doc_entries)

        prompt = dedent(f"""
            다음 문서들을 분석하여 **정말로 중복되거나 동일한 내용**인 문서만 그룹으로 묶어주세요.

            병합 기준 (모두 충족해야 함):
            - 동일한 특정 주제를 다룸 (일반적인 주제 공유는 불충분)
            - 동일한 문서 유형 (가이드는 가이드끼리, 리포트는 리포트끼리)
            - 내용이 실제로 중복되거나 하나로 합쳐야 의미가 있는 경우

            병합하면 안 되는 경우:
            - 단순히 같은 도메인/분야를 다루는 경우 (예: 둘 다 "데이터" 관련)
            - 문서 유형이 다른 경우 (가이드 vs 리포트 vs 기술문서)
            - 각각 독립적인 정보를 담고 있는 경우

            확실하지 않으면 병합하지 마세요. 대부분의 문서는 단독 그룹이어야 합니다.

            문서들:
            {docs_text}

            JSON 형식으로 그룹을 반환해주세요 (다른 텍스트 없이):
            [["key1", "key2"], ["key3"], ...]

            주의: 모든 문서 키는 반드시 하나의 그룹에만 포함되어야 합니다.
        """).strip()

        response = await self.query_text(prompt, max_turns=1)

        try:
            groups = self._extract_json(response)
            if isinstance(groups, list) and all(isinstance(g, list) for g in groups):
                return groups
        except Exception:
            pass

        # 파싱 실패 시 각 문서를 개별 그룹으로
        return [[doc["key"]] for doc in documents]

    async def merge_documents(
        self,
        documents: list[dict],
    ) -> dict:
        """여러 문서를 하나로 병합

        Args:
            documents: [{key, content, metadata}, ...]

        Returns:
            {content, metadata, filename}
        """
        from textwrap import dedent

        # 문서 내용 조합
        docs_content = []
        for i, doc in enumerate(documents, 1):
            content = doc.get("content", "")
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            docs_content.append(f"=== 문서 {i}: {doc['key']} ===\n{content}")

        docs_text = "\n\n---\n\n".join(docs_content)

        # 첫 번째 문서의 파일명을 기본으로 사용
        first_key = documents[0]["key"]
        base_filename = first_key.split("/")[-1]

        prompt = dedent(f"""
            다음 문서들을 분석하여 하나의 **요약된 통합 문서**로 만들어주세요.

            작성 방식:
            - 단순히 문서들을 이어붙이지 말고, 핵심 내용을 추출하여 요약
            - 중복 정보는 한 번만 포함
            - 논리적 구조로 재구성 (제목, 섹션 등)
            - 원본보다 간결하지만 중요 정보는 모두 포함
            - 마크다운 형식으로 작성

            원본 문서들:
            {docs_text}

            JSON으로 반환해주세요 (다른 텍스트 없이):
            {{
                "directory": "주제-도메인명",
                "filename": "구체적-내용.md",
                "content": "요약된 통합 문서 (마크다운)",
                "metadata": {{
                    "summary": "통합 문서 요약 (2-3문장)",
                    "categories": ["카테고리1", "카테고리2"],
                    "tags": ["태그1", "태그2", "태그3"]
                }}
            }}

            directory/filename 작성 규칙:
            - 반드시 영문 kebab-case 사용 (소문자, 하이픈으로 연결)
            - directory: 문서의 주제/도메인을 나타내는 2-4단어
              예시: samsung-stock-analysis, fnguide-roe-query, kospi-etf-ranking, us-stock-price, compustat-data-guide
            - filename: 구체적인 문서 내용을 설명하는 이름.md
              예시: daily-price-summary.md, roe-consensus-report.md, top10-etf-list.md
            - 절대 "uncategorized", "session-report" 같은 일반적인 이름 사용 금지
            - 문서 내용에서 핵심 키워드를 추출하여 명명
        """).strip()

        response = await self.query_text(prompt, max_turns=1)

        try:
            result = self._extract_json(response)
            if isinstance(result, dict) and "content" in result and "metadata" in result:
                # directory, filename 기본값 설정
                if "directory" not in result or not result["directory"] or result["directory"] == "uncategorized":
                    # 카테고리/태그에서 디렉토리명 생성
                    result["directory"] = self._generate_directory_name(result.get("metadata", {}))
                if "filename" not in result or not result["filename"]:
                    result["filename"] = base_filename
                return result
        except Exception:
            pass

        # 파싱 실패 시 단순 연결
        merged_content = "\n\n---\n\n".join(
            doc.get("content", "").decode("utf-8", errors="replace")
            if isinstance(doc.get("content"), bytes)
            else doc.get("content", "")
            for doc in documents
        )

        # 메타데이터 병합
        all_summaries = []
        all_categories = set()
        all_tags = set()
        for doc in documents:
            meta = doc.get("metadata", {})
            if meta.get("summary"):
                all_summaries.append(meta["summary"])
            # categories가 문자열이면 쉼표로 분리
            categories = meta.get("categories", [])
            if isinstance(categories, str):
                categories = [c.strip() for c in categories.split(",") if c.strip()]
            if isinstance(categories, list):
                all_categories.update(categories)
            # tags도 마찬가지
            tags = meta.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            if isinstance(tags, list):
                all_tags.update(tags)

        # 요약 생성: 기존 요약들 조합 또는 첫 문장 사용
        if all_summaries:
            combined_summary = " ".join(all_summaries[:3])  # 최대 3개 요약 조합
            if len(combined_summary) > 500:
                combined_summary = combined_summary[:497] + "..."
        else:
            combined_summary = f"{len(documents)}개 문서 통합"

        metadata = {
            "summary": combined_summary,
            "categories": list(all_categories) or ["기타"],
            "tags": list(all_tags),
        }

        return {
            "content": merged_content,
            "metadata": metadata,
            "directory": self._generate_directory_name(metadata),
            "filename": base_filename,
        }
