"""식단 도메인에서 가르칠 개념 (그래프설계.md §5). criteria.txt 근거.

순수 데이터 — LLM/LangGraph 무관. diagnose 노드가 여기서 target_concept를 고르고,
socratic_q/hint/evaluate 노드가 이 내용을 쓴다.
"""

CONCEPTS = {
    "protein_balance": {
        "title": "탄수에 단백질 곁들이기",
        "criteria": "단백질은 하루 체중 1kg당 약 1.2~1.6g (criteria.txt)",
        "socratic_q": "이 끼니에 뭐가 좀 빠진 것 같아요?",
        "hints": [
            "영양소 종류를 떠올려봐요. 탄수 말고요.",
            "단백질 쪽은 어때요? (계란·두부·고기 같은)",
        ],
        "answer_keywords": ["단백질", "protein", "계란", "두부", "고기", "닭", "생선"],
        "praise": "정확해요! 계란 하나만 얹어도 균형이 살아요.",
    },
    "veggie_fiber": {
        "title": "채소·식이섬유 챙기기",
        "criteria": "배달·외식·야식엔 채소가 부족하기 쉽다 (criteria.txt)",
        "socratic_q": "색깔로 보면 빠진 게 있지 않아요?",
        "hints": [
            "접시에 초록색이 보이나요?",
            "채소·식이섬유 쪽이에요. (나물·샐러드·김치)",
        ],
        "answer_keywords": ["채소", "야채", "식이섬유", "나물", "샐러드", "김치", "녹색"],
        "praise": "맞아요! 나물 한 가지만 곁들여도 든든해져요.",
    },
    "hydration": {
        "title": "수분 챙기기",
        "criteria": "짠 음식·음주는 수분을 뺏고 수면의 질을 떨어뜨린다 (criteria.txt)",
        "socratic_q": "음식 말고 같이 챙기면 좋은 게 있을까요?",
        "hints": [
            "짠 걸 먹었다면 더 필요한 거예요.",
            "물이에요. 한 컵 곁들이면 좋아요.",
        ],
        "answer_keywords": ["물", "수분", "water", "음료", "차"],
        "praise": "그렇죠! 물 한 컵이면 충분해요.",
    },
}

# diagnose가 아직 안 배운 개념을 이 순서로 고른다
CONCEPT_ORDER = ["protein_balance", "veggie_fiber", "hydration"]
