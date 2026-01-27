from datetime import date, datetime, timedelta
from typing import Optional, Tuple

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

COUNTRY_ISO_MAP = {
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
}

SORT_WHITELIST = {
    "jobs_current",
    "jobs_delta_pct",
    "salary_current",
    "salary_delta_pct",
    "remote_current",
    "remote_delta_pp",
    "role",
    "country",
    "state",
}

DEFAULT_SORT_BY = "jobs_current"
DEFAULT_SORT_DIR = "desc"
PAGE_SIZE_ALLOWED = {10, 25, 50, 100}

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

def _normalize_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    upper = value.strip().upper()
    if upper in COUNTRY_ISO_MAP:
        return upper if len(upper) == 2 else "GB"
    if upper == "UNITED STATES":
        return "US"
    if upper == "CANADA":
        return "CA"
    if upper == "UNITED KINGDOM":
        return "GB"
    return upper if len(upper) == 2 else value


def _country_to_iso(country: str) -> Optional[str]:
    if not country:
        return None
    for iso, name in COUNTRY_ISO_MAP.items():
        if name == country and len(iso) == 2 and iso != "UK":
            return iso
    return None


def _iso_to_country(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    return COUNTRY_ISO_MAP.get(iso, None)


def _normalize_sort(
    sort_by: Optional[str],
    sort_dir: Optional[str],
    legacy_sort: Optional[str],
) -> Tuple[str, str]:
    if not sort_by and legacy_sort:
        legacy_map = {
            "jobs_count_desc": ("jobs_current", "desc"),
            "avg_salary_desc": ("salary_current", "desc"),
            "remote_pct_desc": ("remote_current", "desc"),
            "salary_delta_pct_desc": ("salary_delta_pct", "desc"),
            "role_asc": ("role", "asc"),
        }
        mapped = legacy_map.get(legacy_sort)
        if mapped:
            sort_by, sort_dir = mapped
    sort_by = sort_by or DEFAULT_SORT_BY
    sort_by = sort_by if sort_by in SORT_WHITELIST else DEFAULT_SORT_BY
    sort_dir = (sort_dir or DEFAULT_SORT_DIR).lower()
    sort_dir = sort_dir if sort_dir in ("asc", "desc") else DEFAULT_SORT_DIR
    return sort_by, sort_dir

@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/meta/periods")
async def meta_periods():
    return {"items": [7, 30, 90]}


@app.get("/api/v1/meta/countries")
async def meta_countries(_auth=Depends(require_role_explorer)):
    table_name = settings.role_table
    countries = get_countries(table_name)
    iso_items = []
    for country in countries:
        iso = _country_to_iso(country)
        if iso:
            iso_items.append(iso)
    return {"items": iso_items}


@app.get("/api/v1/meta/states")
async def meta_states(country: str = Query(..., min_length=2), _auth=Depends(require_role_explorer)):
    table_name = settings.role_table
    normalized = _normalize_country(country)
    country_name = _iso_to_country(normalized) if normalized else None
    return {"items": get_states_by_country(table_name, country_name)}


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
    sort_by: Optional[str] = Query(None),
    sort_dir: Optional[str] = Query(None),
    sort: Optional[str] = Query(None),
    debug: Optional[bool] = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _auth=Depends(require_role_explorer),
):
    if period_days not in (7, 30, 90):
        return _error_response("VALIDATION_ERROR", "Invalid period_days", 400)

    table_name = settings.role_table
    country_iso = _normalize_country(country) if country else None
    country_name = _iso_to_country(country_iso) if country_iso else None
    state = state or None
    role = role or None
    if page_size not in PAGE_SIZE_ALLOWED:
        page_size = 25

    sort_by, sort_dir = _normalize_sort(sort_by, sort_dir, sort)

    role_end_dates = get_role_end_dates(table_name, country_name, state, role)
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

        current = get_metrics(table_name, role_name, start, end_str, country_name, state)
        previous = get_metrics(table_name, role_name, prev_start, prev_end, country_name, state)

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
                "country": country_name,
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

    rows.sort(key=lambda r: (r.get("role") or "", r.get("country") or "", r.get("state") or ""))

    def primary_key(row):
        value = row.get(sort_by)
        if value is None:
            return (1, None)
        return (0, value)

    rows.sort(key=primary_key, reverse=sort_dir == "desc")

    total = len(rows)
    offset = (page - 1) * page_size
    items = rows[offset : offset + page_size]

    last_update = get_last_update(table_name, country_name, state)

    response = {
        "as_of_date": last_update,
        "total": total,
        "items": items,
        "applied_sort_by": sort_by,
        "applied_sort_dir": sort_dir,
    }

    if debug:
        response["debug_sort_key"] = f"{sort_by}:{sort_dir}"

    return response
