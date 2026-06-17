import asyncio
import os

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool

load_dotenv()  # OPENAI_API_KEY, OPENAI_VECTOR_STORE_ID

VECTOR_STORE_ID = os.getenv("OPENAI_VECTOR_STORE_ID")  # setup_vector_store.py 가 만들어 .env 에 저장

st.set_page_config(page_title="Life Coach", page_icon="🌱")
st.title("🌱 Life Coach")
st.caption("내 목표를 기억하고, 웹에서 찾아 코칭하는 라이프 코치")


# ── 코치 페르소나 ──
INSTRUCTIONS = """
너는 따뜻하고 격려해주는 라이프 코치야.
사용자의 고민에 먼저 공감하고, 현실적이고 구체적인 조언을 한국어 존댓말로 해줘.
응원만 하지 말고 작은 실천 단계를 제안해줘.

[FileSearchTool 사용 규칙]
사용자가 자신의 목표·계획·과거 기록·진행 상황에 대해 물으면,
먼저 FileSearchTool 로 업로드된 '개인 목표 문서'를 찾아서 그 내용을 근거로 답해.
예: "운동 목표 잘 되고 있어?" → 목표 문서에서 운동 계획(주 3회 등)을 먼저 확인.

[WebSearchTool 사용 규칙]
습관·운동·수면·생산성 등 목표 관련 조언을 할 때는,
목표 문서만으로 끝내지 말고 WebSearchTool 로 검증된 최신 방법을 함께 찾아.

[항상 결합 — 중요]
목표·진행 상황·습관 관련 질문에는 아래 세 단계를 모두 수행해:
  1) FileSearchTool 로 내 목표·기록을 먼저 확인하고,
  2) 이어서 WebSearchTool 로 그 목표에 맞는 검증된 방법을 검색하고,
  3) 둘을 합쳐 '개인화된' 추천을 줘.
예: "운동 목표 잘 되고 있어?" → 목표 문서 확인 → "운동 루틴 유지하는 방법" 웹 검색 → 합쳐서 조언.
추측하지 말고 두 도구를 모두 사용해.
"""

# 도구 진행 상태 매핑 (#8.2 웹검색 + #8.3 파일검색)
STATUS_MESSAGES = {
    "response.web_search_call.in_progress": ("🔍 웹 검색 시작", "running"),
    "response.web_search_call.searching": ("🔍 웹 검색 중...", "running"),
    "response.web_search_call.completed": ("✅ 웹 검색 완료", "complete"),
    "response.file_search_call.in_progress": ("📂 목표 문서 검색 시작", "running"),
    "response.file_search_call.searching": ("📂 목표 문서 검색 중...", "running"),
    "response.file_search_call.completed": ("✅ 목표 문서 확인", "complete"),
}


# ── 세션 메모리: 캐싱 ──
if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession("life-coach", "db.sqlite")
session = st.session_state["session"]

# ── 에이전트: 매 재실행마다 새로 구성 (VECTOR_STORE_ID·도구 변화를 항상 반영) ──
tools = [WebSearchTool()]
if VECTOR_STORE_ID:
    tools.append(FileSearchTool(vector_store_ids=[VECTOR_STORE_ID], max_num_results=3))
agent = Agent(name="Life Coach", instructions=INSTRUCTIONS, tools=tools)


# ── 업로드한 파일을 Vector Store 에 보관 (#8.3) ──
def store_file(file):
    client = OpenAI()
    client.vector_stores.files.upload_and_poll(
        vector_store_id=VECTOR_STORE_ID,
        file=(file.name, file.getvalue()),
    )


# ── 대화 기록 다시 그리기 (#8.1) ──
async def paint_history():
    items = await session.get_items()
    for message in items:
        role = message.get("role")
        msg_type = message.get("type")
        if role == "user":
            with st.chat_message("human"):
                st.write(message["content"])
        elif msg_type == "message":
            with st.chat_message("ai"):
                st.write(message["content"][0]["text"])
        elif msg_type == "web_search_call":
            with st.chat_message("ai"):
                st.write("🔍 웹 검색함")
        elif msg_type == "file_search_call":
            with st.chat_message("ai"):
                st.write("📂 목표 문서 참조함")


# ── 에이전트 실행 + 스트리밍 (#8.1·#8.2) ──
async def run_agent(message):
    with st.chat_message("ai"):
        status_slot = st.empty()
        text_placeholder = st.empty()
        status_box = None
        response = ""

        runner = Runner.run_streamed(agent, message, session=session)
        async for event in runner.stream_events():
            if event.type != "raw_response_event":
                continue
            data = event.data
            if data.type in STATUS_MESSAGES:
                label, state = STATUS_MESSAGES[data.type]
                if status_box is None:
                    status_box = status_slot.status(label, state=state)
                else:
                    status_box.update(label=label, state=state)
            elif data.type == "response.output_text.delta":
                response += data.delta
                text_placeholder.write(response)


# ── 메인 흐름 ──
if not VECTOR_STORE_ID:
    st.warning("목표 문서가 아직 연결되지 않았어요. 터미널에서 `uv run python setup_vector_store.py` 를 한 번 실행하세요. (지금은 웹 검색만 작동)")

asyncio.run(paint_history())

# accept_file=True → message 는 .text 와 .files 를 가진 객체 (#8.3)
message = st.chat_input(
    "고민이나 목표 진행을 물어보세요 (예: 내 운동 목표 잘 되고 있어?)",
    accept_file=True,
    file_type=["txt", "pdf"],
)
if message:
    # 1) 파일이 있으면 먼저 목표함(Vector Store)에 보관
    if message.files and VECTOR_STORE_ID:
        for f in message.files:
            store_file(f)
            with st.chat_message("human"):
                st.write(f"📎 '{f.name}' 을(를) 목표함에 보관했어요")
    # 2) 텍스트가 있으면 코치에게 질문
    if message.text:
        with st.chat_message("human"):
            st.write(message.text)
        asyncio.run(run_agent(message.text))


# ── 디버깅 사이드바 ──
with st.sidebar:
    st.subheader("🛠 디버그")
    st.caption(f"Vector Store: {VECTOR_STORE_ID or '미연결'}")
    if st.button("메모리 초기화"):
        asyncio.run(session.clear_session())
        st.rerun()
    st.write(asyncio.run(session.get_items()))
