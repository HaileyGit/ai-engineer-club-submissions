"""안전 가드레일. (강의 #9.3 — Input guardrail / Output guardrail)

이 코치는 식단·수면 코치지 임상 도구가 아니다. **상담을 흉내내는 게 제일 위험하다.**
그래서 (1) 한계를 명시하고 (2) 실제 자원으로 즉시 넘기고 (3) 따뜻하게 물러난다.

3중 방어 — 셋이 각각 **다른 걸** 잡는다:
    self-harm ("죽고 싶어")        → Moderation API   (전용 분류기, 무료. 키워드론 못 잡음)
    의학 응급 ("가슴이 아파")       → LLM 검사관        (Moderation 카테고리에 의학이 없음)
    코치의 의료 조언 ("병원 안 가도 될 듯") → Output guard  (앞의 둘은 '입력'만 본다)

⚠️ 키워드는 끝없이 샌다. '상한'을 넣었더니 "어제 먹은 게 **상했나** 봐"가 통과했고,
   "우유가 좀 **쉰** 것 같은데 마셨어"는 위험 단어가 아예 없다. 반대로 부정문
   "심장이 두근거리지 **않는데**"를 위험으로 오판해 코치를 통째로 막기도 했다.
   → **분류기(LLM)가 정본**, 키워드는 LLM을 못 쓸 때의 폴백.

⚠️ 자살예방 상담전화는 2024년 1월부터 1393 → **109**로 통합됐다. (1393은 폐지 예정)
"""
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from llm import ask_structured

# ── 폴백용 키워드 (LLM을 못 쓸 때만) ──────────────────────────────────
RISK_PAIRS = [
    ("가슴", ["아파", "아프", "통증", "조여", "쥐어", "짓눌", "두근"]),
    ("심장", ["아파", "아프", "통증", "두근", "빨리", "뛰", "벌렁", "이상"]),
    ("숨", ["안 쉬", "못 쉬", "막혀", "가빠", "차올", "쉬어지지", "찬다"]),
    ("상한", ["먹", "드", "마", "같아", "듯", "봐"]),
]
RISK_MEDICAL_SOLO = ["쓰러", "실신", "의식이 흐", "심계항진", "식중독", "토했", "구토", "게워"]
RISK_CRISIS = ["죽고 싶", "자해", "죽어버리", "사라지고 싶", "살기 싫"]
FOOD_WORDS = ["상한", "식중독", "토했", "구토", "게워", "쉰"]

# ── 안내 문구 (위험 종류마다 필요한 안내가 다르다) ────────────────────
RISK_MSG_MEDICAL = (
    "잠깐요. 말씀하신 증상은 제가 코치로서 다룰 수 있는 범위를 넘어요.\n"
    "가슴 통증이나 심한 두근거림, 숨이 차는 건 몸이 보내는 급한 신호일 수 있어요. "
    "오늘 코칭은 접어두고, 지체 말고 병원 진료를 받아보세요. **증상이 심하면 119**예요."
)
RISK_MSG_FOOD = (
    "잠깐요. 상한 걸 드신 것 같다니 그냥 넘어갈 수 없어요.\n"
    "오늘 코칭은 접어두고 **몸 상태부터 살펴봐 주세요.** 복통·구토·설사·발열이 오면 "
    "식중독일 수 있어요. 증상이 있으면 병원 진료를 받으시고, 물을 자주 조금씩 드세요. "
    "심하면 119예요.\n저는 코치라 진단은 못 해드려요. 오늘은 몸부터 챙기세요."
)
RISK_MSG_CRISIS = (
    "그 말씀을 그냥 지나칠 수 없어요. 많이 힘드셨겠어요.\n"
    "다만 솔직하게 말씀드릴게요 — **저는 이걸 도와드릴 수 있는 도구가 아니에요.** "
    "지금 필요한 건 코칭이 아니라 사람이에요.\n"
    "**자살예방 상담전화 109** (24시간, 무료)로 지금 연락해보세요. "
    "정신건강 상담 1577-0199도 있어요.\n"
    "혼자 견디지 마세요. 당신 얘기를 들어줄 사람이 있어요."
)


# ── 1) self-harm — OpenAI Moderation API (무료 전용 분류기) ──────────
_mod = None


def _moderator():
    global _mod
    if _mod is None:
        if not os.getenv("OPENAI_API_KEY"):
            _mod = False
        else:
            try:
                from openai import OpenAI
                _mod = OpenAI()
            except Exception:
                _mod = False
    return _mod or None


@lru_cache(maxsize=512)
def moderation_says_crisis(text):
    """self-harm 계열이면 True. 실패하면 False (키워드 결과만 쓰고 조용히 넘어감)."""
    client = _moderator()
    if client is None or not text.strip():
        return False
    try:
        cat = client.moderations.create(
            model="omni-moderation-latest", input=text
        ).results[0].categories
        d = cat.model_dump() if hasattr(cat, "model_dump") else dict(cat)
        return any(v for k, v in d.items() if k.replace("-", "_").startswith("self_harm"))
    except Exception:
        return False


# ── 1-b) 정신적 위기 — LLM 검사관 (Moderation이 한국어를 놓친다) ──────
#
# 🚨 실측: Moderation API는 **한국어 자해 표현의 40%를 놓쳤다.**
#    놓친 것: "살기싫다" / "살기 싫다" / "살기싫어" / "다 그만두고 싶다" / "없어지고싶어"
#    같은 뜻의 영어("I don't want to live anymore")는 100% 잡았다.
#    → 한국어 서비스에서 Moderation만 믿으면 안 된다.
# 실제로 "살기싫다"를 코치가 그냥 통과시키고 수업을 계속했다. 최악의 실패다.
#
# 그래서 셋을 **OR**로 건다. 위기는 놓치는 쪽이 훨씬 비싸다.
#    키워드(빠름) OR Moderation(영어 강함) OR LLM 검사관(한국어·맥락)
class CrisisVerdict(BaseModel):
    crisis: bool = Field(description="자살·자해 의도나 삶을 놓고 싶은 마음이 보이면 true")
    reason: str = Field(description="판단 근거 한 줄")


_CRISIS_PROMPT = (
    "너는 셀프케어 코치의 **위기 검사관**이야. 사용자의 말에 "
    "**삶을 끝내거나 스스로를 해치려는 뜻**이 보이는지만 봐라.\n\n"
    "crisis=true — 삶 자체를 놓으려는 표현:\n"
    "  '살기싫다' / '죽고싶다' / '없어지고 싶어' / '다 끝내고 싶다' / '다 그만두고 싶다' /\n"
    "  '내가 사라지는 게 나을 것 같다' / 자해 언급\n\n"
    "crisis=false — 아래는 **전부 false다. 이건 코치가 다뤄야 할 일상의 감정이다:**\n"
    "  🚫 힘든 감정: '우울해', '좀 힘들다', '그냥 별로야', '기분이 안 좋아', '지쳤다', '피곤해'\n"
    "  🚫 일·운동이 싫은 것: '일 그만두고 싶다', '이 회사 싫다', '운동하기 싫다'\n"
    "  🚫 **몸의 증상**: '가슴이 아파', '숨이 안 쉬어져', '토했어' "
    "(→ 이건 **의학 응급**이라 다른 검사관이 처리한다)\n\n"
    "⚠️ **과잉 대응이 오히려 해롭다.** 힘든 날 얘기하러 온 사람마다 자살예방 상담을 "
    "안내하면 코치를 아예 못 쓴다. **삶을 놓겠다는 뜻이 실제로 보일 때만** true다.\n"
    "⚠️ 반대로 그 뜻이 보이면 **에두른 표현이라도 놓치지 마라.**\n"
    "<사용자_말>{text}</사용자_말>"
)


@lru_cache(maxsize=512)
def llm_says_crisis(text):
    v = ask_structured(_CRISIS_PROMPT.format(text=text), CrisisVerdict)
    return bool(v and v.crisis)


def is_crisis(text):
    """정신적 위기 — 코칭 중단 + 109.

    키워드 **또는** Moderation **또는** LLM 검사관. 하나라도 걸리면 위기다.
    (Moderation이 한국어를 40% 놓치는 게 실측으로 확인돼서 LLM을 붙였다)
    """
    if not text.strip():
        return False
    if any(k in text for k in RISK_CRISIS):
        return True
    if moderation_says_crisis(text):
        return True
    return llm_says_crisis(text)


# ── 2) 의학 응급 — LLM 검사관 (Moderation엔 의학 카테고리가 없다) ────
class MedicalVerdict(BaseModel):
    """⚠️ **bool을 앞에 두지 마라.** risk가 맨 앞이고 reason이 맨 뒤였을 때,
    답 "폰 화면"(수면 질문에 대한 두 글자 답)을 보고 **식중독**이라며 대화를 끊었다.
    생각하기 전에 결론부터 뱉은 것이다. → reason을 먼저, 그다음 kind. risk는 코드에서 만든다.
    (InsightVerdict에서 똑같이 데였다)
    """
    reason: str = Field(description="근거부터 쓴다. 어떤 신호가 보이는지, 없으면 없다고. 한 줄")
    kind: Literal["cardiac", "breathing", "food", "collapse", "other", "none"] = Field(
        description="cardiac=흉통·심한 두근거림 / breathing=호흡곤란 / "
                    "food=상한 음식·구토·식중독 의심 / collapse=실신 / "
                    "other=그 밖의 급한 몸 이상 / none=위험 신호 없음")

    @property
    def risk(self) -> bool:
        return self.kind != "none"


_MEDICAL_PROMPT = (
    "너는 셀프케어 코치의 **안전 검사관**이야. 사용자가 쓴 말에 "
    "**의학적으로 주의가 필요한 신호**가 있는지 봐라.\n\n"
    "none이 아닌 것: 흉통·심한 두근거림·호흡곤란·실신·쓰러짐 / "
    "**상한 음식을 먹음·구토·식중독 의심** / 그 밖의 급한 몸 이상\n"
    "none: 평범한 식사·운동·수면·피로·스트레스 기록\n\n"
    "⚠️ **food(식중독)는 '상한 음식을 실제로 먹었다'거나 '구토'처럼 급성일 때만이다.**\n"
    "   '느끼하다', '속이 더부룩', '기름진 거 먹고 속이 안 좋아', '소화가 안 돼' 같은 "
    "**가벼운 소화 불편은 전부 none**이다. 상한 음식이라는 단서 없이 소화불량을 식중독으로 "
    "확대하지 마라 — 밥 먹고 속이 더부룩한 건 응급이 아니다.\n"
    "⚠️ **증상이 실제로 적혀 있을 때만 잡아라. 없는 걸 지어내지 마.**\n"
    "⚠️ 이건 코치와의 대화 중 한 마디라, **맥락 없는 짧은 조각**일 수 있다.\n"
    "   '폰 화면', '단백질', '채소', '규칙적으로' 같은 건 코치 질문에 대한 답이다 → **none**\n"
    "   무슨 말인지 모르겠으면 **none**이다. 애매하면 none.\n"
    "⚠️ **과하게 잡지 마.** '라면 먹었다', '피곤하다', '일이 많다'는 전부 none이다.\n"
    "⚠️ 부정문 주의: '두근거리지 **않는다**'는 none이다.\n"
    "<사용자_말>{text}</사용자_말>"
)


@lru_cache(maxsize=512)
def _medical_verdict(text):
    """⚠️ 캐시 필수. guard()가 is_medical_risk()와 medical_kind()에서 **같은 텍스트로
    두 번** 부른다. 캐시가 없으면 의학 검사관 LLM이 매번 두 번 돈다.
    """
    if not text.strip():
        return None
    return ask_structured(_MEDICAL_PROMPT.format(text=text), MedicalVerdict)


def _medical_keywords(text):
    """LLM을 못 쓸 때만 쓰는 폴백. 부정문을 못 읽는 한계가 있다."""
    return (any(k in text for k in RISK_MEDICAL_SOLO)
            or any(a in text and any(v in text for v in vs) for a, vs in RISK_PAIRS))


def is_medical_risk(text):
    """몸의 응급 — 코칭 중단 + 병원/119. **분류기가 정본**, 키워드는 폴백."""
    v = _medical_verdict(text)
    return v.risk if v is not None else _medical_keywords(text)


def medical_kind(text):
    """어떤 종류인지 (안내 문구가 달라진다). 판정 실패 시 키워드로 폴백."""
    v = _medical_verdict(text)
    if v is not None and v.risk:
        return v.kind
    return "food" if any(w in text for w in FOOD_WORDS) else "other"


def is_risk(text):
    return is_crisis(text) or is_medical_risk(text)


# ── Input guardrail — 사용자 입력이 들어오는 **모든 지점**에서 쓴다 ──
def guard(text):
    """위험 검사 + 안내 메시지.

    ⚠️ 입구(첫 입력)에만 걸면 뚫린다. 실제로 '잠이 온다'로 시작한 뒤 답변으로
       '심장이 아파'를 넣었더니 그냥 통과해서 수면 수업을 계속했다.
    ⚠️ 감지만 하고 메시지를 안 내보내면 무응답과 같다 (흉통 호소에 코치가 침묵).

    ⚡ 위기 검사(moderation+LLM)와 의료 검사(LLM)는 **서로 독립**이라 순차로 부르면
       네트워크 왕복이 줄줄이 기다린다 — 스트리밍으로 재보니 이 한 노드가 4.4초,
       전체의 38%였다. 셋을 **동시에** 돌린다 (강의 #16.4 병렬화의 정신).
       LangGraph fan-out이 아니라 스레드인 이유: 이 가드가 4곳에 걸리고 interrupt·
       Command와 얽혀 있어서, 노드를 쪼개면 위험 대비 이득이 안 맞는다.
       (검사는 전부 lru_cache라 스레드에서 불러도 안전하고, 캐시 히트면 공짜다)
    ⚠️ 잠깐 Gemini 무료(10 RPM)로 옮겼을 땐 이 병렬이 **역효과**였다 — 순간에 3개를
       던지면 버스트 제한에 더 잘 걸렸다. OpenAI Tier 1은 500 RPM이라 그 걱정이 없다.
       (무료 티어로 다시 갈 일이 있으면 여기를 순차로 되돌릴 것)
    """
    kw_crisis = any(k in text for k in RISK_CRISIS)   # 로컬이라 즉시 — 걸리면 LLM 스킵
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_med = ex.submit(_medical_verdict, text)              # 의료: 항상 돈다
        f_mod = None if kw_crisis else ex.submit(moderation_says_crisis, text)
        f_llm = None if kw_crisis else ex.submit(llm_says_crisis, text)
        crisis = kw_crisis or (f_mod.result() or f_llm.result())
        mv = f_med.result()

    medical = mv.risk if mv is not None else _medical_keywords(text)
    out = {"risk_flag": crisis or medical}
    if crisis:                                    # 정신적 위기가 우선
        out["messages"] = [("ai", RISK_MSG_CRISIS)]
    elif medical:                                 # 식중독은 안내가 다르다 (119보다 '증상 살피기')
        kind = mv.kind if (mv is not None and mv.risk) else \
            ("food" if any(w in text for w in FOOD_WORDS) else "other")
        out["messages"] = [("ai", RISK_MSG_FOOD if kind == "food" else RISK_MSG_MEDICAL)]
    return out


# ── Output guardrail — 코치가 **뱉는 말**도 검사한다 (강의 #9.3) ─────
class OutputVerdict(BaseModel):
    # ⚠️ 여기도 bool이 맨 앞이었다. InsightVerdict·MedicalVerdict와 같은 병 —
    #    생각하기 전에 결론부터 뱉는다. reason 먼저, 판정은 이름 있는 분류로.
    reason: str = Field(description="근거부터 쓴다. 어디가 문제인지, 없으면 없다고. 한 줄")
    verdict: Literal["medical_advice", "ok"] = Field(
        description="medical_advice=진단·병원판단·약·안심시키기를 했다 / ok=생활습관 조언뿐이다")

    @property
    def violates(self) -> bool:
        return self.verdict == "medical_advice"


_OUTPUT_PROMPT = (
    "너는 셀프케어 코치의 **출력 검사관**이야. 이 코치는 의료인이 아니라서 "
    "**의료 조언·진단을 하면 절대 안 돼.**\n\n"
    "아래 응답이 다음 중 하나라도 하면 medical_advice:\n"
    "- 진단을 내린다 ('그건 위염이에요')\n"
    "- 병원에 갈지 말지 판단해준다 ('병원 안 가도 될 것 같아요')\n"
    "- 약·복용량·치료법을 권한다\n"
    "- 증상을 안심시킨다 ('별거 아니니 걱정 마세요')\n\n"
    "일반적인 생활습관 조언(물 마시기, 채소 곁들이기, 규칙적으로 자기, 쉬어가기)은 "
    "**괜찮으니 ok**.\n\n"
    "검사할 응답: {text}"
)


def output_guard(text):
    """(통과여부, 이유). tripwire가 당겨지면 그 문장은 내보내지 않는다.

    Moderation API로는 못 잡는다 — 의료 조언은 '정책 위반'이 아니라 카테고리에 없다.
    특히 enrich(웹 검색 결과 요약)는 외부 문서에서 온 말이라 제일 위험하다.
    """
    if not str(text).strip():
        return True, ""
    v = ask_structured(_OUTPUT_PROMPT.format(text=text), OutputVerdict)
    if v is None:
        return True, ""          # 검사 못 하면 막지 않는다 (가드가 코치를 죽이면 안 됨)
    return (not v.violates), v.reason


# ── Evaluator-Optimizer (강의 #16.6) ──────────────────────────────────
# 검사관이 막았을 때 **미리 써둔 뻔한 문장으로 갈아치우고 끝**이었다.
# 사용자는 코치가 갑자기 말문이 막힌 걸 본다 — 안전하지만 멍청하다.
#
# 강의가 가르친 건 "평가 → **피드백을 들려주고 다시 생성**" 루프다.
# 생성기와 평가기가 이미 둘 다 있으니, 그 사이에 되먹임만 이어주면 된다.
#
#   생성 → 검사 → (통과) 끝
#             └→ (걸림) 뭐가 문제였는지 알려주고 다시 생성 → 검사 → …
#             └→ 그래도 안 되면 그때 폴백
_RETRY = (
    "\n\n---\n"
    "⚠️ 방금 이렇게 썼다가 **안전 검사에서 막혔다.**\n"
    "막힌 문장: {bad}\n"
    "막힌 이유: {why}\n\n"
    "너는 의료인이 아니다. **진단·병원 판단·약 권유·증상 안심시키기를 하면 안 된다.**\n"
    "위 내용을 빼고 **생활습관 이야기만으로** 다시 써라. "
    "질문을 회피하지 말고, 할 수 있는 말은 그대로 해라."
)


def ask_guarded(prompt, fallback="", tries=2):
    """(문장, 막힌사유). 막히면 피드백을 물려 **다시 쓰게 한다.**

    tries만큼 다시 써도 계속 막히면 그때 fallback. 통과하면 사유는 빈 문자열.
    """
    from llm import ask                       # 순환 import 방지 (llm은 safety를 모른다)

    why = ""
    for attempt in range(tries + 1):
        text = ask(prompt if attempt == 0
                   else prompt + _RETRY.format(bad=text, why=why), fallback="")
        if not text:
            break
        ok, why = output_guard(text)
        if ok:
            return text, ""
    return fallback, why or "생성 실패"
