# Movie Agent — Complete Agentic Loop

AI Agents 마스터클래스 #2.4~2.7 — **완전한 에이전트 루프**를 갖춘 Movie Agent.
수동 프롬프팅(#2.2)이 아니라 OpenAI **`tools` 파라미터 + `tool_calls`** 로 구현.

- API base: `https://nomad-movies-2.nomadcoders.workers.dev`
- 모델: `gpt-4o-mini`

## 요구사항

실제 API를 호출하는 도구 3개:

- `get_popular_movies()` → `GET /movies`
- `get_movie_details(id)` → `GET /movies/:id`
- `get_similar_movies(id)` → `GET /movies/:id/similar`

에이전트 조건:

- OpenAI `tools` 파라미터 사용 (수동 프롬프팅 X)
- 응답의 `tool_calls` 처리
- 실제 API 호출 후 결과를 다시 모델에 전달
- 메모리 기반 멀티턴 대화 지원
- 모델이 최종 답변 줄 때까지 루프 지속

## 상태

🚧 **WIP** — 폼 제출용 placeholder. 강의(#2.4~2.7) 수강 후 `main.ipynb` 에 직접 빌드 예정.
