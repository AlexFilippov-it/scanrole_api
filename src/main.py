from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from auth import require_role_explorer
from config import get_settings
from queries import (
    compute_delta,
    get_countries,
    get_last_update,
    get_metrics,
    get_role_end_dates,
    get_roles,
    get_states_by_country,
)

settings = get_settings()
app = FastAPI(title="ScanRole API", version="1.0.0")

allowed_origins = [settings.api_base_url] if settings.api_base_url else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "ERROR", "message": str(exc.detail)}},
    )


def _error_response(code: str, message: str, status_code: int):
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/meta/periods")
async def meta_periods():
    return {"items": [7, 30, 90]}


@app.get("/api/v1/meta/countries")
async def meta_countries(_auth=Depends(require_role_explorer)):
    table_name = settings.role_table
    return {"items": get_countries(table_name)}


@app.get("/api/v1/meta/states")
async def meta_states(country: str = Query(..., min_length=2), _auth=Depends(require_role_explorer)):
    table_name = settings.role_table
    return {"items": get_states_by_country(table_name, country)}


@app.get("/api/v1/meta/roles")
async def meta_roles(_auth=Depends(require_role_explorer)):
    table_name = settings.role_table
    return {"items": get_roles(table_name)}


@app.get("/api/v1/role-explorer")
async def role_explorer(
    period_days: int = Query(30, ge=7, le=90),
    country: Optional[str] = None,
    state: Optional[str] = None,
    role: Optional[str] = None,
    sort: str = Query("jobs_count_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _auth=Depends(require_role_explorer),
):
    if period_days not in (7, 30, 90):
        return _error_response("VALIDATION_ERROR", "Invalid period_days", 400)

    table_name = settings.role_table
    country = country or None
    state = state or None
    role = role or None

    role_end_dates = get_role_end_dates(table_name, country, state, role)
    if not role_end_dates:
        return {
            "as_of_date": None,
            "total": 0,
            "items": [],
        }

    rows = []
    for role_name, end_date in role_end_dates.items():
        if not end_date:
            continue
        if isinstance(end_date, datetime):
            end_day = end_date.date()
        elif isinstance(end_date, date):
            end_day = end_date
        else:
            end_day = datetime.strptime(str(end_date), "%Y-%m-%d").date()

        start = (end_day - timedelta(days=period_days - 1)).strftime("%Y-%m-%d")
        end_str = end_day.strftime("%Y-%m-%d")
        prev_end = (end_day - timedelta(days=period_days)).strftime("%Y-%m-%d")
        prev_start = (end_day - timedelta(days=period_days * 2 - 1)).strftime("%Y-%m-%d")

        current = get_metrics(table_name, role_name, start, end_str, country, state)
        previous = get_metrics(table_name, role_name, prev_start, prev_end, country, state)

        jobs_current = int(current.get("jobs_count") or 0)
        jobs_prev = int(previous.get("jobs_count") or 0)
        jobs_delta_abs, jobs_delta_pct, jobs_trend = compute_delta(jobs_current, jobs_prev)

        salary_current = float(current["avg_salary"]) if current.get("avg_salary") is not None else None
        salary_prev = float(previous["avg_salary"]) if previous.get("avg_salary") is not None else None
        salary_delta_abs, salary_delta_pct, salary_trend = compute_delta(salary_current or 0, salary_prev or 0)

        remote_current = (float(current["remote_share"]) * 100) if current.get("remote_share") is not None else None
        remote_prev = (float(previous["remote_share"]) * 100) if previous.get("remote_share") is not None else None
        remote_delta_abs, remote_delta_pct, remote_trend = compute_delta(remote_current or 0, remote_prev or 0)

        confidence_current = float(current["avg_confidence"]) if current.get("avg_confidence") is not None else None
        seniority_counts = {
            "Junior": int(current.get("junior_count") or 0),
            "Mid": int(current.get("mid_count") or 0),
            "Senior": int(current.get("senior_count") or 0),
            "Staff": int(current.get("staff_count") or 0),
            "Principal": int(current.get("principal_count") or 0),
        }

        rows.append(
            {
                "role": role_name,
                "country": country,
                "state": state,
                "jobs_current": jobs_current,
                "jobs_prev": jobs_prev,
                "jobs_delta_pct": jobs_delta_pct,
                "jobs_trend": jobs_trend,
                "salary_current": salary_current,
                "salary_prev": salary_prev,
                "salary_delta_pct": salary_delta_pct,
                "salary_trend": salary_trend,
                "remote_current": remote_current,
                "remote_prev": remote_prev,
                "remote_delta_pp": remote_delta_abs,
                "remote_trend": remote_trend,
                "confidence_current": confidence_current,
                "seniority_counts": seniority_counts,
            }
        )

    if role != "Other":
        rows = [row for row in rows if row["role"] != "Other"]

    sort_map = {
        "jobs_count_desc": ("jobs_current", True),
        "avg_salary_desc": ("salary_current", True),
        "remote_pct_desc": ("remote_current", True),
        "salary_delta_pct_desc": ("salary_delta_pct", True),
        "role_asc": ("role", False),
    }
    sort_key, reverse = sort_map.get(sort, ("jobs_current", True))
    rows.sort(key=lambda r: (r.get(sort_key) is None, r.get(sort_key)), reverse=reverse)

    total = len(rows)
    offset = (page - 1) * page_size
    items = rows[offset : offset + page_size]

    last_update = get_last_update(table_name, country, state)

    return {
        "as_of_date": last_update,
        "total": total,
        "items": items,
    }
