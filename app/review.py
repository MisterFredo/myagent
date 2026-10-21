"""Protected extraction-review page. Rendering helpers use only stdlib."""
from __future__ import annotations

import json
import logging
from html import escape
from urllib.parse import urlsplit


DEFAULT_RUN = "27535459-1873-4eba-b557-871b300915c6"
DATASET = "myagent-512316.MYAGENT"
logger = logging.getLogger("myagent.review")


def safe(value):
    return escape(str(value if value is not None else ""), quote=True)


def parse_item(value):
    item = json.loads(value)
    if not isinstance(item, dict):
        raise ValueError("Review item is not a JSON object.")
    return item


def claims(items):
    values = [f"<li>{safe(item.get('text_fr'))}</li>"
              for item in items or [] if item.get("text_fr")]
    return "<ul>" + "".join(values) + "</ul>" if values else ""


def strings(items):
    return "<ul>" + "".join(f"<li>{safe(item)}</li>" for item in items or []) + "</ul>"


def official_link(url):
    try:
        parts = urlsplit(url or "")
        if (parts.scheme == "https" and parts.hostname in
                {"digitalhub.fifa.com", "inside.fifa.com", "www.fifa.com"}
                and parts.username is None and parts.password is None):
            return (f'<a href="{safe(url)}" target="_blank" '
                    'rel="noopener noreferrer">Ouvrir le document officiel</a>')
    except ValueError:
        pass
    return ""


def source_label(proof, source_info):
    meta = source_info.get(proof.get("passage_id"), {})
    title = meta.get("TITLE") or "Passage source"
    page = meta.get("PAGE_START")
    label = f"{title} — page PDF {page}" if page is not None else title
    return label, meta


def render_card(row, source_info):
    proposed = parse_item(row["PROPOSED_ITEM_JSON"])
    original = parse_item(row["ORIGINAL_ITEM_JSON"])
    conditions = claims(proposed.get("conditions"))
    exceptions = claims(proposed.get("exceptions"))
    consequences = claims(proposed.get("consequences"))
    dependencies = proposed.get("unresolved_references") or []
    proof_cards = []
    seen = set()
    for proof in proposed.get("evidence") or []:
        key = (proof.get("passage_id"), proof.get("quote"))
        if key in seen:
            continue
        seen.add(key)
        label, meta = source_label(proof, source_info)
        proof_cards.append(f"""
        <details class="proof">
          <summary>{safe(label)}</summary>
          <p class="muted">Édition {safe(meta.get('EDITION'))}</p>
          <pre>{safe(proof.get('quote'))}</pre>
          {official_link(meta.get('SOURCE_URL'))}
        </details>""")

    related = []
    for passage_id in row.get("RELATED_PASSAGE_IDS") or []:
        meta = source_info.get(passage_id, {})
        if not meta:
            related.append("<li>Passage associé indisponible.</li>")
            continue
        related.append(f"""
        <li>{safe(meta.get('TITLE'))}, page PDF {safe(meta.get('PAGE_START'))}
          — {official_link(meta.get('SOURCE_URL'))}
          <details><summary>Lire le passage associé</summary>
          <pre>{safe(meta.get('EXACT_TEXT'))}</pre></details>
        </li>""")

    dependency_html = (f"<section class='pending'><h3>À approfondir</h3>"
                       f"{strings(dependencies)}</section>" if dependencies else "")
    related_html = ("<h3>Passages associés</h3><ul>" + "".join(related) + "</ul>"
                    if related else "")
    status = "Brouillon de revue" if row.get("REVIEW_STATUS") == "DRAFT" else "Statut à examiner"
    return f"""
    <article>
      <div class="card-top"><span class="reference">Article {safe(row['UNIT_ID'])}</span>
      <span class="badge">{status}</span></div>
      <h2>{safe(proposed.get('title_fr'))}</h2>
      <p class="abstract">{safe(proposed.get('summary_fr'))}</p>
      <h3>Information détaillée</h3>
      <p>{safe(proposed.get('statement_fr'))}</p>
      <h3>Conditions et champ d’application</h3>
      {conditions or '<p class="muted">Pas de condition distincte renseignée dans ce brouillon.</p>'}
      <h3>Exceptions renseignées</h3>
      {exceptions or '<p class="muted">Aucune exception renseignée ici ; cela ne garantit pas son absence dans le corpus.</p>'}
      {'<h3>Conséquences renseignées</h3>' + consequences if consequences else ''}
      {dependency_html}

      <details class="panel"><summary>Voir la revue et les précisions apportées</summary>
        {strings(row.get('REVIEW_NOTES'))}
        <p class="muted">Comparaison assistée par IA avec les sources. Validation juridique en attente.</p>
      </details>

      <details class="panel"><summary>Comparer avec l’extraction originale</summary>
        <h3>Titre initial</h3><p>{safe(original.get('title_fr'))}</p>
        <h3>Résumé initial</h3><p>{safe(original.get('summary_fr'))}</p>
        <h3>Énoncé détaillé initial</h3><p>{safe(original.get('statement_fr'))}</p>
        <h3>Conditions initiales</h3>{claims(original.get('conditions'))}
        <h3>Exceptions initiales</h3>{claims(original.get('exceptions'))}
      </details>

      <details class="panel"><summary>Consulter les sources et les renvois</summary>
        <p class="muted">Extraits du texte stocké ; des défauts de mise en page PDF peuvent subsister.</p>
        {''.join(proof_cards)}
        {related_html}
      </details>
    </article>"""


def render_page(q, run_id, rows, source_info):
    cards = "".join(render_card(row, source_info) for row in rows)
    if not cards:
        cards = """<article><h2>Aucun résultat</h2>
        <p>Aucune revue ne correspond à cette recherche. Si la recherche est vide,
        vérifier que le script de revue de l’extraction concernée a été exécuté dans BigQuery.</p></article>"""
    return f"""<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MYAGENT — Revue des extractions</title>
<style>
* {{box-sizing:border-box}} body {{margin:0;background:#f5f6f8;color:#172033;
font:16px/1.7 system-ui,sans-serif}} main {{max-width:1050px;margin:auto;padding:34px 20px 80px}}
nav {{display:flex;flex-wrap:wrap;gap:22px;margin-bottom:34px}} a {{color:#284f9b;text-underline-offset:3px}}
.label {{font-size:12px;font-weight:750;letter-spacing:.13em;color:#53627a}}
h1 {{font-size:clamp(30px,5vw,44px);line-height:1.2;letter-spacing:-.035em;margin:12px 0 18px}}
h2 {{font-size:22px;line-height:1.4;margin:14px 0}} h3 {{font-size:16px;margin:22px 0 8px}}
.muted {{color:#53627a}} .intro {{max-width:820px}} .abstract {{color:#53627a}}
article {{background:white;border:1px solid #e1e5ec;border-radius:12px;padding:28px;margin:20px 0}}
.card-top {{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
.reference {{font-size:13px;font-weight:750;color:#334863}}
.badge {{font-size:12px;background:#fff3d4;color:#755400;border-radius:20px;padding:4px 10px}}
.pending {{padding:1px 18px 10px;border-left:3px solid #c5952a;background:#fffbef;margin-top:22px}}
.panel {{border-top:1px solid #e1e5ec;padding-top:16px;margin-top:18px}}
summary {{cursor:pointer;font-weight:600}} .proof {{margin:16px 0}}
pre {{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f8;padding:16px;border-radius:8px;
font:13px/1.7 ui-monospace,monospace}} form {{display:flex;gap:10px;margin-top:28px}}
input[type=search] {{flex:1;min-width:0;padding:13px;border:1px solid #ccd3df;border-radius:8px;font:inherit}}
button {{border:0;background:#172033;color:white;padding:12px 20px;border-radius:8px;font:inherit;cursor:pointer}}
li {{margin:7px 0}} @media(max-width:550px){{article{{padding:19px}}form{{flex-direction:column}}}}
</style></head><body><main>
<nav><a href="/">Informations</a><a href="/reviews">Revue des extractions</a></nav>
<div class="label">MYAGENT / REVUE</div>
<h1>Revue des extractions</h1>
<p class="intro muted">Propositions liées à l’extraction sélectionnée.
L’extraction originale et ses sources sont conservées.
Elles sont en cours de revue ; leur applicabilité actuelle et le programme 2027 restent à confirmer.</p>
<form method="get" action="/reviews">
<input type="hidden" name="run_id" value="{safe(run_id)}">
<input type="search" name="q" value="{safe(q)}" maxlength="150"
placeholder="Rechercher : faillite, sanctions, paris…" aria-label="Rechercher dans les propositions">
<button type="submit">Rechercher</button></form>
<p class="muted">{len(rows)} information(s) affichée(s) — maximum 100.</p>
{cards}</main></body></html>"""


def build_review_router(require_admin, get_bigquery_client):
    # Local imports allow rendering checks without installing the server SDKs.
    from fastapi import APIRouter, Depends, HTTPException, Query
    from fastapi.responses import HTMLResponse
    from google.cloud import bigquery

    router = APIRouter(dependencies=[Depends(require_admin)])

    def execute(sql, parameters):
        config = bigquery.QueryJobConfig(
            query_parameters=parameters,
            maximum_bytes_billed=1_000_000_000,
        )
        return list(get_bigquery_client().query(sql, job_config=config).result(timeout=45))

    @router.get('/reviews', response_class=HTMLResponse)
    def review_page(
        q: str = Query(default='', max_length=150),
        run_id: str = Query(default=DEFAULT_RUN, pattern=r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'),
    ):
        q = q.strip()
        try:
            result = execute(f"""
                WITH latest AS (
                  SELECT * FROM `{DATASET}.FIFA_EXTRACTION_REVIEW`
                  WHERE ID_RUN=@run_id
                  QUALIFY ROW_NUMBER() OVER (
                    PARTITION BY ID_RUN, UNIT_ID
                    ORDER BY REVIEW_VERSION DESC, CREATED_AT DESC, ID_REVIEW DESC
                  )=1
                )
                SELECT * FROM latest
                WHERE @q=''
                   OR STRPOS(LOWER(COALESCE(JSON_VALUE(PROPOSED_ITEM_JSON,'$.title_fr'),'')), LOWER(@q))>0
                   OR STRPOS(LOWER(COALESCE(JSON_VALUE(PROPOSED_ITEM_JSON,'$.statement_fr'),'')), LOWER(@q))>0
                ORDER BY UNIT_ID
                LIMIT 100
            """, [
                bigquery.ScalarQueryParameter('run_id','STRING',run_id),
                bigquery.ScalarQueryParameter('q','STRING',q),
            ])
            rows = [dict(row.items()) for row in result]
            passage_ids = set()
            for row in rows:
                item = parse_item(row['PROPOSED_ITEM_JSON'])
                passage_ids.update(p['passage_id'] for p in item.get('evidence', []))
                passage_ids.update(row.get('RELATED_PASSAGE_IDS') or [])
            source_info = {}
            if passage_ids:
                sources = execute(f"""
                    SELECT p.ID_PASSAGE, p.PAGE_START, p.EXACT_TEXT,
                           d.TITLE, d.EDITION, d.SOURCE_URL
                    FROM `{DATASET}.FIFA_PASSAGE` AS p
                    JOIN `{DATASET}.FIFA_DOCUMENT` AS d
                      ON d.ID_DOCUMENT=p.ID_DOCUMENT
                    WHERE p.ID_PASSAGE IN UNNEST(@passage_ids)
                """, [bigquery.ArrayQueryParameter('passage_ids','STRING',sorted(passage_ids))])
                source_info = {r.ID_PASSAGE: dict(r.items()) for r in sources}
            html = render_page(q, run_id, rows, source_info)
        except Exception as exc:
            logger.error('Review consultation failed (%s)', type(exc).__name__)
            raise HTTPException(
                status_code=503,
                detail='Revue indisponible. Vérifier la table FIFA_EXTRACTION_REVIEW et ses accès dans les logs Render.',
            ) from None
        return HTMLResponse(html, headers={'Cache-Control':'no-store'})

    return router
