"""Prepare several FFAR articles, then optionally extract sequentially."""
import argparse,subprocess
from app.batch_core import parse_articles,execute_batch
from app.extraction_core import Fragment,prepare_article,build_source_spans


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--articles',required=True,help='Exemple : 1-3,22-28')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    try:articles=parse_articles(args.articles)
    except ValueError as exc:parser.error(str(exc))
    from google.cloud import bigquery
    client=bigquery.Client(project='myagent-512316',location='europe-west1')
    rows=list(client.query('''SELECT ID_PASSAGE,PAGE_START,EXACT_TEXT
        FROM `myagent-512316.MYAGENT.FIFA_PASSAGE`
        WHERE ID_DOCUMENT=@document AND CORPUS_SECTION_ID='FOOTBALL_AGENT_REGULATIONS'
        ORDER BY PAGE_START''',job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter('document','STRING','DOC_FIFA_EXAM_STUDY_MATERIALS_2026_01_EN')],maximum_bytes_billed=1_000_000_000)).result(timeout=60))
    pages=[Fragment(r.ID_PASSAGE,r.PAGE_START,r.EXACT_TEXT) for r in rows]
    failures=[]
    for number in articles:
        try:
            article=prepare_article(pages,number,include_parents=True)
            build_source_spans(article)
            print(f'Article {number} : {len(article.units)} unités — '+', '.join(u.unit_id for u in article.units),flush=True)
        except Exception as exc:
            failures.append(number)
            print(f'Article {number} : préparation bloquée — {type(exc).__name__}: {exc}',flush=True)
    if failures:
        print('Lot arrêté avant tout appel OpenAI. Articles à examiner : '+', '.join(map(str,failures)))
        raise SystemExit(1)
    if not args.execute:
        print(f'Préparation terminée : {len(articles)} articles. Aucun appel OpenAI ni écriture BigQuery.')
        print('Pour extraire le lot : python -m app.batch_extract --articles '+args.articles+' --execute')
        return
    print(f'Exécution séquentielle : au maximum {2*len(articles)} appels OpenAI payants, moins pour les exécutions identiques déjà enregistrées.',flush=True)
    completed=execute_batch(articles,lambda command:subprocess.run(command,check=False))
    print('Récapitulatif des commandes : '+', '.join(f'{a}: '+('terminée' if code==0 else 'échec') for a,code in completed))
    print('Un statut NEEDS_REVIEW ne bloque pas le lot ; un échec technique l’arrête. Aucun nouvel essai automatique.')
    print('Télécharger les résultats depuis /study, section Exporter des extractions.')
    if completed and completed[-1][1]:raise SystemExit(completed[-1][1])

if __name__=='__main__':main()
