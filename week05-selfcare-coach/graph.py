"""LangGraph 그래프 조립 (그래프설계.md §3).

흐름: safety_guard →(위험? END : empathy)→ diagnose →(다 앎? closing : socratic_q)
      → [유저 답 대기] → evaluate →(correct: praise / else: hint)
      hint →(힌트 소진? closing : socratic_q 루프)  → praise → closing → END

핵심 3가지:
- 분기: add_conditional_edges (앎/모름, 채점 결과, 힌트 소진)
- 유저 답 대기: evaluate 앞에서 멈춤 = compile(interrupt_before=["evaluate"]) + checkpointer
- 힌트 루프: hint → socratic_q 로 되돌아가는 엣지 (HINT_MAX 넘으면 탈출)
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition   # 강의 #14.1 빌트인

from state import CoachState
from nodes import (safety_guard, empathy, diagnose, socratic_q,
                   evaluate, praise, hint, reveal, closing, hint_exhausted,
                   enrich_agent, TOOLS)


def build_graph():
    b = StateGraph(CoachState)
    for fn in (safety_guard, empathy, diagnose, socratic_q,
               evaluate, praise, hint, reveal, closing, enrich_agent):
        b.add_node(fn.__name__, fn)
    b.add_node("tools", ToolNode(TOOLS))       # search_web 실행 노드 (강의 #14.1)

    b.add_edge(START, "safety_guard")
    b.add_conditional_edges("safety_guard",
        lambda s: "risk" if s.get("risk_flag") else "ok",
        {"risk": END, "ok": "empathy"})            # 위험신호면 코치 빠지고 종료
    b.add_edge("empathy", "diagnose")
    b.add_conditional_edges("diagnose",
        lambda s: "done" if s.get("target_concept") is None else "teach",
        {"done": "closing", "teach": "socratic_q"})  # 분기① 다 배웠나/가르칠 게 있나
    b.add_edge("socratic_q", "evaluate")           # 이 사이에서 유저 답 대기(interrupt_before)
    b.add_conditional_edges("evaluate",
        lambda s: s["verdict"],
        {"correct": "praise", "wrong": "hint", "unknown": "hint"})  # 분기② 채점
    b.add_conditional_edges("hint",
        lambda s: "exhausted" if hint_exhausted(s) else "retry",
        {"retry": "evaluate", "exhausted": "reveal"})  # 힌트 뒤 답 대기 / 소진되면 정답 공개
    b.add_edge("reveal", END)                            # 정답 알려주고 오늘은 마무리
    # 정답 → 칭찬 → enrich_agent가 웹 검색 Tool로 실천 팁 찾기 (강의 #14.1 chatbot↔tools 루프)
    b.add_edge("praise", "enrich_agent")
    b.add_conditional_edges("enrich_agent", tools_condition,
        {"tools": "tools", END: "closing"})    # tool call 있으면 tools, 없으면 closing (분기③)
    b.add_edge("tools", "enrich_agent")          # 검색 결과 들고 복귀
    b.add_edge("closing", END)

    # 유저 답을 기다리려면 evaluate 실행 직전에 멈춰야 함 → interrupt_before + checkpointer(재개용)
    return b.compile(checkpointer=MemorySaver(), interrupt_before=["evaluate"])


# ── 규칙기반 데모: LLM 없이 한 흐름 굴려보기 (라면+김밥 → 질문 → 답 → 힌트/칭찬) ──
if __name__ == "__main__":
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "demo"}}
    seen = 0

    def show():
        global seen
        msgs = graph.get_state(cfg).values.get("messages", [])
        for m in msgs[seen:]:
            # ToolNode 원본 검색 덤프 + tool call만 든 빈 메시지는 화면에서 숨김 (내부 처리용)
            if getattr(m, "type", "") == "tool":
                continue
            content = getattr(m, "content", m)
            if not str(content).strip():
                continue
            print("   🩺", content)
        seen = len(msgs)

    print("[사용자] 점심에 라면이랑 김밥 먹었어")
    graph.invoke({"today_input": "점심에 라면이랑 김밥 먹었어", "learned": {}, "hint_count": 0}, cfg)
    show()  # empathy + 첫 소크라테스 질문까지 나오고 evaluate 앞에서 멈춤

    for ans in ["글쎄 잘 모르겠는데", "아 단백질?"]:   # 첫 답 틀림→힌트, 둘째 맞음→칭찬
        print(f"[사용자] {ans}")
        graph.update_state(cfg, {"user_answer": ans})  # 유저 답 주입
        graph.invoke(None, cfg)                          # 멈춘 데서 재개
        show()

    print("\n[진도 메모리]", graph.get_state(cfg).values.get("learned"))
