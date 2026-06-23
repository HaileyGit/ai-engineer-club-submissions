import asyncio
import html
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from agents import Agent, Runner, SQLiteSession
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

load_dotenv()

st.set_page_config(page_title="한상 — 식당 봇", page_icon="🍚")

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Nanum+Brush+Script&family=Gowun+Batang:wght@400;700&family=Nanum+Myeongjo:wght@400;700;800&display=swap');

      html, body, .stApp, [data-testid="stChatInput"] textarea, .bubble, .name, .time, .seat, .stButton button {
        font-family:'Gowun Batang','Nanum Myeongjo',serif; }

      /* 한지 결 — 앱 전체 동일 배경 */
      .stApp, section[data-testid="stSidebar"], [data-testid="stBottom"], [data-testid="stBottomBlockContainer"] {
        background:#efe3cd !important;
        background-image:repeating-linear-gradient(90deg, rgba(120,90,50,.035) 0 1px, transparent 1px 26px) !important; }
      section[data-testid="stSidebar"] { border-right:1px solid #e0d0b0; }
      #MainMenu, footer, header { visibility:hidden; }

      /* 가운데 좁은 컬럼 (채팅앱처럼) */
      .block-container, [data-testid="stMainBlockContainer"] { max-width:820px; padding-top:1rem; }

      /* 현판 헤더 */
      .hero { background:linear-gradient(#332c24,#241e18); color:#fff; text-align:center;
        padding:14px 24px 16px; border-radius:8px; margin-bottom:6px;
        border:3px solid #c9a24a; box-shadow:0 6px 20px rgba(40,30,20,.32), inset 0 0 0 1px #5a4a2e; }
      .hero h1 { margin:0; font-family:'Nanum Brush Script',cursive; font-size:52px; line-height:1;
        color:#ecc873; text-shadow:2px 2px 4px rgba(0,0,0,.5); }
      .hero p { margin:5px 0 0; color:#d8c39a; font-size:13px; font-family:'Nanum Myeongjo',serif; }

      .row { display:flex; gap:8px; margin:13px 0; align-items:flex-end; }
      .row.user { justify-content:flex-end; }
      .row.bot  { justify-content:flex-start; }
      .col { display:flex; flex-direction:column; }
      .bubble { max-width:78%; padding:11px 15px; font-size:15.5px; line-height:1.6;
        box-shadow:0 1px 4px rgba(90,60,30,.16); word-break:break-word; }
      .user .bubble { background:#a8392a; color:#fdf3e6; border-radius:16px 16px 4px 16px; }
      .bot  .bubble { background:#fffdf5; color:#332a1d; border:1px solid #e3d6bd; border-radius:16px 16px 16px 4px; }
      .avatar { width:40px; height:40px; border-radius:50%; flex:none; background:#fffdf5;
        border:1.5px solid #d6c39e; display:flex; align-items:center; justify-content:center;
        font-size:20px; box-shadow:0 1px 3px rgba(90,60,30,.15); }
      .name { font-size:12px; color:#8a6a3f; margin:0 0 3px 4px; font-weight:700; }
      .time { font-size:11px; color:#a8987f; white-space:nowrap; padding-bottom:2px; }

      .sys { text-align:center; margin:18px 0 6px; }
      .sys span { background:#efe1c4; color:#7a2e1e; border:1px solid #c9a24a;
        border-radius:999px; padding:6px 18px; font-size:13px; font-weight:700; }

      .typing { display:inline-flex !important; gap:5px; align-items:center; padding:14px 16px; }
      .typing i { width:7px; height:7px; border-radius:50%; background:#c9b08a; display:inline-block; animation:tb 1s infinite; }
      .typing i:nth-child(2){ animation-delay:.15s } .typing i:nth-child(3){ animation-delay:.3s }
      @keyframes tb { 0%,60%,100%{ transform:translateY(0); opacity:.45 } 30%{ transform:translateY(-5px); opacity:1 } }

      /* 환영 + 예시 */
      .hint { text-align:center; color:#8a7559; font-size:13px; margin:18px 0 8px; }
      .stButton button { background:#fffdf5; border:1px solid #d6c39e; color:#5a4632;
        border-radius:999px; font-size:13.5px; padding:9px 6px; box-shadow:0 1px 3px rgba(90,60,30,.1); }
      .stButton button:hover { border-color:#a8392a; color:#a8392a; background:#fff; }

      /* 입력창 */
      [data-testid="stChatInput"] { background:#fffdf5; border:1px solid #d6c39e; border-radius:14px; }
      [data-testid="stChatInput"] textarea { font-size:15px; }

      .seat { background:#fffdf5; border:1px solid #e3d6bd; border-radius:12px; padding:18px;
        text-align:center; box-shadow:0 2px 10px rgba(90,60,30,.08); color:#7a6a52; font-size:13px; }
      .seat .who { font-size:22px; font-weight:800; color:#a8392a; margin-top:8px; font-family:'Nanum Myeongjo',serif; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hero"><h1>한상</h1>'
    "<p>🍚 정성껏 차린 한 상 · 메뉴·주문·예약을 도와드립니다</p></div>",
    unsafe_allow_html=True,
)


# ── 에이전트 4종 ──
menu_agent = Agent(name="Menu Agent", handoff_description="메뉴, 재료, 알레르기 관련 질문 담당",
    instructions=RECOMMENDED_PROMPT_PREFIX + " 너는 한식당 메뉴 전문가야. 메뉴/재료/알레르기 질문에 한국어 존댓말로 친절히 답해.")
order_agent = Agent(name="Order Agent", handoff_description="주문 받기와 주문 확인 담당",
    instructions=RECOMMENDED_PROMPT_PREFIX + " 너는 주문 담당이야. 손님 주문을 받고 내용을 다시 확인해줘. 한국어 존댓말.")
reservation_agent = Agent(name="Reservation Agent", handoff_description="테이블 예약 처리 담당",
    instructions=RECOMMENDED_PROMPT_PREFIX + " 너는 예약 담당이야. 인원수·날짜·시간을 물어 테이블 예약을 도와줘. 한국어 존댓말.")
triage_agent = Agent(name="Triage Agent", handoff_description="안내",
    instructions=RECOMMENDED_PROMPT_PREFIX + " 너는 한식당 안내 직원이야. 손님 요청을 보고 메뉴/주문/예약 중 알맞은 담당에게 넘겨. 직접 답하려 하지 말고 분류해서 전달해.",
    handoffs=[menu_agent, order_agent, reservation_agent])
ALL = [triage_agent, menu_agent, order_agent, reservation_agent]
for a in (menu_agent, order_agent, reservation_agent):
    a.handoffs = [x for x in ALL if x is not a]

AGENTS = {a.name: a for a in ALL}
KOR = {"Triage Agent": "안내", "Menu Agent": "메뉴", "Order Agent": "주문", "Reservation Agent": "예약"}
AVATAR = {"Triage Agent": "🛎", "Menu Agent": "📜", "Order Agent": "🥢", "Reservation Agent": "📅"}


def esc(t): return html.escape(t).replace("\n", "<br>")

def user_html(t, ts):
    return f'<div class="row user"><span class="time">{ts}</span><div class="bubble">{esc(t)}</div></div>'

def bot_html(agent, t, ts=""):
    ts_html = f'<span class="time">{ts}</span>' if ts else ""
    return (f'<div class="row bot"><div class="avatar">{AVATAR[agent]}</div>'
            f'<div class="col"><div class="name">{KOR[agent]} 담당</div>'
            f'<div class="bubble">{esc(t)}</div></div>{ts_html}</div>')

def typing_html(agent):
    return (f'<div class="row bot"><div class="avatar">{AVATAR[agent]}</div>'
            f'<div class="col"><div class="name">{KOR[agent]} 담당</div>'
            f'<div class="bubble typing"><i></i><i></i><i></i></div></div></div>')

def sys_html(t): return f'<div class="sys"><span>{t}</span></div>'


# ── 상태 ──
if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession("restaurant", "restaurant.db")
session = st.session_state["session"]
st.session_state.setdefault("msgs", [])
st.session_state.setdefault("active_agent_name", "Triage Agent")
active_agent = AGENTS[st.session_state["active_agent_name"]]


async def run_agent(text):
    ts = datetime.now().strftime("%H:%M")
    handoff_slot = st.empty()
    bubble_slot = st.empty()
    cur = st.session_state["active_agent_name"]
    bubble_slot.markdown(typing_html(cur), unsafe_allow_html=True)
    handoff_name = None
    response = ""
    stream = Runner.run_streamed(active_agent, text, session=session)
    async for event in stream.stream_events():
        if event.type == "run_item_stream_event":
            if event.item.type == "handoff_output_item":
                handoff_name = event.item.target_agent.name
                cur = handoff_name
                handoff_slot.markdown(sys_html(f"🔀 {KOR[cur]} 담당에게 연결합니다"), unsafe_allow_html=True)
                bubble_slot.markdown(typing_html(cur), unsafe_allow_html=True)
        elif event.type == "raw_response_event":
            if event.data.type == "response.output_text.delta":
                response += event.data.delta
                bubble_slot.markdown(bot_html(cur, response, ts), unsafe_allow_html=True)
    final = stream.last_agent.name
    if handoff_name:
        st.session_state["msgs"].append({"role": "sys", "text": f"🔀 {KOR[handoff_name]} 담당에게 연결합니다"})
    st.session_state["msgs"].append({"role": "bot", "text": response, "agent": final, "ts": ts})
    st.session_state["active_agent_name"] = final


# ── 화면 ──
user_msg = None
was_empty = not st.session_state["msgs"]

if was_empty:
    st.markdown(
        bot_html("Triage Agent", "안녕하세요, 「한상」입니다 😊 메뉴·주문·예약 무엇이든 편하게 말씀해 주세요."),
        unsafe_allow_html=True,
    )
    st.markdown('<div class="hint">이렇게 물어보실 수 있어요</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("📜 채식 메뉴 있나요?", use_container_width=True):
        user_msg = "채식 메뉴 있나요?"
    if c2.button("🥢 불고기 2인분 주문", use_container_width=True):
        user_msg = "불고기 2인분 주문할게요"
    if c3.button("📅 금요일 저녁 예약", use_container_width=True):
        user_msg = "금요일 저녁 4명 예약하고 싶어요"
else:
    for m in st.session_state["msgs"]:
        if m["role"] == "user":
            st.markdown(user_html(m["text"], m.get("ts", "")), unsafe_allow_html=True)
        elif m["role"] == "sys":
            st.markdown(sys_html(m["text"]), unsafe_allow_html=True)
        else:
            st.markdown(bot_html(m["agent"], m["text"], m.get("ts", "")), unsafe_allow_html=True)

prompt = st.chat_input("무엇을 도와드릴까요? (메뉴 / 주문 / 예약)")
if prompt:
    user_msg = prompt

if user_msg:
    ts = datetime.now().strftime("%H:%M")
    st.session_state["msgs"].append({"role": "user", "text": user_msg, "ts": ts})
    st.markdown(user_html(user_msg, ts), unsafe_allow_html=True)
    asyncio.run(run_agent(user_msg))
    if was_empty:
        st.rerun()  # 환영/예시 버튼이 떠 있던 첫 프레임 → 깨끗이 다시 그림(먹통 방지)


# ── 사이드바 ──
with st.sidebar:
    name = st.session_state["active_agent_name"]
    st.markdown(
        f'<div class="seat">지금 연결된 담당<div class="who">{AVATAR[name]} {KOR[name]}</div></div>',
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button("🔄 처음으로 (안내)", use_container_width=True):
        asyncio.run(session.clear_session())
        st.session_state["msgs"] = []
        st.session_state["active_agent_name"] = "Triage Agent"
        st.rerun()
