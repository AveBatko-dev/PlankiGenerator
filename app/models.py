from pydantic import BaseModel, Field


class GenerateDrawingRequest(BaseModel):
    template_code: str = Field(..., examples=["pl_5"])
    parameters: dict[str, float] = Field(...)


class GenerateDrawingResponse(BaseModel):
    template_code: str
    dxf_path: str
    dwg_path: str | None
    png_original_path: str
    png_100x200_path: str
    success: bool
    message: str
