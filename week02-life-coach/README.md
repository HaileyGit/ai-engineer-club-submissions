# Life Coach Agent — Web Search + File Search

노마드코더 AI 엔지니어 클럽 2주차 과제. **Streamlit + OpenAI Agents SDK**로 만든 라이프 코치 에이전트.
강의: AI Agents 마스터클래스 #8.0 ~ #8.3 (OpenAI Agents SDK).

- 과제①(Web Search): 웹 검색으로 동기부여·습관 조언 — #8.0~8.2
- 과제②(File Search): 개인 목표 문서를 기억·참조 + 웹과 결합 — #8.3

## 기능

- **Streamlit 채팅 UI** — `st.chat_input` / `st.chat_message`
- **세션 메모리** — `SQLiteSession`으로 대화를 기억
- **웹 검색** — `WebSearchTool`로 검증된 최신 방법 검색
- **파일 검색(RAG)** — `FileSearchTool` + Vector Store로 개인 목표 문서(`goals.txt`)를 참조
- **결합** — 내 목표(파일) + 검증된 방법(웹)을 합쳐 개인화 추천
- 스트리밍 + 도구 진행 상태(📂/🔍) + 파일 업로드(채팅창 첨부) + 디버그 사이드바

## 실행

```bash
cp .env.example .env                 # OPENAI_API_KEY 입력
uv sync
uv run python setup_vector_store.py  # ① 한 번만: 목표 문서를 Vector Store에 올리고 ID를 .env에 저장
uv run streamlit run app.py          # ② 앱 실행
```

## 예시 상호작용

```
User : 내 운동 목표 잘 되어가고 있어?
Coach: 📂 목표 문서 검색 → "주 3회 운동·러닝 20분" 확인
Coach: 🔍 웹 검색 → "운동 루틴 유지하는 방법"
Coach: 목표와 검증된 방법을 합쳐 개인화 조언
```

## 파일

| 파일 | 설명 |
|------|------|
| `app.py` | Streamlit 라이프 코치 앱 (제출 본체) |
| `goals.txt` | 개인 목표 문서 (FileSearch 대상) |
| `setup_vector_store.py` | Vector Store 생성 + goals.txt 업로드 (1회 실행) |
| `8.0_chat_ui.ipynb` | #8.0 엔진(Agent·메모리·스트리밍) 학습 노트북 |
| `8.3_file_search.ipynb` | #8.3 RAG(Vector Store·검색·결합) 학습 노트북 |
| `pyproject.toml` / `uv.lock` | 의존성 |
