#!/usr/bin/env python3
"""Resolve identifiers and pull entity records from the Open Targets Platform.

Four things this handles that a hand-written query usually gets wrong:

* Identifier resolution. Every Platform query needs a canonical id -- an
  Ensembl gene id for a target, a MONDO id for a disease, a ChEMBL id for a
  drug. `resolve` turns free text into one and reports what it matched.
* Disease ids are MONDO. Since the 26.06 data release, `disease(efoId: ...)`
  returns null for an `EFO_*` id even though the argument is still named
  `efoId`. `disease` detects that case and tells you to re-resolve rather
  than reporting "no such disease".
* Tractability, safety, and prioritisation come back as untyped key/value
  lists. `target` reshapes them into named columns.
* GraphQL returns `200 OK` with an `errors` array; `_common.post` raises.

Examples:

    python ot_query.py resolve EGFR "non-small cell lung carcinoma"
    python ot_query.py target ENSG00000146648 --section tractability
    python ot_query.py disease MONDO_0005233
    python ot_query.py drug CHEMBL939 --section mechanisms
    python ot_query.py raw my_query.graphql --var ensemblId=ENSG00000146648
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    OpenTargetsError,
    add_common_arguments,
    emit,
    post,
    write_table,
)

RESOLVE_QUERY = """
query Resolve($terms: [String!]!, $entities: [String!]!) {
  mapIds(queryTerms: $terms, entityNames: $entities) {
    total
    mappings {
      term
      hits { id name entity score }
    }
  }
}
"""

SEARCH_QUERY = """
query Search($q: String!, $entities: [String!]!, $index: Int!, $size: Int!) {
  search(queryString: $q, entityNames: $entities, page: {index: $index, size: $size}) {
    total
    hits { id name entity description }
  }
}
"""

TARGET_QUERY = """
query TargetRecord($id: String!) {
  target(ensemblId: $id) {
    id
    approvedSymbol
    approvedName
    biotype
    functionDescriptions
    synonyms { label source }
    proteinIds { id source }
    genomicLocation { chromosome start end strand }
    targetClass { id label level }
    subcellularLocations { location labelSL termSL source }
    tractability { label modality value }
    safetyLiabilities {
      event
      eventId
      datasource
      literature
      effects { direction dosing }
      biosamples { tissueLabel cellLabel }
    }
    geneticConstraint { constraintType score exp obs oe oeLower oeUpper upperRank }
    prioritisation { items { key value } }
    isEssential
    depMapEssentiality {
      tissueName
      screens { cellLineName depmapId geneEffect expression }
    }
    chemicalProbes {
      id
      drugId
      isHighQuality
      probeMinerScore
      probesDrugsScore
      mechanismOfAction
      origin
      control
    }
    tep { name uri therapeuticArea }
    pathways { pathwayId pathway topLevelTerm }
    homologues { speciesName targetGeneSymbol queryPercentageIdentity homologyType }
  }
}
"""

DISEASE_QUERY = """
query DiseaseRecord($id: String!) {
  disease(efoId: $id) {
    id
    name
    description
    synonyms { relation terms }
    therapeuticAreas { id name }
    parents { id name }
    children { id name }
    dbXRefs
    phenotypes(page: {index: 0, size: 25}) {
      count
      rows { phenotypeHPO { id name } phenotypeEFO { id name } }
    }
  }
}
"""

DRUG_QUERY = """
query DrugRecord($id: String!) {
  drug(chemblId: $id) {
    id
    name
    drugType
    description
    maximumClinicalStage
    tradeNames { label source }
    synonyms { label source }
    mechanismsOfAction {
      uniqueActionTypes
      uniqueTargetTypes
      rows {
        actionType
        mechanismOfAction
        targetName
        targets { id approvedSymbol }
      }
    }
    indications {
      count
      rows { maxClinicalStage disease { id name } }
    }
    drugWarnings {
      warningType
      description
      toxicityClass
      country
      year
      efoTerm
    }
  }
}
"""

#: There is no `isApproved` field on Drug. Approval status is read from
#: `maximumClinicalStage`, whose vocabulary is a word, not a number:
#: APPROVAL / PHASE_3 / PHASE_2 / PHASE_1_2 / PHASE_1 / PRECLINICAL.
#: `maximumClinicalStage == "APPROVAL"` is the approved test.

ENTITY_CHOICES = ("target", "disease", "drug", "variant", "study")

TARGET_SECTIONS = (
    "core",
    "tractability",
    "safety",
    "prioritisation",
    "essentiality",
    "probes",
    "pathways",
    "all",
)
DRUG_SECTIONS = ("core", "mechanisms", "indications", "warnings", "all")


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# resolve / search
# --------------------------------------------------------------------------


def command_resolve(args: argparse.Namespace) -> None:
    data = post(
        RESOLVE_QUERY,
        {"terms": args.terms, "entities": list(args.entities)},
        url=args.api_url,
    )
    mappings = (data.get("mapIds") or {}).get("mappings") or []
    rows = []
    for mapping in mappings:
        hits = mapping.get("hits") or []
        if not hits:
            rows.append({"term": mapping.get("term"), "id": "", "name": "", "entity": "", "score": ""})
            continue
        for hit in hits[: args.max_hits]:
            rows.append(
                {
                    "term": mapping.get("term"),
                    "id": hit.get("id"),
                    "name": hit.get("name"),
                    "entity": hit.get("entity"),
                    "score": hit.get("score"),
                }
            )

    unmatched = [row["term"] for row in rows if not row["id"]]
    if unmatched:
        print(
            f"warning: no mapping for {', '.join(unmatched)} -- try `search` for a "
            "fuzzy lookup",
            file=sys.stderr,
        )
    if args.output_format == "json":
        emit(rows, output_format="json")
    else:
        write_table(rows, ("term", "id", "name", "entity", "score"))


def command_search(args: argparse.Namespace) -> None:
    data = post(
        SEARCH_QUERY,
        {
            "q": args.query,
            "entities": list(args.entities),
            "index": 0,
            "size": args.max_hits,
        },
        url=args.api_url,
    )
    result = data.get("search") or {}
    hits = result.get("hits") or []
    print(f"# total matches: {result.get('total')}", file=sys.stderr)
    if args.output_format == "json":
        emit(hits, output_format="json")
    else:
        write_table(hits, ("id", "name", "entity", "description"))


# --------------------------------------------------------------------------
# target
# --------------------------------------------------------------------------


def command_target(args: argparse.Namespace) -> None:
    if not args.ensembl_id.upper().startswith("ENSG"):
        _fail(
            f"`{args.ensembl_id}` is not an Ensembl gene id. Run "
            f"`ot_query.py resolve {args.ensembl_id}` first."
        )
    data = post(TARGET_QUERY, {"id": args.ensembl_id}, url=args.api_url)
    target = data.get("target")
    if target is None:
        _fail(f"no target for {args.ensembl_id}")

    if args.output_format == "json":
        emit(_target_sections(target, args.section), output_format="json")
        return

    section = args.section
    if section in ("core", "all"):
        _print_target_core(target)
    if section in ("tractability", "all"):
        _print_section("TRACTABILITY", target.get("tractability") or [], ("modality", "label", "value"))
    if section in ("safety", "all"):
        rows = [
            {
                "event": item.get("event"),
                "eventId": item.get("eventId"),
                "datasource": item.get("datasource"),
                "direction": "|".join(
                    (effect or {}).get("direction") or "" for effect in item.get("effects") or []
                ),
                "literature": item.get("literature"),
            }
            for item in target.get("safetyLiabilities") or []
        ]
        _print_section("SAFETY LIABILITIES", rows, ("event", "eventId", "datasource", "direction", "literature"))
    if section in ("prioritisation", "all"):
        items = ((target.get("prioritisation") or {}).get("items")) or []
        rows = [{"metric": item.get("key"), "value": item.get("value")} for item in items]
        _print_section("PRIORITISATION (-1 unfavourable .. +1 favourable)", rows, ("metric", "value"))
    if section in ("essentiality", "all"):
        rows = []
        for tissue in target.get("depMapEssentiality") or []:
            screens = tissue.get("screens") or []
            effects = [s.get("geneEffect") for s in screens if s.get("geneEffect") is not None]
            mean = sum(effects) / len(effects) if effects else None
            rows.append(
                {
                    "tissue": tissue.get("tissueName"),
                    "cellLines": len(screens),
                    "meanGeneEffect": f"{mean:.3f}" if mean is not None else "",
                    "minGeneEffect": f"{min(effects):.3f}" if effects else "",
                    "_sort": mean if mean is not None else 0.0,
                }
            )
        # Most essential first: Chronos gene effect is negative for a
        # dependency, so this is a numeric ascending sort, not a string one.
        rows.sort(key=lambda row: row["_sort"])
        _print_section(
            f"DEPMAP ESSENTIALITY (isEssential={target.get('isEssential')})",
            rows,
            ("tissue", "cellLines", "meanGeneEffect", "minGeneEffect"),
        )
    if section in ("probes", "all"):
        probes = sorted(
            target.get("chemicalProbes") or [],
            key=lambda probe: (not probe.get("isHighQuality"), probe.get("id") or ""),
        )
        _print_section(
            "CHEMICAL PROBES (high quality first)",
            probes,
            ("id", "drugId", "isHighQuality", "probeMinerScore", "probesDrugsScore", "origin", "control"),
        )
    if section in ("pathways", "all"):
        _print_section("PATHWAYS", target.get("pathways") or [], ("pathwayId", "pathway", "topLevelTerm"))


def _target_sections(target: dict, section: str) -> dict:
    if section == "all":
        return target
    keys = {
        "core": ("id", "approvedSymbol", "approvedName", "biotype", "proteinIds",
                 "genomicLocation", "targetClass", "synonyms", "functionDescriptions",
                 "subcellularLocations", "homologues"),
        "tractability": ("id", "approvedSymbol", "tractability"),
        "safety": ("id", "approvedSymbol", "safetyLiabilities"),
        "prioritisation": ("id", "approvedSymbol", "prioritisation", "geneticConstraint"),
        "essentiality": ("id", "approvedSymbol", "isEssential", "depMapEssentiality"),
        "probes": ("id", "approvedSymbol", "chemicalProbes", "tep"),
        "pathways": ("id", "approvedSymbol", "pathways"),
    }[section]
    return {key: target.get(key) for key in keys}


def _print_target_core(target: dict) -> None:
    uniprot = [
        protein.get("id")
        for protein in target.get("proteinIds") or []
        if protein.get("source") == "uniprot_swissprot"
    ]
    location = target.get("genomicLocation") or {}
    print(f"# {target.get('approvedSymbol')} ({target.get('id')}) -- {target.get('approvedName')}")
    print(f"# biotype: {target.get('biotype')}")
    print(f"# uniprot (swissprot): {', '.join(uniprot) or 'none'}")
    print(
        "# location: chr{chromosome}:{start}-{end} strand {strand}".format(
            chromosome=location.get("chromosome"),
            start=location.get("start"),
            end=location.get("end"),
            strand=location.get("strand"),
        )
    )
    classes = [item.get("label") for item in target.get("targetClass") or []]
    print(f"# target class: {', '.join(filter(None, classes)) or 'unclassified'}")
    constraint = {
        item.get("constraintType"): item.get("score")
        for item in target.get("geneticConstraint") or []
    }
    if constraint:
        print(f"# genetic constraint (gnomAD): {json.dumps(constraint)}")
    for description in (target.get("functionDescriptions") or [])[:1]:
        print(f"# function: {description[:400]}")
    print()


def _print_section(title: str, rows, columns) -> None:
    print(f"## {title}")
    if not rows:
        print("(none reported)\n")
        return
    write_table(rows, columns)
    print()


# --------------------------------------------------------------------------
# disease / drug
# --------------------------------------------------------------------------


def command_disease(args: argparse.Namespace) -> None:
    data = post(DISEASE_QUERY, {"id": args.disease_id}, url=args.api_url)
    disease = data.get("disease")
    if disease is None:
        hint = ""
        if args.disease_id.upper().startswith("EFO_"):
            hint = (
                " -- the disease ontology is MONDO-first: most EFO ids used by older "
                "tutorials were superseded by a MONDO id, and the argument is still "
                "named `efoId` regardless. Re-resolve the term with "
                "`ot_query.py resolve \"<disease name>\"`."
            )
        _fail(f"no disease for {args.disease_id}{hint}")

    if args.output_format == "json":
        emit(disease, output_format="json")
        return
    print(f"# {disease.get('name')} ({disease.get('id')})")
    areas = [area.get("name") for area in disease.get("therapeuticAreas") or []]
    print(f"# therapeutic areas: {', '.join(filter(None, areas)) or 'none'}")
    if disease.get("description"):
        print(f"# description: {disease['description'][:400]}")
    print()
    _print_section("PARENTS", disease.get("parents") or [], ("id", "name"))
    _print_section("CHILDREN", disease.get("children") or [], ("id", "name"))
    phenotypes = (disease.get("phenotypes") or {}).get("rows") or []
    rows = [
        {
            "hpoId": (row.get("phenotypeHPO") or {}).get("id"),
            "hpoName": (row.get("phenotypeHPO") or {}).get("name"),
        }
        for row in phenotypes
    ]
    _print_section("PHENOTYPES (first page)", rows, ("hpoId", "hpoName"))


def command_drug(args: argparse.Namespace) -> None:
    if not args.chembl_id.upper().startswith("CHEMBL"):
        _fail(f"`{args.chembl_id}` is not a ChEMBL id. Run `ot_query.py resolve` first.")
    data = post(DRUG_QUERY, {"id": args.chembl_id}, url=args.api_url)
    drug = data.get("drug")
    if drug is None:
        _fail(f"no drug for {args.chembl_id}")

    if args.output_format == "json":
        emit(drug, output_format="json")
        return

    section = args.section
    if section in ("core", "all"):
        print(f"# {drug.get('name')} ({drug.get('id')})")
        print(f"# type: {drug.get('drugType')}  max clinical stage: {drug.get('maximumClinicalStage')}")
        trade = [item.get("label") for item in drug.get("tradeNames") or []]
        print(f"# trade names: {', '.join(filter(None, trade[:10])) or 'none'}")
        if drug.get("description"):
            print(f"# description: {drug['description'][:400]}")
        print()
    if section in ("mechanisms", "all"):
        rows = []
        for row in ((drug.get("mechanismsOfAction") or {}).get("rows")) or []:
            rows.append(
                {
                    "actionType": row.get("actionType"),
                    "mechanismOfAction": row.get("mechanismOfAction"),
                    "targetName": row.get("targetName"),
                    "targetIds": "|".join(
                        target.get("id") or "" for target in row.get("targets") or []
                    ),
                    "targetSymbols": "|".join(
                        target.get("approvedSymbol") or "" for target in row.get("targets") or []
                    ),
                }
            )
        _print_section(
            "MECHANISMS OF ACTION",
            rows,
            ("actionType", "mechanismOfAction", "targetName", "targetSymbols", "targetIds"),
        )
    if section in ("indications", "all"):
        rows = [
            {
                "maxClinicalStage": row.get("maxClinicalStage"),
                "diseaseId": (row.get("disease") or {}).get("id"),
                "diseaseName": (row.get("disease") or {}).get("name"),
            }
            for row in ((drug.get("indications") or {}).get("rows")) or []
        ]
        _print_section(
            f"INDICATIONS ({(drug.get('indications') or {}).get('count')} total)",
            rows,
            ("maxClinicalStage", "diseaseId", "diseaseName"),
        )
    if section in ("warnings", "all"):
        _print_section(
            "DRUG WARNINGS",
            drug.get("drugWarnings") or [],
            ("warningType", "toxicityClass", "description", "country", "year"),
        )


# --------------------------------------------------------------------------
# raw
# --------------------------------------------------------------------------


def command_raw(args: argparse.Namespace) -> None:
    query = Path(args.query_file).read_text(encoding="utf-8")
    variables: dict[str, object] = {}
    for assignment in args.variables:
        if "=" not in assignment:
            _fail(f"--var expects name=value, got `{assignment}`")
        name, _, value = assignment.partition("=")
        try:
            variables[name] = json.loads(value)
        except json.JSONDecodeError:
            variables[name] = value
    emit(post(query, variables, url=args.api_url), output_format="json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser(
        "resolve", help="map free-text names to canonical Platform identifiers"
    )
    resolve.add_argument("terms", nargs="+", help="gene symbols, disease names, or drug names")
    resolve.add_argument(
        "--entities",
        nargs="+",
        default=list(ENTITY_CHOICES[:3]),
        choices=ENTITY_CHOICES,
        help="entity types to consider (default: target disease drug)",
    )
    resolve.add_argument("--max-hits", type=int, default=3, help="hits per term (default: 3)")
    add_common_arguments(resolve)
    resolve.set_defaults(handler=command_resolve)

    search = subparsers.add_parser("search", help="fuzzy free-text search across entities")
    search.add_argument("query", help="free text")
    search.add_argument(
        "--entities", nargs="+", default=list(ENTITY_CHOICES[:3]), choices=ENTITY_CHOICES
    )
    search.add_argument("--max-hits", type=int, default=10)
    add_common_arguments(search)
    search.set_defaults(handler=command_search)

    target = subparsers.add_parser("target", help="one target record, by Ensembl gene id")
    target.add_argument("ensembl_id", help="e.g. ENSG00000146648")
    target.add_argument("--section", choices=TARGET_SECTIONS, default="all")
    add_common_arguments(target)
    target.set_defaults(handler=command_target)

    disease = subparsers.add_parser("disease", help="one disease record, by MONDO id")
    disease.add_argument("disease_id", help="e.g. MONDO_0005233")
    add_common_arguments(disease)
    disease.set_defaults(handler=command_disease)

    drug = subparsers.add_parser("drug", help="one drug record, by ChEMBL id")
    drug.add_argument("chembl_id", help="e.g. CHEMBL939")
    drug.add_argument("--section", choices=DRUG_SECTIONS, default="all")
    add_common_arguments(drug)
    drug.set_defaults(handler=command_drug)

    raw = subparsers.add_parser("raw", help="run a GraphQL document from a file")
    raw.add_argument("query_file", help="path to a .graphql file")
    raw.add_argument(
        "--var",
        dest="variables",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="a GraphQL variable; VALUE is parsed as JSON when possible",
    )
    add_common_arguments(raw)
    raw.set_defaults(handler=command_raw)

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
