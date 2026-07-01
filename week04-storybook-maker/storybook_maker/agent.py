"""Story Book Maker — Writer → Illustrator 파이프라인 (노트 11 Shorts 패턴).

ADK가 root_agent 변수를 자동 탐색하므로 이름 고정 필수.
`adk web`은 이 패키지의 부모 폴더(code/storybook-maker/)에서 실행.
"""
from google.adk.agents import Agent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

from .models import StoryBook
from .prompt import STORY_WRITER_PROMPT, ILLUSTRATOR_PROMPT
from .tools import generate_illustrations

# 비-Gemini 모델은 LiteLlm 래퍼로. (노트 10·11 패턴)
MODEL = LiteLlm(model="openai/gpt-4o-mini")

# 1) Story Writer — 테마 → 구조화 5페이지. output_key로 state["story_writer_output"]에 저장.
#    ⚠️ output_schema 쓰는 에이전트는 tool 사용 불가(ADK 제약) → 글만 쓴다.
story_writer_agent = Agent(
    name="StoryWriterAgent",
    description="테마를 받아 5페이지 동화를 구조화 데이터(text+visual)로 작성",
    instruction=STORY_WRITER_PROMPT,
    model=MODEL,
    output_schema=StoryBook,
    output_key="story_writer_output",
)

# 2) Illustrator — state의 동화를 읽어 페이지별 이미지 생성 → Artifact 저장.
#    ⚠️ mini가 가끔 도구를 안 부르면(노트 12 #12.1 팁) model을 "openai/gpt-4o"로 올린다.
illustrator_agent = Agent(
    name="IllustratorAgent",
    description="state의 동화 데이터로 페이지별 삽화를 생성해 artifact로 저장",
    instruction=ILLUSTRATOR_PROMPT,
    model=MODEL,
    tools=[generate_illustrations],
    output_key="illustrator_output",
)

# 3) 파이프라인 — Writer → Illustrator 순서. SequentialAgent = 뇌 없이 순서대로.
#    테마를 입력하면 바로 시작(대화 불필요라 LLM 메인으로 안 감쌈).
root_agent = SequentialAgent(
    name="StoryBookMaker",
    description="동화 작가 → 삽화가 순서로 5페이지 그림동화를 만든다",
    sub_agents=[story_writer_agent, illustrator_agent],
)
