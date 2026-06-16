# Life Coach Agent — Web Search

노마드코더 AI 엔지니어 클럽 2주차 과제. **Streamlit + OpenAI Agents SDK + WebSearchTool**로 만든 라이프 코치 에이전트.
강의: AI Agents 마스터클래스 #8.0 ~ #8.2 (OpenAI Agents SDK - ChatGPT Clone) 응용.

## 기능

- **Streamlit 채팅 UI** — `st.chat_input` / `st.chat_message`
- **세션 메모리** — `SQLiteSession`으로 대화를 기억 (코치가 앞 대화를 이어감)
- **웹 검색 도구** — `WebSearchTool`로 동기부여·습관·자기계발 등 검증된 최신 정보 검색
- **코치 페르소나** — 공감 + 근거 있는 조언 + 작은 실천 제안 (한국어 존댓말)
- 스트리밍 응답 + 웹검색 진행 상태 표시 + 디버그 사이드바(메모리 확인/초기화)

## 실행

```bash
cp .env.example .env        # OPENAI_API_KEY 입력 (WebSearchTool = OpenAI hosted tool 이라 필수)
uv sync
uv run streamlit run app.py
```

## 예시 상호작용

```
User : 아침에 일찍 일어나고 싶은데 자꾸 알람을 끄게 돼
Coach: 🔍 웹 검색 → 검증된 기상 루틴(서카디안 리듬·아침 빛·카페인 차단 등)을 출처와 함께 제안
User : 좋은 습관을 만들려면 어떻게 해야 해?
Coach: 앞 대화를 기억한 채로 습관 형성 기법을 검색해 답변
```

## 파일

| 파일 | 설명 |
|------|------|
| `app.py` | Streamlit 라이프 코치 앱 (제출 본체) |
| `8.0_chat_ui.ipynb` | #8.0 엔진(Agent·메모리·Runner·스트리밍)을 분해해 돌려본 학습 노트북 |
| `pyproject.toml` / `uv.lock` | 의존성 (streamlit, openai-agents, python-dotenv) |
