"""웹검색 Tool. (강의 #14.1 Tool Nodes)

@tool 로 정의 → llm.py가 bind_tools → graph.py의 ToolNode가 실행 → tools_condition이 분기.
검색엔진은 DuckDuckGo (무료·API키 불필요).
"""
from concurrent.futures import ThreadPoolExecutor
from langchain_core.tools import tool


@tool
def search_web(query: str) -> str:
    """건강·식습관 개념을 일상에서 실천하는 실제 방법·팁을 웹에서 검색한다."""
    # ⚠️ DuckDuckGo 무료 검색은 반복 호출하면 rate limit에 걸려 **응답이 안 온다**.
    #    try/except만으로는 예외도 안 나고 무한 대기(hang) — 두 번째 대화가 여기서 멈췄다.
    #    → 스레드에 timeout을 걸어, 6초 안에 안 오면 검색을 포기하고 넘어간다.
    #    (검색 실패 시 enrich 노드는 '더 알아보기' 팁을 조용히 건너뛴다)
    def _search():
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().invoke(query)[:1500]

    # ⚠️ `with ThreadPoolExecutor`를 쓰면 블록 끝에서 hang된 스레드를 기다려(shutdown wait=True)
    #    timeout 6초가 12초가 됐다. → shutdown(wait=False)로 매달린 스레드를 버리고 즉시 나온다.
    ex = ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(_search).result(timeout=6)
    except Exception:
        return "(검색 결과 없음)"
    finally:
        ex.shutdown(wait=False)


TOOLS = [search_web]
