"""Study cards read versioned reviews; they never replace or validate them."""
from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
import re
from app.batch_core import parse_articles

from app.review import safe, claims, strings, official_link, parse_item


DATASET = "myagent-512316.MYAGENT"
logger = logging.getLogger("myagent.study")


REFERENCE_TOPICS = {'representation': ('REF_FFAR_ARTICLE_12_V1', 'Accord de représentation'), 'licensing': ('REF_FFAR_ARTICLE_17_V1', 'Maintien de la licence'), 'becoming-agent': ('REF_FFAR_BECOMING_AGENT_V1', 'Devenir agent'), 'agency-clients': ('REF_FFAR_AGENCY_CLIENTS_V1', 'Agents, agences et clients'), 'fees': ('REF_FFAR_FEES_V1', 'Honoraires'), 'agent-duties': ('REF_FFAR_AGENT_DUTIES_V1', 'Droits et obligations des agents'), 'disputes-discipline': ('REF_FFAR_DISCLOSURE_DISPUTES_DISCIPLINE_V1', 'Publication, litiges et discipline')}


# Stable learning order; unknown future cards follow the numbered core.
STUDY_ORDER = {'framework': 1, 'becoming-agent': 2, 'eligibility': 3, 'licensing': 4, 'agency-clients': 5, 'representation': 6, 'minors': 7, 'agent-duties': 8, 'fees': 9, 'disputes-discipline': 10, 'final-provisions': 11, 'rstp-status-registration': 12, 'rstp-contracts': 13, 'rstp-minors': 14, 'rstp-third-parties': 15, 'rstp-training-solidarity': 16, 'clearing-house': 17, 'safeguarding-risks': 18, 'safeguarding-response': 19, 'ethical-recruitment': 20, 'ethics-core': 21, 'discipline-core': 22, 'tribunal-procedure': 23, 'fifa-institutions': 24}


def numbered_title(slug, title):
    number = STUDY_ORDER.get(slug)
    return f"{number:02d}. {title}" if number is not None else title


def study_sort_key(entry):
    return (STUDY_ORDER.get(entry['slug'], 10000), entry['title'].casefold())


def reference_identity(row):
    reference = json.loads(row['CONTENT_JSON'])
    meta = reference.get('card') or {}
    slug, title = meta.get('slug'), meta.get('title')
    if not slug:
        match = next(((k,v) for k,v in REFERENCE_TOPICS.items() if v[0] == row['ID_REFERENCE']), None)
        if match:
            slug, (_, fallback_title) = match
            title = title or fallback_title
    if not isinstance(slug,str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug) or len(slug)>80:
        raise ValueError('Reference card slug missing or invalid.')
    if slug in ('eligibility','minors'):
        raise ValueError('Reference slug conflicts with legacy card.')
    if not isinstance(title,str) or not title.strip():
        raise ValueError('Reference card title missing.')
    return slug,title


def render_catalog(entries):
    entries = sorted(entries, key=study_sort_key)
    cards=''.join('<article><h2><a href="/study/'+safe(e['slug'])+'">'+safe(numbered_title(e['slug'], e['title']))+'</a></h2><p>'+safe(e['status'])+' · '+safe(e['count'])+' informations</p></article>' for e in entries)
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>MYAGENT — Fiches</title>'
            '<style>body{font:16px/1.65 system-ui;background:#f5f6f8;color:#172033;margin:0}main{max-width:1050px;margin:auto;padding:32px 20px}article,section{background:white;border:1px solid #e1e5ec;border-radius:12px;padding:24px;margin:16px 0}a{color:#284f9b}input,button{font:inherit;padding:10px;max-width:100%;box-sizing:border-box}h2{font-size:21px}</style></head><body><main>'
            '<nav><a href="/">Informations</a></nav><h1>Mes fiches</h1><p>Supports de travail et sources. Le statut de chaque fiche indique sa revue ; leur nombre ne mesure pas la couverture du programme.</p>'+cards+
            '<section><h2>Exporter des extractions</h2><p>Télécharger les derniers résultats des articles choisis pour les faire relire, sans requête SQL.</p><form action="/exports/extractions" method="get"><label>Articles <input name="articles" value="1-3,22-28" maxlength="200" required></label> <button>Télécharger le JSON</button></form></section></main></body></html>')


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
    time_block = strings(item.get('temporal_scope_fr') or [])
    notes_block = strings(item.get('review_notes') or [])
    source_quotes = ''.join(
        '<details class="source"><summary>Extrait exact — ' + safe(e.get('unit_id')) +
        '</summary><pre>' + safe(e.get('quote')) + '</pre></details>'
        for e in item.get('evidence', []) if e.get('quote')
    )
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
      {'<h4>Temps et délais</h4>' + time_block if time_block else ''}
      {'<h4>Précisions de lecture</h4>' + notes_block if notes_block else ''}
      {'<h4>Renvois à étudier</h4>' + strings(dependencies) if dependencies else ''}
      <p class="muted small">{status}. Une liste d’exceptions vide n’établit pas leur absence.</p>
      <details class="evidence"><summary>Vérifier les textes sources</summary>
      {source_quotes}
      {render_sources(passage_ids, sources)}
      </details>
    </details>"""


def render_fee_table(rows):
    if not rows:
        return ''
    body = ''.join('<tr>' + ''.join('<td>' + safe(row.get(k)) + '</td>' for k in ('CLIENT','BASE','FIRST','EXCESS')) + '</tr>' for row in rows)
    return ('<section class="card"><h2>Tableau du texte source — applicabilité à vérifier</h2>'
            '<p>Barème de l’article 15.2, lu avec la règle de l’excédent de 15.2.b. Les plafonds ci-dessous ne sont pas présentés comme actuellement applicables.</p>'
            '<div style="overflow-x:auto"><table><thead><tr><th>Client</th><th>Assiette</th><th>Premiers 200 000 USD de rémunération annuelle</th><th>Part excédant 200 000 USD</th></tr></thead><tbody>' + body + '</tbody></table></div>'
            '<p>Pour l’entité libératrice, le plafond est 10 % de l’indemnité de transfert après exclusions, sans application des tranches de rémunération. Le seuil 200 000 USD s’entend aussi en montant équivalent.</p>'
            '<p>Les extraits exacts du tableau sont consultables dans les informations sur les plafonds ci-dessous.</p></section>')


def render_deadline_table(rows):
    if not rows:
        return ''
    body = ''.join('<tr>' + ''.join('<td>' + safe(row.get(k)) + '</td>' for k in ('EVENT','DEADLINE','PROVISION')) + '</tr>' for row in rows)
    return ('<section class="card"><h2>Délais et points de départ dans le texte source</h2><p>Lire avec les conditions détaillées ci-dessous. Applicabilité et périmètre d’examen à vérifier.</p><div style="overflow-x:auto"><table><thead><tr><th>Situation</th><th>Délai ou déclencheur</th><th>Référence</th></tr></thead><tbody>' + body + '</tbody></table></div></section>')


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
    fee_table = render_fee_table(card.get('FEE_CAP_TABLE'))
    deadline_table = render_deadline_table(card.get('DEADLINE_TABLE'))
    reference_label = card.get('REFERENCE_LABEL') or ''
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
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border:1px solid #e1e5ec;padding:12px;text-align:left;vertical-align:top}}th{{background:#f5f6f8}}li{{margin:7px 0}}.toc{{display:flex;flex-wrap:wrap;gap:10px 24px;margin:24px 0}}
@media(max-width:550px){{.card{{padding:20px}}.ref{{display:block}}}}
@media print{{body{{background:white}}main{{max-width:none;padding:0}}nav,.toc{{display:none}}.card{{border:0;padding:10px 0}}}}
</style></head><body><main>
<nav><a href="/study">Toutes les fiches</a><a href="/">Informations</a><a href="{safe(review_url)}">Revue des extractions</a>
<a href="/study/eligibility">Éligibilité</a><a href="/study/minors">Mineurs</a><a href="/study/representation">Représentation</a><a href="/study/licensing">Maintien de la licence</a><a href="/study/becoming-agent">Devenir agent</a><a href="/study/agency-clients">Agents et clients</a><a href="/study/fees">Honoraires</a><a href="/study/agent-duties">Obligations des agents</a><a href="/study/disputes-discipline">Litiges et discipline</a></nav>
<div class="label">MYAGENT / FICHE DE RÉVISION</div>
<h1>{safe(card['TITLE'])}</h1><span class="badge">{status}</span>
<p class="muted small">{safe(reference_label)}</p>
<p>{safe(card.get('INTRODUCTION'))}</p>
<p class="muted small">La fiche présente {len(reviews)} informations de travail. Aucune validation juridique experte n’est enregistrée. Les versions sources sont conservées ; le statut juridique actuel et le programme 2027 restent à confirmer.</p>
<div class="toc"><a href="#conditions">Informations à connaître</a>
<a href="#definitions">Définitions et renvois</a><a href="#pending">Points ouverts</a></div>
{fee_table}
{deadline_table}
<section class="card" id="conditions"><h2>Les informations à connaître</h2>
<p class="muted">Ouvre une information pour étudier son énoncé, sa portée et ses sources.</p>
{unit_html}</section>
<section class="card" id="definitions"><h2>Définitions et renvois</h2>
<p class="muted">Compléments de lecture liés à la fiche. Leur présence ne vaut pas validation juridique.</p>
{''.join(supplements_html)}</section>
<section class="card pending" id="pending"><h2>Points restant à vérifier</h2>
{strings(card.get('OPEN_POINTS'))}</section>
</main></body></html>"""


def reference_as_card(row):
    """Adapt the stored reference for display without changing database contents."""
    reference = json.loads(row['CONTENT_JSON'])
    if (reference.get('reference_id') != row['ID_REFERENCE']
        or reference.get('version') != row['VERSION_NUMBER']
        or reference.get('status') != row['STATUS']):
        raise ValueError('Reference metadata mismatch.')
    requirements = reference.get('requirements')
    if not isinstance(requirements, list) or not requirements:
        raise ValueError('Reference requirements missing.')
    ids = [r['requirement_id'] for r in requirements]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate reference requirements.')
    reviews = []
    passage_ids = set()
    for requirement in requirements:
        evidence = requirement.get('evidence') or []
        if not evidence or any(not e.get('quote') or not e.get('passage_id') for e in evidence):
            raise ValueError('Requirement evidence missing.')
        passage_ids.update(e['passage_id'] for e in evidence)
        actors = requirement.get('actors_fr') or []
        logic = requirement.get('condition_logic')
        logic_labels = {'ALL':'Conditions cumulatives', 'ANY':'Conditions alternatives',
                        'COMPLEX':'Logique à lire avec les précisions',
                        'NOT_APPLICABLE':'Aucune logique de conditions spécifiée'}
        if logic not in logic_labels:
            raise ValueError('Unknown condition logic.')
        item = {
            'title_fr':requirement['title_fr'],
            'summary_fr':' · '.join(requirement['provisions']) + ' — ' + ', '.join(actors),
            'statement_fr':requirement['action_fr'],
            'evidence':evidence,
            'temporal_scope_fr':requirement.get('temporal_scope_fr') or [],
            'review_notes':([logic_labels[logic]] if requirement.get('conditions_fr') else []) + (requirement.get('review_notes') or []),
            'unresolved_references':requirement.get('unresolved_references') or [],
        }
        for src, dest in [('conditions_fr','conditions'),('exceptions_fr','exceptions'),('consequences_fr','consequences')]:
            item[dest] = [{'text_fr':t} for t in requirement.get(src,[])]
        reviews.append({'UNIT_ID':requirement['requirement_id'],
                        'REVIEW_STATUS':row['STATUS'],
                        'PROPOSED_ITEM_JSON':json.dumps(item,ensure_ascii=False)})
    is_licensing = row['ID_REFERENCE'] == 'REF_FFAR_ARTICLE_17_V1'
    card = {'TITLE':'Maintien de la licence' if is_licensing else 'Accord de représentation', 'STATUS':row['STATUS'],
            'INTRODUCTION':'Article 12 : conclusion de l’accord, durée, mentions minimales, représentation des parties et résiliation. Les paragraphes 8 à 10 nécessitent une vérification séparée de leur applicabilité et de leur inclusion au programme de la session visée.',
            'REFERENCE_LABEL':row['ID_REFERENCE'] + ' · version ' + str(row['VERSION_NUMBER']),
            'SUPPLEMENTS_JSON':'[]', 'OPEN_POINTS':reference.get('open_points') or [],
            'SOURCE_PASSAGE_IDS':sorted(passage_ids)}
    if is_licensing:
        card['INTRODUCTION'] = 'Article 17 : suspension provisoire automatique, contrôle des exigences et procédures distinctes pour l’éligibilité et les autres manquements.'
    if row['ID_REFERENCE'] == 'REF_FFAR_BECOMING_AGENT_V1':
        card['TITLE'] = 'Devenir agent'
        card['INTRODUCTION'] = 'Articles 4 et 6 à 10 : demande, examen, redevance, délivrance, formation continue et cessation volontaire. Compléter cette lecture avec les fiches Éligibilité et Maintien de la licence.'
    if row['ID_REFERENCE'] == 'REF_FFAR_AGENCY_CLIENTS_V1':
        card['TITLE'] = 'Agents, agences et clients'
        card['INTRODUCTION'] = 'Articles 11 et 18 : exercice via une agence, responsabilité, droits des clients, obligations des clubs dans TMS et comportements interdits. Les renvois au RSTP et aux définitions restent signalés.'
    if row['ID_REFERENCE'] == 'REF_FFAR_FEES_V1':
        card['TITLE'] = 'Honoraires'
        card['INTRODUCTION'] = 'Articles 14 et 15 du corpus : principes de paiement, exceptions, assiettes et plafonds. Applicabilité actuelle et inclusion au programme de la session à vérifier séparément.'
        card['FEE_CAP_TABLE'] = reference.get('fee_cap_table') or []
    if row['ID_REFERENCE'] == 'REF_FFAR_AGENT_DUTIES_V1':
        card['TITLE'] = 'Droits et obligations des agents'
        card['INTRODUCTION'] = 'Article 16 : approche et exclusivité, obligations professionnelles, déclarations sur la plateforme, comportements interdits et information du client.'
        card['DEADLINE_TABLE'] = reference.get('deadline_table') or []
    if row['ID_REFERENCE'] == 'REF_FFAR_DISCLOSURE_DISPUTES_DISCIPLINE_V1':
        card['TITLE'] = 'Publication, litiges et discipline'
        card['INTRODUCTION'] = 'Articles 19 à 21 du corpus : informations mises à disposition, compétence pour les litiges, sanctions et coopération. Applicabilité actuelle et périmètre d’examen à vérifier séparément.'
    metadata = reference.get('card') or {}
    if metadata:
        _, card['TITLE'] = reference_identity(row)
        card['INTRODUCTION'] = metadata.get('introduction') or ''
        card['FEE_CAP_TABLE'] = reference.get('fee_cap_table') or []
        card['DEADLINE_TABLE'] = reference.get('deadline_table') or []
    return card, reviews


def build_study_router(require_admin, get_bigquery_client):
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.responses import HTMLResponse, Response
    from google.cloud import bigquery

    router = APIRouter(dependencies=[Depends(require_admin)])

    def query(sql, parameters=None):
        return list(get_bigquery_client().query(
            sql, job_config=bigquery.QueryJobConfig(
                query_parameters=parameters or [],
                maximum_bytes_billed=1_000_000_000,
            )
        ).result(timeout=45))

    @router.get('/study', response_class=HTMLResponse)
    def study_catalog():
        try:
            rows=query(f"""SELECT ID_REFERENCE,VERSION_NUMBER,STATUS,CONTENT_JSON
                FROM `{DATASET}.FIFA_REQUIREMENT_REFERENCE`
                ORDER BY VERSION_NUMBER DESC, CREATED_AT DESC, ID_REFERENCE DESC""")
            entries=[]
            seen=set()
            for row in rows:
                row=dict(row.items())
                # References without any card metadata and without an old mapping
                # are data-only and deliberately not listed as study cards.
                ref=json.loads(row['CONTENT_JSON'])
                if not ref.get('card') and row['ID_REFERENCE'] not in {v[0] for v in REFERENCE_TOPICS.values()}:
                    continue
                slug,title=reference_identity(row)
                if slug in seen:
                    continue
                seen.add(slug)
                entries.append({'slug':slug,'title':title,'status':row['STATUS'],
                                'count':len(ref.get('requirements') or [])})
            legacy=query(f"""SELECT CARD_KEY,TITLE,STATUS,SOURCE_REVIEW_IDS
                FROM `{DATASET}.FIFA_STUDY_CARD`
                WHERE CARD_KEY IN ('FFAR_ELIGIBILITY','FFAR_MINORS')
                QUALIFY ROW_NUMBER() OVER(PARTITION BY CARD_KEY ORDER BY VERSION_NUMBER DESC,CREATED_AT DESC,ID_CARD DESC)=1""")
            for row in legacy:
                entries.append({'slug':{'FFAR_ELIGIBILITY':'eligibility','FFAR_MINORS':'minors'}[row.CARD_KEY],
                                'title':row.TITLE,'status':row.STATUS,'count':len(row.SOURCE_REVIEW_IDS or [])})
            return HTMLResponse(render_catalog(entries),headers={'Cache-Control':'no-store'})
        except Exception as exc:
            logger.error('Study catalogue failed (%s)',type(exc).__name__)
            raise HTTPException(503,'Catalogue indisponible. Vérifier les logs Render.') from None

    @router.get('/exports/extractions')
    def export_extractions(articles: str = '1-3,22-28'):
        try:
            numbers=parse_articles(articles)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from None
        try:
            rows=query(f"""WITH candidates AS (
                SELECT ID_RUN,STATUS,CHECK_ERRORS,MODEL,STARTED_AT,
                SAFE_CAST(JSON_VALUE(RESULT_JSON,'$.article.article') AS INT64) AS ARTICLE,
                JSON_QUERY(RESULT_JSON,'$.article.source_spans') AS SOURCE_SPANS,
                JSON_QUERY(RESULT_JSON,'$.extraction') AS EXTRACTION,
                JSON_QUERY(RESULT_JSON,'$.extraction_selected_spans') AS EXTRACTION_SELECTED_SPANS,
                JSON_QUERY(RESULT_JSON,'$.audit') AS AUDIT
                FROM `{DATASET}.FIFA_EXTRACTION_RUN`
                WHERE PROMPT_VERSION='FFAR_ARTICLE_SOURCE_SPANS_V5'
                  AND SAFE_CAST(JSON_VALUE(RESULT_JSON,'$.article.article') AS INT64) IN UNNEST(@articles)
                ) SELECT * FROM candidates
                QUALIFY ROW_NUMBER() OVER(PARTITION BY ARTICLE ORDER BY STARTED_AT DESC,ID_RUN DESC)=1
                ORDER BY ARTICLE""",[bigquery.ArrayQueryParameter('articles','INT64',numbers)])
            found=[]
            for row in rows:
                item=dict(row.items())
                for field in ('SOURCE_SPANS','EXTRACTION','EXTRACTION_SELECTED_SPANS','AUDIT'):
                    item[field]=json.loads(item[field]) if item.get(field) else None
                item['STARTED_AT']=item['STARTED_AT'].isoformat() if item.get('STARTED_AT') else None
                found.append(item)
            payload={'format_version':1,'requested_articles':numbers,
                     'missing_articles':sorted(set(numbers)-{r['ARTICLE'] for r in found}),
                     'runs':found}
            return Response(content=json.dumps(payload,ensure_ascii=False,indent=2),media_type='application/json',headers={
                'Cache-Control':'no-store','Content-Disposition':'attachment; filename="MYAGENT_extractions.json"'})
        except Exception as exc:
            logger.error('Extraction export failed (%s)',type(exc).__name__)
            raise HTTPException(503,'Export indisponible. Vérifier les logs Render.') from None

    @router.get('/study/{topic}', response_class=HTMLResponse)
    def study_card(topic: str):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',topic) or len(topic)>80:
            raise HTTPException(404,'Fiche inconnue.')
        card_key={'eligibility':'FFAR_ELIGIBILITY','minors':'FFAR_MINORS'}.get(topic)
        try:
            if card_key is None:
                known=REFERENCE_TOPICS.get(topic)
                reference_id=known[0] if known else None
                rows=query(f"""
                    SELECT ID_REFERENCE,VERSION_NUMBER,STATUS,CONTENT_JSON
                    FROM `{DATASET}.FIFA_REQUIREMENT_REFERENCE`
                    WHERE ID_REFERENCE=@reference_id
                       OR JSON_VALUE(CONTENT_JSON,'$.card.slug')=@topic
                    ORDER BY VERSION_NUMBER DESC,CREATED_AT DESC,ID_REFERENCE DESC
                    LIMIT 2
                """,[bigquery.ScalarQueryParameter('reference_id','STRING',reference_id),
                      bigquery.ScalarQueryParameter('topic','STRING',topic)])
                if not rows:
                    raise HTTPException(404,'Fiche absente.')
                if len(rows)>1 and rows[0].VERSION_NUMBER==rows[1].VERSION_NUMBER:
                    raise ValueError('Ambiguous reference version.')
                card, reviews = reference_as_card(dict(rows[0].items()))
                passage_ids = card['SOURCE_PASSAGE_IDS']
                result = query(f"""
                    SELECT p.ID_PASSAGE, p.PAGE_START, p.EXACT_TEXT,
                           d.TITLE, d.EDITION, d.SOURCE_URL
                    FROM `{DATASET}.FIFA_PASSAGE` p
                    JOIN `{DATASET}.FIFA_DOCUMENT` d ON d.ID_DOCUMENT=p.ID_DOCUMENT
                    WHERE p.ID_PASSAGE IN UNNEST(@passage_ids)
                """, [bigquery.ArrayQueryParameter('passage_ids','STRING',passage_ids)])
                sources = {r.ID_PASSAGE:dict(r.items()) for r in result}
                if len(result) != len(passage_ids) or set(sources) != set(passage_ids):
                    raise ValueError('Reference source pages missing or duplicated.')
                for review in reviews:
                    for proof in parse_item(review['PROPOSED_ITEM_JSON'])['evidence']:
                        if proof['quote'] not in sources[proof['passage_id']]['EXACT_TEXT']:
                            raise ValueError('Reference quote differs from stored passage.')
                card = dict(card, TITLE=numbered_title(topic, card['TITLE']))
                return HTMLResponse(render_study_page(card,reviews,sources),headers={'Cache-Control':'no-store'})
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
            card = dict(card, TITLE=numbered_title(topic, card['TITLE']))
            html = render_study_page(card, reviews, sources)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error('Study card failed (%s)',type(exc).__name__)
            raise HTTPException(503,'Fiche indisponible. Vérifier les tables et les accès BigQuery dans les logs Render.') from None
        return HTMLResponse(html,headers={'Cache-Control':'no-store'})

    return router
