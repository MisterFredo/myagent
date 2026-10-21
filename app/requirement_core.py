"""Source inventory binding. No network and no legal approval."""
from copy import deepcopy


def source_input(payload):
    article=payload.get('article') or {}
    spans=[deepcopy(s) for s in article.get('source_spans',[]) if s.get('role')=='OWN' or s.get('role','').startswith('SHARED')]
    if not spans:raise ValueError('Le run ne contient pas de fragments sources V5.')
    span_ids=[s['span_id'] for s in spans]
    if len(span_ids)!=len(set(span_ids)):raise ValueError('Fragments sources dupliqués.')
    fragments={f['passage_id']:f['text'] for f in article.get('fragments',[])}
    for s in spans:
        text=fragments.get(s['passage_id'])
        start,end=s['fragment_start'],s['fragment_end']
        if text is None or not (0<=start<end<=len(text)) or text[start:end]!=s['quote']:
            raise ValueError('Un fragment ne correspond pas à la source enregistrée.')
    # Explicitly exclude old extraction, audit, summaries and previous findings.
    return {'document_id':article['document_id'],'article':article['article'],
            'source_spans':spans,
            'hierarchy':[{k:u[k] for k in ('unit_id','own_span_ids','parent_span_ids')}
                         for u in article.get('inventory',[])]}


def bind_inventory(raw,data):
    bound=deepcopy(raw);errors=[]
    spans={s['span_id']:s for s in data['source_spans']}
    requirements=bound.get('requirements',[])
    ids=[r['requirement_id'] for r in requirements]
    if len(ids)!=len(set(ids)):errors.append('Identifiants d’exigences dupliqués.')
    if not requirements:errors.append('Inventaire sans exigence.')
    reqs={r['requirement_id']:r for r in requirements}
    for r in requirements:
        selected=r.get('source_span_ids',[])
        if not selected or len(selected)!=len(set(selected)):
            errors.append(f"{r['requirement_id']}: preuves absentes ou dupliquées.")
        if not r.get('action_fr','').strip() or not r.get('actors_fr'):
            errors.append(f"{r['requirement_id']}: action ou acteurs manquants.")
        if any(not s.strip() for s in r.get('actors_fr',[])):
            errors.append(f"{r['requirement_id']}: acteur vide.")
        for field in ('conditions_fr','exceptions_fr','consequences_fr','temporal_scope_fr','territorial_scope_fr','unresolved_references'):
            if any(not s.strip() for s in r.get(field,[])):
                errors.append(f"{r['requirement_id']}: {field} contient une valeur vide.")
        if any(s not in spans for s in selected):errors.append(f"{r['requirement_id']}: source inconnue.")
        r['evidence']=[deepcopy(spans[s]) for s in selected if s in spans]
    rows=bound.get('source_accounting',[])
    covered=[r['span_id'] for r in rows]
    if len(covered)!=len(set(covered)) or set(covered)!=set(spans):
        errors.append('Comptabilité des fragments propres incomplète ou dupliquée.')
    for row in rows:
        selected=row.get('requirement_ids',[])
        if len(selected)!=len(set(selected)):errors.append(f"{row['span_id']}: exigences dupliquées.")
        if not row.get('reason_fr','').strip():errors.append(f"{row['span_id']}: justification vide.")
        if row['status']=='CONTEXT_ONLY':
            if selected:errors.append(f"{row['span_id']}: contexte seul avec exigences attachées.")
            # Exclusion still requires a review; never silently discard a source.
            errors.append(f"{row['span_id']}: fragment classé contexte seul, à examiner.")
        elif row['status']=='REQUIREMENTS':
            if not selected:errors.append(f"{row['span_id']}: aucune exigence attachée.")
        else:errors.append(f"{row['span_id']}: statut inconnu.")
        for rid in selected:
            if rid not in reqs or row['span_id'] not in reqs[rid].get('source_span_ids',[]):
                errors.append(f"{row['span_id']}: lien réciproque manquant vers {rid}.")
    for r in requirements:
        for sid in r.get('source_span_ids',[]):
            if not any(row['span_id']==sid and r['requirement_id'] in row.get('requirement_ids',[]) for row in rows):
                errors.append(f"{r['requirement_id']}: preuve non comptabilisée {sid}.")
    for note in bound.get('review_notes',[]):errors.append('NOTE : '+note)
    # Every result stays a review candidate regardless of mechanical checks.
    return bound,sorted(set(errors))
