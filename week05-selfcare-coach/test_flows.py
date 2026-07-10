"""스모크 테스트 — 코치의 대표 경로 7개를 자동으로 돌려 회귀 확인.

    python test_flows.py

손으로 매번 채팅하지 말고 이걸로 한 방에. LLM은 매번 다른 문장을 뱉으니
정확한 텍스트가 아니라 **구조**(끝난 노드 stage / 판별된 domain / 배운 개념)로 판정한다.
새 엣지케이스를 발견하면 SCENARIOS에 케이스 하나만 추가하면 된다.
"""
import warnings
warnings.filterwarnings("ignore")

from graph import build_graph

GRAPH = build_graph()


def run(today, answers, thread):
    """chat.py와 같은 방식으로 흐름을 끝(또는 답 소진)까지 돌리고 최종 state를 돌려준다."""
    cfg = {"configurable": {"thread_id": thread}}
    GRAPH.invoke({"today_input": today, "learned": {}, "hint_count": 0}, cfg)
    i = 0
    while GRAPH.get_state(cfg).next and i < len(answers):
        GRAPH.update_state(cfg, {"user_answer": answers[i]}); i += 1
        GRAPH.invoke(None, cfg)
    return GRAPH.get_state(cfg).values


# (이름, 오늘입력, 답들, 기대검사) — 검사는 최종 state(st)를 받아 (통과여부, 설명) 반환
SCENARIOS = [
    ("식단 정답→칭찬",   "점심에 라면이랑 김밥 먹었어", ["단백질"],
        lambda st: (st.get("stage") == "closing" and "protein_balance" in st.get("learned", {}),
                    f'stage={st.get("stage")} domain={st.get("domain")} learned={list(st.get("learned",{}))}')),
    ("수면 정답→칭찬",   "새벽까지 잠을 못 잤어", ["규칙적으로 일정하게 자는 거"],
        lambda st: (st.get("stage") == "closing" and "sleep_rhythm" in st.get("learned", {}),
                    f'stage={st.get("stage")} domain={st.get("domain")} learned={list(st.get("learned",{}))}')),
    ("번아웃 정답→칭찬", "요새 완전 소진됐어 번아웃이야", ["쉬는 시간이 필요해"],
        lambda st: (st.get("stage") == "closing" and "burnout_rest" in st.get("learned", {}),
                    f'stage={st.get("stage")} domain={st.get("domain")} learned={list(st.get("learned",{}))}')),
    ("운동 정답→칭찬",   "오늘 헬스장서 운동했어", ["자주 조금씩 꾸준히"],
        lambda st: (st.get("stage") == "closing" and "exercise_consistency" in st.get("learned", {}),
                    f'stage={st.get("stage")} domain={st.get("domain")} learned={list(st.get("learned",{}))}')),
    ("힌트 소진→정답공개", "새벽까지 잠을 못 잤어", ["모르겠어", "모르겠어"],
        lambda st: (st.get("stage") == "reveal" and "sleep_rhythm" in st.get("learned", {}),
                    f'stage={st.get("stage")} learned={list(st.get("learned",{}))}')),
    ("위험 가드레일→종료", "가슴이 너무 아파", [],
        lambda st: (st.get("stage") == "safety_guard" and st.get("risk_flag") and not st.get("learned"),
                    f'stage={st.get("stage")} risk={st.get("risk_flag")}')),
    ("애매 입력→식단 질문", "배고프다", [],
        lambda st: (st.get("domain") == "식단" and st.get("stage") == "socratic_q",
                    f'stage={st.get("stage")} domain={st.get("domain")}')),
]


def main():
    print("═" * 56)
    passed = 0
    for i, (name, today, answers, check) in enumerate(SCENARIOS):
        st = run(today, answers, f"t{i}")
        ok, detail = check(st)
        print(f'{"✅ PASS" if ok else "❌ FAIL"}  {name:16s} | {detail}')
        passed += ok
    print("═" * 56)
    print(f"{passed}/{len(SCENARIOS)} 통과")


if __name__ == "__main__":
    main()
