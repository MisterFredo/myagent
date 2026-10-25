"""RSTP pilot articles 2–4. Original quotes preserved; no model calls."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from copy import deepcopy


@dataclass(frozen=True)
class Fragment:
    passage_id: str
    page: int
    text: str


@dataclass(frozen=True)
class Unit:
    unit_id: str
    text: str
    inherited_context: tuple[str, ...]
    shared_context: tuple[str, ...] = ()


@dataclass(frozen=True)
class Article:
    number: int
    fragments: tuple[Fragment, ...]
    units: tuple[Unit, ...]


HEAD = re.compile(r"(?m)^[ \t]*Article[ \t]+(\d+)[ \t]*:")
MARK = re.compile(
    r"(?m)^[ \t]*(?:(?P<number>\d+)\.|(?P<letter>[a-z])[ \t\r\n]*\)|"
    r"(?P<roman>[ivxlcdm]+)\.)[ \t\r\n]+"
)


def normalize(text: str) -> str:
    # Do not delete numbering, punctuation or substantive words to force matches.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def inventory(number: int, text: str, include_parents: bool = False) -> tuple[Unit, ...]:
    markers = list(MARK.finditer(text))
    if not markers:
        raise ValueError(f"Article {number}: no paragraph markers; manual review required.")
    nodes = []
    paragraph = letter = None
    for i, marker in enumerate(markers):
        if marker.group("number"):
            paragraph = marker.group("number")
            letter = None
            path = (str(number), paragraph)
        elif marker.group("letter"):
            if paragraph is None:
                raise ValueError("Letter without paragraph.")
            letter = marker.group("letter")
            path = (str(number), paragraph, letter)
        else:
            if paragraph is None or letter is None:
                raise ValueError("Roman numeral without parent.")
            path = (str(number), paragraph, letter, marker.group("roman"))
        end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
        nodes.append((path, text[marker.start():end].strip()))
    paths = [path for path, _ in nodes]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate clause markers; manual review required.")
    units = []
    for path, own_text in nodes:
        if not include_parents and any(len(p) > len(path) and p[:len(path)] == path for p in paths):
            continue
        context = tuple(
            parent_text for parent, parent_text in nodes
            if len(parent) < len(path) and path[:len(parent)] == parent
        )
        units.append(Unit(".".join(path), own_text, context))
    return tuple(units)


def prepare_article(pages: list[Fragment], number: int, include_parents: bool = False) -> Article:
    """Pilot 2–4, checked against the supplied January 2026 source export."""
    if number not in (2,3,4,5,"5bis",6,7,8,9,10,13,14,"14bis",15,16,17,18,"18quater","18quinquies",19,"19bis","19ter","18bis","18ter",20,21,'a4-1','a4-2','a4-3','a4-4','a4-5','a4-6','a4-7','a5-1','a5-2'):
        raise ValueError("RSTP : article non pris en charge dans cette version.")
    pages = sorted(pages,key=lambda p:p.page)
    if [p.page for p in pages] != list(range(159,210)):
        raise ValueError("RSTP: pages 159 à 209 attendues exactement une fois.")
    if len({p.passage_id for p in pages}) != 51:
        raise ValueError("RSTP: identifiants sources dupliqués.")
    if number in (20,21):
        page=next(p for p in pages if p.page==182)
        head=re.search(r'(?m)^20\. Training compensation[ \t]*$',page.text)
        second=re.search(r'(?m)^21\. Solidarity mechanism[ \t]*$',page.text)
        end=re.search(r'(?m)^09\.[ \t]*$',page.text)
        if not all((head,second,end)):raise ValueError('RSTP 20/21 : bornes absentes.')
        h,stop=(head,second.start()) if number==20 else (second,end.start())
        body=page.text[h.end():stop].strip()
        return Article(number,(Fragment(page.passage_id,182,page.text[h.start():stop]),),(Unit(str(number),body,()),))
    if isinstance(number,str) and re.fullmatch(r'a[45]-[1-7]',number):
        by_page={p.page:p for p in pages}
        def part(n,start,end):
            p=by_page[n];a=p.text.index(start);b=p.text.index(end,a)
            return Fragment(p.passage_id,n,p.text[a:b])
        footer='FIFA Football Agent Exam Study Materials'
        sections={
            'a4-1':(part(201,'1. Objective','2. Payment of training compensation'),),
            'a4-2':(part(201,'2. Payment of training compensation','04.\nANNEXE'),part(202,'2. Training compensation is not due if:','3. Responsibility to pay training compensation')),
            'a4-3':(part(202,'3. Responsibility to pay training compensation','4. Training costs'),),
            'a4-4':(part(202,'4. Training costs','5. Calculation of training compensation'),),
            'a4-5':(part(202,'5. Calculation of training compensation',footer),),
            'a4-6':(part(203,'6. Special provisions for the EU/EEA','7. Disciplinary measures'),),
            'a4-7':(part(203,'7. Disciplinary measures','1. Solidarity contribution'),),
            'a5-1':(part(203,'1. Solidarity contribution','05.\nANNEXE'),part(204,'2. A training club is entitled','2. Payment procedure')),
            'a5-2':(part(204,'2. Payment procedure','06.\nANNEXE'),)
        }
        if number not in sections:raise ValueError('Annexe : article non pris en charge.')
        fragments=sections[number];first=fragments[0].text
        body=first.split('\n',1)[1]+('\n'+fragments[1].text if len(fragments)>1 else '')
        prefix='ANNEX'+number[1] +'.'+number.split('-')[1]
        if number=='a4-7':units=(Unit(prefix,body.strip(),()),)
        else:
            markers=list(MARK.finditer(body));nodes=[];paragraph=letter=None
            for i,m in enumerate(markers):
                if m.group('number'):
                    paragraph=m.group('number');letter=None;path=(prefix,paragraph)
                elif m.group('letter'):
                    if paragraph is None:raise ValueError('Annexe : lettre sans parent.')
                    letter=m.group('letter');path=(prefix,paragraph,letter)
                else:
                    if paragraph is None:raise ValueError('Annexe : romain sans parent.')
                    path=(prefix,paragraph)+((letter,) if letter else ())+(m.group('roman'),)
                stop=markers[i+1].start() if i+1<len(markers) else len(body)
                nodes.append((path,body[m.start():stop].strip()))
            expected={
                'a4-1':{'1','2'},'a4-2':{'1','1.a','1.b','2','2.a','2.b','2.c','3'},
                'a4-3':{'1','2','3'},'a4-4':{'1','2'},'a4-5':{'1','2','3','4'},
                'a4-6':{'1','1.a','1.b','2','3','3.i'},
                'a5-1':{'1'}|{'1.'+c for c in 'abcdefghijkl'}|{'2','2.a','2.b'},
                'a5-2':{'1','2','3','4','5'}
            }[number]
            if {'.'.join(path)[len(prefix)+1:] for path,t in nodes}!=expected or len(nodes)!=len(expected):raise ValueError('Annexe : hiérarchie inattendue.')
            units=tuple(Unit('.'.join(path),text,tuple(t for p,t in nodes if len(p)<len(path) and path[:len(p)]==p)) for path,text in nodes if include_parents or not any(len(p)>len(path) and p[:len(path)]==path for p,t in nodes))
        return Article(number,fragments,units)
    if number in ('18bis','18ter'):
        page=next(p for p in pages if p.page==175)
        bis=re.search(r'(?m)^18bis Third-party influence on clubs[ \t]*$',page.text)
        ter=re.search(r'(?m)^18ter Third-party ownership of players’ economic rights[ \t]*$',page.text)
        footer=page.text.find('FIFA Football Agent Exam Study Materials')
        if not bis or not ter or not bis.end()<ter.start()<footer:raise ValueError('RSTP tiers : bornes non reconnues.')
        head,end=(bis,ter.start()) if number=='18bis' else (ter,footer)
        body=page.text[head.end():end].strip()
        units=inventory(number,body,include_parents=include_parents)
        expected={f'{number}.{i}' for i in range(1,3 if number=='18bis' else 7)}
        if {u.unit_id for u in units}!=expected:raise ValueError('RSTP tiers : inventaire inattendu.')
        return Article(number,(Fragment(page.passage_id,page.page,page.text[head.start():end]),),units)
    if number in (19,'19bis','19ter'):
        by_page={p.page:p for p in pages}
        p178,p179,p180,p181=(by_page[n] for n in (178,179,180,181))
        h19=re.search(r'(?m)^19\. Protection of minors[ \t]*$',p178.text)
        hbis=re.search(r'(?m)^19bis[ \t]+Registration and reporting of minors at academies[ \t]*$',p179.text)
        hter=re.search(r'(?m)^19ter[ \t]+Tr\s*ials[ \t]*$',p180.text)
        if not all((h19,hbis,hter)):raise ValueError('RSTP mineurs : titres non reconnus.')
        footer=lambda p:p.text.index('FIFA Football Agent Exam Study Materials')
        if number==19:
            start=p179.text.index('If the minor has been formally recognised as a refugee')
            fragments=(Fragment(p178.passage_id,178,p178.text[h19.start():footer(p178)]),Fragment(p179.passage_id,179,p179.text[start:hbis.start()]))
            body=fragments[0].text[h19.end()-h19.start():]+'\n'+fragments[1].text
        elif number=='19bis':
            start=p180.text.index('4. A club that wishes to collaborate')
            fragments=(Fragment(p179.passage_id,179,p179.text[hbis.start():footer(p179)]),Fragment(p180.passage_id,180,p180.text[start:hter.start()]))
            body=fragments[0].text[hbis.end()-hbis.start():]+'\n'+fragments[1].text
        else:
            start=p181.text.index('10. Collective bargaining agreements')
            stop=re.search(r'(?m)^08\.[ \t]*$',p181.text)
            if not stop:raise ValueError('19ter : fin non reconnue.')
            fragments=(Fragment(p180.passage_id,180,p180.text[hter.start():footer(p180)]),Fragment(p181.passage_id,181,p181.text[start:stop.start()]))
            body=fragments[0].text[hter.end()-hter.start():]+'\n'+fragments[1].text
        # Direct Roman numerals (19bis) and nested Roman numerals (19/19ter).
        markers=list(MARK.finditer(body));nodes=[];paragraph=letter=None
        for i,m in enumerate(markers):
            if m.group('number'):
                paragraph=m.group('number');letter=None;path=(str(number),paragraph)
            elif m.group('letter'):
                if paragraph is None:raise ValueError('Mineurs : lettre sans parent.')
                letter=m.group('letter');path=(str(number),paragraph,letter)
            else:
                if paragraph is None:raise ValueError('Mineurs : chiffre romain sans parent.')
                path=(str(number),paragraph)+((letter,) if letter else ())+ (m.group('roman'),)
            text=body[m.start():markers[i+1].start() if i+1<len(markers) else len(body)].strip()
            nodes.append((path,text))
        if len({p for p,t in nodes})!=len(nodes):raise ValueError('Mineurs : doublon de numérotation.')
        shared={}
        # The club obligations apply to both geographical alternatives in 19.2.b.
        if number==19:
            t=next(t for p,t in nodes if p==('19','2','b','ii'))
            sentence='The new club must fulfil the following minimum obligations:'
            if sentence not in t:raise ValueError('19.2.b : obligations communes absentes.')
            shared[('19','2','b')]=sentence
            nodes=[(p,t.split(sentence)[0].strip() if p==('19','2','b','ii') else t) for p,t in nodes]
            # Refugee / asylum distinctions qualify all humanitarian alternatives.
            path=('19','2','d','ii');t=next(t for p,t in nodes if p==path)
            at=t.index('If the minor has been formally recognised as a refugee')
            shared[('19','2','d')]=t[at:].strip()
            nodes=[(p,t[:at].strip() if p==path else t) for p,t in nodes]
        if number=='19bis':
            path=('19bis','6','ii');t=next(t for p,t in nodes if p==path)
            at=t.index('Such reports shall contain')
            shared[('19bis','6')]=t[at:].strip()
            nodes=[(p,t[:at].strip() if p==path else t) for p,t in nodes]
        # Exact expected hierarchy, not only total counts.
        expected=({f'19.{i}' for i in range(1,10)}|{f'19.2.{c}' for c in 'abcde'}|{f'19.2.b.{r}' for r in ('i','ii','iii','iv','v','vi')}|{f'19.2.d.{r}' for r in ('i','ii')}|{f'19.4.{c}' for c in 'abc'}|{f'19.7.{c}' for c in 'ab'}) if number==19 else (({f'19bis.{i}' for i in range(1,8)}|{f'19bis.4.{r}' for r in ('i','ii','iii','iv')}|{f'19bis.6.{r}' for r in ('i','ii')}) if number=='19bis' else ({f'19ter.{i}' for i in range(1,12)}|{f'19ter.8.{c}' for c in 'abcde'}|{f'19ter.8.a.{r}' for r in ('i','ii')}))
        if {'.'.join(p) for p,t in nodes}!=expected:raise ValueError('Mineurs : hiérarchie différente de la source attendue.')
        units=[]
        for path,text in nodes:
            if not include_parents and any(len(p)>len(path) and p[:len(path)]==path for p,t in nodes):continue
            parents=tuple(t for p,t in nodes if len(p)<len(path) and path[:len(p)]==p)
            common=tuple(t for p,t in shared.items() if path[:len(p)]==p)
            units.append(Unit('.'.join(path),text,parents,common))
        return Article(number,fragments,tuple(units))
    if number in ('18quater','18quinquies'):
        first=next(p for p in pages if p.page==176);second=next(p for p in pages if p.page==177)
        head=re.search(r'(?m)^18quater[ \t]+Sp\s*ecial provisions relating to pregnancy,\s+adoption and family leave[ \t]*$',first.text)
        quin=re.search(r'(?m)^18quinquies[ \t]+Me\s*nstrual health[ \t]*$',second.text)
        f1=first.text.find('FIFA Football Agent Exam Study Materials');f2=second.text.find('FIFA Football Agent Exam Study Materials')
        if not head or not quin or f1<head.end() or f2<quin.end():raise ValueError('RSTP joueuses : bornes non reconnues.')
        if number=='18quinquies':
            text=second.text[quin.end():f2].strip()
            if list(MARK.finditer(text)):raise ValueError('18quinquies : article non numéroté attendu.')
            return Article(number,(Fragment(second.passage_id,second.page,second.text[quin.start():f2]),),(Unit(number,text,()),))
        continuation=re.search(r'(?m)^b\) in addition to the obligation',second.text)
        if not continuation or continuation.start()>=quin.start():raise ValueError('18quater : continuité absente.')
        main=(Fragment(first.passage_id,first.page,first.text[head.start():f1]),Fragment(second.passage_id,second.page,second.text[continuation.start():quin.start()]))
        body=main[0].text[head.end()-head.start():]+'\n'+main[1].text
        units=inventory(number,body.strip(),include_parents=include_parents)
        expected={f'18quater.{i}' for i in range(1,7)}|{'18quater.2.a'}|{f'18quater.3.{c}' for c in 'abc'}|{f'18quater.3.a.{r}' for r in ('i','ii','iii','iv')}|{f'18quater.4.{c}' for c in 'abc'}|{f'18quater.5.{c}' for c in 'ab'}
        parents={'18quater.2','18quater.3','18quater.3.a','18quater.4','18quater.5'}
        if {u.unit_id for u in units}!=(expected if include_parents else expected-parents):raise ValueError('18quater : inventaire différent des 19 unités attendues.')
        defpage=next(p for p in pages if p.page==164);defs=[]
        for n,label,nextlabel in [(30,'Maternity leave:','31. Club-trained player:'),(42,'Adoption leave:','43. Family leave:'),(43,'Family leave:',None)]:
            a=defpage.text.find(str(n)+'. '+label)
            b=defpage.text.find(nextlabel,a) if nextlabel else defpage.text.find(' Re',a)
            if a<0 or b<=a:raise ValueError('Définition de congé absente.')
            defs.append(defpage.text[a:b].strip())
        full='\n'.join(f.text for f in main)
        shared=re.search(r'The player shall be entitled to receive her full remuneration following her return\s+to football activity\.',full)
        if not shared:raise ValueError('18quater : salaire au retour absent.')
        sentence=shared.group(0);rebuilt=[]
        for u in units:
            own=u.text
            if u.unit_id=='18quater.5.b':
                if sentence not in own:raise ValueError('18quater : salaire hors source attendue.')
                own=own.split(sentence,1)[0].strip()
            context=u.inherited_context+(tuple(defs) if u.unit_id in ('18quater.5','18quater.5.a','18quater.5.b') else ())
            shared_context=(sentence,) if u.unit_id=='18quater.5' or u.unit_id.startswith('18quater.5.') else ()
            rebuilt.append(Unit(u.unit_id,own,context,shared_context))
        return Article(number,(Fragment(defpage.passage_id,defpage.page,'\n'.join(defs)),)+main,tuple(rebuilt))
    if number==18:
        page=next(p for p in pages if p.page==174)
        heads=list(re.finditer(r'(?m)^18\.[ \t]+Special provisions relating to contracts between\s+p\s*rofessionals and clubs[ \t]*$',page.text))
        footer=page.text.find('FIFA Football Agent Exam Study Materials')
        if len(heads)!=1 or footer<=heads[0].end():raise ValueError('RSTP 18 : bornes absentes ou ambiguës.')
        head=heads[0];body=page.text[head.end():footer].strip()
        units=inventory(18,body,include_parents=include_parents)
        if {u.unit_id for u in units}!={f'18.{i}' for i in range(1,8)}:raise ValueError('RSTP 18 : sept paragraphes attendus.')
        return Article(18,(Fragment(page.passage_id,page.page,page.text[head.start():footer]),),units)
    if number==17:
        first=next(p for p in pages if p.page==173);second=next(p for p in pages if p.page==174)
        h=re.search(r'(?m)^17\.[ \t]+Consequences of terminating a contract without just\s+c\s*ause[ \t]*$',first.text)
        end=re.search(r'(?m)^18\.[ \t]+Special provisions relating to contracts between\s+p\s*rofessionals and clubs[ \t]*$',second.text)
        footer=first.text.find('FIFA Football Agent Exam Study Materials')
        continuation=second.text.find('up to a maximum of six monthly salaries.')
        if not h or not end or footer<h.end() or continuation<0 or continuation>=end.start():raise ValueError('RSTP 17 : bornes non reconnues.')
        f1=Fragment(first.passage_id,first.page,first.text[h.start():footer]);f2=Fragment(second.passage_id,second.page,second.text[continuation:end.start()])
        body=f1.text[h.end()-h.start():]+'\n'+f2.text
        mark=re.compile(r'(?m)^[ \t]*(?:(?P<n>\d+)\.|(?P<roman>i{1,3})\.)[ \t\r\n]+')
        markers=list(mark.finditer(body))
        if not markers or markers[0].group('n')!='1':raise ValueError('RSTP 17 : paragraphe 1 absent.')
        intro=body[:markers[0].start()].strip();nodes=[];parent=None
        for i,m in enumerate(markers):
            stop=markers[i+1].start() if i+1<len(markers) else len(body)
            if m.group('n'):parent='17.'+m.group('n');key=parent
            else:
                if parent!='17.1':raise ValueError('RSTP 17 : liste romaine hors paragraphe 1.')
                key=parent+'.'+m.group('roman')
            nodes.append((key,body[m.start():stop].strip()))
        expected={f'17.{i}' for i in range(1,6)}|{'17.1.i','17.1.ii','17.1.iii'}
        if len(nodes)!=8 or {k for k,t in nodes}!=expected:raise ValueError('RSTP 17 : huit paragraphes/sous-paragraphes attendus.')
        defpage=next(p for p in pages if p.page==162)
        a=defpage.text.find('7. Protected period:');b=defpage.text.find('8. Registration period:',a)
        if a<0 or b<=a:raise ValueError('Définition 7 absente.')
        definition=defpage.text[a:b].strip();parent1=next(t for k,t in nodes if k=='17.1')
        units=[Unit('17',intro,())]
        for key,text in nodes:
            contexts=(intro,)+( (parent1,) if key.startswith('17.1.') else ())
            if key=='17.3':contexts+=(definition,)
            units.append(Unit(key,text,contexts))
        if not include_parents:units=[u for u in units if u.unit_id not in ('17','17.1')]
        return Article(17,(Fragment(defpage.passage_id,defpage.page,definition),f1,f2),tuple(units))
    if number in (13,14,"14bis",15,16):
        page=next(p for p in pages if p.page==173)
        patterns={
            13:r'(?m)^13\. Respect of contract[ \t]*$',
            14:r'(?m)^14\. Terminating a contract with just cause[ \t]*$',
            '14bis':r'(?m)^14bis[ \t]+Terminating a contract with just cause for\s+o\s*utstanding salaries[ \t]*$',
            15:r'(?m)^15\. Terminating a contract with sporting just cause[ \t]*$',
            16:r'(?m)^16\.[ \t]+Restriction on terminating a contract during the\s+c\s*ompetition period[ \t]*$',
            17:r'(?m)^17\.[ \t]+Consequences of terminating a contract without just\s+c\s*ause[ \t]*$'}
        sequence=[13,14,'14bis',15,16,17];heads={}
        for n,pattern in patterns.items():
            found=list(re.finditer(pattern,page.text))
            if len(found)!=1:raise ValueError(f'RSTP {n}: titre absent ou ambigu.')
            heads[n]=found[0]
        if not all(heads[a].start()<heads[b].start() for a,b in zip(sequence,sequence[1:])):
            raise ValueError('RSTP 13–16 : titres désordonnés.')
        head=heads[number];end=heads[sequence[sequence.index(number)+1]].start()
        body=page.text[head.end():end].strip()
        if number in (13,15,16):
            if list(MARK.finditer(body)):raise ValueError('RSTP : article non numéroté attendu.')
            units=(Unit(str(number),body,()),)
        else:
            units=inventory(number,body,include_parents=include_parents)
            expected={f'{number}.{i}' for i in range(1,4 if number=='14bis' else 3)}
            if {u.unit_id for u in units}!=expected:raise ValueError('RSTP : paragraphes attendus absents ou inattendus.')
        return Article(number,(Fragment(page.passage_id,page.page,page.text[head.start():end]),),units)
    if number==10:
        first=next(p for p in pages if p.page==170)
        second=next(p for p in pages if p.page==171)
        starts=list(re.finditer(r'(?m)^10\. Loan of professionals[ \t]*$',first.text))
        ends=list(re.finditer(r'(?m)^11\. Unreg[ \t]*istered players[ \t]*$',second.text))
        continuation=re.search(r'(?m)^5\. The terms of article 10 paragraph 4',second.text)
        footer=first.text.find('FIFA Football Agent Exam Study Materials')
        if len(starts)!=1 or len(ends)!=1 or not continuation or footer<starts[0].end() or continuation.start()>=ends[0].start():
            raise ValueError('RSTP 10 : bornes ou continuité non reconnues.')
        fragments=(Fragment(first.passage_id,first.page,first.text[starts[0].start():footer]),Fragment(second.passage_id,second.page,second.text[continuation.start():ends[0].start()]))
        text=fragments[0].text[starts[0].end()-starts[0].start():]+'\n'+fragments[1].text
        units=inventory(10,text.strip(),include_parents=include_parents)
        expected={f'10.{i}' for i in range(1,10)}
        branches={1:'abcdef',4:'abcd',5:'abc',6:'ab',7:'ab',8:'ab',9:'ab'}
        expected|={f'10.{n}.{c}' for n,letters in branches.items() for c in letters}
        leaves=expected-{f'10.{n}' for n in branches}
        if {u.unit_id for u in units}!=(expected if include_parents else leaves):
            raise ValueError('RSTP 10 : inventaire différent des 30 unités attendues.')
        return Article(10,fragments,units)
    if number in (7,8,9):
        selected=[p for p in pages if p.page in (169,170)]
        joined="\n".join(p.text for p in selected)
        titles={7:r"(?m)^7\. Player passport[ \t]*$",8:r"(?m)^8\. Application for registration[ \t]*$",9:r"(?m)^9\. International Transfer Certificate[ \t]*$",10:r"(?m)^10\. Loan of professionals[ \t]*$"}
        heads={}
        for n,pattern in titles.items():
            found=list(re.finditer(pattern,joined))
            if len(found)!=1:raise ValueError(f"RSTP {n}: titre absent ou ambigu.")
            heads[n]=found[0]
        if not all(heads[n].start()<heads[n+1].start() for n in (7,8,9)):
            raise ValueError("RSTP 7–9 : titres désordonnés.")
        start,end=heads[number].start(),heads[number+1].start()
        fragments=[];offset=0
        for page in selected:
            left,right=max(start,offset),min(end,offset+len(page.text))
            if right>left:fragments.append(Fragment(page.passage_id,page.page,page.text[left-offset:right-offset]))
            offset+=len(page.text)+1
        if number==7:
            # Omit page furniture at the split without changing source characters.
            clean=[]
            for f in fragments:
                text=f.text
                if f.page==169:
                    footer=text.find('FIFA Football Agent Exam Study Materials')
                    if footer<0:raise ValueError('RSTP 7 : pied de page absent.')
                    text=text[:footer]
                if f.page==170:
                    continuation=re.search(r'(?m)^2\. For entitlements',text)
                    if not continuation:raise ValueError('RSTP 7 : suite du paragraphe 2 absente.')
                    text=text[continuation.start():]
                clean.append(Fragment(f.passage_id,f.page,text))
            fragments=clean
        full='\n'.join(f.text for f in fragments)
        header=list(re.finditer(titles[number],full))
        if len(header)!=1:raise ValueError('RSTP : titre source non unique.')
        body=full[header[0].end():].strip()
        if number==8:
            if list(MARK.finditer(body)):raise ValueError("RSTP 8 : paragraphe non numéroté attendu.")
            units=(Unit('8',body,()),)
        else:
            units=inventory(number,body,include_parents=include_parents)
            if {u.unit_id for u in units}!={f"{number}.{i}" for i in range(1,5)}:
                raise ValueError("RSTP 7/9 : quatre paragraphes attendus.")
        return Article(number,tuple(fragments),units)
    if number==6:
        page=next(p for p in pages if p.page==169)
        starts=list(re.finditer(r"(?m)^6\. Registration periods[ \t]*$",page.text))
        ends=list(re.finditer(r"(?m)^7\. Player passport[ \t]*$",page.text))
        if len(starts)!=1 or len(ends)!=1 or starts[0].end()>=ends[0].start():
            raise ValueError("RSTP 6 : bornes absentes ou ambiguës.")
        head=starts[0];end=ends[0].start()
        units=inventory(6,page.text[head.end():end].strip(),include_parents=include_parents)
        expected={f"6.{i}" for i in range(1,9)}|{f"6.3.{c}" for c in "abcdef"}
        if {u.unit_id for u in units}!=(expected if include_parents else expected-{'6.3'}):
            raise ValueError("RSTP 6 : inventaire inattendu.")
        return Article(6,(Fragment(page.passage_id,page.page,page.text[head.start():end]),),units)
    if number in (5,"5bis"):
        page=next(p for p in pages if p.page==168)
        patterns=[r"(?m)^5\. Registration[ \t]*$",r"(?m)^5bis Bridge transfer[ \t]*$"]
        matches=[list(re.finditer(pattern,page.text)) for pattern in patterns]
        if any(len(m)!=1 for m in matches):raise ValueError("RSTP 5/5bis : titres ambigus ou absents.")
        h5,hbis=matches[0][0],matches[1][0]
        if h5.start()>=hbis.start():raise ValueError("RSTP : titres désordonnés.")
        footer=re.search(r"(?m)^FIFA Football Agent Exam Study Materials",page.text)
        if not footer or footer.start()<=hbis.end():raise ValueError("RSTP : fin de 5bis non reconnue.")
        head=h5 if number==5 else hbis
        end=hbis.start() if number==5 else footer.start()
        text=page.text[head.end():end].strip()
        units=inventory(number,text,include_parents=include_parents)
        expected=({f"5.{i}" for i in range(1,7)}|{f"5.6.{c}" for c in "abcd"}) if number==5 else {f"5bis.{i}" for i in range(1,4)}
        leaves=expected-({'5.6'} if number==5 else set())
        if {u.unit_id for u in units}!=(expected if include_parents else leaves):raise ValueError("RSTP 5/5bis : inventaire inattendu.")
        return Article(number,(Fragment(page.passage_id,page.page,page.text[head.start():end]),),units)
    page = next(p for p in pages if p.page==167)
    titles = {
        2: r"(?m)^2\. Status of players: amateur and professional players[ \t]*$",
        3: r"(?m)^3\. Reacquisition of amateur status[ \t]*$",
        4: r"(?m)^4\. Termination of activity[ \t]*$",
    }
    heads = {}
    for n, pattern in titles.items():
        matches=list(re.finditer(pattern,page.text))
        if len(matches)!=1:raise ValueError(f"RSTP article {n}: titre absent ou ambigu.")
        heads[n]=matches[0]
    if not heads[2].start()<heads[3].start()<heads[4].start():
        raise ValueError("RSTP: titres désordonnés.")
    section=re.search(r"(?m)^03\.\s*\nREGISTRATION",page.text)
    if not section or section.start()<=heads[4].end():
        raise ValueError("RSTP: borne de fin de l’article 4 non reconnue.")
    end=heads[number+1].start() if number<4 else section.start()
    text=page.text[heads[number].end():end].strip()
    units=inventory(number,text,include_parents=include_parents)
    if {u.unit_id for u in units}!={f"{number}.1",f"{number}.2"}:
        raise ValueError("RSTP: inventaire différent des deux paragraphes attendus.")
    fragment=Fragment(page.passage_id,page.page,page.text[heads[number].start():end])
    return Article(number,(fragment,),units)


def check_result(result: dict, article: Article) -> list[str]:
    """Mechanical checks only. Never a legal-validation decision."""
    errors = []
    expected = {u.unit_id for u in article.units}
    fragments = {f.passage_id: f.text for f in article.fragments}
    items = result.get("items", [])
    keys = [item["unit_id"] for item in items]
    if len(keys) != len(set(keys)):
        errors.append("Duplicate units.")
    if set(keys) != expected:
        errors.append(
            f"Coverage mismatch; missing={sorted(expected-set(keys))}; "
            f"unexpected={sorted(set(keys)-expected)}"
        )
    for item in items:
        key = item["unit_id"]
        if item["disposition"] != f"Article {key}":
            errors.append(f"{key}: wrong provision reference.")
        for name in ("title_fr", "summary_fr"):
            if not item[name].strip():
                errors.append(f"{key}: empty {name}.")
        claims = [item["summary_fr"]] + [
            c["text_fr"] for name in ("conditions", "exceptions", "consequences")
            for c in item[name]
        ]
        if any(not claim.strip() for claim in claims):
            errors.append(f"{key}: empty claim.")
        proof_groups = [item["evidence"]] + [
            c["evidence"] for name in ("conditions", "exceptions", "consequences")
            for c in item[name]
        ]
        for proofs in proof_groups:
            if not proofs:
                errors.append(f"{key}: unsupported claim.")
            for proof in proofs:
                source = fragments.get(proof["passage_id"])
                quote = normalize(proof["quote"])
                if source is None or not quote or quote not in normalize(source):
                    errors.append(f"{key}: quote not found in {proof['passage_id']}.")
        if item["unresolved_references"]:
            errors.append(f"{key}: unresolved references.")
    if result.get("review_notes"):
        errors.append("Extraction contains review notes.")
    return sorted(set(errors))


def build_source_spans(article: Article):
    """Select evidence in code, preserving every original source character.

    Model outputs select span identifiers, never type or reconstruct quotations.
    Offsets below are relative to an article fragment, not to the whole PDF page.
    """
    joined = "\n".join(f.text for f in article.fragments)
    fragments = []
    offset = 0
    for f in article.fragments:
        fragments.append((offset, offset + len(f.text), f))
        offset += len(f.text) + 1
    spans, inventories = {}, []
    for unit in article.units:
        own_ids, context_ids = [], []
        segments = [("OWN", unit.text)] + [
            (f"PARENT{i}", text)
            for i, text in enumerate(unit.inherited_context, 1)
        ] + [(f"SHARED{i}", text) for i, text in enumerate(unit.shared_context, 1)]
        for role, text in segments:
            start = joined.find(text)
            if start < 0 or joined.find(text, start + 1) >= 0:
                raise ValueError(f"{unit.unit_id}: non-unique source span.")
            end = start + len(text)
            piece = 0
            for left, right, fragment in fragments:
                first, last = max(left, start), min(right, end)
                if last <= first or not joined[first:last].strip():
                    continue
                # The next article heading can follow a page number/running
                # header. Do not attach a fragment consisting only of known
                # FFAR layout furniture as a separate legal proof.
                candidate = joined[first:last]
                layout_lines = {
                    str(fragment.page - 260),
                    "ACTING AS A FOOTBALL AGENT", "BECOMING A FOOTBALL AGENT",
                    "GENERAL RULES", "FINAL PROVISIONS", "DEFINITIONS",
                }
                meaningful = [
                    line.strip() for line in candidate.splitlines()
                    if line.strip() and line.strip() not in layout_lines
                    and not re.fullmatch(r"[IVX]+\.", line.strip())
                    and not re.fullmatch(r"\d+ of \d+", line.strip())
                    and not line.strip().startswith("FIFA Football Agent Exam Study Materials")
                ]
                if not meaningful:
                    continue
                piece += 1
                span_id = f"S_{unit.unit_id.replace('.', '_')}_{role}_{piece}"
                spans[span_id] = {
                    "span_id": span_id,
                    "unit_id": unit.unit_id,
                    "role": role,
                    "passage_id": fragment.passage_id,
                    "fragment_start": first-left,
                    "fragment_end": last-left,
                    "quote": fragment.text[first-left:last-left],
                }
                (own_ids if role == "OWN" else context_ids).append(span_id)
        if not own_ids:
            raise ValueError(f"{unit.unit_id}: no primary source.")
        inventories.append({
            "unit_id": unit.unit_id,
            "own_span_ids": own_ids,
            "parent_span_ids": context_ids,
        })
    return spans, inventories


def resolve_evidence(raw_result, spans, inventories):
    """Hydrate selected IDs from the source; never repair an invented quote."""
    result = deepcopy(raw_result)
    errors = []
    inventory_by_id = {u["unit_id"]: u for u in inventories}
    for item in result.get("items", []):
        key = item["unit_id"]
        # Provision identifiers are deterministic metadata, never model prose.
        item["disposition"] = f"Article {key}"
        entry = inventory_by_id.get(key)
        if entry is None:
            errors.append(f"{key}: unknown inventory unit.")
            allowed = set()
        else:
            allowed = set(entry["own_span_ids"] + entry["parent_span_ids"])
            # A parent may describe requirements in its own descendants.
            # Siblings and unrelated branches remain forbidden.
            for descendant in inventories:
                if descendant['unit_id'].startswith(key + '.'):
                    allowed.update(descendant['own_span_ids'] + descendant['parent_span_ids'])
        claims = [item] + [
            claim for field in ("conditions", "exceptions", "consequences")
            for claim in item[field]
        ]
        for claim in claims:
            hydrated = []
            for selected in claim["evidence"]:
                span_id = selected["span_id"]
                span = spans.get(span_id)
                if span is None or span_id not in allowed:
                    errors.append(f"{key}: invalid source span {span_id}.")
                    continue
                hydrated.append(deepcopy(span))
            claim["evidence"] = hydrated
        if entry:
            selected = {p["span_id"] for p in item["evidence"]}
            required = set(entry["own_span_ids"] + entry["parent_span_ids"])
            if not required <= selected:
                errors.append(f"{key}: missing own or inherited source references.")
        if not item.get("statement_fr", "").strip():
            errors.append(f"{key}: detailed statement missing.")
    return result, sorted(set(errors))


def check_article_5_thresholds(result):
    """Independent pilot checks for four explicit temporal thresholds.

    These checks are intentionally narrow and do not certify legal completeness.
    Source strings, quotations and provision identifiers are not searched here.
    """
    patterns = {
        "5.1.a.iii": r"\b(?:2|deux)\s+ans\b",
        "5.1.b": r"\b(?:24|vingt[- ]quatre)\s+mois\b",
        "5.1.c.i": r"\b(?:5|cinq)\s+ans\b",
        "5.1.d.i": r"\b(?:12|douze)\s+mois\b",
    }
    errors = []
    for item in result.get("items", []):
        key = item["unit_id"]
        pattern = patterns.get(key)
        content = normalize(" ".join(
            [item.get("statement_fr", "")] + [
                c["text_fr"] for field in ("conditions", "exceptions", "consequences")
                for c in item[field]
            ]
        )).lower()
        if pattern and not re.search(pattern, content):
            errors.append(f"{key}: temporal threshold missing from French details.")
        if key == "5.1.a.iii":
            if not re.search(r"(?:au moins|minimum|ou plus|sup[ée]rieure? ou [ée]gale?)", content):
                errors.append(f"{key}: inclusive suspension threshold not explicit.")
    return errors


def is_layout_only(text):
    """Known FFAR furniture only; never strip a substantive source sentence."""
    labels = {'ACTING AS A FOOTBALL AGENT', 'BECOMING A FOOTBALL AGENT',
              'GENERAL RULES', 'FINAL PROVISIONS', 'DEFINITIONS',
              'RIGHTS AND', 'OBLIGATIONS OF', 'CLIENTS',
              'RIGHTS AND OBLIGATIONS OF CLIENTS'}
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and all(
        line in labels or re.fullmatch(r'\d+|[IVX]+\.|\d+ of \d+',line)
        or line.startswith('FIFA Football Agent Exam Study Materials')
        for line in lines
    )


def check_source_coverage(audit, spans, inventories):
    """Check bookkeeping; it cannot certify that every legal detail was found."""
    expected = {sid for u in inventories for sid in u['own_span_ids']
                if sid in spans and not is_layout_only(spans[sid]['quote'])}
    # A shared sentence may have one evidence alias for each affected unit.
    # Audit it once, accepting any exact alias of the same source interval.
    shared_groups = {}
    aliases = {}
    for sid, span in spans.items():
        if not span.get('role','').startswith('SHARED'):
            continue
        fingerprint = (span['passage_id'], span['fragment_start'],
                       span['fragment_end'], span['quote'])
        canonical = shared_groups.setdefault(fingerprint, sid)
        aliases[sid] = canonical
        expected.add(canonical)
    known_units = {u['unit_id'] for u in inventories}
    rows = []
    for original in audit.get('source_checks', []):
        sid = original['span_id']
        if sid in spans and is_layout_only(spans[sid]['quote']):
            continue
        row = deepcopy(original)
        row['span_id'] = aliases.get(sid, sid)
        rows.append(row)
    ids = [r['span_id'] for r in rows]
    errors = []
    if len(ids) != len(set(ids)) or set(ids) != expected:
        errors.append('AUDIT: couverture source absente, dupliquée ou inattendue; '
                      + 'manquants=' + str(sorted(expected-set(ids)))
                      + '; inattendus=' + str(sorted(set(ids)-expected)))
    for row in rows:
        sid = row['span_id']
        if sid not in expected or sid not in spans:
            errors.append(f'AUDIT: fragment inconnu {sid}.')
        if not row.get('details'):
            errors.append(f'AUDIT {sid}: aucun détail source examiné.')
        for detail in row.get('details', []):
            if not detail.get('source_detail_fr', '').strip() or not detail.get('reason_fr', '').strip():
                errors.append(f'AUDIT {sid}: justification vide.')
            targets = detail.get('target_unit_ids', [])
            if any(u not in known_units for u in targets):
                errors.append(f'AUDIT {sid}: cible inconnue.')
            status = detail.get('status')
            if status == 'COVERED' and not targets:
                errors.append(f'AUDIT {sid}: détail couvert sans cible.')
            elif status == 'MISSING':
                errors.append(f"AUDIT {sid}: détail absent : {detail.get('source_detail_fr', '')}")
            elif status not in ('COVERED', 'NON_NORMATIVE'):
                errors.append(f'AUDIT {sid}: statut inconnu.')
    return sorted(set(errors))
