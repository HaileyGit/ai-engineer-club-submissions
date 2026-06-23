# 한상 — Restaurant Bot (Multi-Agent Handoffs)

노마드코더 AI 엔지니어 클럽 과제. **OpenAI Agents SDK의 handoff**로 만든 멀티 에이전트 한식당 봇.
강의: AI Agents 마스터클래스 #9.4 ~ #9.6.

## 에이전트 4종
- **Triage(안내)** — 손님 요청을 보고 알맞은 담당에게 라우팅 (직접 답 X)
- **Menu(메뉴)** — 메뉴·재료·알레르기
- **Order(주문)** — 주문 받기·확인
- **Reservation(예약)** — 인원/날짜/시간 예약

## 기능
- **Handoff** — `handoffs=[...]` 로 Triage → 전문가 인계. 전문가들도 서로 handoff (예약 중 메뉴 질문 → Menu 로 전환)
- **handoff UI 표시** — "🔀 메뉴 담당에게 연결합니다" 시스템 배너
- **#9.5 멀티턴 유지** — 현재 담당(`active_agent_name`)을 `session_state`에 캐싱 → 매번 Triage로 안 돌아감
- **메신저 UI** — 좌/우 말풍선, 담당별 아바타·이름, 시간, 타이핑 인디케이터, 한국 전통(한지·현판) 디자인
- 환영 + 예시 버튼, 대화 메모리(`SQLiteSession`)

## 실행
```bash
cp .env.example .env        # OPENAI_API_KEY 입력
uv sync
uv run streamlit run app.py
```

## 파일
| 파일 | 설명 |
|------|------|
| `app.py` | Streamlit 멀티 에이전트 봇 (제출 본체) |
| `9.4_handoffs.ipynb` | #9.4 handoff 개념 학습 노트북 |
| `pyproject.toml` / `uv.lock` | 의존성 (streamlit, openai-agents, python-dotenv) |
