"""Repo-wide guards: every skill conforms, and every skill with scripts is tested.

This suite is deliberately not per-skill. It imports no skill code -- the
structural contract parses scripts with `ast` and never executes them -- so
running it across all skills in one interpreter is safe, and it is the only
place that can see the whole repository at once. That is what lets it enforce
the rule `AGENTS.md` states but nothing previously checked:

    If the skill ships `scripts/`, put their tests in `tests/<name>/`.

It runs in the project environment and needs no scientific packages, so CI can
run it on every pull request in seconds.
"""

from __future__ import annotations

import json
import re
import tempfile
import tomllib
import unittest
from pathlib import Path

import skill_contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
TESTS_DIR = REPO_ROOT / "tests"
REQUIREMENTS = TESTS_DIR / "skill-requirements.toml"
PLUGIN_MANIFEST = REPO_ROOT / "plugin.json"
PYPROJECT = REPO_ROOT / "pyproject.toml"

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_NAME = "drug-discovery-agent-skills"
ALLOWED_PLUGIN_KEYS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

structure = skill_contract.structure
office = skill_contract.office

ALL_SKILLS = structure.all_skills(SKILLS_DIR)
SCRIPT_BEARING = structure.script_bearing_skills(SKILLS_DIR)
KNOWN_SKILLS = structure.all_skill_names(SKILLS_DIR)


def _suite_names() -> set[str]:
    """Test directories that stand for a skill, excluding infrastructure."""
    return {
        path.name
        for path in TESTS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith((".", "_"))
    }


class CoverageTests(unittest.TestCase):
    """The rule this whole suite exists to enforce."""

    maxDiff = None

    def test_every_skill_with_scripts_has_a_test_suite(self) -> None:
        suites = _suite_names()
        untested = sorted(
            skill.name for skill in SCRIPT_BEARING if skill.name not in suites
        )
        self.assertEqual(
            untested,
            [],
            "these skills ship scripts/ but have no tests/<name>/ suite; add one "
            "(see AGENTS.md, 'Creating a skill' step 5)",
        )

    def test_every_suite_has_a_test_file(self) -> None:
        empty = sorted(
            name
            for name in _suite_names()
            if not any((TESTS_DIR / name).glob("test_*.py"))
        )
        self.assertEqual(empty, [], "test directories with no test_*.py")

    def test_no_test_suite_is_orphaned(self) -> None:
        orphans = sorted(name for name in _suite_names() if name not in KNOWN_SKILLS)
        self.assertEqual(
            orphans, [], "test directories that do not name a skill under skills/"
        )

    def test_every_skill_with_scripts_has_a_requirements_entry(self) -> None:
        """`--isolated` needs a `[skills.<name>]` entry or it cannot build the env."""
        manifest = tomllib.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        entries = manifest.get("skills", {})
        missing = sorted(
            skill.name for skill in SCRIPT_BEARING if skill.name not in entries
        )
        self.assertEqual(
            missing,
            [],
            f"add a [skills.<name>] block to {REQUIREMENTS.name} "
            "(packages = [] for standard-library-only skills)",
        )

    def test_requirements_entries_name_real_skills(self) -> None:
        manifest = tomllib.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        unknown = sorted(set(manifest.get("skills", {})) - KNOWN_SKILLS)
        self.assertEqual(unknown, [], f"stale entries in {REQUIREMENTS.name}")

    def test_unavailable_entries_name_real_skills(self) -> None:
        """`[unavailable]` reasons are matched by prefix, so a stale one is silent.

        `run_all.py` prints an entry only when its reason starts with
        `<suite name> skill:`. A reason naming a skill this repository does not
        carry is never printed and never noticed -- which is how the table
        accumulated a dozen entries inherited from the wider collection.
        """
        manifest = tomllib.loads(REQUIREMENTS.read_text(encoding="utf-8"))
        stale = {}
        for package, reason in sorted(manifest.get("unavailable", {}).items()):
            named = reason.split(" skill:", 1)[0]
            if " skill:" not in reason or named not in KNOWN_SKILLS:
                stale[package] = reason
        self.assertEqual(
            stale,
            {},
            f"each [unavailable] reason in {REQUIREMENTS.name} must start with "
            "'<skill-name> skill: ' naming a skill under skills/",
        )


class StructuralContractTests(unittest.TestCase):
    """Every rule in `skill_contract.structure`, against every skill.

    Every skill, not just the script-bearing ones: frontmatter conformance,
    the SKILL.md length limit, link resolution, and the leaked-local-path check
    apply just as much to a skill that ships nothing but documentation.
    """

    maxDiff = None

    def test_all_skills_satisfy_every_structural_rule(self) -> None:
        self.assertTrue(ALL_SKILLS, "no skills found -- the anchor is wrong")
        for rule, check in structure.CHECKS.items():
            for skill in ALL_SKILLS:
                with self.subTest(rule=rule, skill=skill.name):
                    problems = (
                        check(skill, KNOWN_SKILLS)
                        if rule == "local_links_resolve"
                        else check(skill)
                    )
                    self.assertEqual(problems, [])


class PersonalPathRuleTests(unittest.TestCase):
    """The leaked-local-path rule itself, against a synthetic skill.

    Worth pinning directly: the rule was POSIX-only for long enough that a
    `C:\\Users\\<name>\\` path shipped in a real SKILL.md without CI noticing.
    """

    maxDiff = None

    def _skill(self, body: str) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        skill = Path(temporary.name) / "example"
        skill.mkdir()
        (skill / "SKILL.md").write_text(body, encoding="utf-8")
        return skill

    def test_a_windows_home_directory_is_caught(self) -> None:
        skill = self._skill(r"Data is stored at `C:\Users\eamon\Documents\kg.csv`.")
        problems = structure.personal_path_problems(skill)
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("eamon", problems[0])

    def test_a_posix_home_directory_is_still_caught(self) -> None:
        for path in ("/Users/eamon/kg.csv", "/home/eamon/kg.csv", "/mnt/c/Users/eamon/kg.csv"):
            with self.subTest(path=path):
                self.assertEqual(len(structure.personal_path_problems(self._skill(path))), 1)

    def test_placeholders_and_service_accounts_are_allowed(self) -> None:
        for path in (
            r"C:\Users\<you>\kg.csv",
            r"C:\Users\%USERNAME%\kg.csv",
            r"C:\Users\Public\kg.csv",
            "/Users/$USER/kg.csv",
            "/home/dnanexus/kg.csv",
            "/home/runner/work/kg.csv",
        ):
            with self.subTest(path=path):
                self.assertEqual(structure.personal_path_problems(self._skill(path)), [])


class SharedCopyTests(unittest.TestCase):
    """Files several skills ship identical copies of must not drift apart."""

    maxDiff = None

    def test_docx_pptx_xlsx_ship_the_same_office_tree(self) -> None:
        self.assertEqual(office.identical_tree_problems(SKILLS_DIR), [])

    def test_shared_scripts_are_identical_across_their_skills(self) -> None:
        self.assertEqual(office.shared_file_problems(SKILLS_DIR), [])


class AgentPluginTests(unittest.TestCase):
    """Root plugin.json keeps the repo a valid Agent Plugins 1.0.0 package."""

    maxDiff = None

    def test_plugin_manifest_conforms(self) -> None:
        self.assertTrue(PLUGIN_MANIFEST.is_file(), "plugin.json must exist at the repo root")
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        self.assertIsInstance(manifest, dict)

        unknown = sorted(set(manifest) - ALLOWED_PLUGIN_KEYS)
        self.assertEqual(unknown, [], "plugin.json has closed top-level schema")

        self.assertEqual(manifest.get("$schema"), PLUGIN_SCHEMA)
        self.assertEqual(manifest.get("name"), PLUGIN_NAME)
        self.assertRegex(manifest["name"], PLUGIN_NAME_RE)

        project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
        self.assertEqual(
            manifest.get("version"),
            project["version"],
            "plugin.json version must match pyproject.toml [project].version",
        )

    def test_skills_component_is_discoverable(self) -> None:
        """Agent Plugins discovers only immediate children of skills/ with SKILL.md."""
        self.assertTrue(SKILLS_DIR.is_dir())
        self.assertTrue(KNOWN_SKILLS, "no discoverable skills under skills/")
        for name in sorted(KNOWN_SKILLS):
            with self.subTest(skill=name):
                skill_md = SKILLS_DIR / name / "SKILL.md"
                self.assertTrue(skill_md.is_file())
                self.assertEqual(skill_md.parent.parent, SKILLS_DIR)


if __name__ == "__main__":
    unittest.main()
