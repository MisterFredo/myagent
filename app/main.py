import logging
import os
import secrets
from functools import lru_cache
from html import escape

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from google.cloud import bigquery


PROJECT = "myagent-512316"
LOCATION = "europe-west1"
STUDY_VIEW = f"{PROJECT}.MYAGENT.FIFA_STUDY_REVIEW"

logger = logging.getLogger("myagent")

app = FastAPI(
    title="MYAGENT",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

security = HTTPBasic()


# ============================================================
# AUTHENTIFICATION
# ============================================================

def require_admin(
    credentials: HTTPBasicCredentials = Depends(security),
):
    expected_user = os.environ.get("MYAGENT_ADMIN_USER", "")
    expected_password = os.environ.get("MYAGENT_ADMIN_PASSWORD", "")

    if not expected_user or not expected_password:
        raise HTTPException(
            status_code=503,
            detail="Accès administrateur non configuré.",
        )

    user_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        expected_user.encode("utf-8"),
    )

    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        expected_password.encode("utf-8"),
    )

    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Identifiants incorrects.",
            headers={"WWW-Authenticate": 'Basic realm="MYAGENT"'},
        )


# ============================================================
# BIGQUERY
# Les identifiants sont lus via GOOGLE_APPLICATION_CREDENTIALS.
# ============================================================

@lru_cache(maxsize=1)
def get_bigquery_client():
    return bigquery.Client(
        project=PROJECT,
        location=LOCATION,
    )


def search_rules(query: str):
    sql = f"""
        SELECT
          ID_RULE,
          TITLE,
          RULE_SUMMARY,
          CONDITION_LOGIC,
          CONDITIONS,
          EXCEPTIONS,
          CONSEQUENCE,
          LEGAL_REFERENCES,
          VALIDATION_STATUS,
          LEGAL_STATUS,
          APPLICABILITY_NOTES,
          EVIDENCE
        FROM `{STUDY_VIEW}`
        WHERE
          @query = ''
          OR STRPOS(
            LOWER(COALESCE(TITLE, '')),
            LOWER(@query)
          ) > 0
          OR STRPOS(
            LOWER(COALESCE(RULE_SUMMARY, '')),
            LOWER(@query)
          ) > 0
        ORDER BY TITLE, ID_RULE
        LIMIT 100
    """

    config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "query", "STRING", query
            )
        ],
        maximum_bytes_billed=1_000_000_000,
    )

    return list(
        get_bigquery_client()
        .query(sql, job_config=config)
        .result(timeout=45)
    )


# ============================================================
# AFFICHAGE
# ============================================================

def safe(value):
    return escape(str(value if value is not None else ""))


def text_list(items, field):
    values = [
        f"<li>{safe(item.get(field))}</li>"
        for item in (items or [])
        if item.get(field)
    ]
    return "<ul>" + "".join(values) + "</ul>" if values else ""


def render_rule(row):
    conditions = text_list(row.CONDITIONS, "CONDITION_TEXT")
    exceptions = text_list(row.EXCEPTIONS, "EXCEPTION_TEXT")

    condition_block = (
        f"<h3>Conditions et contexte</h3>{conditions}"
        if conditions else ""
    )

    exception_block = (
        f"<h3>Exceptions identifiées</h3>{exceptions}"
        if exceptions else
        "<p class='muted'>Exceptions : revue non finalisée.</p>"
    )

    consequence_block = (
        f"<h3>Conséquence</h3><p>{safe(row.CONSEQUENCE)}</p>"
        if row.CONSEQUENCE else ""
    )

    references = "".join(
        "<li>"
        f"{safe(ref.get('ID_DOCUMENT'))}"
        f" — {safe(ref.get('PROVISION'))}"
        "</li>"
        for ref in (row.LEGAL_REFERENCES or [])
    )

    evidence = "".join(
        f"""
        <details class="source">
          <summary>
            {safe(source.get("DOCUMENT_TITLE"))}
            — édition {safe(source.get("EDITION"))}
            — page {safe(source.get("PAGE_START"))}
          </summary>
          <p class="muted">
            Vérification :
            {safe(source.get("VERIFICATION_STATUS"))}
          </p>
          <pre>{safe(source.get("EXACT_TEXT"))}</pre>
        </details>
        """
        for source in (row.EVIDENCE or [])
    )

    return f"""
    <article>
      <div class="status">
        Extraction : {safe(row.VALIDATION_STATUS)}
        · Statut juridique : {safe(row.LEGAL_STATUS)}
      </div>

      <h2>{safe(row.TITLE)}</h2>
      <p>{safe(row.RULE_SUMMARY)}</p>

      <details>
        <summary>Conditions, références et sources</summary>

        {condition_block}
        {exception_block}
        {consequence_block}

        <h3>Références</h3>
        <ul>{references}</ul>

        <p class="muted">{safe(row.APPLICABILITY_NOTES)}</p>

        <h3>Passages sources</h3>
        {evidence}
      </details>
    </article>
    """


def render_page(query, rows):
    cards = "".join(render_rule(row) for row in rows)

    if not rows:
        cards = "<article>Aucune règle trouvée.</article>"

    return f"""
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MYAGENT — Informations</title>

  <style>
    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: #f5f6f8;
      color: #172033;
      font-family: system-ui, sans-serif;
      line-height: 1.65;
    }}

    main {{
      max-width: 1050px;
      margin: auto;
      padding: 40px 20px 80px;
    }}

    .label {{
      font-size: 13px;
      letter-spacing: .12em;
      font-weight: 750;
      color: #53627a;
    }}

    h1 {{
      font-size: clamp(30px, 6vw, 44px);
      letter-spacing: -.035em;
      margin: 12px 0;
    }}

    h2 {{ font-size: 21px; margin: 10px 0; }}
    h3 {{ font-size: 16px; margin: 22px 0 8px; }}

    .muted, .status {{ color: #53627a; }}
    .status {{ font-size: 12px; overflow-wrap: anywhere; }}

    form {{
      display: flex;
      gap: 10px;
      margin: 28px 0 14px;
    }}

    input {{
      min-width: 0;
      flex: 1;
      padding: 14px;
      border: 1px solid #ccd3df;
      border-radius: 8px;
      font: inherit;
    }}

    button {{
      padding: 12px 20px;
      background: #172033;
      color: white;
      border: 0;
      border-radius: 8px;
      font: inherit;
      cursor: pointer;
    }}

    article {{
      background: white;
      border: 1px solid #e1e5ec;
      border-radius: 12px;
      padding: 24px;
      margin-top: 18px;
    }}

    summary {{ cursor: pointer; font-weight: 600; }}
    .source {{ margin: 12px 0; }}

    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      background: #f5f6f8;
      padding: 16px;
      border-radius: 8px;
      font: 13px/1.7 ui-monospace, monospace;
    }}

    @media (max-width: 500px) {{
      form {{ flex-direction: column; }}
      article {{ padding: 18px; }}
    }}
  </style>
</head>

<body>
  <main>
    <div class="label">MYAGENT</div>
    <h1>Les informations et leurs sources</h1>

    <p class="muted">
      Corpus de travail. Les statuts indiquent les vérifications
      restant à effectuer. Cette liste n’est pas filtrée par
      session d’examen.
    </p>

    <form method="get" action="/">
      <input
        type="search"
        name="q"
        maxlength="150"
        value="{safe(query)}"
        placeholder="Rechercher : licence, paiement, éligibilité…"
        aria-label="Rechercher dans les règles"
      >
      <button type="submit">Rechercher</button>
    </form>

    <p class="muted">
      {len(rows)} résultat(s) affiché(s) — maximum 100.
    </p>

    {cards}
  </main>
</body>
</html>
"""


# ============================================================
# ROUTES
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "myagent",
    }


@app.get(
    "/",
    response_class=HTMLResponse,
    dependencies=[Depends(require_admin)],
)
def home(q: str = Query(default="", max_length=150)):
    query = q.strip()

    try:
        rows = search_rules(query)
    except Exception as exc:
        logger.error(
            "BigQuery consultation failed (%s)",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Consultation momentanément indisponible. "
                "Vérifier la configuration et les accès BigQuery."
            ),
        ) from None

    return HTMLResponse(
        content=render_page(query, rows),
        headers={"Cache-Control": "no-store"},
    )

    from app.review import build_review_router

app.include_router(
    build_review_router(require_admin, get_bigquery_client)
)
