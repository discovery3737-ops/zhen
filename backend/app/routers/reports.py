import os
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/reports", tags=["reports"])
REPORTS_BASE = os.environ.get("REPORTS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "reports"))


@router.get("/daily/download")
async def download_daily_report(dt: str = Query(..., description="YYYY-MM-DD")):
    # 简单校验日期格式
    if len(dt) != 10 or dt[4] != "-" or dt[7] != "-":
        return JSONResponse(status_code=400, content={"ok": False, "message": "Invalid date format, use YYYY-MM-DD"})
    filename = f"daily_report_{dt}.xlsx"
    filepath = os.path.join(REPORTS_BASE, "daily", filename)
    if not os.path.isfile(filepath):
        return JSONResponse(status_code=404, content={"ok": False, "message": "Report not found"})
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
