import os
import re
import pandas as pd
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from libsql_client import create_client
    logger.info("libsql_client imported successfully")
except Exception as e:  # pragma: no cover
    logger.error(f"Failed to import libsql_client: {e}")
    create_client = None

# Global event loop for client operations
_event_loop = None

def _get_or_create_event_loop():
    """Get existing event loop or create a new one."""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
    return _event_loop


async def _create_turso_client_async():
    """Internal async function to create Turso client."""
    logger.info("[DB] Initializing Turso client")
    try:
        import streamlit as st
        from core.secrets import get_secret
        db_url = get_secret("TURSO_DB_URL")
        db_token = get_secret("TURSO_DB_AUTH_TOKEN")
    except Exception:
        # Fallback to os.getenv if Streamlit not available
        import os
        db_url = os.getenv("TURSO_DB_URL")
        db_token = os.getenv("TURSO_DB_AUTH_TOKEN")

    if not db_url:
        logger.error("[DB] TURSO_DB_URL not found in environment")
    if not db_token:
        logger.error("[DB] TURSO_DB_AUTH_TOKEN not found in environment")
    if create_client is None:
        logger.error("[DB] libsql_client not available (create_client is None)")

    if not db_url or not db_token or create_client is None:
        logger.warning("[DB] Cannot create Turso client - missing credentials or library")
        return None

    # Log transport hint
    transport = "wss" if db_url.startswith("libsql://") else ("https" if db_url.startswith("https://") else "unknown")
    logger.info(f"[DB] Creating client for url={db_url} (transport={transport})")

    try:
        client = create_client(db_url, auth_token=db_token)
        logger.info("[DB] Turso client created successfully")
        return client
    except Exception as e:
        logger.error(f"[DB] Error creating Turso client: {e}", exc_info=True)
        return None


def get_turso_client():
    """Create a Turso (libsql) client from env vars - wraps async creation."""
    loop = _get_or_create_event_loop()
    return loop.run_until_complete(_create_turso_client_async())


def generate_create_table_sql(df: pd.DataFrame, table_name: str, model) -> str:
    logger.info(f"[DB] Generating CREATE TABLE SQL for table: {table_name}")
    logger.debug(f"[DB] DataFrame shape: {df.shape}")

    schema = "\n".join([f"- {col}: {str(dtype)}" for col, dtype in df.dtypes.items()])
    sample = df.head(3).to_dict(orient="records")
    prompt = f"""
Produce a single SQLite CREATE TABLE IF NOT EXISTS statement named `{table_name}`.
Map pandas dtypes to SQLite types: int->INTEGER, float->REAL, bool->INTEGER, datetime->TEXT, object->TEXT.
Only return the CREATE TABLE statement.

Schema:\n{schema}\nSamples:\n{sample}
"""
    try:
        logger.debug("[DB] Calling model.generate_content for CREATE TABLE")
        response = model.generate_content(prompt)
        text = response.text or ""
        logger.debug(f"[DB] Model response: {text[:200]}...")

        match = re.search(r"CREATE\s+TABLE[\s\S]*?\)", text, re.IGNORECASE)
        if match:
            sql = match.group(0)
            if "IF NOT EXISTS" not in sql.upper():
                sql = re.sub(r"CREATE\s+TABLE", "CREATE TABLE IF NOT EXISTS", sql, flags=re.IGNORECASE)
            logger.info(f"[DB] Generated CREATE TABLE SQL: {sql}")
            return sql
    except Exception as e:
        logger.warning(f"[DB] Model generation failed, using fallback: {e}")

    type_map = {"int64": "INTEGER", "int32": "INTEGER", "float64": "REAL", "float32": "REAL", "bool": "INTEGER", "datetime64[ns]": "TEXT"}
    cols = []
    for col, dtype in df.dtypes.items():
        sql_type = type_map.get(str(dtype), "TEXT")
        cols.append(f"`{col}` {sql_type}")

    sql = "CREATE TABLE IF NOT EXISTS `" + table_name + "` (" + ", ".join(cols) + ")"
    logger.info(f"[DB] Fallback CREATE TABLE SQL: {sql}")
    return sql


def create_table_if_needed(client, create_sql: str):
    logger.info("[DB] Creating table if needed (sync)")
    logger.info(f"[DB] CREATE TABLE SQL:\n{create_sql}")

    try:
        # FIX: Use the same event loop
        loop = _get_or_create_event_loop()
        loop.run_until_complete(client.execute(create_sql))
        logger.info("[DB] Table created/verified successfully")
        return True, None
    except Exception as e:
        logger.error(f"[DB] Error creating table: {e}", exc_info=True)
        return False, str(e)


def batch_insert_dataframe(client, df: pd.DataFrame, table_name: str):
    logger.info(f"[DB] Starting batch insert for table: {table_name} (sync)")
    logger.debug(f"[DB] DataFrame shape: {df.shape}")

    if df.empty:
        logger.warning("[DB] DataFrame is empty, skipping insert")
        return 0, None

    columns = list(df.columns)
    placeholders = ",".join(["?"] * len(columns))
    col_list = ",".join([f"`{c}`" for c in columns])
    sql = f"INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})"
    logger.info(f"[DB] INSERT template: {sql}")

    inserted = 0
    params = [tuple(None if pd.isna(v) else v for v in row) for row in df[columns].itertuples(index=False, name=None)]
    logger.info(f"[DB] Total rows to insert: {len(params)}")

    # FIX: Use the same event loop
    loop = _get_or_create_event_loop()

    try:
        for chunk_start in range(0, len(params), 500):
            chunk = params[chunk_start:chunk_start+500]
            logger.debug(f"[DB] Inserting chunk: {chunk_start} to {chunk_start + len(chunk)}")

            for i, p in enumerate(chunk):
                try:
                    loop.run_until_complete(client.execute(sql, p))
                    inserted += 1
                    if inserted % 100 == 0:
                        logger.debug(f"[DB] Inserted {inserted} rows so far")
                except Exception as e:
                    logger.error(f"[DB] Error inserting row {chunk_start + i}: {e}", exc_info=True)

        logger.info(f"[DB] Successfully inserted {inserted} rows")
        return inserted, None
    except Exception as e:
        logger.error(f"[DB] Batch insert failed: {e}", exc_info=True)
        return inserted, str(e)


def get_table_schema_sql(client, table_name: str) -> str:
    logger.info(f"[DB] Getting schema for table: {table_name} (sync)")

    try:
        # FIX: Use the same event loop
        loop = _get_or_create_event_loop()
        res = loop.run_until_complete(client.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)))
        rows = getattr(res, "rows", []) or []

        if rows:
            schema = rows[0][0]
            logger.info(f"[DB] Schema retrieved: {schema}")
            return schema
        else:
            logger.warning(f"[DB] No schema found for table: {table_name}")
            return ""
    except Exception as e:
        logger.error(f"[DB] Error getting table schema: {e}", exc_info=True)
        return ""


def _parse_columns_from_ddl(ddl: str):
    cols = []
    try:
        body = ddl.split("(", 1)[1].rsplit(")", 1)[0]
        for line in body.splitlines():
            line = line.strip().strip(",")
            if not line or line.startswith("--"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0].strip('`"')
                col_type = parts[1].upper()
                cols.append((name, col_type))
    except Exception:
        pass
    return cols


def _sanitize_sql(sql: str) -> str:
    sql = (sql or "").strip()
    # remove code fences or comments if any
    if sql.startswith("```"):
        sql = sql.strip("`")
    # strip trailing semicolons
    sql = re.sub(r";+$", "", sql)
    return sql


def _is_safe_select(sql: str) -> bool:
    upper = sql.upper().strip()
    if not upper.startswith("SELECT"):
        return False
    banned = [" DROP ", " ALTER ", " INSERT ", " UPDATE ", " DELETE ", " ATTACH ", " PRAGMA "]
    return not any(b in f" {upper} " for b in banned)


def _fallback_query_from_prompt(prompt: str, table_name: str, table_schema_sql: str) -> str:
    # build a simple LIKE-based filter across likely text columns using tokens from the prompt
    tokens = [t for t in re.findall(r"[A-Za-z0-9_]+", prompt or "") if len(t) > 2]
    columns = _parse_columns_from_ddl(table_schema_sql)
    text_cols = [c for c, t in columns if t in ("TEXT", "VARCHAR", "CHAR") or "TEXT" in t or "CHAR" in t or "CLOB" in t]
    if not tokens or not text_cols:
        return f"SELECT * FROM `{table_name}` LIMIT 50"
    like_clauses = []
    for tok in tokens[:5]:
        ors = [f"`{col}` LIKE '%{tok}%'" for col in text_cols[:6]]
        like_clauses.append("(" + " OR ".join(ors) + ")")
    where = " AND ".join(like_clauses)
    return f"SELECT * FROM `{table_name}` WHERE {where} LIMIT 200"


def _extract_target_values(prompt: str):
    values = []
    if not prompt:
        return values
    # emails
    values += re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", prompt)
    # quoted strings (names)
    values += [m.strip('"\'') for m in re.findall(r"['\"][^'\"]+['\"]", prompt)]
    # phone-like sequences (10+ digits)
    digits = re.findall(r"\b\+?\d[\d\s-]{8,}\d\b", prompt)
    values += [re.sub(r"[^\d]", "", d)[-10:] for d in digits if len(re.sub(r"[^\d]", "", d)) >= 10]
    # id-like tokens (alnum length>=6)
    values += [t for t in re.findall(r"[A-Za-z0-9_-]{6,}", prompt) if not t.isdigit()]
    # dedupe, preserve order
    seen = set()
    out = []
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _likely_identifier_columns(ddl: str):
    cols = _parse_columns_from_ddl(ddl)
    names = [c for c, _ in cols]
    # heuristic priority order
    preferred = [
        "email", "e_mail", "mail", "email_address",
        "phoneno", "phone", "mobile", "contact",
        "customerid", "customer_id", "userid", "user_id", "id",
        "name", "first_name", "last_name", "full_name",
    ]
    # map lowercase
    lower_map = {n.lower(): n for n in names}
    ranked = []
    for p in preferred:
        if p in lower_map:
            ranked.append(lower_map[p])
    # include remaining text columns
    text_cols = [c for c, t in cols if t in ("TEXT", "VARCHAR", "CHAR") or "TEXT" in t or "CHAR" in t or "CLOB" in t]
    for c in text_cols:
        if c not in ranked:
            ranked.append(c)
    return ranked[:8]


def _build_like_where(values, columns):
    if not values or not columns:
        return ""
    clauses = []
    for v in values[:5]:
        ors = []
        # exact match preferred for emails/phones/ids
        if "@" in v or v.isdigit() or len(v) >= 8:
            for col in columns[:6]:
                ors.append(f"`{col}` = '{v}' OR `{col}` LIKE '%{v}%' ")
        else:
            for col in columns[:6]:
                ors.append(f"`{col}` LIKE '%{v}%' ")
        ors_join = " OR ".join(ors)
        clauses.append(f"({ors_join})")
    return " AND ".join(clauses)


def _columns_from_ddl(ddl: str):
    cols = []
    try:
        body = ddl.split("(", 1)[1].rsplit(")", 1)[0]
        for line in body.splitlines():
            line = line.strip().strip(",")
            if not line or line.startswith("--"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                name = parts[0].strip('`"')
                cols.append(name)
    except Exception:
        pass
    return cols


def _infer_requested_columns(prompt: str, ddl: str):
    if not prompt:
        return []
    candidates = _columns_from_ddl(ddl)
    lower_map = {c.lower(): c for c in candidates}
    requested = []
    # tokens and simple phrases
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", prompt)
    for t in tokens:
        key = t.lower()
        if key in lower_map and lower_map[key] not in requested:
            requested.append(lower_map[key])
    # common synonyms mapping
    synonyms = {
        "age": "Age",
        "phone": "PhoneNo",
        "email": "Email",
        "name": "Name",
        "location": "Location",
        "tenure": "TenureMonths",
        "charges": "MonthlyCharges",
        "payment": "PaymentMethod",
        "engagement": "EngagementScore",
    }
    for k, col in synonyms.items():
        if k in prompt.lower() and col in candidates and col not in requested:
            requested.append(col)
    return requested[:6]


def _replace_select_star(sql: str, requested_cols: list, table_name: str) -> str:
    if not requested_cols:
        return sql
    m = re.match(r"\s*SELECT\s+\*\s+FROM\s+", sql, flags=re.IGNORECASE)
    if m:
        cols = ", ".join(f"`{c}`" for c in requested_cols)
        sql = re.sub(r"\*\s+FROM", f"{cols} FROM", sql, flags=re.IGNORECASE)
    return sql


def _ensure_distinct(sql: str) -> str:
    if not sql:
        return sql
    m = re.match(r"\s*SELECT\s+DISTINCT\b", sql, flags=re.IGNORECASE)
    if m:
        return sql
    # Insert DISTINCT after SELECT
    return re.sub(r"^\s*SELECT\s+", "SELECT DISTINCT ", sql, flags=re.IGNORECASE)


def _is_churn_related_query(prompt: str) -> bool:
    """Check if the query is about churn, high-risk customers, or customer retention"""
    if not prompt:
        return False
    p = prompt.lower()
    churn_keywords = [
        "churn", "high risk", "high-risk", "at risk", "at-risk",
        "risk customer", "churn risk", "likely to churn", "churn prediction",
        "churn probability", "retention", "retain", "losing customer",
        "customer likely to leave", "vulnerable customer", "unhappy customer"
    ]
    return any(keyword in p for keyword in churn_keywords)


def _has_churn_column(table_schema_sql: str) -> bool:
    """Check if the table has a churn-related column"""
    if not table_schema_sql:
        return False
    schema_lower = table_schema_sql.lower()
    churn_indicators = [
        "churn", "churned", "churn_probability", "churn_risk", "is_churn",
        "will_churn", "churn_score", "retention"
    ]
    return any(indicator in schema_lower for indicator in churn_indicators)


def _generate_predictive_churn_sql(table_name: str, table_schema_sql: str, model) -> str:
    """
    Generate SQL to identify high-risk customers using LLM-based predictive analysis.
    Analyzes data characteristics to predict churn risk when no churn column exists.
    """
    logger.info(f"[DB] Generating predictive churn SQL for table: {table_name}")
    
    columns = _parse_columns_from_ddl(table_schema_sql)
    column_names = [col[0] for col in columns]
    column_types = {col[0]: col[1] for col in columns}
    
    # Build column information for LLM
    schema_desc = "\n".join([f"- {name} ({col_type})" for name, col_type in columns])
    
    prompt = f"""You are a data analyst expert in customer churn prediction. Analyze the following table schema and generate a SQLite SELECT query to identify high-risk customers likely to churn.

Table name: `{table_name}`
Table schema:
{schema_desc}

Your task:
1. Analyze the available columns and identify which ones indicate churn risk based on common patterns:
   - Low engagement metrics (low activity, few transactions, low usage)
   - Payment issues (payment failures, overdue, pending payments)
   - Support tickets or complaints
   - Long tenure with declining activity
   - High charges with low value perception
   - Recent negative changes (downgrades, cancellations)

2. Generate a SQL SELECT query that identifies high-risk customers using WHERE conditions based on:
   - Thresholds for numeric columns (e.g., low engagement scores, high charges relative to activity)
   - Status fields (e.g., inactive, suspended, payment_failed)
   - Date-based patterns (e.g., last_login > 90 days ago)
   - Combination of multiple risk indicators

3. Return ONLY a single SQLite SELECT statement with:
   - All relevant columns for customer identification (name, email, phone, customer_id)
   - WHERE clause with logical conditions (AND/OR) to identify high-risk customers
   - ORDER BY to prioritize highest risk customers
   - LIMIT 200

Example patterns to look for:
- Low engagement: engagement_score < 3, last_activity_days > 60
- Payment issues: payment_status = 'failed' OR payment_status = 'overdue'
- Support issues: complaint_count > 2, support_tickets > 0
- Value mismatch: monthly_charges > 100 AND usage_minutes < 60
- Declining usage: recent_activity < average_activity * 0.5

Generate the SQL query now:"""

    try:
        response = model.generate_content(prompt)
        sql = _sanitize_sql(response.text)
        logger.debug(f"[DB] LLM-generated predictive churn SQL: {sql}")
        
        # Validate and ensure it's a safe SELECT
        if not _is_safe_select(sql):
            logger.warning("[DB] LLM generated unsafe SQL, using fallback")
            return _fallback_predictive_churn_sql(table_name, column_names, column_types)
        
        # Ensure table name is correct
        if table_name not in sql.upper() and " FROM " in sql.upper():
            # Replace any table name in the SQL with the correct one
            sql = re.sub(r"FROM\s+`?\w+`?", f"FROM `{table_name}`", sql, flags=re.IGNORECASE)
        elif " FROM " not in sql.upper():
            sql = f"SELECT * FROM `{table_name}` WHERE 1=0"  # Safe fallback
        
        # Ensure DISTINCT
        sql = _ensure_distinct(sql)
        
        logger.info(f"[DB] Final predictive churn SQL: {sql}")
        return sql
    except Exception as e:
        logger.error(f"[DB] Error generating predictive churn SQL: {e}", exc_info=True)
        return _fallback_predictive_churn_sql(table_name, column_names, column_types)


def _fallback_predictive_churn_sql(table_name: str, column_names: list, column_types: dict) -> str:
    """Fallback SQL for churn prediction when LLM generation fails"""
    logger.info("[DB] Using fallback predictive churn SQL")
    
    # Identify potential risk indicator columns
    risk_indicators = []
    
    # Common patterns for churn risk
    low_engagement = [c for c in column_names if any(x in c.lower() for x in ['engagement', 'activity', 'usage', 'score'])]
    payment_issues = [c for c in column_names if any(x in c.lower() for x in ['payment', 'status', 'due', 'overdue'])]
    support_issues = [c for c in column_names if any(x in c.lower() for x in ['complaint', 'ticket', 'support', 'issue'])]
    charges = [c for c in column_names if any(x in c.lower() for x in ['charge', 'amount', 'cost', 'price'])]
    
    conditions = []
    
    # Add conditions for low engagement (if numeric columns exist)
    for col in low_engagement[:2]:  # Limit to 2 columns
        if column_types.get(col, '').upper() in ('REAL', 'INTEGER', 'NUMERIC'):
            conditions.append(f"`{col}` < (SELECT AVG(`{col}`) * 0.7 FROM `{table_name}` WHERE `{col}` IS NOT NULL)")
    
    # Add conditions for payment issues
    for col in payment_issues[:1]:
        if column_types.get(col, '').upper() in ('TEXT', 'VARCHAR', 'CHAR'):
            conditions.append(f"(`{col}` LIKE '%fail%' OR `{col}` LIKE '%overdue%' OR `{col}` LIKE '%pending%')")
    
    # Add conditions for support issues (high count)
    for col in support_issues[:1]:
        if column_types.get(col, '').upper() in ('REAL', 'INTEGER', 'NUMERIC'):
            conditions.append(f"`{col}` > 1")
    
    if conditions:
        where_clause = " OR ".join(conditions)
        return f"SELECT DISTINCT * FROM `{table_name}` WHERE {where_clause} ORDER BY 1 LIMIT 200"
    else:
        # Very basic fallback: return customers with any missing or zero values in numeric columns
        numeric_cols = [c for c in column_names if column_types.get(c, '').upper() in ('REAL', 'INTEGER', 'NUMERIC')]
        if numeric_cols:
            zero_conditions = [f"`{col}` = 0 OR `{col}` IS NULL" for col in numeric_cols[:3]]
            where_clause = " OR ".join(zero_conditions)
            return f"SELECT DISTINCT * FROM `{table_name}` WHERE {where_clause} LIMIT 200"
    
    # Last resort: return limited results
    return f"SELECT DISTINCT * FROM `{table_name}` LIMIT 200"


def generate_select_sql_from_prompt(prompt: str, table_name: str, table_schema_sql: str, model, prior_error: str = None) -> str:
    logger.info(f"[DB] Generating SELECT SQL from prompt: {prompt[:100]}...")
    logger.debug(f"[DB] Table schema: {table_schema_sql}")

    # Check if query is churn-related and if churn column exists
    is_churn_query = _is_churn_related_query(prompt)
    has_churn_col = _has_churn_column(table_schema_sql)
    
    # If churn-related query and no churn column exists, use predictive churn analysis
    if is_churn_query and not has_churn_col:
        logger.info("[DB] Churn-related query detected without churn column - using predictive analysis")
        try:
            return _generate_predictive_churn_sql(table_name, table_schema_sql, model)
        except Exception as e:
            logger.warning(f"[DB] Predictive churn analysis failed: {e}, falling back to regular SQL generation")

    target_values = _extract_target_values(prompt)
    id_columns = _likely_identifier_columns(table_schema_sql)
    requested_cols = _infer_requested_columns(prompt, table_schema_sql)

    system_rules = (
        "You must return exactly ONE SQLite SELECT statement only. "
        "No explanations, comments, or code fences. "
        "It MUST reference the given table name exactly as provided. "
        "Prefer text search using LIKE with wildcards (e.g., column LIKE '%token%'). "
        "If a target value is provided, prioritize filtering identifier columns with exact or LIKE matches. "
        "Select only the columns the user asked for when clear, otherwise a minimal set. "
        "Include LIMIT 200 for broad queries."
    )

    constraints = (
        "Safety constraints: do not use DROP/ALTER/INSERT/UPDATE/DELETE/ATTACH/PRAGMA. "
        "Only SELECT is allowed."
    )

    guidance = (
        f"Likely identifier columns: {id_columns}\n"
        f"Target values (if any): {target_values}\n"
        f"Requested columns (if any): {requested_cols}\n"
    )

    base_prompt = (
        f"{system_rules}\n{constraints}\n\n"
        f"Table name: `{table_name}`\n"
        f"Table DDL:\n{table_schema_sql}\n\n"
        f"{guidance}"
        f"User question:\n{prompt}\n"
        f"Return a single valid SQLite SELECT targeting `{table_name}`."
    )

    attempts = []
    if prior_error:
        attempts.append(base_prompt + f"\n\nPrevious error: {prior_error}\nFix and return a valid SELECT.")
    attempts.append(base_prompt)
    attempts.append(base_prompt + "\nIf unsure about exact columns, use LIKE-based filters on identifier columns and LIMIT 200.")

    for i, p in enumerate(attempts, 1):
        try:
            logger.debug(f"[DB] LLM attempt {i} to generate SQL")
            response = model.generate_content(p)
            sql = _sanitize_sql(response.text)
            logger.debug(f"[DB] Raw LLM SQL (attempt {i}): {sql}")
            if not _is_safe_select(sql):
                raise ValueError("Not a safe SELECT")
            if table_name not in sql and " FROM " not in sql.upper():
                sql = f"SELECT * FROM `{table_name}` LIMIT 200"
            # inject WHERE if missing using target values
            if " WHERE " not in sql.upper() and target_values:
                where = _build_like_where(target_values, id_columns)
                if where:
                    sql = f"SELECT * FROM `{table_name}` WHERE {where} LIMIT 200"
            # replace * with requested columns where obvious
            sql = _replace_select_star(sql, requested_cols, table_name)
            # enforce DISTINCT to avoid duplicate rows
            sql = _ensure_distinct(sql)
            logger.info(f"[DB] Final SELECT SQL: {sql}")
            return sql
        except Exception as e:
            logger.warning(f"[DB] LLM attempt {i} failed to produce valid SQL: {e}")
            continue

    # Fallback heuristic query (identifier LIKE first, minimal projection)
    if target_values:
        where = _build_like_where(target_values, id_columns)
        if where:
            cols = ", ".join(f"`{c}`" for c in (requested_cols or id_columns[:3] or ["*"]))
            fb = f"SELECT DISTINCT {cols} FROM `{table_name}` WHERE {where} LIMIT 200"
            logger.info(f"[DB] Using fallback SELECT SQL with identifier filter: {fb}")
            return fb
    fallback = _fallback_query_from_prompt(prompt, table_name, table_schema_sql)
    if requested_cols and "SELECT *" in fallback.upper():
        fallback = _replace_select_star(fallback, requested_cols, table_name)
    fallback = _ensure_distinct(fallback)
    logger.info(f"[DB] Using fallback SELECT SQL: {fallback}")
    return fallback


def execute_select(client, sql: str):
    logger.info(f"[DB] Executing SELECT (sync): {sql}")

    try:
        # FIX: Use the same event loop
        loop = _get_or_create_event_loop()
        res = loop.run_until_complete(client.execute(sql))
        rows = getattr(res, "rows", []) or []
        column_names = getattr(res, "columns", None)

        logger.info(f"[DB] Query returned {len(rows)} rows")
        logger.debug(f"[DB] Columns: {column_names}")

        return rows, column_names
    except Exception as e:
        logger.error(f"[DB] Error executing SELECT: {e}", exc_info=True)
        raise


def close_client(client):
    """Attempt to close the underlying client/session gracefully."""
    if not client:
        return
    try:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                # if async
                loop = _get_or_create_event_loop()
                return loop.run_until_complete(close())
            except TypeError:
                # sync
                return close()
    except Exception as e:
        logger.warning(f"[DB] Error closing client: {e}")