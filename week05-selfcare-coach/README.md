# Week 05 — 스스로 배우는 셀프케어 코치 (Demo Day)

> 테마: 교육 & 학습 · LangGraph 교육 에이전트

답을 대신 주지 않고 **소크라테스식 질문**으로, 사용자가 자기 몸·마음 신호를 **스스로 읽는 법을 배우게** 가르치는 코치. (물고기 대신 낚시를 가르치는 교육 에이전트)

## 파일
- `데모데이_셀프케어코치.ipynb` — **설계(Step 1) + LangGraph 코드(Step 2) + 데모** (자족 실행)
- `state.py` · `concepts.py` · `nodes.py` · `graph.py` · `criteria.txt` — 코치 모듈
- `.env.example` — LLM 쓸 때 `OPENAI_API_KEY`

## 그래프
`safety_guard → empathy → diagnose →(분기) socratic_q →[답 대기] evaluate →(분기) praise / hint→(루프) → closing`
- 분기(conditional edges) 3곳 · 힌트 루프 · 유저 답 대기(`interrupt_before` + checkpointer)

## 실행
```
pip install langgraph langchain-openai python-dotenv
python graph.py      # 또는 노트북 Run All
```
`evaluate`(의미 판정)·`empathy`·`closing`은 LLM(gpt-4o-mini), 나머지는 규칙기반. **키 없으면 규칙기반으로 자동 폴백**해서 키 없이도 실행됩니다.
