"""Tests for the UniProt / RCSB / AlphaFold retrieval scripts.

No network. Two groups:

* transport behaviours these services get wrong in ways that look like success
  -- header-based pagination, 204-for-no-hits, doubly-gzipped bodies;
* the structure parser, which is the part with real logic. Its fixtures are
  hand-written miniatures rather than downloaded files, so the expected
  answers are obvious by inspection.
"""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "uniprot-rcsb"
SCRIPTS = SKILL_ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


common = _load("_common", "_common.py")
uniprot_fetch = _load("uniprot_fetch_script", "uniprot_fetch.py")
rcsb_search = _load("rcsb_search_script", "rcsb_search.py")
fetch_structure = _load("fetch_structure_script", "fetch_structure.py")
structure_report = _load("structure_report_script", "structure_report.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, status: int = 200, headers: dict | None = None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def responder(pages):
    """Serve a queue of (status, headers, body) tuples, in order."""
    queue = list(pages)

    def _open(request, timeout=None):
        status, headers, body = queue.pop(0)
        return FakeResponse(body, status, headers)

    return _open


class GzipTests(unittest.TestCase):
    def test_a_plain_body_is_returned_unchanged(self) -> None:
        self.assertEqual(common._decoded(b'{"a": 1}'), b'{"a": 1}')

    def test_single_gzip_is_decompressed(self) -> None:
        self.assertEqual(common._decoded(gzip.compress(b"hello")), b"hello")

    def test_double_gzip_is_decompressed(self) -> None:
        """UniProt wraps already-gzipped payloads in transport gzip.

        One round leaves bytes that still start with the gzip magic, and the
        failure surfaces far away as a UnicodeDecodeError on byte 1.
        """
        doubled = gzip.compress(gzip.compress(b"hello"))
        self.assertEqual(common._decoded(doubled), b"hello")

    def test_decompression_is_bounded(self) -> None:
        deep = gzip.compress(gzip.compress(gzip.compress(gzip.compress(b"x"))))
        result = common._decoded(deep)
        self.assertIsInstance(result, bytes)


class LinkHeaderPaginationTests(unittest.TestCase):
    """UniProt paginates in a header; a body-only reader silently truncates."""

    def test_every_page_is_followed(self) -> None:
        pages = [
            (
                200,
                {"Link": '<https://rest.uniprot.org/next-1>; rel="next"'},
                json.dumps({"results": [{"primaryAccession": "P1"}]}).encode(),
            ),
            (
                200,
                {"Link": '<https://rest.uniprot.org/next-2>; rel="next"'},
                json.dumps({"results": [{"primaryAccession": "P2"}]}).encode(),
            ),
            (200, {}, json.dumps({"results": [{"primaryAccession": "P3"}]}).encode()),
        ]
        with mock.patch("urllib.request.urlopen", responder(pages)):
            accessions = [
                entry["primaryAccession"]
                for page in common.uniprot_pages("https://rest.uniprot.org/uniprotkb/search")
                for entry in page["results"]
            ]
        self.assertEqual(accessions, ["P1", "P2", "P3"])

    def test_a_link_header_without_a_next_relation_stops(self) -> None:
        pages = [(200, {"Link": '<https://x/prev>; rel="prev"'}, b'{"results": []}')]
        with mock.patch("urllib.request.urlopen", responder(pages)):
            collected = list(common.uniprot_pages("https://rest.uniprot.org/uniprotkb/search"))
        self.assertEqual(len(collected), 1)

    def test_a_204_page_ends_the_walk(self) -> None:
        with mock.patch("urllib.request.urlopen", responder([(204, {}, b"")])):
            self.assertEqual(list(common.uniprot_pages("https://rest.uniprot.org/x")), [])


class NoHitsTests(unittest.TestCase):
    def test_rcsb_204_means_no_hits_not_a_parse_error(self) -> None:
        with mock.patch("urllib.request.urlopen", responder([(204, {}, b"")])):
            total, results = rcsb_search.run_search({"type": "terminal"})
        self.assertEqual((total, results), (0, []))

    def test_a_populated_result_set_is_returned(self) -> None:
        body = json.dumps(
            {"total_count": 2, "result_set": [{"identifier": "1IEP", "score": 1.0}]}
        ).encode()
        with mock.patch("urllib.request.urlopen", responder([(200, {}, body)])):
            total, results = rcsb_search.run_search({"type": "terminal"})
        self.assertEqual(total, 2)
        self.assertEqual(results[0]["identifier"], "1IEP")

    def test_experimental_content_is_pinned_by_default(self) -> None:
        """The API default includes computational models."""
        captured = {}

        def _open(request, timeout=None):
            captured.update(json.loads(request.data.decode()))
            return FakeResponse(b"", 204)

        with mock.patch("urllib.request.urlopen", _open):
            rcsb_search.run_search({"type": "terminal"})
        self.assertEqual(
            captured["request_options"]["results_content_type"], ["experimental"]
        )


class SearchQueryTests(unittest.TestCase):
    def test_a_single_node_group_is_not_wrapped(self) -> None:
        node = rcsb_search.attribute_node("a", "exact_match", "x")
        self.assertEqual(rcsb_search.group([node]), node)

    def test_several_nodes_become_an_and_group(self) -> None:
        nodes = [
            rcsb_search.attribute_node("a", "exact_match", "x"),
            rcsb_search.attribute_node("b", "less", 2),
        ]
        combined = rcsb_search.group(nodes)
        self.assertEqual(combined["logical_operator"], "and")
        self.assertEqual(len(combined["nodes"]), 2)

    def test_ligand_search_uses_a_searchable_attribute(self) -> None:
        """`chem_comp.id` is not enabled on the text service."""
        source = (SCRIPTS / "rcsb_search.py").read_text(encoding="utf-8")
        self.assertIn(
            "rcsb_nonpolymer_entity_container_identifiers.nonpolymer_comp_id", source
        )

    def test_short_sequences_are_refused_before_the_request(self) -> None:
        args = rcsb_search.build_parser().parse_args(["sequence", "MKV"])
        with self.assertRaises(common.ServiceError):
            args.handler(args)


class EntryFlatteningTests(unittest.TestCase):
    ENTRY = {
        "rcsb_id": "1IEP",
        "struct": {"title": "Imatinib bound to ABL kinase"},
        "exptl": [{"method": "X-RAY DIFFRACTION"}],
        "refine": [{"ls_R_factor_R_free": 0.262}],
        "rcsb_accession_info": {"initial_release_date": "2002-08-14T00:00:00Z"},
        "rcsb_entry_info": {
            "resolution_combined": [2.1],
            "polymer_entity_count": 1,
            "deposited_polymer_monomer_count": 548,
            "deposited_unmodeled_polymer_monomer_count": 38,
        },
        "polymer_entities": [
            {
                "rcsb_polymer_entity": {"pdbx_description": "ABL1", "pdbx_mutation": "H396P"},
                "rcsb_polymer_entity_container_identifiers": {"uniprot_ids": ["P00520"]},
            }
        ],
        "nonpolymer_entities": [
            {"nonpolymer_comp": {"chem_comp": {"id": "STI", "formula_weight": 493.6}}},
            {"nonpolymer_comp": {"chem_comp": {"id": "CL", "formula_weight": 35.5}}},
        ],
    }

    def test_additives_are_not_counted_as_ligands(self) -> None:
        flat = rcsb_search._flatten_entry(self.ENTRY)
        self.assertEqual(flat["ligands"], "STI")
        self.assertEqual(flat["ligandCount"], 1, "chloride is an additive, not a ligand")

    def test_mutations_and_uniprot_ids_are_surfaced(self) -> None:
        flat = rcsb_search._flatten_entry(self.ENTRY)
        self.assertEqual(flat["mutations"], "H396P")
        self.assertEqual(flat["uniprotIds"], "P00520")

    def test_unmodelled_residue_count_is_kept(self) -> None:
        flat = rcsb_search._flatten_entry(self.ENTRY)
        self.assertEqual(flat["unmodelledResidues"], 38)

    def test_an_apo_entry_reports_no_ligands(self) -> None:
        entry = dict(self.ENTRY, nonpolymer_entities=[])
        flat = rcsb_search._flatten_entry(entry)
        self.assertEqual(flat["ligands"], "")
        self.assertEqual(flat["ligandCount"], 0)

    def test_missing_optional_blocks_do_not_crash(self) -> None:
        flat = rcsb_search._flatten_entry({"rcsb_id": "XXXX"})
        self.assertEqual(flat["pdbId"], "XXXX")
        self.assertIsNone(flat["resolution"])


MINI_PDB = """\
REMARK 465 MISSING RESIDUES
REMARK 465 THE FOLLOWING RESIDUES WERE NOT LOCATED IN THE
REMARK 465   M RES C SSSEQI
REMARK 465     GLY A    10
REMARK 465     SER A    11
REMARK 465     LYS A    16
REMARK 465     TRP A    31
ATOM      1  N   ALA A  12      11.104  13.207  10.000  1.00 20.00           N
ATOM      2  CA  ALA A  12      12.104  13.207  10.000  1.00 20.00           C
ATOM      3  N   CYS A  13      13.104  13.207  10.000  0.50 20.00           N
ATOM      4  CA ACYS A  13      14.104  13.207  10.000  0.50 20.00           C
ATOM      5  CA BCYS A  13      14.504  13.607  10.000  0.50 20.00           C
ATOM      6  N   GLY A  15      15.104  13.207  10.000  1.00 20.00           N
ATOM      7  N   VAL B  20      16.104  13.207  10.000  1.00 20.00           N
HETATM    8  C1  STI A 201      17.104  13.207  10.000  1.00 20.00           C
HETATM    9  C2  STI A 201      18.104  13.207  10.000  1.00 20.00           C
HETATM   10  S   SO4 A 301      19.104  13.207  10.000  1.00 20.00           S
HETATM   11  O   HOH A 401      20.104  13.207  10.000  1.00 20.00           O
END
"""

MINI_CIF = """\
data_TEST
#
loop_
_pdbx_unobs_or_zero_occ_residues.id
_pdbx_unobs_or_zero_occ_residues.PDB_model_num
_pdbx_unobs_or_zero_occ_residues.auth_asym_id
_pdbx_unobs_or_zero_occ_residues.auth_comp_id
_pdbx_unobs_or_zero_occ_residues.auth_seq_id
1 1 A GLY 10
2 1 A SER 11
3 1 A LYS 16
4 1 A TRP 31
#
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_alt_id
_atom_site.label_comp_id
_atom_site.auth_asym_id
_atom_site.auth_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.occupancy
_atom_site.auth_comp_id
_atom_site.pdbx_PDB_model_num
ATOM   1  N N  . ALA A 12 ? 1.00 ALA 1
ATOM   2  C CA . ALA A 12 ? 1.00 ALA 1
ATOM   3  N N  . CYS A 13 ? 0.50 CYS 1
ATOM   4  C CA A CYS A 13 ? 0.50 CYS 1
ATOM   5  C CA B CYS A 13 ? 0.50 CYS 1
ATOM   6  N N  . GLY A 15 ? 1.00 GLY 1
ATOM   7  N N  . VAL B 20 ? 1.00 VAL 1
HETATM 8  C C1 . STI A 201 ? 1.00 STI 1
HETATM 9  C C2 . STI A 201 ? 1.00 STI 1
HETATM 10 S S  . SO4 A 301 ? 1.00 SO4 1
HETATM 11 O O  . HOH A 401 ? 1.00 HOH 1
#
"""


class StructureParsingTests(unittest.TestCase):
    """Both formats must produce the same answer for the same structure."""

    def setUp(self) -> None:
        self.pdb_atoms = structure_report.parse_pdb(MINI_PDB)
        self.cif_atoms = structure_report.parse_mmcif(MINI_CIF)

    def test_both_parsers_find_every_atom(self) -> None:
        self.assertEqual(len(self.pdb_atoms), 11)
        self.assertEqual(len(self.cif_atoms), 11)

    def test_chains_residues_and_records_agree(self) -> None:
        for label, atoms in (("pdb", self.pdb_atoms), ("cif", self.cif_atoms)):
            with self.subTest(format=label):
                self.assertEqual({atom.chain for atom in atoms}, {"A", "B"})
                self.assertEqual(
                    sum(1 for atom in atoms if atom.record == "HETATM"), 4
                )
                self.assertEqual({atom.altloc for atom in atoms} & {"A", "B"}, {"A", "B"})

    def test_occupancy_is_read_as_a_number(self) -> None:
        for atoms in (self.pdb_atoms, self.cif_atoms):
            partial = [atom for atom in atoms if atom.occupancy < 0.99]
            self.assertEqual(len(partial), 3)


class StructureAnalysisTests(unittest.TestCase):
    def _summary(self, text: str, is_cif: bool) -> dict:
        atoms = structure_report.parse_mmcif(text) if is_cif else structure_report.parse_pdb(text)
        unobserved = structure_report.parse_unobserved(text, is_cif)
        return structure_report.analyse(atoms, None, unobserved)

    def test_internal_gaps_are_found_from_the_numbering(self) -> None:
        summary = self._summary(MINI_PDB, False)
        chain_a = next(row for row in summary["chains"] if row["chain"] == "A")
        # Observed 12,13,15; 14 is missing inside the range.
        self.assertEqual(chain_a["gaps"], "14")
        self.assertEqual(chain_a["gapResidues"], 1)

    def test_declared_unobserved_residues_inside_the_range_join_the_gaps(self) -> None:
        summary = self._summary(MINI_PDB, False)
        chain_a = next(row for row in summary["chains"] if row["chain"] == "A")
        self.assertNotIn("16", chain_a["gaps"], "16 is past the last observed residue")

    def test_terminal_truncation_is_reported_separately(self) -> None:
        """Terminal loss leaves no numbering gap -- the whole point of the field."""
        summary = self._summary(MINI_PDB, False)
        chain_a = next(row for row in summary["chains"] if row["chain"] == "A")
        # Observed range is 12-15; the declared-unobserved 10, 11, 16 and 31
        # all fall outside it, so none of them shows up as a numbering gap.
        self.assertEqual(chain_a["terminalMissing"], 4)
        self.assertEqual(chain_a["terminal"], "10-11,16,31")

    def test_the_two_formats_agree(self) -> None:
        from_pdb = self._summary(MINI_PDB, False)
        from_cif = self._summary(MINI_CIF, True)
        for key in ("chains", "ligands", "solvent", "altlocResidues"):
            with self.subTest(key=key):
                self.assertEqual(from_pdb[key], from_cif[key])

    def test_ligands_exclude_water_and_additives(self) -> None:
        summary = self._summary(MINI_PDB, False)
        self.assertEqual([row["component"] for row in summary["ligands"]], ["STI"])
        self.assertEqual(summary["solvent"], {"SO4": 1, "water": 1})

    def test_alternate_locations_are_counted_per_residue(self) -> None:
        summary = self._summary(MINI_PDB, False)
        self.assertEqual(summary["altlocResidues"], 1)

    def test_observed_sequence_skips_the_gap(self) -> None:
        summary = self._summary(MINI_PDB, False)
        chain_a = next(row for row in summary["chains"] if row["chain"] == "A")
        self.assertEqual(chain_a["sequence"], "ACG")

    def test_no_hydrogens_is_detected(self) -> None:
        summary = self._summary(MINI_PDB, False)
        self.assertEqual(summary["hydrogens"], 0)


class RangeFormattingTests(unittest.TestCase):
    def test_consecutive_numbers_collapse(self) -> None:
        self.assertEqual(structure_report._ranges([3, 4, 5, 9]), "3-5,9")
        self.assertEqual(structure_report._ranges([7]), "7")
        self.assertEqual(structure_report._ranges([]), "")
        self.assertEqual(structure_report._ranges([1, 3, 5]), "1,3,5")


class CifRowSplittingTests(unittest.TestCase):
    def test_quoted_values_survive(self) -> None:
        self.assertEqual(
            structure_report._split_cif_row("ATOM 1 'C A' \"x y\" ALA"),
            ["ATOM", "1", "C A", "x y", "ALA"],
        )


class MultiModelTests(unittest.TestCase):
    def test_only_the_requested_model_is_analysed(self) -> None:
        text = MINI_PDB.replace(
            "ATOM      1", "MODEL        1\nATOM      1"
        ).replace("END", "ENDMDL\nMODEL        2\nATOM     99  N   ALA A  12      "
                         "11.104  13.207  10.000  1.00 20.00           N\nENDMDL\nEND")
        atoms = structure_report.parse_pdb(text)
        self.assertEqual(sorted({atom.model for atom in atoms}), [1, 2])
        summary = structure_report.analyse(atoms, 2)
        self.assertEqual(summary["atoms"], 1)
        self.assertEqual(summary["models"], [1, 2])


class UniProtShapeTests(unittest.TestCase):
    ENTRY = {
        "entryType": "UniProtKB reviewed (Swiss-Prot)",
        "primaryAccession": "P00533",
        "uniProtkbId": "EGFR_HUMAN",
        "proteinDescription": {"recommendedName": {"fullName": {"value": "EGFR"}}},
        "genes": [{"geneName": {"value": "EGFR"}}],
        "organism": {"scientificName": "Homo sapiens"},
        "sequence": {"length": 1210, "value": "MRPSG"},
        "uniProtKBCrossReferences": [
            {"database": "PDB", "id": "1IVO"},
            {"database": "PDB", "id": "1M14"},
            {"database": "ChEMBL", "id": "CHEMBL203"},
        ],
    }

    def test_reviewed_entries_are_recognised(self) -> None:
        self.assertTrue(uniprot_fetch._reviewed(self.ENTRY))
        unreviewed = dict(self.ENTRY, entryType="UniProtKB unreviewed (TrEMBL)")
        self.assertFalse(uniprot_fetch._reviewed(unreviewed))

    def test_summary_counts_only_pdb_cross_references(self) -> None:
        record = uniprot_fetch.summarise(self.ENTRY)
        self.assertEqual(record["pdbCount"], 2)
        self.assertEqual(record["accession"], "P00533")
        self.assertEqual(record["organism"], "Homo sapiens")

    def test_a_submitted_name_is_used_when_there_is_no_recommended_one(self) -> None:
        entry = dict(
            self.ENTRY,
            proteinDescription={"submissionNames": [{"fullName": {"value": "Uncharacterised"}}]},
        )
        self.assertEqual(uniprot_fetch._protein_name(entry), "Uncharacterised")

    def test_an_entry_without_genes_or_sequence_does_not_crash(self) -> None:
        record = uniprot_fetch.summarise({"primaryAccession": "X"})
        self.assertEqual(record["genes"], "")
        self.assertIsNone(record["length"])


class AlphaFoldTests(unittest.TestCase):
    PREDICTION = [
        {
            "entryId": "AF-P00533-F1",
            "uniprotDescription": "EGFR",
            "organismScientificName": "Homo sapiens",
            "latestVersion": 6,
            "toolUsed": "AlphaFold Monomer v2.0 pipeline",
            "uniprotStart": 1,
            "uniprotEnd": 1210,
            "globalMetricValue": 75.94,
            "fractionPlddtVeryHigh": 0.474,
            "fractionPlddtConfident": 0.233,
            "fractionPlddtLow": 0.065,
            "fractionPlddtVeryLow": 0.228,
            "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-P00533-F1-model_v6.cif",
        }
    ]

    def test_metadata_only_reports_bands_and_downloads_nothing(self) -> None:
        args = fetch_structure.build_parser().parse_args(
            ["alphafold", "P00533", "--metadata-only"]
        )
        body = json.dumps(self.PREDICTION).encode()
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch("urllib.request.urlopen", responder([(200, {}, body)])):
            with mock.patch("sys.stdout", stdout), mock.patch("sys.stderr", stderr):
                args.handler(args)
        output = stdout.getvalue()
        self.assertIn("AF-P00533-F1", output)
        self.assertIn("47.4", output)
        # 6.5 % low + 22.8 % very low is under the 30 % warning threshold.
        self.assertNotIn("warning", stderr.getvalue())

    def test_a_mostly_disordered_model_warns(self) -> None:
        prediction = [dict(self.PREDICTION[0], fractionPlddtVeryLow=0.5)]
        args = fetch_structure.build_parser().parse_args(
            ["alphafold", "Q00000", "--metadata-only"]
        )
        stderr = io.StringIO()
        with mock.patch("urllib.request.urlopen", responder([(200, {}, json.dumps(prediction).encode())])):
            with mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", stderr):
                args.handler(args)
        self.assertIn("below pLDDT 70", stderr.getvalue())

    def test_an_absent_model_explains_the_coverage_limit(self) -> None:
        args = fetch_structure.build_parser().parse_args(
            ["alphafold", "P99999", "--metadata-only"]
        )
        with mock.patch("urllib.request.urlopen", responder([(200, {}, b"[]")])):
            with self.assertRaises(common.ServiceError) as caught:
                args.handler(args)
        self.assertIn("reference proteome", str(caught.exception))


class LegacyPdbFormatTests(unittest.TestCase):
    def test_a_404_on_pdb_format_explains_the_size_limit(self) -> None:
        import urllib.error

        def _open(request, timeout=None):
            raise urllib.error.HTTPError(
                request.full_url, 404, "Not Found", {}, io.BytesIO(b"")
            )

        args = fetch_structure.build_parser().parse_args(
            ["pdb", "8ETU", "--file-format", "pdb", "--out-dir", "."]
        )
        with mock.patch("urllib.request.urlopen", _open):
            with mock.patch.object(common.time, "sleep"):
                with self.assertRaises(common.ServiceError) as caught:
                    args.handler(args)
        self.assertIn("mmCIF", str(caught.exception))


class DownloadCapTests(unittest.TestCase):
    def test_an_oversized_response_is_refused_rather_than_written(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "big.cif"
            with mock.patch("urllib.request.urlopen", responder([(200, {}, b"x" * 100)])):
                with self.assertRaises(common.ServiceError):
                    common.download("https://example/big.cif", destination, max_bytes=10)
            self.assertFalse(destination.exists(), "nothing should be written on refusal")

    def test_a_normal_response_is_written(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "ok.cif"
            with mock.patch("urllib.request.urlopen", responder([(200, {}, b"data_x\n")])):
                size = common.download("https://example/ok.cif", destination)
        self.assertEqual(size, 7)


class ParserTests(unittest.TestCase):
    def test_every_subcommand_binds_a_handler(self) -> None:
        cases = [
            (uniprot_fetch, ["entry", "P00533"]),
            (uniprot_fetch, ["search", "gene:EGFR"]),
            (uniprot_fetch, ["fasta", "P00533"]),
            (uniprot_fetch, ["features", "P00533"]),
            (uniprot_fetch, ["map", "P00533"]),
            (uniprot_fetch, ["pdb", "P00533"]),
            (rcsb_search, ["uniprot", "P00533"]),
            (rcsb_search, ["sequence", "M" * 30]),
            (rcsb_search, ["text", "kinase"]),
            (rcsb_search, ["ligand", "STI"]),
            (rcsb_search, ["attribute", "a", "exact_match", "b"]),
            (fetch_structure, ["pdb", "1IEP"]),
            (fetch_structure, ["assembly", "4HHB"]),
            (fetch_structure, ["alphafold", "P00533"]),
            (fetch_structure, ["ligand", "STI"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(getattr(args, "handler", None)))

    def test_structure_report_defaults_to_mmcif_friendly_arguments(self) -> None:
        args = structure_report.build_parser().parse_args(["x.cif", "--gaps-near", "750,790"])
        self.assertEqual(args.gaps_near, "750,790")
        self.assertIsNone(args.model)


if __name__ == "__main__":
    unittest.main()
