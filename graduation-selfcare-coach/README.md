# 셀프케어 코치 (LangGraph Education Agent)

**답을 대신 주지 않고, 내 몸·마음 신호를 스스로 읽을 줄 알게 가르치는** 교육형 코치.
오늘의 기록(식단·수면·휴식·운동)을 넣으면 **소크라테스식 질문 → 채점 → 힌트/정답 → 자기 몸에 적용**으로 이끌고,
그렇게 나온 **"나에 대해 알게 된 것"을 카드로 모아준다.** 산출물은 대화 로그가 아니라 **자기 발견**이다.

**배포:** https://selfcare-coach.streamlit.app/
설계: [../../졸업과제/그래프설계.md](../../졸업과제/그래프설계.md)

![그래프](coach_graph.png)

## 흐름

```
START → safety_guard ─(위험? 안내 후 END)─→ route_record
  route_record ─(기록? empathy / 질문·잡담? redirect → END)
  empathy ─(애매? clarify →[답 대기]→ absorb / 명확? diagnose)
  diagnose ─(다 배웠나? closing / 가르칠 개념 있나? socratic_q)
  socratic_q →[답 대기]→ guard_answer ─(위험? END)─→ route_intent
  route_intent ─→ answer: evaluate / object: handle_object→absorb / confused: rephrase / stop: closing
  evaluate ─→ correct: praise / 틀림: hint / 힌트 소진: reveal(정답 공개)
  hint →[답 대기]→ guard_answer (재시도)
  praise·reveal → reflect →[답 대기]→ capture_insight
  capture_insight ─(자기 신호를 읽었나? 발견 저장)─→ enrich_agent ⇄ tools(웹검색) → closing → END
```

*답을 기다리는 3지점에서 멈춘다 → `interrupt_before=["absorb","guard_answer","capture_insight"]` + checkpointer.*
*못 맞혀도(`reveal`) 끝내지 않고 `reflect`로 이어, 배운 걸 자기 몸에 적용해 발견 하나를 남긴다.*

## 과제 요구사항 대응

| 요구 | 구현 |
|---|---|
| **노드 3개+** | **21개** (safety·empathy·diagnose·socratic_q·evaluate·hint·reveal·reflect·capture_insight·enrich·tools …) |
| **분기 1개+** | **10군데** — 조건부 엣지 6(기록·애매·도메인·의도·채점·툴호출) + **Command 분기 4**(안전·답변안전·되묻기·발견) |
| **Tool 연동 1개+** | `search_web` — `@tool` → `bind_tools` → `ToolNode` → `tools_condition` (#14.1) |
| (선택) 메모리 | **SqliteSaver** checkpointer — 재시작해도 배운 개념·발견 유지 (#14.2) |
| (선택) 여러 도메인 | 식단·수면·휴식·운동 (개념 9개) |

## 고급 패턴 (강의 이후 심화)

| 패턴 | 강의 | 코치에서 |
|---|---|---|
| **Command** | #13.9 | `safety_guard`·`guard_answer`·`absorb`·`capture_insight` — 상태 갱신과 분기를 한 노드에서 (중복 라우팅 람다 4개 제거) |
| **Evaluator-Optimizer** | #16.6 | 출력 가드가 막으면 피드백을 들고 **재생성**(`ask_guarded`) — 차단하고 끝내지 않는다 |
| **Streaming** | #14.2 | `stream_mode="updates"` — 노드가 끝날 때마다 "지금 뭐 하는 중"을 UI에 표시 |
| **Parallelization** | #16.4 | 안전 검사(키워드·Moderation·LLM 검사관)를 `ThreadPoolExecutor`로 병렬 |
| **langgraph.json** | #14.5 | LangGraph 배포·관측 설정 |

## 강의 적용

| 강의 | 코치에서 |
|---|---|
| **#9.3 Guardrails** | Input 가드(입력 3지점 전부) + **Output 가드**(코치 응답의 의료 조언·진단 차단) |
| **#14.1 Tool Nodes** | `search_web` 웹검색 — 개념을 **맞힌 뒤에만** 실천 팁 한 줄 |
| **#14.2 Memory** | **SqliteSaver** — 배운 개념·발견이 재시작 후에도 남는다 |
| **#14.3 Human-in-the-loop** | `interrupt_before=["absorb","guard_answer","capture_insight"]` — 답 대기 3지점 |
| **#16.3 Routing** | `route_intent` — 답변/항의/혼란/중단을 갈라서 다르게 처리 |
| **#17 Testing** | pytest + parametrize + 노드 단위 테스트 + **LLM as Judge** |

## 설계 포인트

**1. 개념은 데이터, 그래프는 고정.** 도메인을 아무리 더해도 노드·엣지는 안 늘어난다. `diagnose`가 도메인을 판별하면 `socratic_q → evaluate → praise/hint → reflect → capture_insight` 공통 흐름이 어떤 개념이든 똑같이 처리한다. 복잡함은 **판별 단계로 옮긴다.**

**2. 넘겨짚지 않는다.** 도메인을 알 수 없는 입력("피곤해")은 `clarify`가 되묻고, 코치가 잘못 짚었으면 `route_intent`가 **항의를 알아듣고** `handle_object`가 사과 후 다시 진단한다.

**3. 산출물은 자기 발견.** 개념을 한 단어 맞히는 걸로 끝나지 않는다. `reflect`가 **자기 몸에 적용**하게 하고, 거기서 나온 "나는 이럴 때 이렇더라"를 `capture_insight`가 카드로 모은다. 못 맞혀도(`reveal`) 이 단계로 이어 빈손으로 보내지 않는다.

**4. 안전은 여러 겹.** 키워드(의학 응급) + **Moderation API**(self-harm, 무료) + **LLM 검사관**(한국어·맥락) + **Output 가드**(의료 조언 차단). 각각 다른 걸 잡는다 — Moderation은 한국어 자해 표현을 놓쳐서 LLM 검사관을 덧댔다. 의학 응급 → 119·병원 / 정신적 위기 → **109**로 갈래를 나눴다.

**5. 판정은 temperature=0.** 분류·채점(라우팅·evaluate·output guard)은 매번 같은 답이 나와야 한다. 생성(공감·힌트)만 온도를 준다.

**6. 구조화 출력에 bool을 앞세우지 않는다.** 모델은 필드 순서대로 생각한다 — bool이 맨 앞이면 근거 쓰기 전에 결론부터 뱉는다. `reason`을 맨 앞에, 판정은 이름 있는 분류(`Literal: felt/cause/none` 등)로 받고 bool은 코드에서 만든다.

## 파일

| 파일 | 내용 |
|---|---|
| `app.py` | **Streamlit UI** (홈=발견 갤러리 / 기록 / 대화 / 완료) |
| `state.py` | `CoachState` (messages는 `add_messages` 리듀서) |
| `concepts.py` | 개념 9개 (식단3·수면2·휴식2·운동2) + 도메인 키워드 |
| `nodes.py` | 노드 + 라우터 + `capture_insight`(발견 저장) + `enrich_agent`(웹검색) |
| `prompts.py` | 코칭 프롬프트 (공감·힌트·insight·bridge 등) |
| `safety.py` | 입·출력 가드 · Moderation · LLM 위기/의료 검사관 |
| `tools.py` | `search_web` (`@tool`, DuckDuckGo) |
| `graph.py` | 그래프 조립 · `build_persistent_graph()`(SQLite) |
| `llm.py` / `vision.py` | LLM 팩토리 · 운동기구 화면 사진 판독 |
| `tests.py` / `test_flows.py` | **pytest + LLM Judge** (강의 #17) |
| `langgraph.json` | LangGraph 배포 설정 |

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env             # OPENAI_API_KEY (없으면 규칙기반 폴백)
streamlit run app.py             # 웹 UI
python chat.py                   # 터미널 대화 (진도는 coach_memory.db에 저장)
python -m pytest -q              # 테스트
```

- LLM: `gpt-4o-mini`. 웹검색: DuckDuckGo(무료). Moderation: OpenAI(무료).
- 배포(Streamlit Cloud)에선 키를 **Secrets**에 넣는다 — `app.py`가 `st.secrets` → 환경변수로 넘긴다.
- ⚠️ `coach_memory.db`는 **개인 건강 기록**이라 gitignore. 절대 커밋·배포 금지.
- 개발자는 대화를 수집·열람하지 않는다. 세션 이어가기용으로만 임시 저장되고, 답변 생성을 위해 OpenAI로만 전송된다.

> 이 코치는 학습용입니다. 의료 조언·위기 상담 도구가 아닙니다.
> 몸이 급하면 119 · 마음이 힘들면 자살예방 상담 **109** (24시간, 무료)
