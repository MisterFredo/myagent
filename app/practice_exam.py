"""Exam mode. Reuses the existing event table; no model calls."""
import json,os,re,time,uuid,random
from html import escape
from urllib.parse import parse_qs
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from app.practice_core import token,untoken,digest
from app.exam_core import load_exam,select_exam,score_exam,time_status,REASONS
DATASET='myagent-512316.MYAGENT'
def safe(x):return escape(str(x if x is not None else ''))
def build_exam_router(data,query,read_event,save_event,respond,problem):
 router=APIRouter()
 def signed(action,id=None):return token({'action':action,'id':id,'expires':int(time.time())+86400},os.environ['MYAGENT_ADMIN_PASSWORD'])
 def hidden(value):return '<input type="hidden" name="token" value="'+safe(value)+'">'
 async def fields(request,action):
  if 'application/x-www-form-urlencoded' not in request.headers.get('content-type',''):raise HTTPException(415,'Formulaire requis')
  raw=await request.body()
  if len(raw)>20000:raise HTTPException(413,'Formulaire trop volumineux')
  f=parse_qs(raw.decode(),keep_blank_values=True)
  try:
   t=untoken(f.get('token',[''])[0],os.environ['MYAGENT_ADMIN_PASSWORD'])
   if t['action']!=action:raise ValueError()
  except (KeyError,ValueError):raise HTTPException(400,'Formulaire expiré ou invalide') from None
  return f,t
 def history(kind):
  if kind not in ('EXAM','EXAM_SESSION'):raise ValueError()
  rows=query(f"SELECT ID_EVENT,CREATED_AT,PAYLOAD_JSON FROM `{DATASET}.FIFA_PRACTICE_EVENT` WHERE EVENT_TYPE='{kind}' ORDER BY CREATED_AT DESC, ID_EVENT DESC LIMIT 1000")
  return [(row,json.loads(row['PAYLOAD_JSON'])) for row in rows]
 def session(id):
  if not re.fullmatch(r'[a-f0-9-]{36}',id):raise HTTPException(404,'Session absente')
  s=read_event(id)
  if not s or s.get('kind')!='EXAM_SESSION':raise HTTPException(404,'Session absente')
  _,corpus=data();bank=load_exam(corpus)
  if s['bank_hash']!=digest(bank) or s['corpus_hash']!=digest(corpus):raise HTTPException(409,'Banque modifiée : commencer une nouvelle série.')
  return s,bank
 @router.get('/practice/exam')
 def home():
  try:
   _,corpus=data();bank=load_exam(corpus);events=history('EXAM');sessions=history('EXAM_SESSION')
  except Exception as exc:problem(exc)
  completed={e['session_id'] for _,e in events};recent=''
  for row,e in events[:10]:recent+='<li><a href="/practice/exam/session/'+safe(e['session_id'])+'">'+safe(str(row['CREATED_AT'])[:19])+' : '+str(e['score']['correct'])+'/20</a> — '+safe({'ON_TIME':'chronométré, remis à temps','LATE':'remis hors délai','UNTIMED':'sans chronomètre'}[e['time_status']])+'</li>'
  pending=''
  for row,s in sessions[:10]:
   if row['ID_EVENT'] not in completed:pending+='<li><a href="/practice/exam/session/'+safe(row['ID_EVENT'])+'">Reprendre la série du '+safe(str(row['CREATED_AT'])[:19])+'</a> — '+('sans chronomètre' if s['deadline'] is None else 'chronomètre conservé')+'</li>'
  return respond('Mode Examen', '<p><a href="/practice">Retour à l’apprentissage</a></p><section><h2>Une série de 20 questions</h2><p>Banque distincte de 40 cas pédagogiques, dont dix à réponses multiples. Le nombre de réponses attendues n’est pas donné. Pour obtenir le point, sélectionner exactement toutes les bonnes réponses : aucun point partiel.</p><p>Seuil de travail : 15/20 (75 %). Ce seuil sur notre banque ne prédit pas le résultat à l’examen officiel. Questions construites à partir de nos fiches DRAFT, non officielles ; elles ne détectent pas seules les sujets absents du corpus.</p><form method="post" action="/practice/exam/start">'+hidden(signed('exam_start'))+'<label><input type="radio" name="mode" value="untimed" checked> Sans chronomètre</label><br><label><input type="radio" name="mode" value="timed"> 60 minutes</label><p><button>Commencer les 20 questions</button></p></form><p>Correction à la fin. Aucun appel OpenAI. Les questions les moins travaillées sont privilégiées. Le chronomètre continue si la page est fermée ; une remise tardive reste corrigeable mais est signalée hors délai.</p></section><section><h2>Séries à reprendre</h2><ul>'+pending+'</ul></section><section><h2>Derniers résultats</h2><ul>'+recent+'</ul></section>')
 @router.post('/practice/exam/start')
 async def start(request:Request):
  f,t=await fields(request,'exam_start');mode=f.get('mode',[''])[0]
  if mode not in ('timed','untimed'):raise HTTPException(400,'Mode inconnu')
  def create():
   _,corpus=data();bank=load_exam(corpus);events=history('EXAM');ids=select_exam(bank,[e for _,e in events]);id=str(uuid.uuid4());now=time.time();by={q['id']:q for q in bank}
   order={i:random.SystemRandom().sample(list(by[i]['choices']),4) for i in ids}
   s={'kind':'EXAM_SESSION','ids':ids,'started_at':now,'deadline':now+3600 if mode=='timed' else None,'bank_hash':digest(bank),'corpus_hash':digest(corpus),'choice_order':order}
   save_event(id,'EXAM_SESSION',s);return id
  try:id=await run_in_threadpool(create)
  except Exception as exc:problem(exc)
  return RedirectResponse('/practice/exam/session/'+id,status_code=303,headers={'Cache-Control':'no-store'})
 def render_result(id,e,bank):
  by={q['id']:q for q in bank};s=e['score'];status=e['time_status'];valid=status!='LATE'
  study_bank,_=data();slugs={q['theme']:q['study_slug'] for q in study_bank if q.get('study_slug') and q.get('theme')}
  label={'ON_TIME':'Remis dans le délai','UNTIMED':'Sans chronomètre','LATE':'Remis hors délai : score pédagogique seulement'}[status]
  body='<p><a href="/practice/exam">Retour au mode Examen</a></p><section><h2>'+str(s['correct'])+'/20 — '+str(s['percentage'])+' %</h2><p>'+label+'</p><p>'+('Seuil de travail atteint.' if s['threshold_reached'] and valid else 'Seuil de travail non validé pour cette session.')+'</p><p>'+str(s['abstentions'])+' abstention(s). Aucun point partiel aux questions à réponses multiples.</p></section>'
  for n,item in enumerate(s['items'],1):
   q=by[item['question_id']];body+='<article><h2>'+str(n)+'. '+safe(q['question'])+'</h2><p>'+('Juste' if item['correct'] else 'Abstention' if item['abstained'] else 'À revoir')+'</p><p>Ton choix : '+safe(', '.join(item['selected']) or '—')+' ; attendu : '+safe(', '.join(item['approved_answers']))+'</p>'
   for k,v in q['choices'].items():body+='<p><strong>'+k+' — '+safe(v)+'</strong> ('+('juste' if k in q['approved_answers'] else 'faux')+')<br>'+safe(q['option_explanations'][k])+'</p>'
   body+='<details><summary>Informations utilisées</summary>'+''.join('<p>'+safe(p['information_id'])+'</p><blockquote>'+safe(p['quote'])+'</blockquote>' for p in q['support_quotes'])+'</details>'
   if q['theme'] in slugs:body+='<p><a href="/study/'+safe(slugs[q['theme']])+'">Revoir la fiche principale</a></p>'
   body+='</article>'
  errors=[x for x in s['items'] if not x['correct']]
  if errors:
   body+='<section><h2>Comprendre mes erreurs</h2><p>Classe les erreurs pour guider la révision. « Fiche manquante ou ambiguë » est un signalement à examiner, pas un diagnostic automatique.</p><form method="post" action="/practice/exam/reasons">'+hidden(signed('exam_reasons',id))
   for item in errors:
    qid=item['question_id'];saved=e.get('reasons',{}).get(qid,'');body+='<label>'+safe(by[qid]['question'])+'<br><select name="'+qid+'"><option value="">À classer</option>'+''.join('<option value="'+key+'"'+(' selected' if saved==key else '')+'>'+safe(value)+'</option>' for key,value in REASONS.items())+'</select></label><br>'
   body+='<p><button>Enregistrer mon analyse</button></p></form></section>'
  return respond('Correction de ma série',body)
 @router.get('/practice/exam/session/{id}')
 def show(id:str):
  try:s,bank=session(id);result=read_event('EXAM_RESULT_'+id)
  except HTTPException:raise
  except Exception as exc:problem(exc)
  if result:return render_result(id,result,bank)
  by={q['id']:q for q in bank};body='<p>Réponds selon le corpus étudié. Les règles et barèmes sont ceux de nos supports, sans présumer leur applicabilité actuelle. Aucun corrigé n’est fourni avant la remise.</p>'
  if s['deadline'] is not None:body+='<p id="clock" role="timer">Chronomètre en cours.</p><noscript>Le contrôle du délai fonctionne sur le serveur même sans JavaScript. Le formulaire n’est pas automatiquement remis sans JavaScript.</noscript>'
  body+='<form id="exam-form" method="post" action="/practice/exam/submit">'+hidden(signed('exam_submit',id))
  for n,qid in enumerate(s['ids'],1):
   q=by[qid];multi=q['answer_mode']=='MULTIPLE_CHOICE';body+='<article><h2>'+str(n)+'. '+safe(q['question'])+'</h2><p>'+('Plusieurs réponses possibles' if multi else 'Une seule réponse')+'</p>'
   for k in s['choice_order'][qid]:body+='<label><input type="'+('checkbox' if multi else 'radio')+'" name="'+qid+'" value="'+k+'"> '+k+'. '+safe(q['choices'][k])+'</label><br>'
   body+='</article>'
  body+='<button>Remettre et corriger</button></form>'
  # Browser state is convenience only. Signed session data and server time determine scoring.
  body+='<script>(()=>{const form=document.getElementById("exam-form"),key="myagent-exam-'+id+'";try{const saved=JSON.parse(localStorage.getItem(key)||"{}");for(const input of form.querySelectorAll("input[name]:not([type=hidden])")){input.checked=(saved[input.name]||[]).includes(input.value);}form.addEventListener("change",()=>{const data={};for(const input of form.querySelectorAll("input:checked")){(data[input.name]??=[]).push(input.value);}localStorage.setItem(key,JSON.stringify(data));});}catch(e){}'
  if s['deadline'] is not None:
   remaining=max(0,s['deadline']-time.time());body+='const stop=performance.now()+'+str(int(remaining*1000))+';let sent=false;function tick(){const left=Math.max(0,Math.ceil((stop-performance.now())/1000));document.getElementById("clock").textContent="Temps restant : "+Math.floor(left/60)+":"+String(left%60).padStart(2,"0");if(left===0&&!sent){sent=true;form.requestSubmit();}}tick();setInterval(tick,500);'
  body+='})();</script>'
  return respond('Ma série Examen',body)
 @router.post('/practice/exam/submit')
 async def submit(request:Request):
  f,t=await fields(request,'exam_submit')
  def finish():
   s,bank=session(t['id']);old=read_event('EXAM_RESULT_'+t['id'])
   if old:return render_result(t['id'],old,bank)
   try:score=score_exam(bank,s['ids'],f)
   except ValueError:raise HTTPException(400,'Réponses invalides') from None
   e={'session_id':t['id'],'score':score,'time_status':time_status(s),'elapsed_seconds':max(0,int(time.time()-s['started_at'])),'bank_hash':s['bank_hash'],'corpus_hash':s['corpus_hash'],'reasons':{}}
   save_event('EXAM_RESULT_'+t['id'],'EXAM',e);return render_result(t['id'],e,bank)
  try:return await run_in_threadpool(finish)
  except HTTPException:raise
  except Exception as exc:problem(exc)
 @router.post('/practice/exam/reasons')
 async def reasons(request:Request):
  f,t=await fields(request,'exam_reasons')
  def update():
   s,bank=session(t['id']);e=read_event('EXAM_RESULT_'+t['id'])
   if not e:raise HTTPException(404,'Résultat absent')
   allowed={x['question_id'] for x in e['score']['items'] if not x['correct']};values={}
   for key in allowed:
    value=f.get(key,[''])[0]
    if value and value not in REASONS:raise HTTPException(400,'Cause inconnue')
    if value:values[key]=value
   e['reasons']=values;save_event('EXAM_RESULT_'+t['id'],'EXAM',e)
  try:await run_in_threadpool(update)
  except HTTPException:raise
  except Exception as exc:problem(exc)
  return RedirectResponse('/practice/exam/session/'+t['id'],status_code=303,headers={'Cache-Control':'no-store'})
 return router
