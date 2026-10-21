import copy
import unittest

from app.extraction_core import (
    Article, Fragment, Unit, EXPECTED_ARTICLE_5,
    inventory, prepare_article, check_result,
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


if __name__ == "__main__":
    unittest.main()
