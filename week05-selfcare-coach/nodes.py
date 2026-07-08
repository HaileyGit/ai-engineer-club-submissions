"""그래프 노드 8개 (그래프설계.md §2).

각 노드 = state를 받아 바뀐 부분만 dict로 return 하는 함수.
지금은 **스텁** — LangGraph 강의 후 LLM 호출/판단 로직을 채운다.
(LLM 클라이언트는 llm.py로 분리 예정. 1주차는 규칙 기반으로 먼저 굴려보고 LLM은 그 다음.)
"""
import os

from dotenv import load_dotenv, find_dotenv

from concepts import CONCEPTS, CONCEPT_ORDER
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

# 위험신호 키워드 (safety_guard) — 감지되면 코치 빠지고 전문가/1393
RISK_KEYWORDS = ["가슴이 아", "가슴 통증", "숨이 안", "죽고 싶", "자해", "쓰러"]


def safety_guard(state):
    """위험신호 감지 → risk_flag. (그래프설계 §2-0)"""
    text = state.get("today_input", "")
    risk = any(k in text for k in RISK_KEYWORDS)
    return {"risk_flag": risk, "stage": "safety_guard"}


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


def diagnose(state):
    """아직 안 배운 개념 중 오늘 입력에 맞는 target_concept 선택. (§2-2)
    MVP: CONCEPT_ORDER에서 learned에 없는 첫 개념. (나중에 입력 맥락 매칭으로 고도화)
    """
    learned = state.get("learned", {})
    target = next((c for c in CONCEPT_ORDER if c not in learned), None)
    return {"target_concept": target, "stage": "diagnose"}


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
    """틀림/모름 → 힌트 1개 + hint_count++. (§2-5b)"""
    n = state.get("hint_count", 0)
    c = CONCEPTS[state["target_concept"]]
    msg = c["hints"][min(n, len(c["hints"]) - 1)]
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


# hint 루프 탈출 조건 (그래프설계 §3)
def hint_exhausted(state):
    return state.get("hint_count", 0) >= HINT_MAX
