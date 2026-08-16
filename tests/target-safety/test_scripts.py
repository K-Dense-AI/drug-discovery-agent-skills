"""Tests for the target-safety clients.

Nothing here touches the network. The parts worth testing are the ones where
these two services fail quietly: gnomAD returning GraphQL errors with HTTP 200,
the GWAS Catalog silently ignoring an unrecognised filter and handing back the
entire catalogue, and the LOEUF banding that decides how a target reads.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import skill_contract

SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "target-safety"
SCRIPTS = SKILL_ROOT / "scripts"


def _load(name: str, filename: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


common = _load("_common", "_common.py")
# safety_dossier imports gnomad_constraint by module name, so register it under
# its real name rather than an alias.
gnomad_constraint = _load("gnomad_constraint", "gnomad_constraint.py")
gwas_evidence = _load("gwas_evidence_script", "gwas_evidence.py")
safety_dossier = _load("safety_dossier_script", "safety_dossier.py")

CliHelpTests = skill_contract.cli.help_test_case(SKILL_ROOT)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def fake_urlopen(payload, *, urls=None):
    def _open(request, timeout=None):
        if urls is not None:
            urls.append(request.full_url)
        body = payload(request) if callable(payload) else payload
        return FakeResponse(json.dumps(body).encode("utf-8"))

    return _open


def http_error(status: int, detail: str):
    def _open(request, timeout=None):
        raise urllib.error.HTTPError(
            request.full_url, status, "error", {}, io.BytesIO(detail.encode("utf-8"))
        )

    return _open


def constraint_payload(**fields):
    base = {
        "exp_lof": 302.5,
        "obs_lof": 203,
        "oe_lof": 0.67,
        "oe_lof_lower": 0.59,
        "oe_lof_upper": 0.7537,
        "pLI": 1.3e-43,
        "oe_mis": 0.95,
        "oe_mis_upper": 0.98,
        "mis_z": 0.94,
        "lof_z": 4.85,
        "syn_z": -0.63,
    }
    base.update(fields)
    return {
        "data": {
            "gene": {
                "gene_id": "ENSG00000188906",
                "symbol": "LRRK2",
                "name": "leucine rich repeat kinase 2",
                "gnomad_constraint": base,
            }
        }
    }


class GnomadTransportTests(unittest.TestCase):
    def test_graphql_errors_arrive_with_http_200_and_still_raise(self) -> None:
        """The failure this client exists to prevent."""
        payload = {"errors": [{"message": 'Cannot query field "nonsense" on type "Gene".'}]}
        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            with self.assertRaises(common.TargetSafetyError) as caught:
                common.gnomad_post("{ gene { nonsense } }")
        self.assertIn("nonsense", str(caught.exception))

    def test_data_is_returned_on_success(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen(constraint_payload())):
            data = common.gnomad_post("{ gene { symbol } }")
        self.assertEqual(data["gene"]["symbol"], "LRRK2")

    def test_unknown_gene_names_the_symbol_problem(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"data": {"gene": None}})):
            with self.assertRaises(common.TargetSafetyError) as caught:
                gnomad_constraint.fetch("NOTAGENE", genome="GRCh38", api_url=common.GNOMAD_URL)
        self.assertIn("HGNC", str(caught.exception))

    def test_retryable_status_is_retried(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(503, "down")):
            with mock.patch("time.sleep") as sleep:
                with self.assertRaises(common.TargetSafetyError):
                    common.gnomad_post("{}", max_attempts=3)
        self.assertEqual(sleep.call_count, 2)

    def test_400_is_not_retried(self) -> None:
        with mock.patch("urllib.request.urlopen", http_error(400, "bad")):
            with mock.patch("time.sleep") as sleep:
                with self.assertRaises(common.TargetSafetyError):
                    common.gnomad_post("{}", max_attempts=3)
        sleep.assert_not_called()


class SilentFilterTests(unittest.TestCase):
    """`?gene=X` returns 1.1 M rows instead of 93, with no error at all."""

    def test_unknown_parameter_is_refused_locally(self) -> None:
        with self.assertRaises(common.TargetSafetyError) as caught:
            common.gwas_get(
                "associations", {"gene": "LRRK2"}, known_params=common.GWAS_ASSOCIATION_PARAMS
            )
        message = str(caught.exception)
        self.assertIn("not a recognised filter", message)
        self.assertIn("mappedGene", message)

    def test_the_correct_parameter_is_allowed(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"_embedded": {}})):
            common.gwas_get(
                "associations",
                {"mappedGene": "LRRK2"},
                known_params=common.GWAS_ASSOCIATION_PARAMS,
            )

    def test_no_known_params_means_no_validation(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"ok": True})):
            self.assertEqual(common.gwas_get("genes/LRRK2"), {"ok": True})

    def test_none_valued_parameters_are_dropped_not_rejected(self) -> None:
        urls: list[str] = []
        with mock.patch("urllib.request.urlopen", fake_urlopen({}, urls=urls)):
            common.gwas_get(
                "associations",
                {"mappedGene": "LRRK2", "size": None},
                known_params=common.GWAS_ASSOCIATION_PARAMS,
            )
        self.assertNotIn("size", urls[0])


class GwasPagingTests(unittest.TestCase):
    def test_pages_until_total_pages_is_reached(self) -> None:
        pages = [
            {"_embedded": {"associations": [{"i": 1}]}, "page": {"totalPages": 2, "number": 0}},
            {"_embedded": {"associations": [{"i": 2}]}, "page": {"totalPages": 2, "number": 1}},
        ]
        seen = {"n": 0}

        def payload(request):
            page = pages[min(seen["n"], len(pages) - 1)]
            seen["n"] += 1
            return page

        with mock.patch("urllib.request.urlopen", fake_urlopen(payload)):
            records = list(common.gwas_paged("associations", {}, "associations"))
        self.assertEqual(len(records), 2)

    def test_empty_embedded_terminates(self) -> None:
        with mock.patch("urllib.request.urlopen", fake_urlopen({"_embedded": {}})):
            self.assertEqual(list(common.gwas_paged("associations", {}, "associations")), [])

    def test_limit_is_respected(self) -> None:
        page = {
            "_embedded": {"associations": [{"i": n} for n in range(30)]},
            "page": {"totalPages": 99, "number": 0},
        }
        with mock.patch("urllib.request.urlopen", fake_urlopen(page)):
            self.assertEqual(len(list(common.gwas_paged("associations", {}, "associations", limit=4))), 4)


class LoeufBandTests(unittest.TestCase):
    """Banding decides how a target reads, so the boundaries are pinned."""

    def test_constrained_band(self) -> None:
        self.assertEqual(common.loeuf_band(0.154)[0], "constrained")

    def test_moderately_constrained_band(self) -> None:
        self.assertEqual(common.loeuf_band(0.45)[0], "moderately constrained")

    def test_tolerant_band(self) -> None:
        self.assertEqual(common.loeuf_band(0.7537)[0], "tolerant")

    def test_unconstrained_band(self) -> None:
        self.assertEqual(common.loeuf_band(1.144)[0], "unconstrained")

    def test_missing_constraint_is_unknown_not_zero(self) -> None:
        """Reporting absent data as LOEUF 0 would invert the conclusion."""
        band, meaning = common.loeuf_band(None)
        self.assertEqual(band, "unknown")
        self.assertIn("not zero constraint", meaning)

    def test_band_boundaries_are_half_open(self) -> None:
        self.assertEqual(common.loeuf_band(0.35)[0], "moderately constrained")
        self.assertEqual(common.loeuf_band(0.60)[0], "tolerant")
        self.assertEqual(common.loeuf_band(1.00)[0], "unconstrained")


class ConstraintRowTests(unittest.TestCase):
    def test_loeuf_is_read_from_oe_lof_upper(self) -> None:
        gene = constraint_payload()["data"]["gene"]
        self.assertAlmostEqual(gnomad_constraint.row_for(gene)["loeuf"], 0.7537)

    def test_absent_constraint_block_yields_unknown(self) -> None:
        row = gnomad_constraint.row_for({"symbol": "X", "gene_id": "ENSG0"})
        self.assertIsNone(row["loeuf"])
        self.assertEqual(row["band"], "unknown")


class VerdictTests(unittest.TestCase):
    """The two axes mean opposite things; the 2x2 must not collapse."""

    def test_tolerant_and_associated_is_supported(self) -> None:
        label, _ = safety_dossier.verdict(1.144, 44)
        self.assertEqual(label, "genetically supported")

    def test_tolerant_without_association_is_unvalidated(self) -> None:
        self.assertEqual(safety_dossier.verdict(1.144, 0)[0], "tolerated, unvalidated")

    def test_constrained_and_associated_warns_about_toxicity(self) -> None:
        label, reasoning = safety_dossier.verdict(0.3379, 59)
        self.assertEqual(label, "associated but constrained")
        self.assertIn("mechanism-based toxicity", reasoning)

    def test_constrained_without_association_is_weakest(self) -> None:
        self.assertEqual(safety_dossier.verdict(0.2, 0)[0], "constrained, unvalidated")

    def test_missing_constraint_is_never_called_safe(self) -> None:
        label, reasoning = safety_dossier.verdict(None, 44)
        self.assertEqual(label, "unknown")
        self.assertIn("absence of data", reasoning)

    def test_tolerance_threshold_matches_the_documented_cut(self) -> None:
        self.assertEqual(safety_dossier.TOLERANT_LOEUF, 0.6)
        self.assertEqual(safety_dossier.verdict(0.6, 1)[0], "genetically supported")
        self.assertEqual(safety_dossier.verdict(0.59, 1)[0], "associated but constrained")


class SignificanceTests(unittest.TestCase):
    def test_genome_wide_threshold(self) -> None:
        self.assertEqual(common.GWAS_SIGNIFICANCE, 5e-8)

    def test_traits_are_read_from_the_efo_field(self) -> None:
        record = {"efo_traits": [{"efo_id": "EFO_1", "efo_trait": "Parkinson disease"}]}
        self.assertEqual(gwas_evidence._traits(record), ["Parkinson disease"])

    def test_missing_traits_is_empty_not_an_error(self) -> None:
        self.assertEqual(gwas_evidence._traits({}), [])


class CliWiringTests(unittest.TestCase):
    def test_every_subcommand_has_a_handler(self) -> None:
        cases = [
            (gnomad_constraint, ["gene", "LRRK2"]),
            (gnomad_constraint, ["compare", "LRRK2", "PCSK9"]),
            (gwas_evidence, ["gene", "LRRK2"]),
            (gwas_evidence, ["traits", "LRRK2"]),
            (safety_dossier, ["gene", "PCSK9"]),
        ]
        for module, argv in cases:
            with self.subTest(argv=argv):
                args = module.build_parser().parse_args(argv)
                self.assertTrue(callable(args.handler))

    def test_default_genome_is_grch38(self) -> None:
        args = gnomad_constraint.build_parser().parse_args(["gene", "LRRK2"])
        self.assertEqual(args.genome, "GRCh38")

    def test_default_output_format_is_tsv(self) -> None:
        args = safety_dossier.build_parser().parse_args(["gene", "PCSK9"])
        self.assertEqual(args.output_format, "tsv")

    def test_floats_are_formatted_compactly(self) -> None:
        self.assertEqual(common._cell(0.7537248912492516), "0.7537")


if __name__ == "__main__":
    unittest.main()
