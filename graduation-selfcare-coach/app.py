"""내 몸·마음 읽기 코치 — Streamlit UI.

    streamlit run app.py

**챗 로그를 버렸다.** 이 코치의 산출물은 대화가 아니라 "내가 나에 대해 알아낸 것"이다.
그래서 화면을 넷으로 나눈다.

    home    내가 발견한 것들 (별처럼 쌓인다)   ← 주인공
    record  오늘 뭘 기록할지 고르고 한 줄
    qa      질문 하나만 크게 (모바일 네이티브)
    done    방금 발견한 것 + 홈으로

색은 밤하늘. 병원(흰/파랑)도 챗봇(회색)도 아니다. 발견한 패턴은 별빛으로 쌓인다.

설계 원칙
- **모바일 우선.** 폰에선 사이드바가 숨는다 → 중요한 건 전부 본문에.
- **사용자가 1초에 알려줄 수 있는 걸 LLM이 추측하게 하지 않는다.** 도메인은 고르게 한다.
  추측은 사람이 하기 귀찮은 것에만 — 운동기구 화면에서 수치 읽기 같은 것.
"""
import os
import secrets

import streamlit as st

# Streamlit Cloud엔 .env가 없다 → st.secrets에 넣은 키를 환경변수로 넘겨서
# llm.py·vision.py의 os.getenv("OPENAI_API_KEY")가 그대로 잡게 한다.
# (로컬은 .env를 쓰고 st.secrets가 없으니 try/except로 조용히 넘어간다)
try:
    if "OPENAI_API_KEY" in st.secrets and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

from concepts import CONCEPTS
from graph import build_persistent_graph

DOMAINS = ["식단", "수면", "휴식", "운동"]
HINTS = {
    "식단": "오늘 뭘 드셨어요?",
    "수면": "잠은 어떠셨어요?",
    "휴식": "쉴 틈은 있으셨어요?",
    "운동": "몸은 좀 움직이셨어요?",
}

st.set_page_config(page_title="내 몸·마음 읽기 코치", layout="centered",
                   initial_sidebar_state="collapsed")

st.markdown("""
<style>
  /* Streamlit 헤더가 투명이라 콘텐츠가 뒤로 비치며 겹쳐 제목이 잘렸다.
     → 종이색으로 불투명하게 채우고(콘텐츠가 뒤로 안 비침), 그 높이만큼 본문을 민다. */
  header[data-testid="stHeader"] { background: #FCFCFA; height: 3rem; }
  .block-container { padding: 4.5rem 1rem 5rem 1rem; max-width: 30rem; }
  h1, h2, h3 { letter-spacing: -.01em; }

  .brand { font-size: 1.5rem; font-weight: 680; letter-spacing: -.02em;
           color: #12172A; margin-bottom: .25rem; }
  .lede  { color: #7A8090; font-size: .85rem; line-height: 1.6; margin-bottom: 1.8rem; }
  .sec   { display: flex; align-items: baseline; gap: .5rem;
           font-size: .72rem; font-weight: 600; letter-spacing: .12em;
           color: #9AA0AE; margin: 0 0 .7rem 0; }
  .sec .n { color: #2C3A64; font-weight: 700; letter-spacing: 0; }

  /* 알아차린 것 카드. (별 아이콘은 뺐다 — ★가 즐겨찾기처럼 읽혀 의도와 반대였다) */
  .star { background: #FFFFFF; border: 1px solid #E6E7EC; border-radius: 14px;
          box-shadow: 0 1px 3px rgba(27,31,42,.05);
          padding: 1rem 1.1rem .85rem 1.1rem; margin-bottom: .6rem; }
  .star .v { font-size: .97rem; line-height: 1.6; color: #1B1F2A; }
  .star .m { margin-top: .6rem; font-size: .7rem; color: #9AA0AE; letter-spacing: .03em; }
  .dot { color: #B0B5C0; }        /* 도메인 태그 앞 점 (은은하게) */

  /* 오늘의 기록 — 대화가 길어져도 맨 위에 붙어 있게 (sticky).
     자동 스크롤로 최신 대화가 보일 때 "내가 뭘 기록했는지"가 사라지던 걸 막는다. */
  .rec-head { position: sticky; top: 3rem; z-index: 4; background: #FCFCFA;
              padding: .55rem 0 .5rem 0; margin-bottom: .5rem;
              border-bottom: 1px solid #ECEEF1; }
  .rec  { color: #9AA0AE; font-size: .78rem; letter-spacing: .03em; margin-bottom: .15rem; }
  .rec b{ color: #3D4456; font-weight: 550; }
  .q    { font-size: 1.28rem; line-height: 1.6; font-weight: 600; color: #12172A;
          margin: 1.8rem 0 1.5rem 0; letter-spacing: -.01em; }
  .said { color: #5C6373; font-size: .9rem; line-height: 1.65; margin-bottom: .5rem; }

  /* 카톡식 말풍선 — 내 말은 오른쪽(남색), 코치 말은 왼쪽(회색) */
  .row  { display: flex; margin: .35rem 0; }
  .row.me { justify-content: flex-end; }
  .bubble { max-width: 82%; padding: .55rem .85rem; border-radius: 16px;
            font-size: .93rem; line-height: 1.55; word-break: break-word; }
  .bubble.me    { background: #2C3A64; color: #F4F6FB; border-bottom-right-radius: 5px; }
  .bubble.coach { background: #EEF0F4; color: #1B1F2A; border-bottom-left-radius: 5px; }
  .bubble.tip   { background: #F4F6FB; border: 1px solid #DFE4F0; color: #333A4C; max-width: 100%; }
  .bubble.tip .k{ display:block; color:#2C3A64; font-size:.66rem; font-weight:700;
                  letter-spacing:.1em; margin-bottom:.25rem; }
  .tip  { background: #F4F6FB; border: 1px solid #DFE4F0; border-radius: 12px;
          padding: .75rem .9rem; margin-top: .9rem; font-size: .87rem;
          line-height: 1.6; color: #333A4C; }
  .tip .k { display: block; color: #2C3A64; font-size: .67rem; font-weight: 700;
            letter-spacing: .1em; margin-bottom: .3rem; }

  .empty { color: #9AA0AE; font-size: .88rem; line-height: 1.8; text-align: center;
           padding: 2.6rem 1rem; border: 1px dashed #DDDFE6; border-radius: 16px; }
  .muted { color: #9AA0AE; font-size: .8rem; line-height: 1.6; }
  hr { border-color: #E6E7EC; }
  .stButton button { border-radius: 10px; font-weight: 600; padding: .6rem 0; }

  div[data-testid="stSegmentedControl"] button { padding: .5rem 0 !important; flex: 1; }
  /* iOS Safari는 입력창 폰트가 16px 미만이면 포커스 시 화면을 확대(zoom)한다 → 16px로 막는다 */
  input, textarea { font-size: 16px !important; }
  /* ⚠️ 폰에서 상단이 잘리던 진짜 원인 — 여기서 padding-top을 1.4rem으로 줄여서
     브랜드가 헤더(3rem) 뒤로 걸쳤다. 좌우 여백만 줄이고 상단은 데스크탑과 같게 둔다. */
  @media (max-width: 640px) { .block-container { padding: 4.2rem .8rem 5rem .8rem; } }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_graph():
    return build_persistent_graph()


graph = get_graph()

# ── 세션 격리 + 재방문 연속성 ───────────────────────────────────────────
# 예전엔 이름을 텍스트로 받아 thread_id로 썼다 → 아무나 남의 이름을 치면 그 사람의
# 대화·건강기록이 통째로 보인다. 인증이 아니라 그냥 문자열이었다. → secrets로.
#
# 그런데 secrets를 session_state에만 두면 브라우저를 닫는 순간 사라져서, 다음에 열면
# 기록이 통째로 날아간다 (데모 다음 날 다 초기화). → **URL 쿼리(?s=…)에 담는다.**
# 그 URL로 다시 열면 이어지고, secrets라 남이 추측할 수 없다.
# (localStorage 컴포넌트도 있지만 재방문 첫 순간 값을 못 읽어 새 세션을 만들어버리는
#  타이밍 함정이 있다 → URL 방식이 안정적이다)
if "sid" not in st.session_state:
    q = st.query_params.get("s")
    st.session_state.sid = q or secrets.token_urlsafe(12)
    if not q:
        st.query_params["s"] = st.session_state.sid
if "view" not in st.session_state:
    st.session_state.view = "home"

cfg = {"configurable": {"thread_id": f"s-{st.session_state.sid}"}}
snap = graph.get_state(cfg)
values = snap.values or {}
waiting = bool(snap.next)                 # 코치가 답을 기다리는 중
insights = values.get("insights") or []
idomains = values.get("insight_domains") or []
learned = values.get("learned") or {}

# 코치 말만 뽑으면 "내가 뭐라고 답했는지"가 화면에서 사라진다 → 대화가 갑자기 튄 것처럼 보인다.
# 사람 말도 같이 들고 온다. (첫 메시지 = 오늘의 기록이라 위에 따로 보여주므로 뺀다)
turns = [(getattr(m, "type", ""), str(m.content).strip())
         for m in (values.get("messages") or [])
         if getattr(m, "type", "") in ("ai", "human") and str(getattr(m, "content", "")).strip()]
if turns and turns[0][0] == "human":
    turns = turns[1:]
coach_lines = [t for r, t in turns if r == "ai"]

if waiting:                               # 답을 기다리면 무조건 질문 화면
    st.session_state.view = "qa"


# 노드마다 "지금 뭘 하는 중인지". 한 번 보내면 노드가 5~6개 도는데 그동안 화면이
# 죽은 것처럼 멈춰 있었다 (invoke는 다 끝나야 돌아온다).
# → stream_mode="updates"로 **노드가 끝날 때마다** 받아서 진행을 보여준다. (강의 #14.2)
DOING = {
    "safety_guard": "안전 확인 중", "guard_answer": "안전 확인 중",
    "route_record": "기록을 읽는 중", "empathy": "코치가 읽는 중",
    "clarify": "되묻는 중", "absorb": "이어서 읽는 중",
    "read_record": "오늘 기록을 살피는 중", "acknowledge": "가볍게 받아주는 중",
    "socratic_q": "질문을 만드는 중", "route_intent": "답을 읽는 중",
    "evaluate": "답을 살펴보는 중", "hint": "힌트를 고르는 중",
    "reveal": "정리해서 알려주는 중", "praise": "정리하는 중",
    "reflect": "본인 얘기로 잇는 중", "capture_insight": "발견한 걸 적는 중",
    "enrich_agent": "실천 팁을 찾는 중", "tools": "웹에서 찾는 중",
    "closing": "마무리하는 중", "rephrase": "질문을 다시 쓰는 중",
    "redirect": "안내하는 중", "handle_object": "다시 여쭙는 중",
}


def _archive_and_clear(snap_now):
    """새 대화를 시작하기 전에 **지난 대화를 보관함으로 옮기고 채팅을 비운다.**
    안 그러면 messages(add_messages 리듀서)에 계속 쌓여 채팅이 끝없이 길어진다.
    비우는 유일한 방법은 RemoveMessage다 ([]는 '빈 걸 더하기'라 안 지워진다)."""
    from langchain_core.messages import RemoveMessage
    old = snap_now.values.get("messages") or []
    old_turns = [(m.type, str(m.content).strip()) for m in old
                 if getattr(m, "type", "") in ("ai", "human") and str(m.content).strip()]
    if not old_turns:
        return
    past = (snap_now.values.get("past_chats") or []) + [
        {"ti": snap_now.values.get("today_input", ""), "turns": old_turns}]
    graph.update_state(cfg, {
        "messages": [RemoveMessage(id=m.id) for m in old if getattr(m, "id", None)],
        "past_chats": past})


def send(text, domain=None):
    """입력 하나로 두 경우를 다 처리한다 — 답 대기 중이면 재개, 아니면 새 대화 시작."""
    snap_now = graph.get_state(cfg)
    if snap_now.next:                         # 대화 중 → 답변으로 재개
        bubble("human", text)                 # 카톡처럼 내 말풍선부터 띄운다 (검색 도는 동안 보이게)
        graph.update_state(cfg, {"user_answer": text, "messages": [("human", text)]})
        payload = None
    else:                                     # 새 대화 → 지난 채팅 접어두고 시작
        _archive_and_clear(snap_now)
        payload = {"today_input": text, "messages": [("human", text)],
                   "domain": domain or "", "learned": learned,
                   "hint_count": 0, "clarify_count": 0, "rephrase_count": 0,
                   "user_answer": "", "intent": "", "risk_flag": False}

    with st.status("코치가 읽는 중", expanded=False) as box:
        for step in graph.stream(payload, cfg, stream_mode="updates"):
            for node in step:                     # {노드이름: 바뀐 state}
                box.update(label=DOING.get(node, "생각하는 중"))
        box.update(label="다 됐어요", state="complete")

    st.session_state.view = "qa" if graph.get_state(cfg).next else "done"
    st.rerun()


def bubble(role, text):
    """카톡식 말풍선. human=오른쪽 남색 / ai=왼쪽 회색. '더 알아보기'만 팁 카드로."""
    if role != "human" and text.startswith("더 알아보기"):
        body = text.replace("더 알아보기 ·", "", 1).replace("더 알아보기", "", 1).strip()
        st.markdown(f"<div class='row'><div class='bubble tip'>"
                    f"<span class='k'>더 알아보기</span>{body}</div></div>",
                    unsafe_allow_html=True)
        return
    me = role == "human"
    st.markdown(f"<div class='row {'me' if me else ''}'>"
                f"<div class='bubble {'me' if me else 'coach'}'>{text}</div></div>",
                unsafe_allow_html=True)


st.markdown("<div class='brand'>내 몸·마음 읽기 코치</div>", unsafe_allow_html=True)

# ═══ HOME — 내가 발견한 것들 (주인공) ═══════════════════════════════════
if st.session_state.view == "home":
    st.markdown("<div class='lede'>오늘 먹고 잔 걸 한 줄 적으면, 질문을 주고받으며 "
                "<b>나에 대한 패턴</b>이 하나씩 쌓여요.</div>",
                unsafe_allow_html=True)

    # 첫 방문(발견 0)이면 소개를 펼쳐둔다 — "뭐 하는 앱이지?"를 안 눌러도 알게.
    with st.expander("이 코치는 뭔가요?", expanded=(len(insights) == 0)):
        st.markdown("""
**보통 앱은** "단백질 챙기세요" 하고 답을 줘요.
**여긴 답 대신 질문**을 던져요 — "탄수만 먹으면 뭐가 부족할까요?"

답하다 보면 "나는 이럴 때 이렇더라"가 보여요. 그게 아래에 쌓이고요.
정답 맞히기가 아니라, 나를 알아가는 거예요.
""")

    st.markdown(f"<div class='sec'>나에 대해 알게 된 것 <span class='n'>{len(insights)}</span></div>",
                unsafe_allow_html=True)

    if insights:
        for i, s in enumerate(insights):
            tag = idomains[i] if i < len(idomains) else ""
            st.markdown(f"<div class='star'><div class='v'>{s}</div>"
                        f"<div class='m'><span class='dot'>●</span> {tag}</div></div>",
                        unsafe_allow_html=True)
        # "9가지 중 N가지" 캡션은 뺐다 — '9가지'가 뭔지 앱에 설명이 없어 뜬금없었다.
        # 개수는 위 '나에 대해 알게 된 것 N'으로 충분하다.
    else:
        st.markdown("<div class='empty'>아직 비어 있어요.<br>"
                    "오늘 있었던 일을 하나 기록하면<br>거기서 알게 된 게 여기 쌓여요.</div>",
                    unsafe_allow_html=True)

    st.write("")
    if st.button("오늘 기록하기", type="primary", use_container_width=True):
        st.session_state.view = "record"
        st.rerun()

# ═══ RECORD — 카테고리 고르고 한 줄 ════════════════════════════════════
elif st.session_state.view == "record":
    st.markdown("<div class='lede'>오늘 있었던 일을 한 줄로 적어주세요.</div>",
                unsafe_allow_html=True)

    picked = st.segmented_control("무엇에 대한 기록인가요?", DOMAINS)

    if picked == "운동":
        with st.expander("운동기구 화면 사진으로 기록하기"):
            img = st.file_uploader("화면 사진", type=["png", "jpg", "jpeg"],
                                   label_visibility="collapsed")
            if img is not None:
                st.image(img, width=240)
                if st.button("이 기록으로 코칭 받기", type="primary", use_container_width=True):
                    from vision import read_workout_image
                    with st.spinner("화면에서 수치 읽는 중"):
                        rec = read_workout_image(img.getvalue(), img.type)
                    if rec is None:
                        st.error("운동기구 화면을 못 읽었어요. 아래에 직접 적어주세요.")
                    else:
                        send(rec.as_record(), picked)

    # chat_input은 화면 맨 아래에 고정돼서 카드형 화면과 뚝 떨어진다 → 폼으로 붙인다.
    # ⚠️ send()는 st.rerun()으로 끝난다 → **폼 블록 안에서 부르면 안 된다.** 안에서 부르면
    #    폼을 그리는 도중에 화면을 새로 그리게 돼서 빨간 에러가 번쩍한다. 제출 여부만 받아 나온다.
    with st.form("rec", border=False, clear_on_submit=True):
        typed = st.text_input(
            "기록", placeholder=HINTS[picked] if picked else "위에서 카테고리를 먼저 골라주세요",
            label_visibility="collapsed", disabled=picked is None)
        submitted = st.form_submit_button("코칭 받기", type="primary",
                                          use_container_width=True, disabled=picked is None)

    if st.button("돌아가기", use_container_width=True):
        st.session_state.view = "home"
        st.rerun()

    if submitted and typed.strip():
        send(typed.strip(), picked)

# ═══ QA — 대화 ════════════════════════════════════════════════════════
# 질문 카드 한 장씩(타입폼/듀오링고식)으로 만들어봤는데, 저건 단답 퀴즈에나 맞는 형태다.
# 이 코치는 힌트를 주고 되묻고 딴소리도 받아준다 → 내 답이 화면에 안 남으니 대화가 튄 것처럼
# 보였다. 익숙한 채팅이 여기선 이득. 차별점은 홈(수집)에 두고, 여긴 헤매지 않게 만든다.
elif st.session_state.view == "qa":
    ti = values.get("today_input") or ""
    dom = values.get("domain") or ""
    st.markdown(f"<div class='rec'>오늘의 기록 · {dom}</div>"
                f"<div class='rec'><b>{ti}</b></div><br>", unsafe_allow_html=True)

    # 지난 대화는 접어둔다 — 완료된 대화가 채팅에 계속 쌓이던 걸 여기로 뺐다
    past = values.get("past_chats") or []
    if past:
        with st.expander(f"지난 대화 {len(past)}개"):
            for chat in past:
                st.caption(chat.get("ti", ""))
                for role, text in chat.get("turns", []):
                    bubble(role, text)
                st.markdown("<hr>", unsafe_allow_html=True)

    for role, text in turns:                  # 현재 대화만 (오른쪽=나 / 왼쪽=코치)
        bubble(role, text)

    # 카톡식 자동 스크롤 — 답하면 화면이 최신 대화로 내려간다.
    # 커스텀 말풍선은 st.chat_message와 달리 자동 스크롤이 없어서 "마지막이 안 보였다".
    # components.html은 iframe이라 window.parent로 부모 문서의 스크롤 컨테이너를 잡는다.
    st.components.v1.html("""
        <script>
          const doc = window.parent.document;
          const main = doc.querySelector('section[data-testid="stMain"]')
                    || doc.querySelector('.main');
          if (main) main.scrollTo({top: main.scrollHeight, behavior: 'smooth'});
        </script>
    """, height=0)

    if typed := st.chat_input("편하게 적어보세요 (몰라도 괜찮아요)"):
        send(typed)

# ═══ DONE — 정돈된 요약 (대화 조각을 쌓지 않는다) ══════════════════════
# 예전엔 대화 끝부분("그거예요…", closing 긴 말)을 날것으로 늘어놨더니 어수선했다.
# 대화는 '지난 대화'에 있으니, 여기선 **AI가 정돈한 결과**만 카드 둘로 보여준다.
else:
    # ⚠️ **이번 대화에서 발견했을 때만** '오늘 알게 된 것'을 보여준다.
    #    예전엔 insights[-1]을 무조건 띄워서, 오늘 발견이 없으면(예: "별느낌없었는데")
    #    직전 발견(어제 파스타)을 '오늘 알게 된 것'이라며 끌어왔다. 코치의 발견 확정
    #    메시지가 현재 대화(coach_lines)에 있으면 = 오늘 것.
    found_today = insights and any("본인 신호를 직접" in l for l in coach_lines)
    if found_today:
        st.markdown("<div class='sec'>오늘 알게 된 것</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='star'><div class='v'>{insights[-1]}</div>"
                    f"<div class='m'><span class='dot'>●</span> "
                    f"{idomains[-1] if idomains else ''}</div></div>", unsafe_allow_html=True)
    elif values.get("fit") == "skip" and coach_lines:
        # 가르칠 게 없어 가볍게 받아준 경우(read_record→skip→acknowledge) —
        # "오늘은 여기까지" 대신 코치가 실제로 한 말을 보여준다.
        # ("초코칩 달콤했겠네요. 오늘은 딱히 짚을 건 없어요 — 혹시 끼니 얘기도 해볼까요?")
        st.markdown(f"<div class='empty'>{coach_lines[-1]}</div>", unsafe_allow_html=True)
        # ⚠️ 여기서 끝내지 않는다. "혹시 다른 얘기?"라고 해놓고 대답할 데가 없으면 허무하다.
        #    이어 친 건 send()가 **새 기록**으로 받아 read_record를 다시 태운다(코칭되거나 또 skip).
        #    이어갈 게 없으면 아래 '홈으로'로 나가면 된다.
        if typed := st.chat_input("이어서 얘기하려면 적어주세요"):
            send(typed)
    else:                                     # 가르쳤는데 발견이 부실(못 맞힘·신호 없음)
        st.markdown("<div class='empty'>오늘은 여기까지예요.<br>"
                    "다음에 또 같이 살펴봐요.</div>", unsafe_allow_html=True)

    tip = next((l for l in coach_lines if l.startswith("더 알아보기")), "")
    if tip:
        body = tip.replace("더 알아보기 ·", "", 1).replace("더 알아보기", "", 1).strip()
        st.markdown(f"<div class='bubble tip' style='margin-top:1rem'>"
                    f"<span class='k'>더 알아보기</span>{body}</div>", unsafe_allow_html=True)

    st.write("")
    if st.button("홈으로", type="primary", use_container_width=True):
        st.session_state.view = "home"
        st.rerun()


# ── 사이드바 — 부차적인 것만 ────────────────────────────────────────────
with st.sidebar:
    for k, v in learned.items():
        st.markdown(f"- {CONCEPTS[k]['title']}" + ("" if v >= 2 else "  *(개념만)*"))
    if learned:
        st.divider()

    with st.expander("다음에 이어서 하기"):
        st.caption("**이 페이지를 북마크하면** 다음에 열 때 자동으로 이어져요 "
                   "(주소에 코드가 담겨 있어요). 다른 기기에서 이어하려면 아래 코드를 옮겨서 입력하세요. "
                   "코드를 모르면 아무도 이 기록을 볼 수 없어요.")
        st.code(st.session_state.sid, language=None)
        resume = st.text_input("가지고 있던 코드", placeholder="코드 붙여넣기")
        if resume and resume.strip() != st.session_state.sid:
            st.session_state.sid = resume.strip()
            st.query_params["s"] = resume.strip()      # URL도 갱신 → 이후 재방문 이어짐
            st.session_state.view = "home"
            st.rerun()

    if st.button("처음부터 다시", use_container_width=True):
        # messages는 add_messages 리듀서라 []를 넣으면 "빈 걸 추가"가 돼서 안 지워진다.
        from langchain_core.messages import RemoveMessage
        graph.update_state(cfg, {
            "messages": [RemoveMessage(id=m.id) for m in (values.get("messages") or [])
                         if getattr(m, "id", None)],
            "learned": {}, "insights": [], "insight_domains": [], "past_chats": [],
            "today_input": "", "user_answer": "",
            "target_concept": None, "domain": "",
            "hint_count": 0, "clarify_count": 0, "rephrase_count": 0,
        }, as_node="closing")
        st.session_state.view = "home"
        st.rerun()

    st.divider()
    st.markdown("<span class='muted'>학습용 코치예요. "
                "<b>의료 조언이나 위기 상담 도구가 아닙니다.</b><br>"
                "몸이 급하면 <b>119</b> · 마음이 힘들면 자살예방 상담 <b>109</b><br><br>"
                "<b>개발자는 대화를 따로 수집하거나 들여다보지 않아요.</b> "
                "세션을 이어가려고 잠깐 저장될 뿐, 다른 사람도 볼 수 없어요.<br>"
                "다만 답변을 만들기 위해 입력한 내용이 OpenAI로 전송되니, "
                "<b>실제 민감한 건강 정보는 넣지 마세요.</b></span>",
                unsafe_allow_html=True)
