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
    domain: str           # 오늘 입력이 어느 도메인인지 (식단/수면/번아웃/운동) — diagnose가 판별
    target_concept: str   # 이번에 가르칠 개념 key (concepts.py)
    learned: dict         # 진도 메모리 {concept_key: 숙련도} — 이미 앎/모름 판단
    hint_count: int       # 현재 개념 힌트 몇 번 줬나 (루프 종료용, max=HINT_MAX)
    user_answer: str      # 소크라테스 질문에 대한 유저 답
    verdict: str          # "correct" | "wrong" | "unknown"
    risk_flag: bool       # 의학 위험신호 감지 여부
    stage: str            # 현재 노드 (디버그·재개용)


HINT_MAX = 2  # 힌트 2번까지, 3번째도 못 맞히면 정답 알려주고 넘어감 (그래프설계.md §4)
