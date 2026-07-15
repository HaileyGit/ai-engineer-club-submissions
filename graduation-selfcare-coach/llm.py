"""LLM 클라이언트 + 호출 헬퍼.

노드마다 이 3줄이 **18번** 반복되고 있었다:
    llm = get_llm()
    if llm is None: return fallback
    try: msg = llm.invoke(...).content.strip()
    except Exception: msg = fallback
→ ask() / ask_structured() 로 한 곳에 모은다. 노드는 프롬프트와 폴백만 넘긴다.

클라이언트를 둘로 나눈 이유:
- **생성**(공감·힌트·마무리)은 temperature=0.4 — 매번 같은 말이면 기계 같다.
- **판정**(분류·채점·검사)은 temperature=0 — 같은 입력엔 같은 답이 나와야 한다.
  (둘을 같은 0.4로 쓰다가 채점·라우팅이 들쭉날쭉했다)

**모델은 gpt-4o-mini다.** 한때 Gemini 무료로 옮겨봤지만, 이 코치는 대화 하나에 LLM을
19번 부르는데 무료 티어 10 RPM에 계속 걸려 앱이 멈췄다 — 무료 티어는 호출이 성긴
서비스엔 맞지만 이 앱과는 안 맞았다. OpenAI는 지출 한도만 올리면 바로 돌아간다.
(전환 흔적: _text_of는 Gemini의 리스트 응답을 흡수하려던 것 — OpenAI는 str이라 무해해서 남겨둔다)
"""
import os
import re

from dotenv import find_dotenv, load_dotenv

from tools import TOOLS

MODEL = "gpt-4o-mini"

# API 키 — 이 파일 옆의 .env를 먼저 본다 (어느 폴더에서 실행하든 붙게).
# 노트북에 인라인될 땐 __file__이 없으므로 cwd 기준으로 폴백.
try:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except NameError:
    pass
load_dotenv(find_dotenv(usecwd=True))

_cache = {}


def _client(key, temperature):
    """키가 없으면 None → 노드들이 규칙기반으로 자동 폴백한다."""
    if key not in _cache:
        if not os.getenv("OPENAI_API_KEY"):
            _cache[key] = None
        else:
            from langchain_openai import ChatOpenAI
            _cache[key] = ChatOpenAI(model=MODEL, temperature=temperature)
    return _cache[key]


def get_llm():
    """생성용 (공감·힌트·마무리 등)."""
    return _client("gen", 0.4)


def get_llm_precise():
    """판정용 (분류·채점·안전검사). temperature=0."""
    return _client("judge", 0)


def get_llm_with_tools():
    """bind_tools 된 LLM. (강의 #14.1 — ToolNode만으로는 부족, LLM에도 schema를 알려야 함)"""
    if "tools" not in _cache:
        llm = get_llm()
        _cache["tools"] = llm.bind_tools(TOOLS) if llm is not None else None
    return _cache["tools"]


# 프롬프트에 "이모지 금지"라고 써도 LLM이 슬쩍 넣는다. 코드로 걷어낸다.
# (라벨·요약을 LLM에 맡겼다가 데인 것과 같은 교훈 — 코드가 할 수 있는 건 코드가 한다)
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\u2190-\u21FF\u2B00-\u2BFF\uFE0F\u200D]+"
)


def strip_emoji(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI.sub("", text)).strip()


def _text_of(content) -> str:
    """응답 본문을 문자열로. **OpenAI는 str, Gemini는 파트 리스트**를 준다.
    (Gemini: [{'type':'text','text':'...'}]) — 여기서 흡수해서 노드는 신경 안 쓴다."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p)
                       for p in content)
    return str(content)


def ask(prompt, fallback=""):
    """생성 호출. 키가 없거나 실패하면 조용히 fallback을 돌려준다. 이모지는 걷어낸다."""
    llm = get_llm()
    if llm is None:
        return fallback
    try:
        return strip_emoji(_text_of(llm.invoke(prompt).content)) or fallback
    except Exception:
        return fallback


def ask_structured(prompt, schema, fallback=None):
    """판정 호출 (temperature=0 + structured output). 실패하면 fallback."""
    llm = get_llm_precise()
    if llm is None:
        return fallback
    try:
        return llm.with_structured_output(schema).invoke(prompt)
    except Exception:
        return fallback
