import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

app = FastAPI(title="Krini PDF Service")

logger = logging.getLogger("krinipdf")
logging.basicConfig(level=logging.INFO)

# Créé UNE SEULE FOIS au démarrage du process, pas à chaque requête.
# Sans cela, WeasyPrint rescanne toutes les polices système (fontconfig)
# à CHAQUE conversion, une opération coûteuse indépendante du HTML.
FONT_CONFIG = FontConfiguration()


class PDFRequest(BaseModel):
    html: str


class PDFRequestWithOptions(BaseModel):
    html: str


def render_pdf(html_string: str) -> bytes:
    """Convertit le HTML en PDF via WeasyPrint.
    Fonction synchrone exécutée dans le thread pool de FastAPI
    (pas dans l'event loop) pour ne pas bloquer les autres requêtes."""
    html_doc = HTML(string=html_string)
    return html_doc.write_pdf(font_config=FONT_CONFIG)


# Endpoint **synchronisé** (def, pas async def) :
# FastAPI l'exécute dans un worker thread, libérant l'event loop.
# Avec uvicorn --workers 1, les conversions concurrentes ne se bloquent plus.
@app.post("/convert")
def convert(request: PDFRequest):
    start = time.perf_counter()
    try:
        pdf_bytes = render_pdf(request.html)
        logger.info(
            "pdf_converted",
            extra={
                "html_bytes": len(request.html.encode("utf-8")),
                "pdf_bytes": len(pdf_bytes),
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return Response(content=pdf_bytes, media_type="application/pdf")
    except Exception as e:
        logger.exception("pdf_conversion_failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}