from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import VERSION
from .database import engine, Base, get_db
from .models import AppJobRun
<<<<<<< HEAD
from .routers import health, runs, reports
=======
from .routers import health, runs, reports, auth, config_api, jobs
>>>>>>> edfd4a2 (M2: config in DB + web-configurable settings)


app = FastAPI(title="Crawler API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(runs.router)
app.include_router(reports.router)
<<<<<<< HEAD
=======
app.include_router(auth.router)
app.include_router(config_api.router)
app.include_router(jobs.router)
>>>>>>> edfd4a2 (M2: config in DB + web-configurable settings)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message", str(detail))
        extra = {k: v for k, v in detail.items() if k != "message"}
    else:
        message = str(detail)
        extra = {"detail": detail} if detail else None
    body: dict = {"ok": False, "message": message}
    if extra:
        body["detail"] = extra
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=exc.status_code, content=body)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
