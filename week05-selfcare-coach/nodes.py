"""그래프 노드 8개 (그래프설계.md §2).

각 노드 = state를 받아 바뀐 부분만 dict로 return 하는 함수.
지금은 **스텁** — LangGraph 강의 후 LLM 호출/판단 로직을 채운다.
(LLM 클라이언트는 llm.py로 분리 예정. 1주차는 규칙 기반으로 먼저 굴려보고 LLM은 그 다음.)
"""
import os

from dotenv import load_dotenv, find_dotenv

from concepts import CONCEPTS, CONCEPT_ORDER, DOMAIN_KEYWORDS
from state import HINT_MAX

load_dotenv(find_dotenv(usecwd=True))  # OPENAI_API_KEY 로드 (cwd 기준, 노트북/스크립트 양쪽 안전)

# LLM (gpt-4o-mini). 키 없으면 None → 노드가 규칙기반으로 자동 폴백.
_llm = None
def get_llm():
    global _llm
    if _llm == "none":
        return None
    if _llm is None:
        if not os.getenv("OPENAI_API_KEY"):
            _llm = "none"; return None
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)
    return _llm

# ── Tool 연동 (강의 #14.1 Tool Nodes 패턴) ──────────────────────────────
# @tool 로 정의 → get_llm_with_tools()가 bind_tools 로 LLM에 schema 알림 →
# graph.py의 ToolNode가 실제 실행. (여기선 실제 검색엔진으로 DuckDuckGo 무료·무키 사용)
from langchain_core.tools import tool


@tool
def search_web(query: str) -> str:
    """건강·식습관 개념을 일상에서 실천하는 실제 방법·팁을 웹에서 검색한다."""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().invoke(query)[:1500]
    except Exception as e:
        return f"(검색 실패: {e})"


TOOLS = [search_web]

# 툴 바인딩된 LLM (enrich_agent 전용). 키 없으면 None → enrich 스킵.
_llm_tools = None
def get_llm_with_tools():
    global _llm_tools
    if _llm_tools == "none":
        return None
    if _llm_tools is None:
        llm = get_llm()
        if llm is None:
            _llm_tools = "none"; return None
        _llm_tools = llm.bind_tools(TOOLS)   # LLM에 tool schema 알려주기 (강의 #14.1)
    return _llm_tools

# 위험신호 감지 (safety_guard) — 감지되면 코치 빠지고 전문가/1393.
# 단어 사이 '너무' 같은 게 껴도 잡히게 '앵커 + 증상' 동시등장으로 판정.
RISK_PAIRS = [
    ("가슴", ["아파", "아프", "통증", "조여", "쥐어", "짓눌"]),   # 심장 관련
    ("숨", ["안 쉬", "못 쉬", "막혀", "가빠", "차올", "쉬어지지"]),  # 호흡 곤란
]
RISK_SOLO = ["죽고 싶", "자해", "쓰러", "실신", "의식이 흐"]      # 단독으로도 위험


def is_risk(text):
    if any(k in text for k in RISK_SOLO):
        return True
    return any(anchor in text and any(v in text for v in verbs)
               for anchor, verbs in RISK_PAIRS)


def safety_guard(state):
    """위험신호 감지 → risk_flag. (그래프설계 §2-0)"""
    return {"risk_flag": is_risk(state.get("today_input", "")), "stage": "safety_guard"}


def empathy(state):
    """criteria 톤으로 먼저 공감 (번역체 금지). (§2-1) — LLM, 키 없으면 규칙기반 폴백."""
    ti = state.get("today_input", "")
    llm = get_llm()
    if llm is None:
        return {"messages": [("ai", "오늘도 기록 남겨줘서 좋아요. 같이 천천히 살펴봐요.")],
                "stage": "empathy"}
    try:
        msg = llm.invoke(
            f'너는 따뜻한 셀프케어 코치야. 사용자가 오늘 이렇게 기록했어: "{ti}"\n'
            "판단·평가·지시 없이, 자연스러운 한국어 **친근한 존댓말(~요체, 반말 금지)**로 "
            "딱 한 문장만 공감해줘. 번역체·이모지 금지."
        ).content.strip()
    except Exception:
        msg = "오늘도 기록 남겨줘서 좋아요. 같이 천천히 살펴봐요."
    return {"messages": [("ai", msg)], "stage": "empathy"}


def classify_domain(text):
    """오늘 입력이 어느 도메인인지 판별. 키워드 우선(빠름·확실) → LLM 폴백 → 기본 식단."""
    for dom, kws in DOMAIN_KEYWORDS.items():
        if any(k in text for k in kws):
            return dom
    llm = get_llm()
    if llm is not None:
        try:
            out = llm.invoke(
                f'다음 기록이 어느 주제인지 "식단/수면/번아웃/운동" 중 하나로만 답해: "{text}"'
            ).content.strip()
            for d in ("식단", "수면", "번아웃", "운동"):
                if d in out:
                    return d
        except Exception:
            pass
    return "식단"


def diagnose(state):
    """오늘 입력의 domain을 판별해, 그 도메인에서 안 배운 target_concept 선택. (§2-2)
    맥락 매칭: '못 잤어'→수면 개념, '치킨 먹음'→식단, '운동했어'→운동.
    해당 도메인을 다 배웠으면 남은 아무 개념으로 폴백, 그것도 없으면 None(→closing).
    """
    learned = state.get("learned", {})
    domain = classify_domain(state.get("today_input", ""))
    target = next((c for c in CONCEPT_ORDER
                   if c not in learned and CONCEPTS[c]["domain"] == domain), None)
    if target is None:                       # 그 도메인은 다 뗐으면 → 남은 아무 개념
        target = next((c for c in CONCEPT_ORDER if c not in learned), None)
    return {"target_concept": target, "domain": domain, "stage": "diagnose"}


def socratic_q(state):
    """답 대신 질문. (§2-3)"""
    c = CONCEPTS[state["target_concept"]]
    return {"messages": [("ai", c["socratic_q"])], "stage": "socratic_q"}


def evaluate(state):
    """유저 답 채점 → verdict. (§2-4) — LLM 의미 판정, 키 없으면 키워드 매칭 폴백.
    (LLM은 '프로틴 쉐이크' 같은 키워드에 없는 표현도 개념적으로 맞으면 정답 처리)
    """
    c = CONCEPTS[state["target_concept"]]
    ans = state.get("user_answer", "")
    if not ans.strip():
        return {"verdict": "unknown", "stage": "evaluate"}
    llm = get_llm()
    if llm is None:  # 규칙기반 폴백
        v = "correct" if any(k in ans for k in c["answer_keywords"]) else "wrong"
        return {"verdict": v, "stage": "evaluate"}
    prompt = (
        f"개념: {c['title']} — {c['criteria']}\n"
        f"이 개념에서 맞다고 볼 답의 방향(예): {', '.join(c['answer_keywords'])}\n"
        f'사용자 답: "{ans}"\n'
        "사용자 답이 이 개념을 개념적으로 맞게 짚었으면 correct, 틀렸으면 wrong, "
        "모르겠다는 취지면 unknown. 다른 말 없이 딱 한 단어로만 답해."
    )
    try:
        out = llm.invoke(prompt).content.strip().lower()
    except Exception:
        out = ""
    v = "correct" if "correct" in out else ("unknown" if "unknown" in out else "wrong")
    return {"verdict": v, "stage": "evaluate"}


def praise(state):
    """맞음 → 칭찬 + learned 기록. (§2-5a)"""
    key = state["target_concept"]
    learned = {**state.get("learned", {}), key: 1}
    return {
        "learned": learned,
        "messages": [("ai", CONCEPTS[key]["praise"])],
        "stage": "praise",
    }


def hint(state):
    """틀림/모름 → 힌트 1개 + hint_count++. (§2-5b) — LLM 반응형(유저 답을 받아 유도),
    키 없으면 concepts.py의 고정 힌트로 폴백.
    """
    n = state.get("hint_count", 0)
    c = CONCEPTS[state["target_concept"]]
    fallback = c["hints"][min(n, len(c["hints"]) - 1)]
    llm = get_llm()
    ans = state.get("user_answer", "").strip()
    if llm is None or not ans:
        return {"hint_count": n + 1, "messages": [("ai", fallback)], "stage": "hint"}
    try:
        msg = llm.invoke(
            f"너는 셀프케어 코치야. 사용자가 '{c['title']}' 개념을 스스로 깨닫게 유도하는 중이야.\n"
            f"개념 핵심: {c['criteria']}\n"
            f'사용자가 방금 이렇게 답했어: "{ans}"\n'
            "사용자 말을 먼저 한 마디로 받아준 뒤, 정답을 그대로 말하진 말고 개념 쪽으로 살짝 "
            "유도하는 질문 한 문장을 친근한 존댓말(~요체)로 해줘. 목록·이모지·번역체 금지, 한 문장.\n"
            f"(참고용 정석 힌트: {fallback})"
        ).content.strip()
    except Exception:
        msg = fallback
    return {"hint_count": n + 1, "messages": [("ai", msg)], "stage": "hint"}


def closing(state):
    """격려 + 다음에 스스로 해볼 것 1개. (§2-6) — LLM, 키 없으면 규칙기반 폴백."""
    learned = state.get("learned", {})
    llm = get_llm()
    if llm is None or not learned:
        if learned:
            last = CONCEPTS[list(learned)[-1]]["title"]
            msg = f"오늘 '{last}' 하나 스스로 찾아냈어요. 다음 끼니엔 뭐가 빠졌는지 먼저 떠올려봐요."
        else:
            msg = "오늘은 여기까지! 다음에 또 같이 살펴봐요."
        return {"messages": [("ai", msg)], "stage": "closing"}
    last = CONCEPTS[list(learned)[-1]]["title"]
    try:
        msg = llm.invoke(
            f"너는 셀프케어 코치야. 사용자가 오늘 '{last}' 개념을 스스로 깨쳤어. "
            "자연스러운 한국어 **친근한 존댓말(~요체, 반말 금지)**로, 칭찬 한 마디 + "
            "다음에 스스로 해볼 것 한 가지를 2문장으로. 번역체·이모지 금지."
        ).content.strip()
    except Exception:
        msg = f"오늘 '{last}' 하나 스스로 찾아냈어요. 다음 끼니엔 뭐가 빠졌는지 먼저 떠올려봐요."
    return {"messages": [("ai", msg)], "stage": "closing"}


# enrich_agent가 첫 진입 때 얹는 지시 (search_web 호출을 유도)
ENRICH_SYS = (
    "너는 셀프케어 코치야. 방금 사용자가 '{title}' 개념을 스스로 깨쳤어.\n"
    "이 개념을 일상에서 실천할 진짜 팁을 찾으려면 search_web 툴을 딱 한 번 써.\n"
    "검색 결과가 오면 그걸 바탕으로 친근한 존댓말 딱 한 문장으로 "
    "'더 알아보기 · ...' 형태의 실천 팁을 만들어줘. "
    "목록·번호·여러 문장 금지, 한 줄. 이모지·번역체 금지."
)


def enrich_agent(state):
    """마스터한 개념의 실천 팁을 웹 검색 Tool로 찾는 에이전트. (강의 #14.1 chatbot↔tools 루프)

    LLM이 tool call을 낼지 스스로 판단 → (graph의) ToolNode가 search_web 실행 →
    결과를 들고 이 노드로 복귀 → 더는 tool call이 없으면 tools_condition이 closing으로 보냄.
    키 없으면 조용히 스킵(규칙기반 흐름은 그대로 closing으로).
    """
    llm_t = get_llm_with_tools()
    learned = state.get("learned", {})
    if llm_t is None or not learned:
        return {"stage": "enrich"}
    title = CONCEPTS[list(learned)[-1]]["title"]
    msgs = list(state.get("messages", []))
    # 지시는 매 호출 끝에 얹는다(첫 호출=검색 유도, 둘째 호출=한 문장 팁 강제). state엔 안 남김.
    call_msgs = msgs + [("system", ENRICH_SYS.format(title=title))]
    resp = llm_t.invoke(call_msgs)      # bind_tools 된 LLM → tool call 또는 최종 답
    return {"messages": [resp], "stage": "enrich"}


def reveal(state):
    """힌트 소진 → 다그치지 않고 정답(개념)을 따뜻하게 알려주고 배운 걸로 기록. (§2-5c)
    설계 의도 "정답 알려주고 넘어감"의 실제 구현. 못 맞혀도 오늘 하나는 배우고 가게.
    """
    key = state["target_concept"]
    c = CONCEPTS[key]
    learned = {**state.get("learned", {}), key: 1}   # 다음엔 같은 개념 안 묻게
    llm = get_llm()
    if llm is None:
        msg = f"괜찮아요, 오늘은 제가 알려드릴게요 — 핵심은 '{c['title']}'예요. {c['criteria']} 다음엔 이걸 떠올려봐요."
    else:
        try:
            msg = llm.invoke(
                f"너는 셀프케어 코치야. 사용자가 '{c['title']}' 개념을 여러 번 못 맞혔어. "
                "이제 다그치지 말고, 괜찮다고 다독이며 따뜻하게 정답을 알려줘.\n"
                f"개념: {c['title']} — {c['criteria']}\n"
                "친근한 존댓말(~요체)로 핵심을 쉽게 풀어 2문장 이내. 이모지·번역체·목록 금지."
            ).content.strip()
        except Exception:
            msg = f"괜찮아요, 오늘은 제가 알려드릴게요 — 핵심은 '{c['title']}'예요. {c['criteria']}"
    return {"learned": learned, "messages": [("ai", msg)], "stage": "reveal"}


# hint 루프 탈출 조건 (그래프설계 §3)
def hint_exhausted(state):
    return state.get("hint_count", 0) >= HINT_MAX
