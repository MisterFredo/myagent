"""Targeted regression checks. They do not certify legal completeness."""
import re
import unicodedata


def norm(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', value or '')).lower()


def details(item):
    return norm(' '.join([item.get('statement_fr','')] + [
        c.get('text_fr','') for field in ('conditions','exceptions','consequences')
        for c in item.get(field,[])]))


def check_extraction(payload):
    extraction = payload.get('extraction') or {}
    items = extraction.get('items') or []
    issues = []
    def issue(code, unit, message):
        issues.append({'code':code,'unit_id':unit,'message':message})
    if not items:
        issue('NO_EXTRACTION','ARTICLE','Aucune extraction exploitable.')
        return issues
    by_id = {}
    for item in items:
        key = item.get('unit_id','')
        if key in by_id:issue('DUPLICATE',key,'Unité dupliquée.')
        by_id[key]=item
        if item.get('disposition') != 'Article '+key:
            issue('REFERENCE',key,'La référence précise diffère de UNIT_ID.')
    if all(not item.get(f) for item in items for f in ('conditions','exceptions','consequences')):
        issue('EMPTY_STRUCTURE','ARTICLE','Conditions, exceptions et conséquences sont vides dans toutes les unités : revue nécessaire, sans conclure que chaque unité exige ces champs.')

    # Gold checks are deliberately article-specific. No inferred rule is applied
    # to unrelated articles. Evidence is read only as a trigger, never as coverage.
    if any(k.startswith('12.') for k in by_id):
        x=by_id.get('12.8.a')
        if x:
            source=norm(' '.join(p.get('quote','') for p in x.get('evidence',[])))
            text=details(x)
            if 'prior' in source and not re.search(r'préalabl|prealabl|avant|antérieur',text):
                issue('PRIOR_CONSENT','12.8.a','Le consentement préalable figure dans la source mais pas dans les détails français.')
        x=by_id.get('12.3')
        if x:
            short=norm(x.get('summary_fr',''))
            if 'individu' not in short:
                issue('SUMMARY_SCOPE','12.3','Le résumé de la limite de durée ne précise pas son application aux individus.')
            if re.search(r'sauf\s+renégociation|sauf\s+renegociation',short):
                issue('SUMMARY_EXTENSION','12.3','« Sauf renégociation » doit être remplacé par la formulation précise sur le nouvel accord.')
        x=by_id.get('12.4')
        texts=[details(x)] if x else []
        texts += [details(by_id[k]) for k in ('12.4.a','12.4.b') if k in by_id]
        if not any(re.search(r'(?:un|1) seul accord',t) and 'individu' in t for t in texts):
            issue('PARENT_EXCLUSIVITY','12.4','La règle d’un seul accord avec le même individu n’est pas explicitement retrouvée.')
        if x and not all(re.search(r'avant',details(by_id.get(k,{}))) for k in ('12.4.a','12.4.b')):
            issue('INHERITED_TIMING','12.4.a/b','Le caractère préalable à la conclusion ou modification doit être explicite dans les unités filles, ou être hérité par des liens structurés vérifiables.')
        x=by_id.get('12.14')
        texts=[details(x)] if x else []
        texts += [details(by_id[k]) for k in ('12.14.a','12.14.b','12.14.c') if k in by_id]
        whole=' '.join(texts)
        if not ('sans juste cause' in whole and re.search(r'indemnis|dommages',whole)):
            issue('TERMINATION_DAMAGE','12.14','Indemnisation des dommages en cas de résiliation sans juste cause non retrouvée.')
        if not re.search(r'non exhaust|pas limit|sans s.y limiter|notamment',whole):
            issue('TERMINATION_EXAMPLES','12.14','Le caractère non exhaustif des exemples de juste cause n’est pas explicite.')
    checks=(payload.get('audit') or {}).get('source_checks') or []
    comparable=[]
    for check in checks:
        for entry in check.get('details',[]):
            target=entry.get('target_unit_ids') or []
            if len(target)==1 and target[0] in by_id:
                comparable.append(norm(entry.get('source_detail_fr')) == norm(by_id[target[0]].get('summary_fr')))
    if len(comparable)>=5 and sum(comparable)/len(comparable)>=0.8:
        issue('AUDIT_REPEATS_SUMMARIES','AUDIT','Au moins 80 % des détails sources comparables recopient exactement le résumé : cela ne démontre pas une décomposition indépendante des exigences.')
    return issues
