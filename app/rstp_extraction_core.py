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
    if number not in (2,3,4,5,"5bis",6,7,8,9):
        raise ValueError("RSTP : articles 2 à 9 et 5bis uniquement.")
    pages = sorted(pages,key=lambda p:p.page)
    if [p.page for p in pages] != list(range(159,210)):
        raise ValueError("RSTP: pages 159 à 209 attendues exactement une fois.")
    if len({p.passage_id for p in pages}) != 51:
        raise ValueError("RSTP: identifiants sources dupliqués.")
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
