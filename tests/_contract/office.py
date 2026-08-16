"""Shared tests for the OOXML `office/` tree bundled by docx, pptx, and xlsx.

Those three skills each ship a byte-identical copy of `scripts/office/` --
`helpers/`, `validators/`, `validate.py`, `soffice.py`, and the vendored
ISO/ECMA schemas. Rather than write the same tests three times, each suite
instantiates `office_test_case()` against its own copy, so a change that lands
in one copy and not the others fails on the copy that was missed as well as on
`identical_tree_problems()` in `tests/_meta`.

The interesting surface is the safety logic: `safe_extract` guards zip-slip and
symlink entries, and `opc_target` refuses relationship targets that escape the
package. Both are reachable with nothing but the standard library.
"""

from __future__ import annotations

import hashlib
import importlib
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

#: The skills that ship the shared tree. Kept here so adding a fourth is one edit.
OFFICE_SKILLS = tuple(
    name for name in ("docx", "pptx", "xlsx") if (SKILLS_DIR / name).is_dir()
)

#: Other files several skills ship byte-identical copies of. A copy that drifts
#: is a skill quietly behaving differently from its siblings, so `tests/_meta`
#: pins them together. Each entry is (path relative to the skill, skills).
SHARED_FILES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "scripts/generate_schematic.py",
        (
            "scientific-schematics",
            "latex-posters",
            "literature-review",
            "scientific-slides",
        ),
    ),
    (
        "scripts/generate_schematic_ai.py",
        (
            "scientific-schematics",
            "latex-posters",
            "literature-review",
            "scientific-slides",
        ),
    ),
)


def shared_file_problems(skills_dir: Path = SKILLS_DIR) -> list[str]:
    """Every skill in a `SHARED_FILES` group ships the same bytes."""
    problems = []
    for relative, skills in SHARED_FILES:
        skills = tuple(name for name in skills if (skills_dir / name).is_dir())
        if len(skills) < 2:
            continue
        digests = {}
        for name in skills:
            path = skills_dir / name / relative
            if not path.is_file():
                problems.append(f"{name}: {relative} is missing")
                continue
            digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if len(set(digests.values())) > 1:
            reference = skills[0]
            problems.extend(
                f"{name}: {relative} has drifted from {reference}'s copy"
                for name, digest in digests.items()
                if digest != digests.get(reference)
            )
    return problems


def _tree_digest(office_dir: Path) -> str:
    """A digest over every path and byte under an `office/` tree."""
    digest = hashlib.sha256()
    for path in sorted(office_dir.rglob("*")):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(office_dir)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def identical_tree_problems(skills_dir: Path = SKILLS_DIR) -> list[str]:
    """The shared `office/` trees have not drifted apart."""
    if not OFFICE_SKILLS:
        return []
    digests = {}
    for name in OFFICE_SKILLS:
        office = skills_dir / name / "scripts" / "office"
        if not office.is_dir():
            return [f"{name}: scripts/office/ is missing"]
        digests[name] = _tree_digest(office)

    reference = digests[OFFICE_SKILLS[0]]
    return [
        f"{name}: scripts/office/ has drifted from {OFFICE_SKILLS[0]}'s copy "
        f"({digests[name][:12]} vs {reference[:12]})"
        for name in OFFICE_SKILLS[1:]
        if digests[name] != reference
    ]


def office_test_case(skill_root: Path) -> type[unittest.TestCase]:
    """Build the shared `office/` TestCase for one of docx / pptx / xlsx."""
    office_dir = skill_root / "scripts" / "office"

    def load_helpers():
        # `office/` puts `helpers` and `validators` at the top level -- see the
        # `from helpers import ...` in validate.py -- so office/ itself goes on
        # the path. Safe because this repo runs one skill per process.
        if str(office_dir) not in sys.path:
            sys.path.insert(0, str(office_dir))
        return importlib.import_module("helpers")

    class OfficeSharedTreeTests(unittest.TestCase):
        maxDiff = None

        def setUp(self) -> None:
            self.helpers = load_helpers()

        # -- safe_extract ------------------------------------------------

        def test_safe_extract_unpacks_an_ordinary_package(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "package.docx"
                with zipfile.ZipFile(archive, "w") as handle:
                    handle.writestr("[Content_Types].xml", "<Types/>")
                    handle.writestr("word/document.xml", "<document/>")

                destination = root / "unpacked"
                destination.mkdir()
                with zipfile.ZipFile(archive) as handle:
                    self.helpers.safe_extract(handle, destination)

                self.assertTrue((destination / "[Content_Types].xml").is_file())
                self.assertEqual(
                    (destination / "word" / "document.xml").read_text(), "<document/>"
                )

        def test_safe_extract_refuses_a_traversal_entry(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "evil.docx"
                with zipfile.ZipFile(archive, "w") as handle:
                    handle.writestr("../escaped.xml", "<pwned/>")

                destination = root / "unpacked"
                destination.mkdir()
                with zipfile.ZipFile(archive) as handle:
                    with self.assertRaisesRegex(ValueError, "unsafe archive entry"):
                        self.helpers.safe_extract(handle, destination)
                self.assertFalse((root / "escaped.xml").exists())

        def test_safe_extract_refuses_a_symlink_entry(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                archive = root / "link.docx"
                info = zipfile.ZipInfo("word/document.xml")
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                with zipfile.ZipFile(archive, "w") as handle:
                    handle.writestr(info, "/etc/passwd")

                destination = root / "unpacked"
                destination.mkdir()
                with zipfile.ZipFile(archive) as handle:
                    with self.assertRaisesRegex(ValueError, "symlink archive entry"):
                        self.helpers.safe_extract(handle, destination)

        # -- opc_target --------------------------------------------------

        def test_opc_target_resolves_relative_and_absolute_part_names(self) -> None:
            resolve = self.helpers.opc_target
            self.assertEqual(
                resolve("media/image1.png", "word/document.xml"),
                "word/media/image1.png",
            )
            self.assertEqual(
                resolve("/word/styles.xml", "word/document.xml"), "word/styles.xml"
            )
            self.assertEqual(
                resolve("../customXml/item1.xml", "word/document.xml"),
                "customXml/item1.xml",
            )
            # Percent-encoding is decoded before resolution.
            self.assertEqual(
                resolve("media/my%20image.png", "word/document.xml"),
                "word/media/my image.png",
            )

        def test_opc_target_ignores_external_and_scheme_targets(self) -> None:
            resolve = self.helpers.opc_target
            self.assertIsNone(resolve("", "word/document.xml"))
            self.assertIsNone(
                resolve("https://example.invalid/x", "word/document.xml", "External")
            )
            self.assertIsNone(resolve("mailto:someone@example.invalid", "word/document.xml"))

        def test_opc_target_refuses_targets_that_escape_the_package(self) -> None:
            resolve = self.helpers.opc_target
            with self.assertRaisesRegex(ValueError, "escapes the package"):
                resolve("../../outside.xml", "word/document.xml")
            with self.assertRaisesRegex(ValueError, "not a POSIX part name"):
                resolve("word\\styles.xml", "word/document.xml")
            # A bare "/" is absolute and strips to nothing at all.
            with self.assertRaisesRegex(ValueError, "resolves to nothing"):
                resolve("/", "word/document.xml")

        def test_a_dot_target_resolves_to_its_own_directory(self) -> None:
            # normpath collapses it rather than treating it as an error.
            self.assertEqual(
                self.helpers.opc_target(".", "word/document.xml"), "word"
            )

        # -- text rendering ----------------------------------------------

        def test_rendered_text_honours_xml_space_preserve(self) -> None:
            render = self.helpers.rendered_text
            self.assertEqual(render("  spaced  ", True), "  spaced  ")
            self.assertEqual(render("  spaced  ", False), "spaced")
            self.assertEqual(render("\t\nmixed\r\n", False), "mixed")

        def test_part_text_survives_undecodable_bytes(self) -> None:
            # surrogateescape, not a crash: a corrupt part must still be
            # reportable rather than taking the whole validation run down.
            self.assertEqual(self.helpers.part_text(b"ok"), "ok")
            self.assertEqual(len(self.helpers.part_text(b"\xff\xfe")), 2)

        # -- rezip -------------------------------------------------------

        def test_rezip_stores_content_types_first_and_uncompressed(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "unpacked"
                (source / "word").mkdir(parents=True)
                (source / "[Content_Types].xml").write_text("<Types/>")
                (source / "word" / "document.xml").write_text("<document/>")

                output = root / "rebuilt.docx"
                self.helpers.rezip(source, output)

                with zipfile.ZipFile(output) as handle:
                    entries = handle.namelist()
                    # OOXML readers require [Content_Types].xml first and stored.
                    self.assertEqual(entries[0], "[Content_Types].xml")
                    self.assertEqual(
                        handle.getinfo("[Content_Types].xml").compress_type,
                        zipfile.ZIP_STORED,
                    )
                    self.assertIn("word/document.xml", entries)

        def test_rezip_leaves_no_temporary_file_behind(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "unpacked"
                source.mkdir()
                (source / "part.xml").write_text("<part/>")

                output = root / "rebuilt.docx"
                self.helpers.rezip(source, output)
                self.assertEqual(
                    sorted(path.name for path in root.iterdir()),
                    ["rebuilt.docx", "unpacked"],
                )

        # -- packaging ---------------------------------------------------

        def test_ooxml_family_covers_this_skill(self) -> None:
            families = set(self.helpers.OOXML_FAMILY.values())
            self.assertEqual(families, {"docx", "pptx", "xlsx"})
            self.assertIn(f".{skill_root.name}", self.helpers.OOXML_FAMILY)

        def test_every_validator_schema_path_exists(self) -> None:
            schemas = office_dir / "schemas"
            self.assertTrue(schemas.is_dir(), "vendored schemas are missing")
            referenced = set()
            for module in sorted((office_dir / "validators").glob("*.py")):
                for line in module.read_text(encoding="utf-8").splitlines():
                    for token in line.split('"'):
                        if token.endswith(".xsd"):
                            referenced.add(token.lstrip("/"))
            missing = sorted(
                name
                for name in referenced
                if not any(schemas.rglob(Path(name).name))
            )
            self.assertEqual(missing, [], "validators name schemas that are not shipped")

    OfficeSharedTreeTests.__qualname__ = f"OfficeSharedTreeTests[{skill_root.name}]"
    return OfficeSharedTreeTests
