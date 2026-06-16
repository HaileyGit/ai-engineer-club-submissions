import asyncio

import streamlit as st
from dotenv import load_dotenv

from agents import Agent, Runner, SQLiteSession, WebSearchTool

load_dotenv()  # .env 의 OPENAI_API_KEY 로드 (WebSearchTool = OpenAI hosted tool 이라 필수)

st.set_page_config(page_title="Life Coach", page_icon="🌱")
st.title("🌱 Life Coach")
st.caption("동기부여·습관·자기계발을 웹에서 찾아 코칭하는 라이프 코치")


# ── 코치 페르소나 (= 노트북 1번 셀 Agent instructions, = 네 Gem '요청 사항') ──
INSTRUCTIONS = """
너는 따뜻하고 격려해주는 라이프 코치야.
사용자의 고민에 먼저 공감하고, 현실적이고 구체적인 조언을 한국어 존댓말로 해줘.
응원만 하지 말고 작은 실천 단계를 제안해줘.

[WebSearchTool 사용 규칙]
동기부여, 자기계발 팁, 습관 형성, 생산성, 수면·운동·건강 루틴처럼
검증된 최신 정보나 구체적인 방법이 필요할 때는 적극적으로 웹을 검색해서
근거 있는 조언을 해줘. 추측보다 검색을 우선해.
"""

# 웹검색 진행 상태 매핑 (= 노트 #8.2 status_messages 딕셔너리)
STATUS_MESSAGES = {
    "response.web_search_call.in_progress": ("🔍 웹 검색 시작", "running"),
    "response.web_search_call.searching": ("🔍 웹 검색 중...", "running"),
    "response.web_search_call.completed": ("✅ 웹 검색 완료", "complete"),
}


# ── 세션 메모리 / 에이전트: st.session_state 에 캐싱 (= 노트북 2·1번 셀) ──
# Streamlit 은 입력마다 파일 전체를 재실행 → 살아남아야 할 건 session_state 에.
if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession("life-coach", "db.sqlite")
session = st.session_state["session"]

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="Life Coach",
        instructions=INSTRUCTIONS,
        tools=[WebSearchTool()],
    )
agent = st.session_state["agent"]


# ── 대화 기록 다시 그리기 (= 노트 #8.1 paint_history) ──
# 재실행마다 화면이 비므로 매번 메모리를 통째로 다시 그린다.
async def paint_history():
    items = await session.get_items()
    for message in items:
        role = message.get("role")
        msg_type = message.get("type")
        if role == "user":
            # user: content 가 문자열 (노트북 5번 셀에서 본 구조)
            with st.chat_message("human"):
                st.write(message["content"])
        elif msg_type == "message":
            # assistant: content 가 리스트 → 텍스트는 content[0]["text"]
            with st.chat_message("ai"):
                st.write(message["content"][0]["text"])
        elif msg_type == "web_search_call":
            # 검색한 흔적 표시
            with st.chat_message("ai"):
                st.write("🔍 웹 검색함")


# ── 에이전트 실행 + 스트리밍 (= 노트북 6번 셀 + Streamlit 누적 방식) ──
async def run_agent(message):
    with st.chat_message("ai"):
        status_slot = st.empty()       # 웹검색 상태는 위에
        text_placeholder = st.empty()  # 답변 텍스트는 아래에
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
                response += data.delta          # 글자 조각 누적
                text_placeholder.write(response)  # 같은 칸에 덮어쓰기


# ── 메인 흐름 ──
asyncio.run(paint_history())  # 1. 지금까지 대화 다시 그리기

message = st.chat_input("고민을 들려주세요 (예: 아침에 일찍 일어나고 싶은데 자꾸 알람을 꺼요)")
if message:
    with st.chat_message("human"):  # 2. 방금 입력 그리기
        st.write(message)
    asyncio.run(run_agent(message))  # 3. 코치 답변 (human 블록 밖에서 호출)


# ── 디버깅 사이드바 (메모리 확인 + 리셋) — 맨 아래에 둬야 최신으로 갱신됨 ──
with st.sidebar:
    st.subheader("🛠 디버그")
    if st.button("메모리 초기화"):
        asyncio.run(session.clear_session())
        st.rerun()
    st.write(asyncio.run(session.get_items()))
