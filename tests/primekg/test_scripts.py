"""Tests for the PrimeKG query helpers.

PrimeKG itself is a ~4 million edge CSV nobody should download to run a test,
so these drive the same code against a small hand-built edge list with the
real column layout (`x_id, x_type, x_name, x_source, relation,
display_relation, y_*`). The queries treat the graph as undirected -- a node
can appear on either side of an edge -- and that symmetry is the easiest thing
to get wrong, so most of the assertions are about it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "primekg"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("pandas", reason="primekg needs pandas")

import query_primekg  # noqa: E402

EDGES = """\
x_id,x_type,x_name,x_source,relation,display_relation,y_id,y_type,y_name,y_source
7157,gene/protein,TP53,NCBI,protein_protein,interacts with,672,gene/protein,BRCA1,NCBI
D001,disease,Breast Cancer,MONDO,disease_protein,associated with,672,gene/protein,BRCA1,NCBI
CHEMBL1,drug,Olaparib,DrugBank,drug_protein,targets,672,gene/protein,BRCA1,NCBI
D001,disease,Breast Cancer,MONDO,disease_phenotype,presents,HP001,phenotype,Breast Mass,HPO
D001,disease,Breast Cancer,MONDO,disease_disease,related to,D002,disease,Ovarian Cancer,MONDO
D002,disease,Ovarian Cancer,MONDO,disease_protein,associated with,7157,gene/protein,TP53,NCBI
"""


class PrimeKgTestCase(unittest.TestCase):
    """Point DATA_PATH at a small synthetic knowledge graph."""

    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self._temporary.cleanup)
        self.data = Path(self._temporary.name) / "kg.csv"
        self.data.write_text(EDGES, encoding="utf-8")
        patcher = mock.patch.object(query_primekg, "DATA_PATH", str(self.data))
        patcher.start()
        self.addCleanup(patcher.stop)


class DataPathTests(unittest.TestCase):
    def test_the_default_path_is_relative_and_env_overridable(self) -> None:
        # A hardcoded absolute path would name one machine and work on no other.
        self.assertFalse(Path(query_primekg.DATA_PATH).is_absolute())

        with mock.patch.dict("os.environ", {"PRIMEKG_DATA": "/somewhere/kg.csv"}):
            import importlib

            reloaded = importlib.reload(query_primekg)
            self.assertEqual(reloaded.DATA_PATH, "/somewhere/kg.csv")
        importlib.reload(query_primekg)

    def test_a_missing_file_explains_where_to_get_the_data(self) -> None:
        with mock.patch.object(query_primekg, "DATA_PATH", "/no/such/kg.csv"):
            with self.assertRaises(FileNotFoundError) as raised:
                query_primekg._load_kg()
        message = str(raised.exception)
        self.assertIn("/no/such/kg.csv", message)
        self.assertIn("PRIMEKG_DATA", message)


class SearchTests(PrimeKgTestCase):
    def test_nodes_are_found_on_either_side_of_an_edge(self) -> None:
        # TP53 appears as x in one row and as y in another; one record either way.
        results = query_primekg.search_nodes("TP53")
        self.assertEqual(len(results), 1)
        # PrimeKG mixes numeric gene ids with string disease ids in one column,
        # so pandas reads it as object dtype and ids come back as strings --
        # which is why get_neighbors coerces with str() before comparing.
        self.assertEqual(str(results[0]["id"]), "7157")
        self.assertEqual(results[0]["type"], "gene/protein")

    def test_search_is_case_insensitive_and_substring_based(self) -> None:
        for query in ("breast cancer", "BREAST", "east Can"):
            with self.subTest(query=query):
                names = {row["name"] for row in query_primekg.search_nodes(query)}
                self.assertIn("Breast Cancer", names)

    def test_a_type_filter_narrows_the_result(self) -> None:
        # "Breast" matches both the disease and the phenotype.
        unfiltered = {row["name"] for row in query_primekg.search_nodes("Breast")}
        self.assertEqual(unfiltered, {"Breast Cancer", "Breast Mass"})

        filtered = query_primekg.search_nodes("Breast", node_type="phenotype")
        self.assertEqual([row["name"] for row in filtered], ["Breast Mass"])

    def test_no_match_returns_an_empty_list(self) -> None:
        self.assertEqual(query_primekg.search_nodes("no-such-gene"), [])

    def test_results_carry_the_source_database(self) -> None:
        self.assertEqual(query_primekg.search_nodes("Olaparib")[0]["source"], "DrugBank")


class NeighborTests(PrimeKgTestCase):
    def test_neighbors_are_collected_from_both_directions(self) -> None:
        # BRCA1 is only ever a y-node, so a one-sided query would return none.
        neighbors = query_primekg.get_neighbors(672)
        names = {row["neighbor_name"] for row in neighbors}
        self.assertEqual(names, {"TP53", "Breast Cancer", "Olaparib"})

    def test_a_node_id_is_matched_as_a_string_or_a_number(self) -> None:
        self.assertEqual(
            len(query_primekg.get_neighbors(672)),
            len(query_primekg.get_neighbors("672")),
        )

    def test_a_relation_filter_restricts_the_edge_type(self) -> None:
        targeted = query_primekg.get_neighbors(672, relation_type="drug_protein")
        self.assertEqual([row["neighbor_name"] for row in targeted], ["Olaparib"])

    def test_the_display_relation_is_carried_through(self) -> None:
        targeted = query_primekg.get_neighbors(672, relation_type="drug_protein")
        self.assertEqual(targeted[0]["display_relation"], "targets")

    def test_an_unknown_node_has_no_neighbors(self) -> None:
        self.assertEqual(query_primekg.get_neighbors("not-a-node"), [])


class PathTests(PrimeKgTestCase):
    def test_a_direct_edge_is_returned_as_a_one_hop_path(self) -> None:
        paths = query_primekg.find_paths("D001", "672")
        self.assertEqual(len(paths), 1)
        self.assertEqual(len(paths[0]), 1)
        self.assertEqual(paths[0][0]["relation"], "disease_protein")

    def test_direction_does_not_matter(self) -> None:
        self.assertEqual(
            len(query_primekg.find_paths("D001", "672")),
            len(query_primekg.find_paths("672", "D001")),
        )

    def test_unconnected_nodes_yield_no_path(self) -> None:
        self.assertEqual(query_primekg.find_paths("CHEMBL1", "HP001"), [])

    def test_two_hop_search_is_documented_as_unimplemented(self) -> None:
        # The depth-2 branch is a stub; assert the current contract rather than
        # a capability the script does not have.
        self.assertEqual(query_primekg.find_paths("CHEMBL1", "D001", max_depth=2), [])


class DiseaseContextTests(PrimeKgTestCase):
    def test_the_context_is_bucketed_by_neighbour_type(self) -> None:
        context = query_primekg.get_disease_context("Breast Cancer")
        self.assertEqual(context["disease_info"]["name"], "Breast Cancer")
        self.assertEqual(
            [row["neighbor_name"] for row in context["associated_genes"]], ["BRCA1"]
        )
        self.assertEqual(
            [row["neighbor_name"] for row in context["phenotypes"]], ["Breast Mass"]
        )
        self.assertEqual(
            [row["neighbor_name"] for row in context["related_diseases"]],
            ["Ovarian Cancer"],
        )

    def test_a_disease_with_no_drug_edges_reports_an_empty_bucket(self) -> None:
        context = query_primekg.get_disease_context("Breast Cancer")
        self.assertEqual(context["associated_drugs"], [])

    def test_an_unknown_disease_reports_an_error_rather_than_raising(self) -> None:
        self.assertEqual(
            query_primekg.get_disease_context("no-such-disease"),
            {"error": "Disease not found"},
        )

    def test_a_gene_name_is_not_mistaken_for_a_disease(self) -> None:
        # search_nodes is type-filtered to 'disease', so a gene must not match.
        self.assertEqual(
            query_primekg.get_disease_context("TP53"), {"error": "Disease not found"}
        )


if __name__ == "__main__":
    unittest.main()
