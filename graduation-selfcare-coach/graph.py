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
from nodes import (safety_guard, route_record, redirect, guard_answer, route_intent,
                   handle_object, rephrase, empathy, clarify, absorb, diagnose,
                   socratic_q, evaluate, praise, reflect, capture_insight, hint, reveal,
                   closing, hint_exhausted, is_vague, enrich_agent, TOOLS)


def build_graph(checkpointer=None):
    """checkpointer를 안 주면 MemorySaver(인메모리) — 테스트용 격리.
    실사용은 build_persistent_graph()로 SQLite를 쓴다. (강의 #14.2)
    """
    b = StateGraph(CoachState)
    for fn in (safety_guard, route_record, redirect, guard_answer, route_intent,
               handle_object, rephrase, empathy, clarify, absorb, diagnose,
               socratic_q, evaluate, praise, reflect, capture_insight, hint, reveal,
               closing, enrich_agent):
        b.add_node(fn.__name__, fn)
    b.add_node("tools", ToolNode(TOOLS))       # search_web 실행 노드 (강의 #14.1)

    b.add_edge(START, "safety_guard")
    # 🚨 safety_guard / guard_answer / absorb / capture_insight 은 **엣지가 없다.**
    #    넷 다 "state를 바꾸면서 동시에 어디로 갈지도" 정하는 노드라 Command로 옮겼다 (강의 #13.9).
    #    예전엔 여기에 똑같은 `lambda s: "risk" if s.get("risk_flag") else "ok"` 가 네 번
    #    복붙돼 있었다 — 가드를 하나 더 걸 때마다 저 람다도 같이 늘어나는 구조였다.

    # 첫 입력이 '기록'인가? — "점심 뭐먹지?"(질문)에도 수업을 시작하던 문제.
    # 이 코치는 답을 대신 주지 않으니, 질문·잡담엔 정체성을 알리고 기록을 청한다.
    b.add_conditional_edges("route_record",
        lambda s: "record" if s.get("input_kind", "record") == "record" else "not_record",
        {"record": "empathy", "not_record": "redirect"})
    b.add_edge("redirect", END)
    # 입력이 애매하면("배고프다"/"피곤해") 넘겨짚지 말고 되묻는다 → 답을 합쳐서 진단 (분기①)
    # 애매하지 않으면 공감(empathy) 뒤 바로 진단으로. (filler였던 care 노드는 없앴다)
    b.add_conditional_edges("empathy",
        lambda s: "vague" if is_vague(s) else "ok",
        {"vague": "clarify", "ok": "diagnose"})
    b.add_edge("clarify", "absorb")   # 이 사이에서 되묻기 답 대기(interrupt_before) → absorb가 Command로 분기
    b.add_conditional_edges("diagnose",
        lambda s: "done" if s.get("target_concept") is None else "teach",
        {"done": "closing", "teach": "socratic_q"})  # 분기① 다 배웠나/가르칠 게 있나

    # 🚨 답변에도 위험이 온다 ("잠온다"로 시작해 답변에 "심장이 아파"). 입구만 지키면 뚫린다.
    b.add_edge("socratic_q", "guard_answer")       # 이 사이에서 유저 답 대기(interrupt_before)

    # 발화 의도 라우팅 (강의 #16) — 모든 입력을 '내 질문의 답'으로만 보면
    # "번아웃이라고 한 적 없는데" 같은 항의도 오답 처리해버린다.
    b.add_conditional_edges("route_intent",
        lambda s: s.get("intent") or "answer",
        {"answer": "evaluate",           # 답하려는 것 → 채점
         "object": "handle_object",      # 넘겨짚음 정정 → 사과하고 맥락 재수집
         "confused": "rephrase",         # 질문을 못 알아들음 → 쉽게 다시
         "stop": "closing"})             # 그만하고 싶음 → 마무리
    b.add_edge("handle_object", "absorb")     # 사과 후 다시 물음 → 답 대기(interrupt) → 재진단
    b.add_edge("rephrase", "guard_answer")    # 쉽게 다시 물음 → 답 다시 대기
    # 채점 → 맞으면 칭찬 / 틀리면 힌트. 단, **힌트를 이미 다 썼으면** 그때 정답을 공개한다.
    # ⚠️ 예전엔 hint 노드에서 소진을 판정해서, 마지막 힌트를 던지자마자 같은 턴에 정답을
    #    알려버렸다. 답할 기회를 안 준 셈. 소진 판정은 **다음 답을 받은 뒤**에 해야 한다.
    b.add_conditional_edges("evaluate",
        lambda s: ("correct" if s["verdict"] == "correct"
                   else ("reveal" if hint_exhausted(s) else "hint")),
        {"correct": "praise", "hint": "hint", "reveal": "reveal"})   # 분기② 채점
    b.add_edge("hint", "guard_answer")      # 힌트 뒤엔 **항상** 답을 기다린다
    # 못 맞혀서 정답을 알려줬어도(reveal) 끝내지 않고 **자기 몸에 적용(reflect)** 으로 잇는다.
    # 예전엔 reveal→END라 못 맞히면 발견이 하나도 안 쌓였다 — "파스타"처럼 짧은 기록으로
    # 개념을 못 맞히면 대화만 하고 카드가 안 늘어 허탈했다. 이제 배운 뒤 발견 기회를 준다.
    b.add_edge("reveal", "reflect")
    # 정답 → 칭찬 → **자기 몸에 적용해보기(reflect)** → 자기 패턴 포착(capture_insight)
    # → 그다음에야 웹검색 팁. (강의 #19 Feynman을 '자기 파악'으로 비튼 것)
    b.add_edge("praise", "reflect")
    b.add_edge("reflect", "capture_insight")   # 이 사이에서 답 대기(interrupt_before)
    b.add_conditional_edges("enrich_agent", tools_condition,
        {"tools": "tools", END: "closing"})    # tool call 있으면 tools, 없으면 closing (분기③)
    b.add_edge("tools", "enrich_agent")          # 검색 결과 들고 복귀
    b.add_edge("closing", END)

    # 사용자 답을 기다려야 하는 두 지점에서 멈춘다 → interrupt_before + checkpointer(재개용)
    #   absorb       = 되묻기에 대한 답 대기
    #   guard_answer = 소크라테스 질문에 대한 답 대기 (받자마자 위험부터 검사)
    return b.compile(checkpointer=checkpointer or MemorySaver(),
                     interrupt_before=["absorb", "guard_answer", "capture_insight"])


def build_persistent_graph(db_path="coach_memory.db"):
    """진도가 **재시작 후에도 남는** 그래프. (강의 #14.2 SQLite Checkpointer)

    MemorySaver는 인메모리라 프로그램을 끄면 learned(배운 개념)가 통째로 날아간다.
    "배운 건 다음엔 안 묻는다"가 이 코치의 핵심 기능인데, 그동안 매 실행마다 초기화됐다.
    """
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver
    conn = sqlite3.connect(db_path, check_same_thread=False)   # 스레드 제약 해제 (강의)
    return build_graph(SqliteSaver(conn))


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
