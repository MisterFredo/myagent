import copy
import unittest

from app.extraction_core import (
    Article, Fragment, Unit, EXPECTED_ARTICLE_5,
    inventory, prepare_article, check_result,
    build_source_spans, resolve_evidence, check_article_5_thresholds,
)


# Synthetic typography fixture, not an authoritative legal source.
FIRST = """Article 5: Eligibility requirements
1. An applicant must:
a) upon submitting their application and subsequently thereafter:
i. have made no false statements;
ii. never have been convicted of specified crimes;
iii. never have been suspended for two years or more;
iv. not be an official, except when representing agents;
v. not hold any Interest in a club.
b) in the 24 months before application, never have been found
performing services without the required licence;
"""
SECOND = """13
c) in the five years before application and subsequently thereafter:
i. never have declared bankruptcy;
d) in the 12 months before application and subsequently thereafter:
i. not have held an Interest in sports betting.
2. An applicant must satisfy the requirements:
a) at application; and
b) at all times after obtaining a licence, under article 17.
3. The general secretariat investigates compliance.
"""


def pages_fixture():
    texts = {page: f"Page {page}\n" for page in range(261, 300)}
    # Contents headings must not be mistaken for the actual articles.
    texts[264] += "\n".join(f"Article {i}: Contents" for i in range(1, 29))
    texts[269] += "Article 1: Objectives\n1. Example.\n"
    texts[270] += "Article 2: Scope\n1. Example.\n"
    texts[271] += "Article 3: National rules\n1. Example.\n"
    texts[272] += "Article 4: General provisions\n1. Example.\n" + FIRST
    texts[273] += SECOND + "Article 6: Exam\n1. Example.\n"
    texts[274] += "\n".join(
        f"Article {i}: Example\n1. Example." for i in range(7, 29)
    )
    return [Fragment(f"P{page}", page, text) for page, text in texts.items()]


def simple_result():
    return {"items": [{
        "unit_id": "5.3", "disposition": "Article 5.3",
        "title_fr": "Autorité de contrôle", "summary_fr": "Le secrétariat contrôle.",
        "conditions": [], "exceptions": [], "consequences": [],
        "evidence": [{"passage_id": "P273", "quote": "investigates compliance."}],
        "unresolved_references": [],
    }], "review_notes": []}


class InventoryTests(unittest.TestCase):
    def test_eleven_leaf_clauses(self):
        units = inventory(5, FIRST + SECOND)
        self.assertEqual({u.unit_id for u in units}, EXPECTED_ARTICLE_5)

    def test_parent_timing_is_inherited(self):
        units = {u.unit_id: u for u in inventory(5, FIRST + SECOND)}
        self.assertIn("subsequently", " ".join(units["5.1.a.iv"].inherited_context))
        self.assertIn("five years", " ".join(units["5.1.c.i"].inherited_context))
        self.assertIn("12 months", " ".join(units["5.1.d.i"].inherited_context))

    def test_complete_article_excludes_neighbours_and_contents(self):
        article = prepare_article(pages_fixture(), 5)
        text = "\n".join(f.text for f in article.fragments)
        self.assertEqual([f.page for f in article.fragments], [272, 273])
        self.assertNotIn("Article 4:", text)
        self.assertNotIn("Article 6:", text)
        self.assertEqual(len(article.units), 11)

    def test_missing_page_stops_preparation(self):
        with self.assertRaises(ValueError):
            prepare_article(pages_fixture()[:-1], 5)

    def test_duplicate_clause_stops_preparation(self):
        with self.assertRaises(ValueError):
            inventory(5, FIRST + SECOND + "\n3. Duplicate paragraph.")


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.article = Article(5, (Fragment("P273", 273, SECOND),),
                               (Unit("5.3", "Text", ()),))

    def test_valid_quote(self):
        self.assertEqual(check_result(simple_result(), self.article), [])

    def test_missing_unit_detected(self):
        result = {"items": [], "review_notes": []}
        self.assertTrue(check_result(result, self.article))

    def test_wrong_page_detected(self):
        result = simple_result()
        result["items"][0]["evidence"][0]["passage_id"] = "P999"
        self.assertTrue(check_result(result, self.article))

    def test_ellipsis_is_not_repaired(self):
        result = simple_result()
        result["items"][0]["evidence"][0]["quote"] = "investigates...compliance."
        self.assertTrue(check_result(result, self.article))

    def test_unsupported_condition_detected(self):
        result = simple_result()
        result["items"][0]["conditions"] = [{"text_fr": "Condition", "evidence": []}]
        self.assertTrue(check_result(result, self.article))

    def test_duplicate_unit_detected(self):
        result = simple_result()
        result["items"].append(copy.deepcopy(result["items"][0]))
        self.assertTrue(check_result(result, self.article))

    def test_reference_unresolved_is_visible(self):
        result = simple_result()
        result["items"][0]["unresolved_references"] = ["Article 17"]
        self.assertTrue(check_result(result, self.article))


class SourceSpanTests(unittest.TestCase):
    def setUp(self):
        self.article = prepare_article(pages_fixture(), 5)
        self.spans, self.inventories = build_source_spans(self.article)

    def selected_result(self):
        return {"items": [{
            "unit_id": u["unit_id"],
            "disposition": "Article " + u["unit_id"],
            "title_fr": "Titre", "summary_fr": "Résumé",
            "statement_fr": "Énoncé détaillé",
            "conditions": [], "exceptions": [], "consequences": [],
            "unresolved_references": [],
            "evidence": [{"span_id": span_id} for span_id in
                         u["own_span_ids"] + u["parent_span_ids"]],
        } for u in self.inventories], "review_notes": []}

    def test_spans_preserve_source_bytes_as_text(self):
        source_by_id = {f.passage_id: f.text for f in self.article.fragments}
        for span in self.spans.values():
            original = source_by_id[span["passage_id"]]
            self.assertEqual(span["quote"], original[span["fragment_start"]:span["fragment_end"]])

    def test_hydrated_evidence_passes_exact_quote_check(self):
        result, errors = resolve_evidence(self.selected_result(), self.spans, self.inventories)
        self.assertEqual(errors, [])
        self.assertEqual(check_result(result, self.article), [])

    def test_unknown_span_rejected(self):
        raw = self.selected_result()
        raw["items"][0]["evidence"] = [{"span_id": "INVENTED"}]
        _, errors = resolve_evidence(raw, self.spans, self.inventories)
        self.assertTrue(errors)

    def test_other_unit_span_rejected(self):
        raw = self.selected_result()
        raw["items"][0]["evidence"].append(raw["items"][1]["evidence"][0])
        _, errors = resolve_evidence(raw, self.spans, self.inventories)
        self.assertTrue(any("invalid source span" in error for error in errors))

    def test_parent_context_cannot_be_silently_omitted(self):
        raw = self.selected_result()
        entry = self.inventories[0]
        raw["items"][0]["evidence"] = [{"span_id": entry["own_span_ids"][0]}]
        _, errors = resolve_evidence(raw, self.spans, self.inventories)
        self.assertTrue(any("inherited" in error for error in errors))

    def test_model_quote_is_never_used(self):
        raw = self.selected_result()
        raw["items"][0]["evidence"][0]["quote"] = "fabricated quote [...]"
        result, errors = resolve_evidence(raw, self.spans, self.inventories)
        self.assertEqual(errors, [])
        self.assertNotIn("fabricated", result["items"][0]["evidence"][0]["quote"])

    def test_french_threshold_cannot_exist_only_in_quote(self):
        raw = self.selected_result()
        result, _ = resolve_evidence(raw, self.spans, self.inventories)
        errors = check_article_5_thresholds(result)
        self.assertTrue(any("5.1.a.iii" in error for error in errors))

    def test_four_explicit_french_thresholds(self):
        result = self.selected_result()
        statements = {
            "5.1.a.iii": "Suspension d’au moins deux ans.",
            "5.1.b": "Période de 24 mois avant candidature.",
            "5.1.c.i": "Période de cinq ans avant candidature.",
            "5.1.d.i": "Période de douze mois avant candidature.",
        }
        for item in result["items"]:
            item["statement_fr"] = statements.get(item["unit_id"], "Autre règle.")
        self.assertEqual(check_article_5_thresholds(result), [])


if __name__ == "__main__":
    unittest.main()
