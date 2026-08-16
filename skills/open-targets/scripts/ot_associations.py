#!/usr/bin/env python3
"""Paged target-disease association and evidence tables from Open Targets.

The association endpoints are where an interactive query stops being enough:
EGFR has ~6,500 associated diseases and asthma ~7,400 associated targets, so
anything useful means paging, filtering by data type, and flattening the
per-datatype score breakdown into columns.

Commands:

    target-diseases   one target  -> ranked diseases   (ENSG id in)
    disease-targets   one disease -> ranked targets    (MONDO id in)
    evidence          the individual evidence records behind one pair

Scores are 0-1 harmonic sums, not probabilities, and they are relative within
a release -- a 0.6 is only meaningful next to the other rows of the same
query. `--only-datasources` rescores from the named sources alone, which is
how you ask "what does the genetic evidence by itself say?"; it both filters
the rows and changes the ranking, so its scores are not comparable with an
unrestricted run.

Examples:

    python ot_associations.py target-diseases ENSG00000146648 --limit 25
    python ot_associations.py target-diseases ENSG00000146648 \\
        --only-datasources gwas_credible_sets gene_burden eva --limit 25
    python ot_associations.py disease-targets MONDO_0004979 --limit 50 \\
        --min-score 0.5 --format tsv
    python ot_associations.py evidence ENSG00000146648 MONDO_0005233 \\
        --datasources clinical_precedence --limit 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    OpenTargetsError,
    add_common_arguments,
    emit,
    paged,
    post,
    write_table,
)

TARGET_DISEASES_QUERY = """
query TargetDiseases(
  $id: String!
  $index: Int!
  $size: Int!
  $datasources: [DatasourceSettingsInput!]
  $enableIndirect: Boolean
) {
  target(ensemblId: $id) {
    id
    approvedSymbol
    associatedDiseases(
      page: {index: $index, size: $size}
      datasources: $datasources
      enableIndirect: $enableIndirect
    ) {
      count
      rows {
        score
        disease { id name therapeuticAreas { id name } }
        datatypeScores { id score }
        datasourceScores { id score }
      }
    }
  }
}
"""

DISEASE_TARGETS_QUERY = """
query DiseaseTargets(
  $id: String!
  $index: Int!
  $size: Int!
  $datasources: [DatasourceSettingsInput!]
  $enableIndirect: Boolean
) {
  disease(efoId: $id) {
    id
    name
    associatedTargets(
      page: {index: $index, size: $size}
      datasources: $datasources
      enableIndirect: $enableIndirect
    ) {
      count
      rows {
        score
        target {
          id
          approvedSymbol
          approvedName
          biotype
          tractability { label modality value }
        }
        datatypeScores { id score }
        datasourceScores { id score }
      }
    }
  }
}
"""

EVIDENCE_QUERY = """
query PairEvidence(
  $ensemblId: String!
  $efoIds: [String!]!
  $datasourceIds: [String!]
  $size: Int!
  $cursor: String
) {
  target(ensemblId: $ensemblId) {
    evidences(
      efoIds: $efoIds
      datasourceIds: $datasourceIds
      size: $size
      cursor: $cursor
    ) {
      count
      cursor
      rows {
        id
        score
        datasourceId
        datatypeId
        disease { id name }
        drug { id name }
        clinicalStage
        clinicalSignificances
        targetModulation
        literature
        publicationYear
        pValueMantissa
        pValueExponent
        studyId
        variantRsId
        confidence
        diseaseFromSource
        targetFromSourceId
      }
    }
  }
}
"""

#: Datatype ids as returned by the 26.06 release. Two of these were renamed
#: from the vocabulary most tutorials still use: `known_drug` is now
#: `clinical`, and `genetic_literature` was split out of `literature`.
DATATYPES = (
    "genetic_association",
    "genetic_literature",
    "somatic_mutation",
    "clinical",
    "affected_pathway",
    "literature",
    "rna_expression",
    "animal_model",
)

#: Datasource ids observed across the 26.06 association scores. The list is
#: needed in full, not just for documentation: restricting a score to a subset
#: means giving every *other* source a weight of zero, so a source missing
#: here would silently keep contributing. Two renames to know about:
#: `chembl` -> `clinical_precedence`, `ot_genetics_portal` ->
#: `gwas_credible_sets`.
DATASOURCES = (
    "cancer_biomarkers",
    "cancer_gene_census",
    "chembl",
    "clingen",
    "clinical_precedence",
    "crispr",
    "crispr_screen",
    "europepmc",
    "eva",
    "eva_somatic",
    "expression_atlas",
    "gene2phenotype",
    "gene_burden",
    "genomics_england",
    "gwas_credible_sets",
    "impc",
    "intogen",
    "orphanet",
    "ot_genetics_portal",
    "progeny",
    "reactome",
    "slapenrich",
    "sysbio",
    "uniprot_literature",
    "uniprot_variants",
)


def _datasource_settings(names: list[str] | None) -> list[dict] | None:
    """`DatasourceSettingsInput` that rescores from `names` alone.

    Two independent knobs, and conflating them is the usual mistake:

    * `required: true` filters the association list to rows carrying at least
      one required source -- it is an OR across the named sources, and it
      trims the zero-scoring tail without changing the ranking of what
      remains. Ask for a source the target has no evidence from at all and
      the count is legitimately 0.
    * `weight` scales a source's contribution to the aggregate score. Sending
      any settings array resets the Platform's default weights for every
      source it mentions, so restricting means explicitly zeroing all the
      others -- hence the full `DATASOURCES` tuple above.

    The per-source `datasourceScores` breakdown in the response is always the
    unweighted score and does not move when these settings change.
    """
    if not names:
        return None
    kept = set(names)
    unknown = sorted(kept - set(DATASOURCES))
    if unknown:
        print(
            f"warning: unrecognised datasource id(s): {', '.join(unknown)} -- "
            "they are still sent, but check references/datasources.md for the "
            "current vocabulary",
            file=sys.stderr,
        )
    return [
        {
            "id": source,
            "weight": 1.0 if source in kept else 0.0,
            "propagate": True,
            "required": source in kept,
        }
        for source in sorted(kept | set(DATASOURCES))
    ]


def _flatten_scores(row: dict, key: str) -> dict[str, float]:
    return {entry["id"]: entry["score"] for entry in row.get(key) or [] if entry.get("id")}


def command_target_diseases(args: argparse.Namespace) -> None:
    variables = {
        "id": args.ensembl_id,
        "datasources": _datasource_settings(args.datasources),
        "enableIndirect": args.indirect,
    }
    rows = []
    for row in paged(
        TARGET_DISEASES_QUERY,
        variables,
        path=("target", "associatedDiseases"),
        size=args.page_size,
        limit=args.limit,
        url=args.api_url,
    ):
        score = row.get("score") or 0.0
        if score < args.min_score:
            continue
        disease = row.get("disease") or {}
        datatypes = _flatten_scores(row, "datatypeScores")
        record = {
            "diseaseId": disease.get("id"),
            "diseaseName": disease.get("name"),
            "score": round(score, 4),
            "therapeuticAreas": "|".join(
                area.get("name") or "" for area in disease.get("therapeuticAreas") or []
            ),
        }
        record.update({datatype: round(datatypes.get(datatype, 0.0), 4) for datatype in DATATYPES})
        if args.with_datasources:
            record["datasourceScores"] = _flatten_scores(row, "datasourceScores")
        rows.append(record)

    columns = ["diseaseId", "diseaseName", "score", *DATATYPES, "therapeuticAreas"]
    _emit_rows(rows, columns, args)


def command_disease_targets(args: argparse.Namespace) -> None:
    variables = {
        "id": args.disease_id,
        "datasources": _datasource_settings(args.datasources),
        "enableIndirect": args.indirect,
    }
    rows = []
    for row in paged(
        DISEASE_TARGETS_QUERY,
        variables,
        path=("disease", "associatedTargets"),
        size=args.page_size,
        limit=args.limit,
        url=args.api_url,
    ):
        score = row.get("score") or 0.0
        if score < args.min_score:
            continue
        target = row.get("target") or {}
        datatypes = _flatten_scores(row, "datatypeScores")
        tractability = {
            f"{item.get('modality')}:{item.get('label')}"
            for item in target.get("tractability") or []
            if item.get("value")
        }
        record = {
            "targetId": target.get("id"),
            "symbol": target.get("approvedSymbol"),
            "score": round(score, 4),
            "biotype": target.get("biotype"),
            "tractableSM": any(bucket.startswith("SM:") for bucket in tractability),
            "tractableAB": any(bucket.startswith("AB:") for bucket in tractability),
            "tractabilityBuckets": "|".join(sorted(tractability)),
        }
        record.update({datatype: round(datatypes.get(datatype, 0.0), 4) for datatype in DATATYPES})
        if args.with_datasources:
            record["datasourceScores"] = _flatten_scores(row, "datasourceScores")
        rows.append(record)

    columns = [
        "targetId",
        "symbol",
        "score",
        *DATATYPES,
        "biotype",
        "tractableSM",
        "tractableAB",
        "tractabilityBuckets",
    ]
    _emit_rows(rows, columns, args)


def command_evidence(args: argparse.Namespace) -> None:
    """Walk the cursor-paginated evidence field for one target-disease pair.

    Unlike the association fields, `evidences` pages by opaque cursor, so this
    cannot reuse `paged()`. A null cursor in the response means the last page.
    """
    rows = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    while True:
        data = post(
            EVIDENCE_QUERY,
            {
                "ensemblId": args.ensembl_id,
                "efoIds": [args.disease_id],
                "datasourceIds": args.datasources or None,
                "size": min(args.page_size, 100),
                "cursor": cursor,
            },
            url=args.api_url,
        )
        target = data.get("target")
        if target is None:
            raise OpenTargetsError(f"no target for {args.ensembl_id}")
        evidences = target.get("evidences") or {}
        for row in evidences.get("rows") or []:
            rows.append(
                {
                    "datasourceId": row.get("datasourceId"),
                    "datatypeId": row.get("datatypeId"),
                    "score": round(row.get("score") or 0.0, 4),
                    "diseaseId": (row.get("disease") or {}).get("id"),
                    "diseaseFromSource": row.get("diseaseFromSource"),
                    "drug": (row.get("drug") or {}).get("name"),
                    "clinicalStage": row.get("clinicalStage"),
                    "clinicalSignificances": "|".join(row.get("clinicalSignificances") or []),
                    "variantRsId": row.get("variantRsId"),
                    "pValue": _p_value(row),
                    "studyId": row.get("studyId"),
                    "publicationYear": row.get("publicationYear"),
                    "literature": "|".join(row.get("literature") or []),
                }
            )
            if args.limit is not None and len(rows) >= args.limit:
                cursor = None
                break
        else:
            cursor = evidences.get("cursor")
            if cursor and cursor in seen_cursors:
                break
            if cursor:
                seen_cursors.add(cursor)
        if not cursor:
            break

    columns = [
        "datasourceId",
        "datatypeId",
        "score",
        "diseaseId",
        "diseaseFromSource",
        "drug",
        "clinicalStage",
        "clinicalSignificances",
        "variantRsId",
        "pValue",
        "studyId",
        "publicationYear",
        "literature",
    ]
    _emit_rows(rows, columns, args)


def _p_value(row: dict) -> str:
    mantissa = row.get("pValueMantissa")
    exponent = row.get("pValueExponent")
    if mantissa is None or exponent is None:
        return ""
    return f"{mantissa:g}e{int(exponent)}"


def _emit_rows(rows: list[dict], columns: list[str], args: argparse.Namespace) -> None:
    print(f"# rows: {len(rows)}", file=sys.stderr)
    if args.output_format == "json":
        emit(rows, output_format="json")
    else:
        if args.with_datasources and "datasourceScores" not in columns:
            columns = [*columns, "datasourceScores"]
        write_table(rows, columns)


def _add_shared(parser: argparse.ArgumentParser, *, scoring: bool = True) -> None:
    if scoring:
        # Association scoring: a weighting knob, so the flag says "only".
        parser.add_argument(
            "--only-datasources",
            dest="datasources",
            nargs="+",
            default=None,
            metavar="ID",
            help=(
                "rescore from these datasource ids alone, zeroing every other "
                "source and dropping rows that carry none of them (e.g. "
                "gwas_credible_sets gene_burden eva); see references/datasources.md"
            ),
        )
    else:
        # Evidence records: a plain server-side filter on `datasourceIds`,
        # with no reweighting involved, so the flag is named for what it does.
        parser.add_argument(
            "--datasources",
            nargs="+",
            default=None,
            metavar="ID",
            help="return only evidence from these datasource ids",
        )
    parser.add_argument("--limit", type=int, default=50, help="rows to return (default: 50)")
    parser.add_argument("--page-size", type=int, default=50, help="rows per request (max 500)")
    parser.add_argument(
        "--min-score", type=float, default=0.0, help="drop rows below this association score"
    )
    parser.add_argument(
        "--indirect",
        action="store_true",
        help="include evidence propagated from ontology descendants (default: direct only)",
    )
    parser.add_argument(
        "--with-datasources",
        action="store_true",
        help="add the full per-datasource score breakdown as a JSON column",
    )
    add_common_arguments(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    target_diseases = subparsers.add_parser(
        "target-diseases", help="diseases associated with one target, ranked"
    )
    target_diseases.add_argument("ensembl_id", help="e.g. ENSG00000146648")
    _add_shared(target_diseases)
    target_diseases.set_defaults(handler=command_target_diseases)

    disease_targets = subparsers.add_parser(
        "disease-targets", help="targets associated with one disease, ranked"
    )
    disease_targets.add_argument("disease_id", help="e.g. MONDO_0004979")
    _add_shared(disease_targets)
    disease_targets.set_defaults(handler=command_disease_targets)

    evidence = subparsers.add_parser(
        "evidence", help="individual evidence records behind one target-disease pair"
    )
    evidence.add_argument("ensembl_id", help="e.g. ENSG00000146648")
    evidence.add_argument("disease_id", help="e.g. MONDO_0005233")
    _add_shared(evidence, scoring=False)
    evidence.set_defaults(handler=command_evidence)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.handler(args)
    except OpenTargetsError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
