"""구조화 출력 스키마 (노트 11의 ContentPlanOutput 패턴).

Story Writer가 자유 글이 아니라 이 형태로 뱉도록 output_schema에 건다.
→ Illustrator가 state에서 pages를 page_number/visual로 정확히 읽을 수 있음.
"""
from pydantic import BaseModel, Field


class Page(BaseModel):
    page_number: int = Field(description="페이지 번호 (1부터)")
    text: str = Field(description="이 페이지에 들어갈 동화 문장 (한국어, 한두 문장)")
    visual: str = Field(
        description="이 페이지 삽화를 그리기 위한 상세 묘사 (이미지 생성용). 영어로, 등장인물·배경·분위기 포함"
    )


class StoryBook(BaseModel):
    theme: str = Field(description="동화 주제")
    art_style: str = Field(
        description="전체 삽화 화풍 한 줄(영어). 예: soft watercolor children's storybook illustration. 모든 페이지 동일 적용"
    )
    character: str = Field(
        description="주인공 외형 고정 묘사(영어): 색·종류·옷·특징. 모든 페이지 동일해야 함"
    )
    pages: list[Page] = Field(description="정확히 5페이지")
