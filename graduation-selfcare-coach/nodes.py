"""그래프 노드 (그래프설계.md §2).

각 노드 = state를 받아 **바뀐 부분만** dict로 return 하는 함수.
노드는 "무엇을 하는지"만 담는다. 나머지는 옆으로 뺐다:
    llm.py      LLM 클라이언트 + ask()/ask_structured()  (반복되던 try/except를 여기로)
    safety.py   위험 판정 + 안내 + Output guardrail
    prompts.py  프롬프트 문자열
    tools.py    웹검색 @tool
"""
from typing import Literal

from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel, Field

import prompts as P
from concepts import CONCEPTS, CONCEPT_ORDER, DOMAIN_KEYWORDS
from llm import ask, ask_structured, get_llm, get_llm_with_tools, _text_of
from safety import guard, output_guard, ask_guarded
from state import HINT_MAX
from tools import TOOLS  # noqa: F401  (graph.py가 nodes에서 가져간다)

# safety의 판정 함수들을 여기서도 노출한다 (테스트·외부에서 nodes로 접근하던 것 유지)
from safety import is_crisis, is_medical_risk, is_risk  # noqa: F401


# ── 안전 가드: 사용자 입력이 들어오는 **모든 지점**에 건다 ──────────────
# 입구에만 걸었더니 뚫렸다 — '잠이 온다'로 시작한 뒤 답변에 '심장이 아파'를 넣으니 통과.
#
# 가드 노드는 전부 **state를 바꾸면서 동시에 어디로 갈지도 정한다**(위험이면 END).
# 예전엔 그 "어디로"를 graph.py의 조건부 엣지 람다로 뺐는데, 똑같은
#   lambda s: "risk" if s.get("risk_flag") else "ok"
# 가 **네 군데에 복붙**돼 있었다. 가드를 하나 더 걸 때마다 저 람다도 같이 늘어난다.
# → 강의 #13.9 Command: 업데이트와 이동을 **노드가 함께** 정한다. graph.py에서 람다가 사라진다.
def _guarded(text, stage, ok_next):
    """위험하면 안내하고 END, 아니면 ok_next로. 네 가드가 공유하는 한 줄."""
    g = guard(text)
    return Command(goto=END if g["risk_flag"] else ok_next,
                   update={**g, "stage": stage})


def safety_guard(state) -> Command[Literal["route_record", "__end__"]]:
    """입구 가드 — 오늘 입력 검사."""
    return _guarded(state.get("today_input", ""), "safety_guard", "route_record")


def guard_answer(state) -> Command[Literal["route_intent", "__end__"]]:
    """대화 중 가드 — 질문에 대한 **답변**도 검사한다."""
    return _guarded(state.get("user_answer", ""), "guard_answer", "route_intent")


# ── 첫 입력 라우팅 — 기록인가, 질문인가, 잡담인가 ──────────────────────
# 코치가 오늘 입력을 무조건 "내가 한 일의 기록"으로 가정해서, "점심 뭐먹지?"(질문)에도
# 수업을 시작했다. 답을 대신 주지 않는 코치인데 질문을 덥석 받은 셈.
class RecordVerdict(BaseModel):
    kind: Literal["record", "question", "chitchat"] = Field(
        description="record=오늘 있었던 일의 기록(안 한 것도 기록) / "
                    "question=답을 구하는 질문 / chitchat=인사·잡담")
    reason: str = Field(description="판단 근거 한 줄")


def route_record(state):
    """첫 입력이 코칭할 수 있는 '기록'인지 가른다.

    ⚠️ **UI에서 카테고리(domain)를 골랐으면 이미 명확한 기록이다** → 판정을 건너뛴다.
       예전엔 "오징어"처럼 짧은 기록을 chitchat으로 오판해 redirect로 빠졌다(대화가
       시작도 안 됐다). 카테고리를 고른 건 "이건 식단 기록이야"라고 이미 말한 것이다.
       (route 판정은 카테고리 없이 자유 입력하는 chat.py 경로에서만 의미가 있다)
    """
    text = (state.get("today_input") or "").strip()
    if not text or state.get("domain"):
        return {"input_kind": "record", "stage": "route_record"}
    v = ask_structured(P.RECORD.format(text=text), RecordVerdict)
    return {"input_kind": v.kind if v else "record", "stage": "route_record"}


def redirect(state):
    """질문·잡담 → 코치의 정체성을 알리고 오늘 기록을 청한다. (답을 대신 주지 않는 코치니까)"""
    kind = "질문" if state.get("input_kind") == "question" else "잡담"
    msg = ask(P.REDIRECT.format(text=state.get("today_input", ""), kind=kind),
              fallback="저는 답을 대신 드리는 코치가 아니라, 질문으로 같이 짚어보는 코치예요. "
                       "오늘 있었던 일을 한 줄 적어주시면 함께 살펴볼게요.")
    return {"messages": [("ai", msg)], "stage": "redirect"}


# ── 받아주기 → 되묻기 → 한 박자 ────────────────────────────────────────
def empathy(state):
    """판단·지시 없이 먼저 공감 한 문장."""
    msg = ask(P.EMPATHY.format(ti=state.get("today_input", "")),
              fallback="오늘도 기록 남겨줘서 좋아요. 같이 천천히 살펴봐요.")
    return {"messages": [("ai", msg)], "stage": "empathy"}


def is_vague(state):
    """되물어야 하나? — **도메인 키워드가 하나도 안 잡히면** 애매로 본다.

    "새벽까지 못 잤어"(잠·새벽)는 뭔 얘긴지 알겠으니 그냥 진행하고,
    "피곤해"/"배고프다"는 어느 도메인인지 알 수 없으니 되묻는다.
    (LLM 판정은 "몇 시에 잤는지 정확히 안 썼다"며 멀쩡한 입력까지 과하게 되묻게 만들었다)
    """
    if state.get("domain"):                     # 사용자가 카테고리를 골랐다 → 추측할 게 없다
        return False                            # (UI에서 고르게 하니 넘겨짚기가 통째로 사라진다)
    if state.get("clarify_count", 0) >= 1:      # 한 번만 되묻는다
        return False
    text = state.get("today_input", "").strip()
    return not any(k in text for kws in DOMAIN_KEYWORDS.values() for k in kws)


def clarify(state):
    """애매한 입력 → 넘겨짚지 말고 열린 질문으로 되묻는다."""
    msg = ask(P.CLARIFY.format(text=state.get("today_input", "")),
              fallback="조금만 더 알려줄래요? 오늘 뭘 드셨는지, 몇 시에 주무셨는지 같은 거요.")
    return {"messages": [("ai", msg)],
            "clarify_count": state.get("clarify_count", 0) + 1, "stage": "clarify"}


def absorb(state) -> Command[Literal["read_record", "__end__"]]:
    """되묻기에 대한 답을 오늘 기록에 합친다 → 그 맥락으로 바로 진단."""
    reply = (state.get("user_answer") or "").strip()
    g = guard(reply)                        # 되묻기 답에도 위험이 실려올 수 있다
    return Command(
        goto=END if g["risk_flag"] else "read_record",
        update={"today_input": f'{state.get("today_input", "")} {reply}'.strip(),
                "user_answer": "", "stage": "absorb", **g})


# ⚠️ care 노드를 없앴다.
# 첫 응답이 말풍선 4연타였다 — ①공감(empathy) ②"그럼 하나만 같이 짚어볼까요?"(care)
# ③되짚기(socratic의 bridge) ④질문(socratic). 폰에서 벽처럼 느껴졌다.
# ②는 순수 filler였고, care의 '지친 사람 챙기기'는 EMPATHY가 상황 맞춤 공감으로 이미 한다.
# → care 제거. empathy(공감) → 바로 read_record → socratic(질문). 2~3개로 산뜻해진다.


# ── 진단 → 질문 ────────────────────────────────────────────────────────
def classify_domain(text):
    """어느 도메인인지. 키워드 우선(빠름) → LLM 폴백 → 기본 식단."""
    for dom, kws in DOMAIN_KEYWORDS.items():
        if any(k in text for k in kws):
            return dom
    out = ask(P.DOMAIN.format(text=text), fallback="")
    return next((d for d in ("식단", "수면", "휴식", "운동") if d in out), "식단")


class ConceptPick(BaseModel):
    key: str = Field(description="고른 개념의 key")


def pick_concept(ti, candidates):
    """오늘 기록에 **가장 잘 맞는** 개념을 고른다.

    ⚠️ 예전엔 CONCEPT_ORDER 순서대로만 꺼냈다. 그래서 뭘 먹었든 항상 단백질부터 물었다 —
       "샐러드 먹었어"에도 "밥·면 같은 탄수 위주로 먹으면 뭐가 부족?"을 물어봤다.
    """
    if len(candidates) <= 1:
        return candidates[0] if candidates else None
    options = "\n".join(f"- {k}: {CONCEPTS[k]['title']} ({CONCEPTS[k]['criteria']})"
                         for k in candidates)
    v = ask_structured(P.PICK_CONCEPT.format(ti=ti, options=options), ConceptPick)
    return v.key if v and v.key in candidates else candidates[0]


class FitVerdict(BaseModel):
    # bool-first 금지 — reason 먼저, 이름 있는 분류로. (InsightVerdict 참고)
    reason: str = Field(description="이 기록에 가르칠 개념이 있나 없나, 한 줄 근거")
    fit: Literal["teach", "skip"] = Field(
        description="teach=기록이 아래 개념 중 하나와 맞아 짚어줄 게 있다 / "
                    "skip=군것질·이미 잘 챙김·전제 반대라 가르칠 게 없다")


def read_record(state):
    """이 기록에 **가르칠 게 있나**부터 정한다 (기록 주도).

    예전 diagnose는 무조건 개념 하나를 골랐다 → '초코칩'에도 채소를 들이댔다.
    이제 FIT으로 teach/skip을 먼저 끊고, teach일 때만 개념을 고른다(pick_concept 재사용).
    """
    learned = state.get("learned", {})
    # 사용자가 UI에서 골랐으면 그걸 쓴다. 자유 입력(채팅)이면 그때만 추측한다.
    domain = state.get("domain") or classify_domain(state.get("today_input", ""))
    ti = state.get("today_input", "")
    candidates = [c for c in CONCEPT_ORDER
                  if c not in learned and CONCEPTS[c]["domain"] == domain]
    if not candidates:                      # 이 도메인 개념을 다 뗐다.
        # 🚫 억지로 **다른 도메인** 개념을 들이대지 않는다 — 헬스 기록에 "채소 드세요"가
        #    나오던 버그가 여기서 났다. 이 영역은 오늘 더 볼 게 없으니 그냥 skip.
        return {"fit": "skip", "target_concept": None, "domain": domain, "stage": "read_record"}

    options = "\n".join(f"- {CONCEPTS[c]['title']}: {CONCEPTS[c]['criteria']}" for c in candidates)
    v = ask_structured(P.FIT.format(ti=ti, options=options), FitVerdict)
    if v is None or v.fit == "teach":       # 판정 실패 시 안전빵: 가르친다(코칭이 이 앱의 정체성)
        return {"fit": "teach", "target_concept": pick_concept(ti, candidates),
                "domain": domain, "stage": "read_record"}
    return {"fit": "skip", "target_concept": None, "domain": domain, "stage": "read_record"}


def acknowledge(state):
    """가르칠 게 없는 기록 → 억지로 안 가르치고 가볍게 받아준다 (원하면 이어갈 선택권만)."""
    msg = ask(P.ACKNOWLEDGE.format(ti=state.get("today_input", "")),
              fallback="오늘 그런 하루였군요. 오늘은 딱히 짚을 건 없어요 — 혹시 다른 얘기도 해볼까요?")
    return {"messages": [("ai", msg)], "stage": "acknowledge"}


class Bridge(BaseModel):
    # 필드 순서 = 사고 순서. bool을 앞에 두면 생각하기 전에 결론부터 뱉는다. (InsightVerdict 참고)
    #
    # ⚠️ **묻는 방향을 뒤집었다.** "다리가 필요한가?"라고 물으니 모델이 매번 true를 뱉었다
    #    (7건 중 7건). LLM은 도움 되려는 쪽으로 기운다. 그래서 흔한 쪽(전제와 맞음)을
    #    true로 두고 물으니 제대로 갈린다.
    reason: str = Field(description="오늘 기록이 전제와 같은 방향인가 반대 방향인가, 한 줄")
    fits_premise: bool = Field(
        description="기록이 질문의 전제와 같은 방향이면 true (보통은 true). "
                    "정반대일 때만 false.")
    bridge: str = Field(description="fits_premise가 false일 때만 다리 한 문장. "
                                    "true면 빈 문자열. 정답 유출·물음표 금지.")


def socratic_q(state):
    """답 대신 질문.

    개념이 9개뿐이라 기록이 개념의 **전제와 반대**일 때가 있다.
    ("너무 쉬었는데" → 휴식 개념 둘은 다 '덜 쉬었다'를 전제한다 → 질문이 뜬금없다)

    ⚠️ **질문 문구는 건드리지 않는다.** 질문을 바꾸면 EVALUATE의 채점 기준과 어긋난다.
       대신 기록을 받아주는 **다리 한 문장만** 앞에 붙인다. 필요 없으면 안 붙는다.
    """
    c = CONCEPTS[state["target_concept"]]
    q = c["socratic_q"]
    v = ask_structured(P.BRIDGE.format(ti=state.get("today_input", ""),
                                       premise=c["criteria"],
                                       banned=", ".join(c["answer_keywords"])), Bridge)
    b = (v.bridge or "").strip() if v and not v.fits_premise else ""

    # 프롬프트로 막아도 다리에 정답을 흘리거나 질문을 미리 해버린다 → **코드에서 버린다.**
    # 다리는 없어도 되는 것이라, 의심스러우면 그냥 안 붙이는 게 맞다.
    if b.endswith("?") or any(k in b for k in c["answer_keywords"]):
        b = ""

    msgs = ([("ai", b)] if b else []) + [("ai", q)]
    return {"messages": msgs, "stage": "socratic_q"}


# ── 의도 라우팅 (강의 #16) ─────────────────────────────────────────────
# 모든 입력을 '내 질문의 답'으로만 보면 "번아웃이라고 한 적 없는데"(항의)도 오답 처리한다.
class IntentVerdict(BaseModel):
    intent: Literal["answer", "object", "confused", "stop"] = Field(
        description="answer=답하려는 것 / object=넘겨짚음을 정정·항의 / "
                    "confused=질문을 못 알아들음 / stop=그만하고 싶음")
    reason: str = Field(description="판단 이유 한 줄")


def route_intent(state):
    """사용자 발화가 뭘 하려는 건지 갈라준다."""
    ans = (state.get("user_answer") or "").strip()
    if not ans:
        return {"intent": "answer", "stage": "route_intent"}
    c = CONCEPTS.get(state.get("target_concept") or "", {})
    v = ask_structured(P.INTENT.format(q=c.get("socratic_q", ""), ans=ans), IntentVerdict)
    intent = v.intent if v else "answer"
    if intent == "confused" and state.get("rephrase_count", 0) >= 1:
        intent = "answer"                   # 두 번째부턴 답으로 본다 (무한 루프 방지)
    return {"intent": intent, "stage": "route_intent"}


def handle_object(state):
    """"그거 아닌데" → 넘겨짚은 걸 인정·사과하고 맥락을 처음부터 다시 모은다."""
    msg = ask(P.OBJECT.format(domain=state.get("domain", ""),
                              ans=state.get("user_answer", "")),
              fallback="아, 제가 넘겨짚었네요. 죄송해요. 그럼 오늘 어떠셨는지 편하게 말씀해주실래요?")
    return {"messages": [("ai", msg)], "today_input": "", "user_answer": "",
            "target_concept": None, "domain": "", "hint_count": 0,
            "clarify_count": 1,             # 되묻기는 방금 한 셈 (중복 방지)
            "intent": "", "stage": "handle_object"}


def rephrase(state):
    """질문을 못 알아들음 → 정답은 흘리지 말고 더 쉽게 다시 묻는다."""
    c = CONCEPTS[state["target_concept"]]
    msg = ask(P.REPHRASE.format(q=c["socratic_q"], banned=", ".join(c["answer_keywords"])),
              fallback=c["socratic_q"])
    return {"messages": [("ai", msg)], "user_answer": "",
            "rephrase_count": state.get("rephrase_count", 0) + 1, "stage": "rephrase"}


# ── 채점 → 칭찬 / 힌트 / 정답공개 ──────────────────────────────────────
class _Verdict(BaseModel):
    verdict: Literal["correct", "wrong", "unknown"] = Field(description="채점 결과")


def evaluate(state):
    """유저 답 채점.

    관대하면 아무 말이나 정답이 되고, 빡세면 진짜 정답('단백질?')도 오답이 된다.
    (둘 다 실제로 겪어서 테스트로 균형을 박아뒀다)
    """
    c = CONCEPTS[state["target_concept"]]
    ans = state.get("user_answer", "")
    if not ans.strip():
        return {"verdict": "unknown", "stage": "evaluate"}
    out = ask_structured(  # 한 단어 판정이라 스키마 없이 텍스트로 받는다
        P.EVALUATE.format(title=c["title"], criteria=c["criteria"],
                          keywords=", ".join(c["answer_keywords"]), ans=ans),
        _Verdict, fallback=None)
    if out is None:                          # 키 없음 → 키워드 폴백
        v = "correct" if any(k in ans for k in c["answer_keywords"]) else "wrong"
        return {"verdict": v, "stage": "evaluate"}
    return {"verdict": out.verdict, "stage": "evaluate"}


def praise(state):
    """맞음 → 칭찬 + 숙련도 1 기록. (자기 몸에 적용까지 하면 reflect에서 2로 올라간다)"""
    key = state["target_concept"]
    return {"learned": {**state.get("learned", {}), key: 1},
            "messages": [("ai", CONCEPTS[key]["praise"])], "stage": "praise"}


def hint(state):
    """틀림/모름 → 힌트.

    정답을 흘려도 안 되고(그냥 답을 알려준 셈), 아무 방향 없이 뭉개도 안 된다.
    마지막 힌트는 다음이 reveal이라 바짝 좁혀준다.
    """
    n = state.get("hint_count", 0)
    c = CONCEPTS[state["target_concept"]]
    fallback = c["hints"][min(n, len(c["hints"]) - 1)]
    ans = state.get("user_answer", "").strip()
    if not ans:
        return {"hint_count": n + 1, "messages": [("ai", fallback)], "stage": "hint"}

    banned = c["answer_keywords"]
    # HINT_MAX=1(부담 줄이기)로 굳혔다 → 힌트는 방향만(HINT_MID) 주고 정답은 reveal이 준다.
    # (예전의 '바짝 좁히는 마지막 힌트'(HINT_LAST)는 HINT_MAX>=2에서만 도는 죽은 분기라 들어냈다)
    tail = P.HINT_MID.format(banned=", ".join(banned))
    msg = ask(P.HINT_HEAD.format(title=c["title"], criteria=c["criteria"], ans=ans) + tail,
              fallback=fallback)
    if any(k in msg for k in banned):       # 힌트가 정답을 흘리면 정석 힌트로
        msg = fallback
    # user_answer는 여기서 소비 끝 → 비운다. 안 비우면 다음 guard_answer 재개가 어긋날 때
    # 이 답으로 다시 채점될 수 있다 (user_answer를 여러 질문이 공유하는 구조라 생기는 위험).
    return {"hint_count": n + 1, "messages": [("ai", msg)], "stage": "hint", "user_answer": ""}


def hint_exhausted(state):
    return state.get("hint_count", 0) >= HINT_MAX


def reveal(state):
    """힌트 소진 → 다그치지 말고 정답을 따뜻하게 알려준다.

    가르치는 코치가 안 가르치고 "오늘은 여기까지" 하고 빈손으로 보내던 걸 고친 노드.
    """
    key = state["target_concept"]
    c = CONCEPTS[key]
    # ⚠️ reveal은 **정답을 직접 말하는** 노드라 의료 조언으로 새기 제일 쉽다.
    #    (criteria에 수치·전문용어가 들어 있다) 그런데 여태 출력 검사가 아예 없었다.
    msg, why = ask_guarded(
        P.REVEAL.format(title=c["title"], criteria=c["criteria"]),
        fallback=f"괜찮아요, 오늘은 제가 알려드릴게요 — 핵심은 '{c['title']}'예요.")
    out = {"learned": {**state.get("learned", {}), key: 1},
           "messages": [("ai", msg)], "stage": "reveal"}
    if why:
        out["guard_tripped"] = f"reveal: {why}"
    return out


# ── 자기 파악 (강의 #19 Feynman을 비틀어서) ────────────────────────────
# 개념을 한 단어 맞혔다고 아는 게 아니다. **자기 몸에 적용해서** 읽어야 마스터(2).
# 그렇게 나온 자기 패턴(insight)이 이 코치의 진짜 산출물이다.
class InsightVerdict(BaseModel):
    """⚠️ **bool을 쓰지 마라.** 여기서 두 번 데였다.

    1) 필드 순서 — bool이 맨 앞이면 생각하기 전에 결론부터 뱉는다. reason을 앞으로 뺐다.
    2) 그래도 뒤집혔다. 근거는 멀쩡한데 bool만 정반대로 나왔다:
         reason="배고픔의 **이유를 설명**했다"           → read_own_signal=False
         reason="이유를 **설명하지 않았다**"             → read_own_signal=True
       true/false는 **이름이 없는 라벨**이라 모델이 어느 쪽이 어느 쪽인지 계속 헷갈린다.
    → **이름 있는 분류(Literal)** 로 바꾸고 bool은 코드에서 만든다. 이러면 안 뒤집힌다.
    """
    reason: str = Field(description="근거부터 쓴다. 한 줄. (내부용 — 사용자에게 안 보여준다)")
    kind: Literal["felt", "cause", "none"] = Field(
        description="felt = 답에 내가 실제로 겪은 몸·마음 상태가 있다 ('뻐근했음', '뿌듯함'). "
                    "cause = 답이 오늘 기록에 적힌 내 신호의 이유를 댄다 "
                    "('단백질이 없어서 그런듯'). "
                    "none = 겪은 것도 이유도 없다. 당위('~가 중요하죠')·일반론('건강해야죠')·"
                    "회피('몰라요')는 전부 none이다.")

    @property
    def read_own_signal(self) -> bool:
        return self.kind in ("felt", "cause")
    insight: str = Field(
        description="「A하면 B한다」 꼴의 자기 패턴 한 문장. "
                    "⚠️ **사용자가 실제로 쓴 낱말만** 쓴다. 없는 말을 지어내지 마라. "
                    "오늘 사건 서술·특정 시점 표현·추측 어미 금지. '~한다'로 끊는다. "
                    "자세한 규칙은 프롬프트를 따를 것. read_own_signal이 false면 빈 문자열.")


def reflect(state):
    """개념을 맞힌 뒤 → 자기 몸에 적용해서 말하게 한다.

    ⚠️ **사용자가 이미 한 말을 캔다.** 첫 마디에 "카레 먹고 4시간 뒤 배고파졌다"고
    자기 패턴을 통째로 말했는데 흘려버리고 새로 만들어내라고 요구하던 버그가 있었다.
    """
    c = CONCEPTS[state["target_concept"]]
    ti = state.get("today_input", "")
    msg = ask(P.REFLECT.format(title=c["title"], criteria=c["criteria"], ti=ti),
              fallback=f"그럼 오늘 본인은 어땠어요? '{ti}' 하고 나서 몸이 어떤 신호를 보냈는지 떠올려볼래요?")
    # ⚠️ **여기서 user_answer를 비우는 게 핵심.** 다음 capture_insight도 user_answer를 읽는데,
    #    지금 비우지 않으면 (소크라테스 답 / 힌트 답 / reveal 직전 답)이 남아 있다가,
    #    capture 재개가 어긋날 때 그 옛 답을 '자기 신호'로 오독할 수 있다.
    #    reveal→reflect를 이으면서 이 위험이 커졌다 → 명시적으로 비운다.
    return {"messages": [("ai", msg)], "stage": "reflect", "user_answer": ""}


# "몰라요" 같은 회피에는 신호가 있을 수 없다. 그런데 LLM은 기록에 적힌 신호('배고파졌어')를
# 끌어와서 읽은 것처럼 쳐준다 — 프롬프트로 막아도 9번 중 6번 샜다.
# → **LLM에 묻기 전에 코드에서 끊는다.** 못 잡은 표현은 그대로 LLM으로 넘어가니 손해가 없고,
#   덤으로 API 호출도 아낀다.
_REFUSALS = ("몰라", "모르겠", "글쎄", "없는데", "없어", "생각 안", "기억 안", "패스", "스킵")


def _is_refusal(ans):
    a = ans.replace(" ", "")
    return len(a) <= 12 and any(r.replace(" ", "") in a for r in _REFUSALS)


def capture_insight(state) -> Command[Literal["enrich_agent", "__end__"]]:
    """자기 신호를 읽었으면 → 자기 패턴으로 저장(누적) + 숙련도 2(마스터)."""
    key = state["target_concept"]
    ans = (state.get("user_answer") or "").strip()
    g = guard(ans)                          # 여기도 사용자 입력 → 위험 검사
    if g["risk_flag"]:
        return Command(goto=END, update={**g, "stage": "capture_insight", "user_answer": ""})

    c = CONCEPTS[key]
    v = None if (not ans or _is_refusal(ans)) else \
        ask_structured(P.INSIGHT.format(title=c["title"], criteria=c["criteria"],
                                        ti=state.get("today_input", ""), ans=ans),
                       InsightVerdict)
    # 답을 다 읽었으니 user_answer는 비운다 (다음 대화의 소크라테스 답과 안 섞이게).
    if v is None or not v.read_own_signal:  # 못 읽었으면 다그치지 않고 넘어간다
        out = {"learned": {**state.get("learned", {}), key: 1},
               "stage": "capture_insight", "user_answer": ""}
        if ans:                             # 답을 하긴 했으면(회피여도) 빈손으로 끝내지 않는다
            out["messages"] = [("ai", "괜찮아요. 다음엔 그때 몸이 어땠는지 한 번 살펴봐요.")]
        return Command(goto="enrich_agent", update=out)

    tip = v.insight.strip()
    return Command(goto="enrich_agent", update={
        "learned": {**state.get("learned", {}), key: 2},        # 자기 몸에 적용 = 마스터
        "insights": (state.get("insights") or []) + ([tip] if tip else []),   # 직접 누적
        "insight_domains": (state.get("insight_domains") or []) + ([c["domain"]] if tip else []),
        "messages": [("ai", f"그거예요. 방금 본인 신호를 직접 읽으신 거예요 — “{tip}”")],
        "stage": "capture_insight", "user_answer": ""})


# ── 웹검색 심화 (강의 #14.1 chatbot ⇄ tools 루프) ──────────────────────
ENRICH_LABEL = "더 알아보기 · "   # 라벨은 코드가 붙인다 (LLM에 맡기면 템플릿을 그대로 베낀다)


def enrich_agent(state):
    """개념을 **스스로 깨친 뒤에만** 실천 팁을 웹에서 찾아 한 줄 붙인다.

    LLM이 tool call을 낼지 스스로 판단 → ToolNode가 search_web 실행 → 결과 들고 복귀 →
    더는 tool call이 없으면 tools_condition이 closing으로 보낸다.
    """
    learned = state.get("learned", {})
    if not learned:
        return {"stage": "enrich"}

    # ⚠️ 이미 한 번 검색했으면(messages에 tool 결과가 있으면) **재검색을 막는다.**
    #    검색이 비면 LLM이 또 tool_call을 내서 tools↔enrich 루프에 빠지곤 했다(recursion_limit까지).
    #    → 첫 호출만 tool 붙은 LLM(검색 유도), 그다음엔 tool 없는 LLM으로 팁만 뽑는다.
    msgs = list(state.get("messages", []))
    already_searched = any(getattr(m, "type", "") == "tool" for m in msgs)
    llm_t = get_llm() if already_searched else get_llm_with_tools()
    if llm_t is None:
        return {"stage": "enrich"}

    title = CONCEPTS[list(learned)[-1]]["title"]
    # 지시는 매 호출 끝에 얹는다 (첫 호출=검색 유도 / 둘째 호출=한 문장 팁 강제). state엔 안 남김.
    resp = llm_t.invoke(msgs + [("system", P.ENRICH.format(title=title))])
    if getattr(resp, "tool_calls", None):
        return {"messages": [resp], "stage": "enrich"}      # ToolNode가 받아 실행

    tip = _text_of(resp.content)            # Gemini는 content가 파트 리스트다
    for junk in ("더 알아보기 ·", "더 알아보기·", "더 알아보기"):
        tip = tip.replace(junk, " ")
    tip = tip.replace("...", "").replace("…", "").strip(" ·\"'\n")
    if not tip:
        return {"messages": [resp], "stage": "enrich"}

    ok, why = output_guard(tip)             # 웹에서 긁어온 말이라 의료 조언이 섞일 수 있다
    if not ok:
        return {"stage": "enrich", "guard_tripped": f"enrich: {why}"}
    return {"messages": [("ai", ENRICH_LABEL + tip)], "stage": "enrich"}


def closing(state):
    """격려 + 다음에 스스로 해볼 것 하나. (오늘 상태를 고려해서 — 지친 사람에게 숙제 금지)"""
    learned = state.get("learned", {})
    if not learned:
        return {"messages": [("ai", "오늘은 여기까지! 다음에 또 같이 살펴봐요.")], "stage": "closing"}
    last = CONCEPTS[list(learned)[-1]]["title"]
    # closing은 "다음에 해볼 것"을 제안한다 → 약·치료 얘기로 샐 수 있다
    msg, why = ask_guarded(
        P.CLOSING.format(title=last, ti=state.get("today_input", "")),
        fallback=f"오늘 '{last}' 하나 스스로 찾아냈어요. 다음엔 뭐가 빠졌는지 먼저 떠올려봐요.")
    out = {"messages": [("ai", msg)], "stage": "closing"}
    if why:
        out["guard_tripped"] = f"closing: {why}"
    return out
