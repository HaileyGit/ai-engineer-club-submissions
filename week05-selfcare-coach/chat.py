"""대화형 실행 — 직접 코치랑 얘기해보기.

    python chat.py

오늘 기록을 한 줄 쓰면 코치가 질문한다. 답을 타이핑하면 채점→힌트/칭찬으로 이어진다.
(Ctrl+C로 종료. OPENAI_API_KEY 없으면 규칙기반으로 그래도 돌아감)
"""
from graph import build_graph


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
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "chat"}}

    print("오늘 어땠어요? 한 줄로 적어줘요.")
    print("  예) 점심에 라면이랑 김밥 먹었어  /  새벽까지 못 잤어  /  요새 완전 번아웃이야  /  오늘 헬스 했어")
    log = input("\n나 > ").strip()

    graph.invoke({"today_input": log, "learned": {}, "hint_count": 0}, cfg)
    seen = show(graph, cfg, 0)

    # evaluate 앞에서 멈춤(interrupt). 답 받아 재개 → 끝(END)날 때까지 반복.
    while graph.get_state(cfg).next:          # 다음 실행할 노드가 남아있으면 = 답 대기중
        ans = input("나 > ").strip()
        graph.update_state(cfg, {"user_answer": ans})
        graph.invoke(None, cfg)
        seen = show(graph, cfg, seen)

    learned = graph.get_state(cfg).values.get("learned") or {}
    print(f"\n[오늘 함께 짚어본 개념: {len(learned)}개]")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\n(종료합니다. 또 봐요!)")
