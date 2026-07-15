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
    # 애매한 입력은 넘겨짚지 말고 되물어야 한다 (clarify에서 멈춰 답을 기다림)
    ("애매 입력→되묻기", "배고프다", [],
        lambda st: (st.get("stage") == "clarify" and st.get("clarify_count") == 1,
                    f'stage={st.get("stage")} clarify={st.get("clarify_count")}')),
    # 되묻고 받은 답으로 도메인을 다시 잡아야 한다 ("피곤해"만 보면 수면 같지만 실은 번아웃)
    ("되묻기→번아웃 정정", "피곤해",
        ["요새 일이 너무 많아서 쉴 틈이 없어", "쉬는 시간이 필요해"],
        lambda st: (st.get("domain") == "번아웃" and "burnout_rest" in st.get("learned", {}),
                    f'stage={st.get("stage")} domain={st.get("domain")} learned={list(st.get("learned",{}))}')),
]


# 채점(evaluate) 균형 — 너무 관대하면 아무 말이나 정답, 너무 빡세면 진짜 정답도 오답.
# 둘 다 실제로 겪은 버그라 여기 박아둔다. (개념key, 사용자답, 기대판정)
EVAL_CASES = [
    ("protein_balance", "단백질?", "correct"),                      # 핵심 단어 → 짧아도 정답
    ("protein_balance", "야채?", "wrong"),                          # 다른 개념 → 걸러야
    ("sleep_rhythm", "매일 같은 시간에 자는게 중요하지", "correct"),   # 원리를 말함
    ("sleep_rhythm", "3시에 자는데 10시로 땡기고싶어", "wrong"),      # '일찍 자기' ≠ '일정함'
    ("sleep_rhythm", "몰라", "unknown"),
    ("burnout_rest", "쉬는 시간이 필요해", "correct"),
    ("exercise_consistency", "자주 조금씩", "correct"),
]


def main():
    print("═" * 56)
    passed = 0
    for i, (name, today, answers, check) in enumerate(SCENARIOS):
        st = run(today, answers, f"t{i}")
        ok, detail = check(st)
        print(f'{"✅ PASS" if ok else "❌ FAIL"}  {name:16s} | {detail}')
        passed += ok
    print("─" * 56)
    from nodes import evaluate
    for key, ans, want in EVAL_CASES:
        got = evaluate({"target_concept": key, "user_answer": ans})["verdict"]
        ok = got == want
        print(f'{"✅ PASS" if ok else "❌ FAIL"}  채점: {ans[:20]:22s} | 기대={want} 결과={got}')
        passed += ok
    total = len(SCENARIOS) + len(EVAL_CASES)
    print("═" * 56)
    print(f"{passed}/{total} 통과")


if __name__ == "__main__":
    main()
