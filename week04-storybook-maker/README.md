# Story Book Maker (ADK 과제 — Basic Pipeline)

테마 → 5페이지 그림동화. **Story Writer**가 글(text+visual)을 구조화로 쓰고, **Illustrator**가 그걸 읽어 페이지별 삽화를 만들어 Artifact로 저장. (= 노트 11 Shorts Maker 패턴의 단순화)

## 파일

```
storybook-maker/            ← 여기서 `adk web` 실행
  storybook_maker/          ← 에이전트 패키지 (root_agent 자동탐색)
    __init__.py             from . import agent
    agent.py                story_writer / illustrator / root_agent(Sequential)
    models.py               Page, StoryBook (output_schema)
    prompt.py               두 에이전트 프롬프트 (수정 포인트)
    tools.py                generate_illustrations (state 읽고 → 이미지 → save_artifact)
    .env.example
  pyproject.toml
```

## 요구사항 매핑

| 과제 요구 | 구현 |
|---|---|
| ADK 두 에이전트 | `story_writer_agent`, `illustrator_agent` |
| Writer = 구조화 5페이지(text+visual) | `output_schema=StoryBook` |
| State로 공유 | Writer `output_key="story_writer_output"` → Illustrator가 `tool_context.state[...]` 로 읽음 |
| Illustrator 이미지 생성 | `tools=[generate_illustrations]` → gpt-image-1 |
| 이미지 = Artifact 저장 | `tool_context.save_artifact("page_N_image.jpeg", part)` |
| `adk web` 테스트 | root_agent = SequentialAgent |

## 실행

```bash
cd code/storybook-maker
uv sync                                   # google-adk 등 설치
cp storybook_maker/.env.example storybook_maker/.env   # OPENAI_API_KEY 채우기
adk web                                    # 브라우저 → 테마 입력 (예: "보라색 하늘을 좋아하는 토끼")
```
→ Writer가 5페이지 JSON을 state에 저장 → Illustrator가 페이지별 이미지를 artifact로. Web UI의 State/Artifacts 탭에서 확인.

## 알아둘 함정 (노트 기반)

- **output_schema 에이전트는 tool 못 씀** → Writer는 글만, Illustrator는 tool만. 역할 분리 이유.
- **mini가 도구를 안 부르면** (노트 12 #12.1) `agent.py`의 MODEL을 `openai/gpt-4o`로.
- **gpt-image-1**은 OpenAI org 인증이 필요할 수 있음. 막히면 `dall-e-3`로 교체(텍스트 삽입은 약함).
- 도구가 중복 호출돼도 `list_artifacts()` 체크로 재생성 스킵(비용 방지).
