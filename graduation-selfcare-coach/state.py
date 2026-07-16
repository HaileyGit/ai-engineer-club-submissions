"""그래프가 들고 다니는 상태 (그래프설계.md §1).

messages는 add_messages 리듀서로 대화를 누적하고, 나머지는 커스텀 TypedDict 필드.
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class CoachState(TypedDict, total=False):
    # add_messages 리듀서: 노드가 return한 messages를 '덮어쓰기'가 아니라 '누적'.
    # ("ai", "텍스트") 튜플도 알아서 메시지 객체로 변환해준다.
    messages: Annotated[list, add_messages]
    today_input: str      # 이번 턴 사용자 입력 (예: "점심 라면+김밥")
    clarify_count: int    # 되묻기 횟수 (애매한 입력에 한 번만 되묻고, 무한 되묻기 방지)
    guard_tripped: str    # Output guardrail이 막은 문장의 사유 (디버그·로그용)
    input_kind: str       # 첫 입력이 뭔지 (record/question/chitchat) — 질문·잡담엔 수업 안 함
    intent: str           # 사용자 발화 의도 (answer/object/confused/stop) — 강의 #16 Routing
    rephrase_count: int   # 질문을 쉽게 다시 물어준 횟수 (무한 되묻기 방지)
    domain: str           # 오늘 입력이 어느 도메인인지 (식단/수면/휴식/운동) — read_record가 판별
    fit: str              # 이 기록에 가르칠 게 있나 (teach/skip) — read_record가 정함
    target_concept: str   # 이번에 가르칠 개념 key (concepts.py). skip이면 None
    learned: dict         # 진도 메모리 {concept_key: 숙련도}
                          #   1 = 개념을 맞힘 / 2 = 내 몸에 적용해서 읽음(마스터)
    # 사용자가 스스로 발견한 **자기 패턴**. 개념 지식이 아니라 "나에 대한 앎"이 쌓인다.
    # 예: "라면만 먹으면 2시간 뒤 다시 배고파진다"
    #
    # ⚠️ 일부러 리듀서를 안 쓴다. operator.add를 걸었더니 **비울 수가 없었다** —
    #    초기화하려고 []를 넣으면 "빈 리스트를 더하기"가 돼서 그대로 남았다.
    #    (누적은 capture_insight 노드가 직접 한다)
    insights: list
    # insights[i]가 어느 도메인에서 나왔나. UI 카드 태그용.
    # ⚠️ 사용자가 고른 카테고리(domain)를 태그로 쓰면 틀린다 — 그 도메인 개념을 다 뗐으면
    #    diagnose가 다른 도메인 개념으로 넘어간다. 태그는 **실제 배운 개념**을 따라가야 한다.
    insight_domains: list
    # 완료된 지난 대화들의 보관함. [{"ti": 오늘의기록, "turns": [(role, text), ...]}, ...]
    # messages는 새 대화 시작 때 비우니(안 그러면 채팅이 끝없이 쌓인다), 비우기 전에 여기 옮겨둔다.
    # → 채팅은 '현재 대화'만, 지난 건 접어서(UI expander) 열람.
    past_chats: list
    hint_count: int       # 현재 개념 힌트 몇 번 줬나 (루프 종료용, max=HINT_MAX)
    user_answer: str      # 소크라테스 질문에 대한 유저 답
    verdict: str          # "correct" | "wrong" | "unknown"
    risk_flag: bool       # 의학 위험신호 감지 여부
    stage: str            # 현재 노드 (디버그·재개용)


# 힌트 1번까지, 2번째도 못 맞히면 정답 알려주고 넘어감.
# ⚠️ 원래 2였는데 1로 줄였다 — "쉬려고 연 셀프케어 앱인데 시험 보는 느낌"이라 부담을 낮췄다.
# 소크라테스식(스스로 깨닫기)은 유지하되, 한 번 유도하고 그래도 안 되면 빨리 알려주고 넘어간다.
HINT_MAX = 1
