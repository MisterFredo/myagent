"""Article segmentation and source checks. No network or model calls."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


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


@dataclass(frozen=True)
class Article:
    number: int
    fragments: tuple[Fragment, ...]
    units: tuple[Unit, ...]


HEAD = re.compile(r"(?m)^[ \t]*Article[ \t]+(\d+)[ \t]*:")
MARK = re.compile(
    r"(?m)^[ \t]*(?:(?P<number>\d+)\.|(?P<letter>[a-z])\)|"
    r"(?P<roman>[ivxlcdm]+)\.)[ \t\r\n]+"
)


def normalize(text: str) -> str:
    # Do not delete numbering, punctuation or substantive words to force matches.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def inventory(number: int, text: str) -> tuple[Unit, ...]:
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
        if any(len(p) > len(path) and p[:len(path)] == path for p in paths):
            continue
        context = tuple(
            parent_text for parent, parent_text in nodes
            if len(parent) < len(path) and path[:len(parent)] == parent
        )
        units.append(Unit(".".join(path), own_text, context))
    return tuple(units)


def segment_articles(pages: list[Fragment]) -> dict[int, Article]:
    """Require the actual FFAR sequence 1..28, ignoring earlier contents headings."""
    pages = sorted(pages, key=lambda p: p.page)
    if len({p.passage_id for p in pages}) != len(pages):
        raise ValueError("Duplicate source identifiers.")
    if [p.page for p in pages] != list(range(261, 300)):
        raise ValueError("FFAR section must contain pages 261..299 exactly once.")
    joined = ""
    spans = []
    for page in pages:
        start = len(joined)
        joined += page.text
        spans.append((start, len(joined), page))
        joined += "\n"
    headings = list(HEAD.finditer(joined))
    starts = [i for i, h in enumerate(headings) if int(h.group(1)) == 1]
    if not starts:
        raise ValueError("Article 1 not found.")
    headings = headings[starts[-1]:]
    if [int(h.group(1)) for h in headings] != list(range(1, 29)):
        raise ValueError("Expected complete, ordered FFAR articles 1..28.")
    result = {}
    for i, h in enumerate(headings):
        number = int(h.group(1))
        end = headings[i + 1].start() if i + 1 < len(headings) else len(joined)
        fragments = []
        for left, right, page in spans:
            first, last = max(left, h.start()), min(right, end)
            if last > first and joined[first:last].strip():
                fragments.append(Fragment(page.passage_id, page.page, joined[first:last]))
        text = "\n".join(f.text for f in fragments)
        # Inventory only the chosen article later: not every FFAR article uses
        # the same subparagraph typography.
        result[number] = Article(number, tuple(fragments), ())
    return result


EXPECTED_ARTICLE_5 = {
    "5.1.a.i", "5.1.a.ii", "5.1.a.iii", "5.1.a.iv", "5.1.a.v",
    "5.1.b", "5.1.c.i", "5.1.d.i", "5.2.a", "5.2.b", "5.3",
}


def prepare_article(pages: list[Fragment], number: int) -> Article:
    if number != 5:
        raise ValueError("This pilot is deliberately limited to article 5.")
    block = segment_articles(pages)[number]
    units = inventory(number, "\n".join(f.text for f in block.fragments))
    if {u.unit_id for u in units} != EXPECTED_ARTICLE_5:
        raise ValueError("Article 5 inventory differs from the 11 expected clauses.")
    return Article(number, block.fragments, units)


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
