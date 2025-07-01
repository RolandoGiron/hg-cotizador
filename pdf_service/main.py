
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import io

app = FastAPI()

# Montar el directorio 'static' para servir archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

env = Environment(loader=FileSystemLoader('.'))
template = env.get_template("quote_template.html")

@app.post("/api/v1/generate-pdf")
async def generate_pdf(request: Request):
    data = await request.json()
    # Pasar la URL base para poder encontrar los archivos estáticos
    base_url = str(request.base_url)
    html_out = template.render(data, base_url=base_url)
    pdf_file = HTML(string=html_out, base_url=base_url).write_pdf()
    
    return StreamingResponse(io.BytesIO(pdf_file), media_type="application/pdf")
