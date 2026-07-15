"""대화형 실행 — 직접 코치랑 얘기해보기.

    python chat.py

오늘 기록을 한 줄 쓰면 코치가 질문한다. 답을 타이핑하면 채점→힌트/칭찬으로 이어진다.
진도(배운 개념)는 **SQLite에 저장돼서 다시 켜도 이어진다.** (강의 #14.2)
(Ctrl+C로 종료. OPENAI_API_KEY 없으면 규칙기반으로 그래도 돌아감)
"""
from concepts import CONCEPTS
from graph import build_persistent_graph

USER = "hailey"          # thread_id — 사용자별로 진도가 따로 쌓인다


def show(graph, cfg, seen):
    """seen 이후로 새로 쌓인 코치 메시지만 출력 (ToolNode 원본·빈 메시지는 숨김)."""
    msgs = graph.get_state(cfg).values.get("messages", [])
    for m in msgs[seen:]:
        if getattr(m, "type", "") == "tool":
            continue
        content = getattr(m, "content", m)
        if str(content).strip():
            print("🩺", content)
    return len(msgs)


def main():
    graph = build_persistent_graph()
    cfg = {"configurable": {"thread_id": USER}}

    snap = graph.get_state(cfg)
    prev = snap.values or {}
    learned = prev.get("learned") or {}
    seen = len(prev.get("messages") or [])

    # 지난 세션이 답을 기다리다 끊겼으면(Ctrl+C 등) 그 대기를 풀고 새로 시작한다.
    # as_node로 "closing이 방금 실행된 척" 하면 다음 노드가 END가 되어 대기가 풀린다. (강의 #17.3)
    if snap.next:
        graph.update_state(cfg, {"stage": "closing"}, as_node="closing")

    print("─" * 62)
    print("⚠️  이 코치는 학습용 셀프케어 코치예요. 의료 조언이나 위기 상담 도구가 아닙니다.")
    print("    몸이 급하면 119 · 마음이 힘들면 자살예방 상담 109 (24시간, 무료)")
    print("─" * 62)
    insights = prev.get("insights") or []
    if insights:
        print("📗 지금까지 스스로 발견한 내 패턴")
        for s in insights:
            print(f"   · {s}")
        print()
    if learned:
        mastered = [k for k, v in learned.items() if v >= 2]
        print(f"   (개념 {len(learned)}개 익힘 · 그중 {len(mastered)}개는 내 몸에 적용까지)")
        print("   배운 건 다시 안 물어봐요. 새 개념으로 갈게요.\n")
    print("오늘 어땠어요? 한 줄로 적어줘요.")
    print("  예) 점심에 라면이랑 김밥 먹었어  /  새벽까지 못 잤어  /  요새 완전 번아웃이야  /  오늘 헬스 했어")
    log = input("\n나 > ").strip()

    # learned는 이어받고, 세션 단위 값들만 초기화한다.
    graph.invoke({"today_input": log, "learned": learned,
                  "hint_count": 0, "clarify_count": 0, "rephrase_count": 0,
                  "user_answer": "", "intent": "", "risk_flag": False}, cfg)
    seen = show(graph, cfg, seen)

    # 답을 기다리는 지점(absorb / guard_answer)에서 멈춘다 → 답 받아 재개, 끝날 때까지 반복.
    while graph.get_state(cfg).next:
        ans = input("나 > ").strip()
        graph.update_state(cfg, {"user_answer": ans})
        graph.invoke(None, cfg)
        seen = show(graph, cfg, seen)

    v = graph.get_state(cfg).values
    after, ins = v.get("learned") or {}, v.get("insights") or []
    print(f"\n[개념 {len(after)}/{len(CONCEPTS)}개 · 내 패턴 {len(ins)}개 발견]")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n(종료합니다. 진도는 저장돼 있어요. 또 봐요!)")
