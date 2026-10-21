"""Study cards read versioned reviews; they never replace or validate them."""
from __future__ import annotations

import json
import logging
from urllib.parse import urlencode

from app.review import safe, claims, strings, official_link, parse_item


DATASET = "myagent-512316.MYAGENT"
logger = logging.getLogger("myagent.study")


def render_sources(passage_ids, sources):
    blocks = []
    for passage_id in dict.fromkeys(passage_ids):
        source = sources.get(passage_id)
        if source is None:
            blocks.append('<p class="pending">Passage associé indisponible.</p>')
            continue
        blocks.append(f"""
        <details class="source"><summary>
          {safe(source.get('TITLE'))} — page PDF {safe(source.get('PAGE_START'))}
        </summary>
        <p class="muted">Édition {safe(source.get('EDITION'))}</p>
        <pre>{safe(source.get('EXACT_TEXT'))}</pre>
        {official_link(source.get('SOURCE_URL'))}
        </details>""")
    return ''.join(blocks)


def render_unit(row, sources):
    item = parse_item(row['PROPOSED_ITEM_JSON'])
    conditions = claims(item.get('conditions'))
    exceptions = claims(item.get('exceptions'))
    consequences = claims(item.get('consequences'))
    dependencies = item.get('unresolved_references') or []
    passage_ids = [p['passage_id'] for p in item.get('evidence', [])]
    raw_status = row.get('REVIEW_STATUS')
    status = 'Brouillon de revue' if raw_status == 'DRAFT' else 'Statut à examiner'
    return f"""
    <details class="unit">
      <summary><span class="ref">{safe(row['UNIT_ID'])}</span>
      {safe(item.get('title_fr'))}</summary>
      <p class="muted">{safe(item.get('summary_fr'))}</p>
      <p>{safe(item.get('statement_fr'))}</p>
      {'<h4>Conditions et portée</h4>' + conditions if conditions else ''}
      {'<h4>Exceptions renseignées</h4>' + exceptions if exceptions else ''}
      {'<h4>Conséquences renseignées</h4>' + consequences if consequences else ''}
      {'<h4>Renvois à étudier</h4>' + strings(dependencies) if dependencies else ''}
      <p class="muted small">{status}. Une liste d’exceptions vide n’établit pas leur absence.</p>
      <details class="evidence"><summary>Vérifier les textes sources</summary>
      {render_sources(passage_ids, sources)}
      </details>
    </details>"""


def render_study_page(card, reviews, sources):
    review_url = '/reviews'
    if reviews and reviews[0].get('ID_RUN'):
        review_url += '?' + urlencode({'run_id': reviews[0]['ID_RUN']})
    supplements = json.loads(card.get('SUPPLEMENTS_JSON') or '[]')
    if not isinstance(supplements, list):
        raise ValueError('Invalid study-card supplements.')
    unit_html = ''.join(render_unit(row, sources) for row in reviews)
    supplements_html = []
    for section in supplements:
        supplements_html.append(f"""
        <section class="supplement" id="{safe(section['SECTION_ID'])}">
          <h3>{safe(section['TITLE'])}</h3>
          <p>{safe(section['STATEMENT_FR'])}</p>
          {strings(section.get('POINTS'))}
          <details class="evidence"><summary>Vérifier le passage officiel</summary>
          {render_sources(section.get('SOURCE_PASSAGE_IDS') or [], sources)}
          </details>
        </section>""")
    status = 'Fiche en brouillon' if card.get('STATUS') == 'DRAFT' else 'Statut à examiner'
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MYAGENT — {safe(card['TITLE'])}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f6f8;color:#172033;font:16px/1.75 system-ui,sans-serif}}
main{{max-width:1050px;margin:auto;padding:32px 20px 80px}}nav{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:30px}}
a{{color:#284f9b;text-underline-offset:3px}}h1{{font-size:clamp(30px,5vw,43px);line-height:1.2;letter-spacing:-.035em;margin:12px 0 20px}}
h2{{font-size:24px;margin:0 0 18px}}h3{{font-size:19px}}h4{{font-size:15px;margin:20px 0 5px}}
.label{{font-size:12px;font-weight:750;letter-spacing:.12em;color:#53627a}}.muted{{color:#53627a}}.small{{font-size:13px}}
.badge{{display:inline-block;background:#fff3d4;color:#755400;padding:4px 12px;border-radius:20px;font-size:12px}}
.card{{background:white;border:1px solid #e1e5ec;border-radius:12px;padding:28px;margin-top:24px}}
.unit{{border-top:1px solid #e1e5ec;padding:18px 0}}summary{{cursor:pointer;font-weight:650}}
.ref{{display:inline-block;min-width:84px;color:#53627a;font-size:13px}}.evidence{{margin-top:18px}}
.source{{padding:12px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f6f8;padding:16px;border-radius:8px;font:13px/1.7 ui-monospace,monospace}}
.supplement+.supplement{{border-top:1px solid #e1e5ec;margin-top:26px;padding-top:12px}}
.pending{{background:#fffbef;border-left:3px solid #c5952a;padding:18px 22px}}
li{{margin:7px 0}}.toc{{display:flex;flex-wrap:wrap;gap:10px 24px;margin:24px 0}}
@media(max-width:550px){{.card{{padding:20px}}.ref{{display:block}}}}
@media print{{body{{background:white}}main{{max-width:none;padding:0}}nav,.toc{{display:none}}.card{{border:0;padding:10px 0}}}}
</style></head><body><main>
<nav><a href="/">Informations</a><a href="{safe(review_url)}">Revue des extractions</a>
<a href="/study/eligibility">Éligibilité</a><a href="/study/minors">Mineurs</a><a href="/study/representation">Représentation</a></nav>
<div class="label">MYAGENT / FICHE DE RÉVISION</div>
<h1>{safe(card['TITLE'])}</h1><span class="badge">{status}</span>
<p>{safe(card.get('INTRODUCTION'))}</p>
<p class="muted small">La fiche référence {len(reviews)} informations revues. Les versions sources sont conservées ; le statut juridique actuel et le programme 2027 restent à confirmer.</p>
<div class="toc"><a href="#conditions">Informations à connaître</a>
<a href="#definitions">Définitions et renvois</a><a href="#pending">Points ouverts</a></div>
<section class="card" id="conditions"><h2>Les informations à connaître</h2>
<p class="muted">Ouvre une information pour étudier son énoncé, sa portée et ses sources.</p>
{unit_html}</section>
<section class="card" id="definitions"><h2>Définitions et renvois</h2>
<p class="muted">Compléments de lecture liés à la fiche. Leur présence ne vaut pas validation juridique.</p>
{''.join(supplements_html)}</section>
<section class="card pending" id="pending"><h2>Points restant à vérifier</h2>
{strings(card.get('OPEN_POINTS'))}</section>
</main></body></html>"""


def build_study_router(require_admin, get_bigquery_client):
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.responses import HTMLResponse
    from google.cloud import bigquery

    router = APIRouter(dependencies=[Depends(require_admin)])

    def query(sql, parameters=None):
        return list(get_bigquery_client().query(
            sql, job_config=bigquery.QueryJobConfig(
                query_parameters=parameters or [],
                maximum_bytes_billed=1_000_000_000,
            )
        ).result(timeout=45))

    @router.get('/study/{topic}', response_class=HTMLResponse)
    def study_card(topic: str):
        card_keys = {'eligibility': 'FFAR_ELIGIBILITY', 'minors': 'FFAR_MINORS', 'representation': 'FFAR_REPRESENTATION'}
        card_key = card_keys.get(topic)
        if card_key is None:
            raise HTTPException(404, 'Fiche inconnue.')
        try:
            cards = query(f"""
                SELECT * FROM `{DATASET}.FIFA_STUDY_CARD`
                WHERE CARD_KEY=@card_key
                ORDER BY VERSION_NUMBER DESC, CREATED_AT DESC, ID_CARD DESC
                LIMIT 1
            """, [bigquery.ScalarQueryParameter('card_key','STRING',card_key)])
            if not cards:
                raise HTTPException(404, 'Fiche non créée. Exécuter le script SQL de création de cette fiche dans BigQuery.')
            card = dict(cards[0].items())
            review_ids = card.get('SOURCE_REVIEW_IDS') or []
            if not review_ids or len(review_ids) != len(set(review_ids)):
                raise ValueError('Invalid review links.')
            result = query(f"""
                SELECT * FROM `{DATASET}.FIFA_EXTRACTION_REVIEW`
                WHERE ID_REVIEW IN UNNEST(@review_ids)
                ORDER BY UNIT_ID
            """, [bigquery.ArrayQueryParameter('review_ids','STRING',review_ids)])
            reviews = [dict(r.items()) for r in result]
            if len(reviews) != len(review_ids):
                raise ValueError('Referenced reviews missing or duplicated.')
            supplements = json.loads(card.get('SUPPLEMENTS_JSON') or '[]')
            passage_ids = set(card.get('SOURCE_PASSAGE_IDS') or [])
            for section in supplements:
                passage_ids.update(section.get('SOURCE_PASSAGE_IDS') or [])
            for row in reviews:
                item = parse_item(row['PROPOSED_ITEM_JSON'])
                passage_ids.update(p['passage_id'] for p in item.get('evidence',[]))
            sources = {}
            if passage_ids:
                result = query(f"""
                    SELECT p.ID_PASSAGE, p.PAGE_START, p.EXACT_TEXT,
                           d.TITLE, d.EDITION, d.SOURCE_URL
                    FROM `{DATASET}.FIFA_PASSAGE` AS p
                    JOIN `{DATASET}.FIFA_DOCUMENT` AS d
                      ON d.ID_DOCUMENT=p.ID_DOCUMENT
                    WHERE p.ID_PASSAGE IN UNNEST(@passage_ids)
                """, [bigquery.ArrayQueryParameter('passage_ids','STRING',sorted(passage_ids))])
                sources = {r.ID_PASSAGE:dict(r.items()) for r in result}
            if set(sources) != passage_ids:
                raise ValueError('Referenced passages missing.')
            html = render_study_page(card, reviews, sources)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error('Study card failed (%s)',type(exc).__name__)
            raise HTTPException(503,'Fiche indisponible. Vérifier les tables et les accès BigQuery dans les logs Render.') from None
        return HTMLResponse(html,headers={'Cache-Control':'no-store'})

    return router
