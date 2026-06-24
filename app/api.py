from fastapi import FastAPI, HTTPException

from app.dwg_converter import convert_dxf_to_dwg
from app.dxf_generator import generate_dxf
from app.file_storage import create_output_paths
from app.models import GenerateDrawingRequest, GenerateDrawingResponse
from app.png_generator import generate_pngs
from app.templates import load_template


app = FastAPI(title="Planki Generator")


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/generate", response_model=GenerateDrawingResponse)
def generate_drawing(request: GenerateDrawingRequest):
    try:
        template = load_template(request.template_code)
        dxf_path, dwg_path, png_original_path, png_100x200_path = create_output_paths(
            request.template_code
        )

        document = generate_dxf(
            template=template,
            output_path=dxf_path,
            parameters=request.parameters,
        )
        generate_pngs(
            document=document,
            original_path=png_original_path,
            thumbnail_path=png_100x200_path,
        )

        dwg_created = convert_dxf_to_dwg(
            dxf_path=dxf_path,
            dwg_path=dwg_path,
        )

        return GenerateDrawingResponse(
            template_code=request.template_code,
            dxf_path=str(dxf_path) if dxf_path else None,
            dwg_path=str(dwg_path) if dwg_created else None,
            png_original_path=str(png_original_path),
            png_100x200_path=str(png_100x200_path),
            success=True,
            message="DXF and PNG files created. DWG created."
            if dwg_created
            else "DXF and PNG files created. DWG converter not available.",
        )

    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
