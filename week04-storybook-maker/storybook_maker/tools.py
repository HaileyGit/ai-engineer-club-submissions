"""삽화 생성 도구 (노트 11의 generate_images 패턴 그대로).

state["story_writer_output"]의 pages를 읽어 페이지별 이미지를 생성하고
각각 artifact(page_N_image.jpeg)로 저장한다.
"""
import base64

from openai import OpenAI
from google.adk.tools import ToolContext
from google.genai import types


async def generate_illustrations(tool_context: ToolContext):
    # 1) Story Writer가 state에 남긴 동화 데이터 읽기 (= 두 에이전트의 State 공유 지점)
    story = tool_context.state.get("story_writer_output")
    if not story:
        return {"status": "error", "reason": "story_writer_output 이 state에 없음"}
    pages = story.get("pages", [])
    art_style = story.get("art_style", "children's storybook illustration")
    character = story.get("character", "")

    # 2) 이미 만든 artifact는 건너뛰기 (agent가 도구를 중복 호출해 돈 새는 것 방지)
    existing = await tool_context.list_artifacts()
    client = OpenAI()
    made = []

    for page in pages:
        n = page.get("page_number")
        visual = page.get("visual")
        file_name = f"page_{n}_image.jpeg"
        if file_name in existing:
            continue

        # 화풍 + 주인공을 매 페이지에 강제 주입 → 페이지 간 일관성 (실사·캐릭터 변경 방지)
        prompt = (
            f"{art_style}. Main character, always identical: {character}. "
            f"Scene: {visual}. Keep the exact same art style and character design as every page."
        )
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            n=1,
            moderation="low",
            output_format="jpeg",
            background="opaque",
            size="1024x1024",
            quality="low",  # 비용·속도 절감 (high로 올리면 선명·비쌈)
        )
        image_bytes = base64.b64decode(resp.data[0].b64_json)

        # 3) bytes → Part → artifact 저장
        artifact = types.Part.from_bytes(mime_type="image/jpeg", data=image_bytes)
        await tool_context.save_artifact(file_name, artifact)

        made.append({"page": n, "filename": file_name})

    return {"status": "complete", "total_images": len(made), "images": made}
