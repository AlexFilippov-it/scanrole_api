from typing import Dict, List, Optional, Tuple

from db import get_connection


US_STATE_MAP = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}


def _country_aliases(country: str) -> List[str]:
    if country == "United States":
        return ["United States", "US", "USA"]
    if country == "United Kingdom":
        return ["United Kingdom", "UK", "GB"]
    if country == "Canada":
        return ["Canada", "CA"]
    if country == "Germany":
        return ["Germany", "DE"]
    if country == "Netherlands":
        return ["Netherlands", "NL", "NE"]
    return [country]


def _append_location_filter(sql: str, params: List, country: Optional[str], state: Optional[str]) -> str:
    country_aliases = _country_aliases(country) if country else []
    if state:
        sql += " AND (location LIKE %s OR location LIKE %s)"
        params.append(f"%, {state}")
        params.append(f"%, {state}, %")
        if country_aliases:
            conditions = []
            for alias in country_aliases:
                conditions.append("location LIKE %s")
                params.append(f"%, {alias}")
            if conditions:
                sql += " AND (" + " OR ".join(conditions) + ")"
        return sql
    if country:
        if country == "United States":
            conditions = []
            for code in US_STATE_MAP.keys():
                conditions.append("location LIKE %s")
                params.append(f"%, {code}")
            if conditions:
                sql += " AND (" + " OR ".join(conditions) + ")"
        else:
            conditions = []
            for alias in country_aliases:
                conditions.append("location LIKE %s")
                params.append(f"%, {alias}")
            if conditions:
                sql += " AND (" + " OR ".join(conditions) + ")"
            if country == "Canada":
                sql += " AND location NOT LIKE %s AND location NOT LIKE %s"
                params.append("%, CA")
                params.append("%, CA, %")
    return sql


def get_roles(table_name: str) -> List[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT normalized_role FROM {table_name} "
                "WHERE normalized_role IS NOT NULL AND normalized_role <> ''"
            )
            rows = [row["normalized_role"] for row in cur.fetchall()]
    roles = list(dict.fromkeys(rows))
    roles.sort(key=lambda r: (r == "Other", r))
    return roles


def _parse_location_parts(location: str) -> Dict[str, Optional[str]]:
    parts = [p.strip() for p in location.split(",")]
    if len(parts) < 2:
        return {"city": None, "state": None, "country": None}
    city = parts[0]
    state = None
    country = None
    if len(parts) >= 3:
        last = parts[-1].upper()
        prev = parts[-2].upper()
        canada_provinces = {"AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"}
        if last == "CA" and prev in canada_provinces:
            state = parts[-2]
            country = "Canada"
        elif last in US_STATE_MAP:
            state = parts[-1]
            country = "United States"
        else:
            state = parts[-2]
            country = _normalize_country_token(parts[-1])
    else:
        state = parts[-1]
        country = _infer_country_from_state(state)
        if country not in ("United States", None):
            state = None
    return {"city": city, "state": state, "country": country}


def _normalize_country_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    upper = token.upper()
    if upper in {"US", "USA", "UNITED STATES"}:
        return "United States"
    if upper in {"UK", "GB", "UNITED KINGDOM"}:
        return "United Kingdom"
    if upper in {"CA", "CANADA"}:
        return "Canada"
    if upper in {"DE", "GERMANY"}:
        return "Germany"
    if upper in {"NL", "NE", "NETHERLANDS"}:
        return "Netherlands"
    if len(upper) == 2:
        return None
    return token


def _infer_country_from_state(state: Optional[str]) -> Optional[str]:
    if not state:
        return None
    upper = state.upper()
    if upper in US_STATE_MAP or upper == "DC":
        return "United States"
    if upper in {"UK", "GB", "UNITED KINGDOM"}:
        return "United Kingdom"
    if upper == "CANADA":
        return "Canada"
    if upper == "GERMANY":
        return "Germany"
    if upper == "NETHERLANDS":
        return "Netherlands"
    return None


def get_countries(table_name: str) -> List[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT location FROM {table_name} "
                "WHERE location IS NOT NULL AND location <> ''"
            )
            locations = [row["location"] for row in cur.fetchall()]

    countries = {}
    for location in locations:
        parts = _parse_location_parts(location)
        if parts["country"]:
            countries[parts["country"]] = True
        elif parts["state"] and parts["state"].upper() in US_STATE_MAP:
            countries["United States"] = True

    allowed = ["United States", "Canada", "United Kingdom"]
    filtered = [c for c in allowed if c in countries]
    filtered.sort()
    return filtered


def get_states_by_country(table_name: str, country: str) -> List[str]:
    if not country:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT DISTINCT location FROM {table_name} "
                "WHERE location IS NOT NULL AND location <> ''"
            )
            locations = [row["location"] for row in cur.fetchall()]

    states: Dict[str, bool] = {}
    for location in locations:
        parts = _parse_location_parts(location)
        country_token = parts["country"]
        if country == "United States" and not country_token and parts["state"]:
            if parts["state"].upper() in US_STATE_MAP:
                states[parts["state"]] = True
        elif country_token == country and parts["state"]:
            states[parts["state"]] = True

    state_list = list(states.keys())
    state_list.sort()
    return state_list


def get_role_end_dates(
    table_name: str,
    country: Optional[str],
    state: Optional[str],
    role: Optional[str],
) -> Dict[str, str]:
    sql = (
        f"SELECT normalized_role, MAX(date_posted) AS end_date "
        f"FROM {table_name} WHERE date_posted IS NOT NULL"
    )
    params: List = []
    sql = _append_location_filter(sql, params, country, state)
    if role:
        sql += " AND normalized_role = %s"
        params.append(role)
    sql += " GROUP BY normalized_role"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return {row["normalized_role"]: row["end_date"] for row in rows if row["normalized_role"]}


def get_metrics(
    table_name: str,
    role: str,
    start_date: str,
    end_date: str,
    country: Optional[str],
    state: Optional[str],
) -> Dict:
    sql = (
        "SELECT COUNT(*) AS jobs_count,"
        " AVG(CASE WHEN min_amount IS NOT NULL AND max_amount IS NOT NULL THEN (min_amount + max_amount) / 2 "
        " WHEN min_amount IS NOT NULL THEN min_amount "
        " WHEN max_amount IS NOT NULL THEN max_amount "
        " ELSE NULL END) AS avg_salary,"
        " AVG(CASE WHEN is_remote IS NULL THEN NULL ELSE is_remote END) AS remote_share,"
        " AVG(role_confidence) AS avg_confidence,"
        " SUM(CASE WHEN seniority = 'Junior' THEN 1 ELSE 0 END) AS junior_count,"
        " SUM(CASE WHEN seniority = 'Mid' THEN 1 ELSE 0 END) AS mid_count,"
        " SUM(CASE WHEN seniority = 'Senior' THEN 1 ELSE 0 END) AS senior_count,"
        " SUM(CASE WHEN seniority = 'Staff' THEN 1 ELSE 0 END) AS staff_count,"
        " SUM(CASE WHEN seniority = 'Principal' THEN 1 ELSE 0 END) AS principal_count"
        f" FROM {table_name} WHERE normalized_role = %s AND date_posted BETWEEN %s AND %s"
    )
    params: List = [role, start_date, end_date]
    sql = _append_location_filter(sql, params, country, state)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone() or {}
    return row


def get_last_update(table_name: str, country: Optional[str], state: Optional[str]) -> Optional[str]:
    sql = f"SELECT MAX(date_posted) AS last_update FROM {table_name} WHERE date_posted IS NOT NULL"
    params: List = []
    sql = _append_location_filter(sql, params, country, state)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return row["last_update"] if row else None


def compute_delta(current: float, previous: float) -> Tuple[float, Optional[float], str]:
    delta_abs = current - previous
    if previous > 0:
        delta_pct = (delta_abs / previous) * 100
    elif previous == 0 and current == 0:
        delta_pct = 0
    else:
        delta_pct = None

    if delta_abs > 0:
        trend = "up"
    elif delta_abs < 0:
        trend = "down"
    else:
        trend = "flat"
    return delta_abs, delta_pct, trend
