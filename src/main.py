import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles 
from devices.devices import Device 
from sdwan.client import ManagerClient, ManagerError
from sdwan.collector import analyze, collect
from sdwan.render import render_html


load_dotenv()

device = {
    "device_type": os.getenv("DEVICE_TYPE", "cisco_ios"),
    "host": os.getenv("DEVICE_HOST", "10.255.0.2"),
    "username": os.getenv("DEVICE_USERNAME", "cisco"),
    "password": os.getenv("DEVICE_PASSWORD", "cisco"),
}
if os.getenv("DEVICE_SECRET"):
    device["secret"] = os.environ["DEVICE_SECRET"]

app = FastAPI()
app.mount("/static", StaticFiles(directory="templates/style"), name="static")
templates = Jinja2Templates(directory="templates")

device_manager = Device()

@app.get("/")
async def main():
    return {"MSN": "API no AR"}

@app.get("/show-commands", response_class=HTMLResponse)
async def run_commands(request: Request):
    comandos_para_rodar = ["sh clock", "sh ip int br"]
    output_data = device_manager.send_show_command(device, comandos_para_rodar)

    context = {
        "request": request,
        "titulo": "Status dos Roteadores",
        "resultados": output_data
    }

    return templates.TemplateResponse(request=request, name="index.html", context=context)


@app.get("/sdwan/report", response_class=HTMLResponse)
def sdwan_report():
    """Relatório Day 2 do Catalyst SD-WAN (somente leitura)."""
    client = ManagerClient(
        host=os.getenv("VMANAGE_HOST", "199.1.1.2"),
        port=int(os.getenv("VMANAGE_PORT", "443")),
        username=os.getenv("VMANAGE_USERNAME", "admin"),
        password=os.getenv("VMANAGE_PASSWORD", "admin"),
        verify_ssl=os.getenv("VMANAGE_VERIFY_SSL", "false").lower() == "true",
    )
    try:
        with client:
            report = analyze(collect(client))
    except ManagerError as error:
        return HTMLResponse(f"<h1>Erro ao consultar o Manager</h1><p>{error}</p>", status_code=502)
    return HTMLResponse(render_html(report))


@app.get("/show-comands", include_in_schema=False)
async def legacy_route():
    # Mantém links antigos funcionando
    return RedirectResponse(url="/show-commands")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
