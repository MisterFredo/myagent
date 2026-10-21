"""Recheck a saved extraction with current controls; no model calls or writes."""
import argparse,json,uuid
from app.extraction_core import (Article,Fragment,Unit,resolve_evidence,
                                check_result,check_source_coverage,
                                check_article_5_thresholds)


def recheck_payload(payload):
    data=payload['article']
    spans={s['span_id']:s for s in data['source_spans']}
    inventories=data['inventory']
    article=Article(data['article'],tuple(Fragment(f['passage_id'],f['pdf_page'],f['text']) for f in data['fragments']),
                    tuple(Unit(u['unit_id'],'',()) for u in inventories))
    resolved,errors=resolve_evidence(payload['extraction_selected_spans'],spans,inventories)
    errors += check_result(resolved,article)
    if article.number==5:errors+=check_article_5_thresholds(resolved)
    audit=payload.get('audit')
    if not audit:
        errors.append('Audit absent : relecture nécessaire.')
    else:
        errors+=check_source_coverage(audit,spans,inventories)
        reviews=audit.get('reviews',[])
        ids=[r['unit_id'] for r in reviews]
        expected={u.unit_id for u in article.units}
        if len(ids)!=len(set(ids)) or set(ids)!=expected:
            errors.append('Relecture incomplète ou dupliquée.')
        for review in reviews:
            if not review.get('source_details_checked_fr'):
                errors.append('AUDIT '+review['unit_id']+': aucun détail vérifié.')
            for field in ('omitted_details_fr','unsupported_claims_fr','scope_or_logic_errors_fr','unresolved_dependencies_fr'):
                errors.extend('AUDIT '+review['unit_id']+' '+field+': '+v for v in review.get(field,[]))
        errors.extend('AUDIT ARTICLE: '+note for note in audit.get('article_notes_fr',[]))
    return resolved,sorted(set(errors))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    args=parser.parse_args()
    try:run_id=str(uuid.UUID(args.run))
    except ValueError:parser.error('--run doit être un UUID.')
    from google.cloud import bigquery
    client=bigquery.Client(project='myagent-512316',location='europe-west1')
    rows=list(client.query('''SELECT STATUS,RESULT_JSON FROM `myagent-512316.MYAGENT.FIFA_EXTRACTION_RUN`
        WHERE ID_RUN=@run LIMIT 2''',job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('run','STRING',run_id)],maximum_bytes_billed=1_000_000_000)).result(timeout=60))
    if len(rows)!=1:raise SystemExit('Run absent ou dupliqué.')
    payload=json.loads(rows[0].RESULT_JSON or '{}')
    if not all(k in payload for k in ('article','extraction_selected_spans')):
        raise SystemExit('Ce run ne contient pas une extraction à preuves sélectionnées.')
    resolved,errors=recheck_payload(payload)
    print('Exécution : '+run_id)
    print('Statut enregistré, inchangé : '+rows[0].STATUS)
    print(f"Unités relues : {len(resolved['items'])}")
    print(f'Points mécaniques et audit déclaratif : {len(errors)}')
    print(json.dumps(errors,ensure_ascii=False,indent=2))
    print('Lecture seule : aucun appel OpenAI, aucune écriture BigQuery.')
    print('Un résultat sans alerte ne constitue ni une revue sémantique indépendante ni une validation juridique.')
    raise SystemExit(2 if errors else 0)

if __name__=='__main__':main()
