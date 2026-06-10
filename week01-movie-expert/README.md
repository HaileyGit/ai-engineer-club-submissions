# Movie Expert Agent

AI Agents 마스터클래스 챌린지 — OpenAI API + 실제 영화 API로 만든 첫 에이전트 (프레임워크 없음, #2.2 방식).

## 무엇

프롬프트로 모델에게 함수 3개를 설명하고, 모델이 `{"function", "arguments"}` JSON으로 호출 의도를 출력 → 우리 코드가 실제 영화 API를 호출 → 결과를 다시 모델에 넣어 자연어로 답한다.

| 함수 | 엔드포인트 |
|------|-----------|
| `get_popular_movies()` | `GET /movies` |
| `get_movie_details(movie_id)` | `GET /movies/:id` |
| `get_movie_credits(movie_id)` | `GET /movies/:id/credits` |

API base: `https://nomad-movies.nomadcoders.workers.dev` · 모델: `gpt-4o-mini`

## 실행

```bash
uv sync
cp .env.example .env   # .env 에 실제 OPENAI_API_KEY 입력
```

그 다음 `main.ipynb`를 열고 **Run All**. 모든 셀 출력이 찍힌 상태로 커밋해 제출.
