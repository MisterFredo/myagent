"""Read-only checks of an existing run. No OpenAI calls or BigQuery writes."""
import argparse
import json
import uuid
from app.extraction_checks import check_extraction


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    args=parser.parse_args()
    try:run_id=str(uuid.UUID(args.run))
    except ValueError:parser.error('--run doit être un UUID.')
    from google.cloud import bigquery
    client=bigquery.Client(project='myagent-512316',location='europe-west1')
    rows=list(client.query('''SELECT ID_RUN,STATUS,RESULT_JSON
        FROM `myagent-512316.MYAGENT.FIFA_EXTRACTION_RUN`
        WHERE ID_RUN=@run LIMIT 2''',job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('run','STRING',run_id)],
        maximum_bytes_billed=1_000_000_000)).result(timeout=45))
    if len(rows)!=1:raise SystemExit('Exécution absente ou dupliquée.')
    payload=json.loads(rows[0].RESULT_JSON or '{}')
    issues=check_extraction(payload)
    print(f'Exécution : {run_id} ; statut enregistré : {rows[0].STATUS}')
    print(f'Points signalés : {len(issues)}')
    print(json.dumps(issues,ensure_ascii=False,indent=2))
    print('Lecture seule. Aucun appel OpenAI, aucune écriture BigQuery.')
    print('Contrôles ciblés ; une liste vide ne certifie pas la complétude juridique.')
    raise SystemExit(2 if issues else 0)

if __name__=='__main__':main()
