"""Pure helpers: source answers are never a scoring key or model input."""
import hashlib,hmac,json,os,random,time
from pathlib import Path
ROOT=Path(__file__).parent/'data'
PROMPT_VERSION='CLOSED_CORPUS_PRACTICE_V1'
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_data():
 bank=json.loads((ROOT/'practice_bank.json').read_text());corpus=json.loads((ROOT/'practice_corpus.json').read_text())
 if len(corpus)!=352 or len({x['information_id'] for x in corpus})!=352:raise ValueError('Invalid corpus snapshot')
 if len({q['id'] for q in bank})!=len(bank):raise ValueError('Duplicate bank ids')
 return bank,corpus

def pick_quiz(bank,limit=10):
 eligible=[q for q in bank if q['status']=='REVIEWED_CORPUS'];random.SystemRandom().shuffle(eligible)
 out=[];seen=set()
 for q in eligible:
  if q['family'] not in seen:out.append(q['id']);seen.add(q['family'])
 return out[:min(limit,len(out))]

def public_question(q):return {k:q[k] for k in ('id','question','choices')}

TARGETED_PROMPT_VERSION='CLOSED_CORPUS_TARGETED_V2'
def targeted_context(q,corpus):
 if q.get('family')!='minor-signature':raise ValueError('Targeted pilot unavailable')
 return [x for x in corpus if x['card_id']=='FFAR_MINORS' or (x['card_id']=='REF_FFAR_ARTICLE_12_V1' and '12.7' in str(x['content'].get('provisions',[])))]
def model_input(q,corpus,targeted=False):
 result={'question':public_question(q),'corpus':corpus}
 if targeted:result['question']['answer_mode']='SINGLE_CHOICE'
 return result

def score(bank,ids,answers):
 by={q['id']:q for q in bank};result=[]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate quiz question')
 for qid in ids:
  q=by[qid]
  if q['status']!='REVIEWED_CORPUS':raise ValueError('Unreviewed scoring forbidden')
  choice=answers.get(qid,'')
  if choice and choice not in q['choices']:raise ValueError('Invalid choice')
  result.append(dict(question_id=qid,selected=choice,correct=bool(choice) and [choice]==q['approved_answers'],abstained=not bool(choice),approved_answers=q['approved_answers'],note=q['review_note'],information_ids=q['information_ids']))
 return {'correct':sum(r['correct'] for r in result),'total':len(result),'abstentions':sum(r['abstained'] for r in result),'items':result}

def token(payload,secret):
 raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode().hex()
 return raw+'.'+hmac.new(secret.encode(),raw.encode(),'sha256').hexdigest()
def untoken(value,secret):
 try:
  raw,signature=value.split('.')
  if not hmac.compare_digest(signature,hmac.new(secret.encode(),raw.encode(),'sha256').hexdigest()):raise ValueError()
  obj=json.loads(bytes.fromhex(raw))
  if obj['expires']<time.time():raise ValueError()
  return obj
 except Exception:raise ValueError('Formulaire expiré ou invalide') from None

def strings(obj):
 if isinstance(obj,str):return [obj]
 if isinstance(obj,dict):return [s for v in obj.values() for s in strings(v)]
 if isinstance(obj,list):return [s for v in obj for s in strings(v)]
 return []

def validate_result(result,q,corpus,single_choice=False):
 known={x['information_id']:x for x in corpus};errors=[]
 if result.get('status') not in ('ANSWERABLE','PARTIAL','INSUFFICIENT'):errors.append('Statut inconnu')
 selected=result.get('selected',[])
 if single_choice and len(selected)>1:errors.append('Question à choix unique : plusieurs réponses sélectionnées')
 if len(selected)!=len(set(selected)) or any(x not in q['choices'] for x in selected):errors.append('Choix invalides')
 if result.get('status')=='INSUFFICIENT' and selected:errors.append('Abstention incohérente')
 if result.get('status')=='ANSWERABLE' and not selected:errors.append('Réponse manquante')
 opts=result.get('options',[])
 if sorted(x.get('choice','') for x in opts)!=sorted(q['choices']):errors.append('Couverture des propositions incomplète')
 for option in opts:
  verdict=option.get('verdict')
  if verdict not in ('SUPPORTED','REFUTED','UNKNOWN'):errors.append('Verdict inconnu')
  evidence=option.get('evidence',[])
  if verdict!='UNKNOWN' and not evidence:errors.append('Justification sans preuve')
  if result.get('status')=='ANSWERABLE' and verdict=='UNKNOWN':errors.append('Réponse complète avec proposition indécidable')
  for proof in evidence:
   unit=known.get(proof.get('information_id'))
   if not unit:errors.append('Identifiant inconnu');continue
   quote=proof.get('quote','')
   if not quote or not any(quote in s for s in strings(unit['content'])):errors.append('Citation absente de l’information')
 supported={x.get('choice') for x in opts if x.get('verdict')=='SUPPORTED'}
 if set(selected)!=supported:errors.append('Choix et verdicts incohérents')
 return sorted(set(errors))

def response_schema():
 def obj(fields):return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
 st={'type':'string'}
 proof=obj({'information_id':st,'quote':st})
 opt=obj({'choice':st,'verdict':{'type':'string','enum':['SUPPORTED','REFUTED','UNKNOWN']},'explanation_fr':st,'evidence':{'type':'array','items':proof}})
 return obj({'status':{'type':'string','enum':['ANSWERABLE','PARTIAL','INSUFFICIENT']},'selected':{'type':'array','items':st},'explanation_fr':st,'missing_fr':{'type':'array','items':st},'options':{'type':'array','items':opt}})
