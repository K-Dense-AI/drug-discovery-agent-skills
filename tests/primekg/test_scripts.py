"""Tests for the PrimeKG query helpers.

PrimeKG itself is a ~4 million edge CSV nobody should download to run a test,
so these drive the same code against a small hand-built edge list with the
real column layout (`x_id, x_type, x_name, x_source, relation,
display_relation, y_*`). The queries treat the graph as undirected -- a node
can appear on either side of an edge -- and that symmetry is the easiest thing
to get wrong, so most of the assertions are about it.
"""

from __future__ import annotations

import os
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


class LoadingTests(PrimeKgTestCase):
    """The edge list is parsed once per graph, not once per query."""

    def test_repeated_queries_parse_the_csv_only_once(self) -> None:
        # PrimeKG is ~4 million edges; get_disease_context alone calls two
        # query functions, so a re-read per call is seconds of wasted work.
        with mock.patch.object(
            query_primekg.pd, "read_csv", wraps=query_primekg.pd.read_csv
        ) as read_csv:
            query_primekg.search_nodes("BRCA1")
            query_primekg.get_neighbors("672")
            query_primekg.get_disease_context("Breast Cancer")
        self.assertEqual(read_csv.call_count, 1)

    def test_a_changed_file_is_re_read(self) -> None:
        query_primekg.search_nodes("BRCA1")
        self.data.write_text(
            EDGES.replace("BRCA1", "BRCA2"), encoding="utf-8"
        )
        # st_mtime_ns has nanosecond resolution but some filesystems do not;
        # the size is unchanged here, so touch the mtime explicitly.
        stat = self.data.stat()
        os.utime(self.data, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        self.assertEqual(
            [row["name"] for row in query_primekg.search_nodes("BRCA2")], ["BRCA2"]
        )

    def test_pointing_at_a_different_graph_does_not_serve_the_old_one(self) -> None:
        query_primekg.search_nodes("BRCA1")
        other = Path(self._temporary.name) / "other.csv"
        other.write_text(EDGES.replace("BRCA1", "BRCA2"), encoding="utf-8")
        with mock.patch.object(query_primekg, "DATA_PATH", str(other)):
            self.assertEqual(query_primekg.search_nodes("BRCA1"), [])


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

    def test_the_query_is_a_literal_substring_not_a_regular_expression(self) -> None:
        # Gene and drug names carry regex metacharacters. Passing the query
        # through as a pattern would either raise or match far too much.
        self.assertEqual(query_primekg.search_nodes("BRCA1("), [])
        self.assertEqual(query_primekg.search_nodes("B.CA1"), [])
        self.assertEqual(
            [row["name"] for row in query_primekg.search_nodes("BRCA1")], ["BRCA1"]
        )

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

    def test_a_two_hop_path_goes_through_a_shared_neighbour(self) -> None:
        # Olaparib and Breast Cancer share no edge, but both touch BRCA1 --
        # the drug-repurposing shape the skill advertises.
        paths = query_primekg.find_paths("CHEMBL1", "D001", max_depth=2)
        self.assertEqual(len(paths), 1)
        hops = paths[0]
        self.assertEqual(len(hops), 2)
        self.assertEqual(
            [hop["relation"] for hop in hops], ["drug_protein", "disease_protein"]
        )

    def test_the_hops_are_ordered_from_start_to_end(self) -> None:
        # First hop leaves the start node, second hop arrives at the end node.
        first, second = query_primekg.find_paths("CHEMBL1", "D001")[0]
        self.assertEqual(str(first["x_id"]), "CHEMBL1")
        self.assertEqual(str(second["x_id"]), "D001")
        # Both hops meet at BRCA1.
        self.assertEqual(str(first["y_id"]), "672")
        self.assertEqual(str(second["y_id"]), "672")

    def test_depth_one_excludes_two_hop_paths(self) -> None:
        self.assertEqual(query_primekg.find_paths("CHEMBL1", "D001", max_depth=1), [])

    def test_an_unsupported_depth_is_rejected_rather_than_ignored(self) -> None:
        # The old stub accepted any depth and silently searched one hop.
        for depth in (0, 3):
            with self.subTest(depth=depth):
                with self.assertRaises(ValueError):
                    query_primekg.find_paths("CHEMBL1", "D001", max_depth=depth)

    def test_a_two_hop_search_does_not_bounce_off_the_endpoints(self) -> None:
        # TP53 and Ovarian Cancer are directly connected. The two-hop search
        # must not also report the degenerate path start -> end -> start.
        paths = query_primekg.find_paths("7157", "D002")
        self.assertTrue(all(len(hops) == 1 for hops in paths))


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


# query_primekg.py is both an importable module and an argparse CLI, so it owes
# the same --help contract as every other script in the bundle.
CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class CliWiringTests(unittest.TestCase):
    """Parse argv through the real parser rather than shelling out."""

    def test_every_subcommand_binds_a_callable_handler(self) -> None:
        cases = [
            ["search", "Breast"],
            ["neighbors", "D001"],
            ["context", "Breast Cancer"],
            ["paths", "CHEMBL1", "D001"],
        ]
        parser = query_primekg.build_parser()
        for argv in cases:
            with self.subTest(command=argv[0]):
                args = parser.parse_args(argv)
                self.assertTrue(callable(getattr(args, "handler", None)))

    def test_documented_defaults_are_what_the_parser_actually_sets(self) -> None:
        parser = query_primekg.build_parser()
        self.assertEqual(parser.parse_args(["paths", "A", "B"]).max_depth, 2)
        self.assertEqual(parser.parse_args(["search", "x"]).format, "tsv")
        self.assertIsNone(parser.parse_args(["search", "x"]).node_type)

    def test_a_missing_data_file_exits_non_zero_rather_than_tracebacking(self) -> None:
        # The whole point of the exit code: a caller must be able to tell a
        # missing download from an empty result set.
        with mock.patch.object(query_primekg, "DATA_PATH", "/nonexistent/kg.csv"):
            self.assertEqual(query_primekg.main(["search", "anything"]), 2)


if __name__ == "__main__":
    unittest.main()
