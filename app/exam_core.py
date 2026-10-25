"""Versioned pedagogical exams; exact-set scoring, not an official FIFA bank."""
import json,random,time
from pathlib import Path
from app.practice_core import digest,strings
ROOT=Path(__file__).parent/'data'
REASONS={'KNOWLEDGE':'Connaissance oubliée','APPLICATION':'Mauvaise application de la règle','READING':'Détail mal lu','CORPUS':'Fiche manquante ou ambiguë — à examiner'}
def load_exam(corpus):
 bank=json.loads((ROOT/'practice_exam.json').read_text());known={x['information_id']:x for x in corpus}
 if len(bank)!=40 or len({q['id'] for q in bank})!=40:raise ValueError('Invalid exam bank')
 for q in bank:
  choices=q['choices'];answers=q['approved_answers']
  if set(choices)!=set('ABCD') or len(set(choices.values()))!=4:raise ValueError('Invalid choices')
  if not answers or len(answers)!=len(set(answers)) or not set(answers)<=set(choices):raise ValueError('Invalid answers')
  if q['answer_mode']!=('MULTIPLE_CHOICE' if len(answers)>1 else 'SINGLE_CHOICE'):raise ValueError('Invalid answer mode')
  if set(q['option_explanations'])!=set(choices) or not all(q['option_explanations'].values()):raise ValueError('Missing option explanation')
  if not q['information_ids'] or any(i not in known for i in q['information_ids']):raise ValueError('Unknown source')
  if {p['information_id'] for p in q['support_quotes']}!=set(q['information_ids']):raise ValueError('Missing proof')
  for p in q['support_quotes']:
   if not p['quote'] or not any(p['quote'] in s for s in strings(known[p['information_id']]['content'])):raise ValueError('Inexact proof')
 return bank

def select_exam(bank,history,limit=20):
 seen={}
 for event in history:
  for item in event.get('score',{}).get('items',[]):seen[item['question_id']]=seen.get(item['question_id'],0)+1
 pool=list(bank);rng=random.SystemRandom();rng.shuffle(pool);out=[];themes={}
 while pool and len(out)<limit:
  i=min(range(len(pool)),key=lambda i:(seen.get(pool[i]['id'],0),themes.get(pool[i]['theme'],0)))
  q=pool.pop(i);out.append(q['id']);themes[q['theme']]=themes.get(q['theme'],0)+1
 rng.shuffle(out);return out

def score_exam(bank,ids,answers):
 by={q['id']:q for q in bank}
 if len(ids)!=20 or len(set(ids))!=20 or any(i not in by for i in ids):raise ValueError('Invalid exam series')
 items=[]
 for id in ids:
  q=by[id];selected=answers.get(id,[])
  if not isinstance(selected,list) or len(selected)!=len(set(selected)) or not set(selected)<=set(q['choices']):raise ValueError('Invalid choices')
  if q['answer_mode']=='SINGLE_CHOICE' and len(selected)>1:raise ValueError('Single choice required')
  items.append({'question_id':id,'selected':sorted(selected),'approved_answers':sorted(q['approved_answers']),'correct':bool(selected) and set(selected)==set(q['approved_answers']),'abstained':not bool(selected)})
 correct=sum(x['correct'] for x in items)
 return {'items':items,'total':20,'correct':correct,'percentage':correct*5,'abstentions':sum(x['abstained'] for x in items),'threshold_reached':correct>=15}

def time_status(session,now=None):
 now=time.time() if now is None else now
 return 'UNTIMED' if session['deadline'] is None else 'ON_TIME' if now<=session['deadline']+5 else 'LATE'
