"""운동기구·앱 화면 사진을 읽어 오늘 기록으로 바꾼다.

사용자가 실제로 하던 방식이 이거였다 — 러닝머신·자전거 화면을 찍어서 AI한테 읽히고 기록.
손으로 "17분 탔고 심박 89였어" 타이핑할 필요 없이 **사진 한 장이면 today_input이 된다.**

gpt-4o-mini는 이미지 입력을 지원한다. structured output으로 수치를 뽑고,
코치가 읽을 수 있는 자연어 한 문장으로 만들어 그래프에 넣는다.
"""
import base64

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from llm import get_llm_precise


class WorkoutRecord(BaseModel):
    """운동기구 화면에서 읽어낸 값. 화면에 없는 항목은 None."""
    is_workout_screen: bool = Field(description="운동기구·운동앱 화면이면 true")
    machine: str = Field("", description="기구 종류 (예: '실내 자전거', '러닝머신'). 모르면 빈 문자열")
    duration: str | None = Field(None, description="운동 시간 (예: '17분 24초')")
    calories: int | None = Field(None, description="소모 칼로리 (kcal)")
    heart_rate: int | None = Field(None, description="평균 심박수 (bpm)")
    distance: float | None = Field(None, description="이동 거리 (km)")
    speed: float | None = Field(None, description="평균 속도 (km/h)")
    watt: int | None = Field(None, description="평균 와트")
    rpm: int | None = Field(None, description="평균 rpm")

    def as_record(self) -> str:
        """코치에게 넘길 오늘 기록 문장을 **코드가 조립한다.**

        LLM에 요약을 맡겼더니 심박·칼로리를 빼먹고 문어체로 뱉었다.
        수치를 읽는 건 LLM만 할 수 있지만, **문장 조립은 코드가 할 수 있다.**
        (라벨을 LLM에 맡겼다가 템플릿을 그대로 베끼던 것과 같은 실수)
        """
        machine = (self.machine or "").strip()
        if machine.lower() in ("none", "null", "unknown"):   # LLM이 문자열 "None"을 넣기도 한다
            machine = ""
        parts = []
        if self.duration:
            parts.append(f"{self.duration} 탔고" if machine else f"{self.duration} 운동했고")
        if self.distance:
            parts.append(f"{self.distance}km")
        if self.speed:
            parts.append(f"평균 시속 {self.speed}km")
        if self.heart_rate:
            parts.append(f"평균 심박 {self.heart_rate}")
        if self.calories:
            parts.append(f"{self.calories}kcal 소모")
        if self.watt:
            parts.append(f"평균 {self.watt}W")
        head = f"{machine} " if machine else "오늘 운동 — "
        return (head + ", ".join(parts)).strip()


PROMPT = (
    "이 사진은 운동기구(러닝머신·실내자전거 등)나 운동 앱의 화면일 수 있어.\n"
    "화면에 보이는 **수치를 그대로** 읽어라.\n"
    "⚠️ 추측하거나 지어내지 마. 화면에 안 보이는 항목은 None이다.\n"
    "⚠️ 운동 화면이 아니면 is_workout_screen=false."
)


def read_workout_image(image_bytes: bytes, mime: str = "image/jpeg"):
    """사진 → WorkoutRecord. 운동 화면이 아니거나 못 읽으면 None."""
    llm = get_llm_precise()          # 수치 추출은 판정이라 temperature=0
    if llm is None:
        return None
    b64 = base64.b64encode(image_bytes).decode()
    msg = HumanMessage(content=[
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ])
    try:
        rec = llm.with_structured_output(WorkoutRecord).invoke([msg])
    except Exception:
        return None
    return rec if rec and rec.is_workout_screen else None
