"""한 번만 실행하는 셋업 스크립트.

목표 문서(goals.txt)를 OpenAI Vector Store 에 업로드하고,
그 Vector Store ID 를 .env 에 저장한다.

실행:  uv run python setup_vector_store.py
"""

from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # OPENAI_API_KEY
client = OpenAI()

GOALS = Path("goals.txt")
ENV = Path(".env")

# 1) Vector Store 생성 (= RAG 의 "의미 기반 장기 기억 저장소")
vs = client.vector_stores.create(name="life-coach-goals")
print("Vector Store 생성됨:", vs.id)

# 2) 목표 문서 업로드 + 임베딩 인덱싱 완료까지 대기
#    (업로드 → 청크 분할 → 임베딩 → 저장. 시험에서 본 랭체인 5요소가 이 한 줄에서 일어남)
with GOALS.open("rb") as f:
    client.vector_stores.files.upload_and_poll(
        vector_store_id=vs.id,
        file=(GOALS.name, f.read()),
    )
print(f"'{GOALS.name}' 업로드·인덱싱 완료")

# 3) .env 에 ID 저장 (기존 줄 있으면 교체)
lines = ENV.read_text().splitlines() if ENV.exists() else []
lines = [ln for ln in lines if not ln.startswith("OPENAI_VECTOR_STORE_ID=")]
lines.append(f"OPENAI_VECTOR_STORE_ID={vs.id}")
ENV.write_text("\n".join(lines) + "\n")

print("✅ .env 에 OPENAI_VECTOR_STORE_ID 저장 완료.")
print("   이제  uv run streamlit run app.py  로 앱을 실행하세요.")
