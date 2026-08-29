"""This repository must not reimplement a statistic a sibling owns.

QUACKZ owns the Sharpe ratio, the deflated Sharpe, the stationary bootstrap and the trial
deflation table. Writing another version of any of them here would be two implementations of one
argument in one portfolio, which is how two repositories end up quietly disagreeing about a
number that has one right answer.

The rule is enforced on the SOURCE rather than on a naming convention, and the reason it is a
rule at all is in docs/adr/0003.
"""

from __future__ import annotations

import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]

#: What a sibling owns, as the words its implementation would have to contain.
OWNED_ELSEWHERE = (
    "sharpe",
    "deflated",
    "stationary bootstrap",
    "probabilistic sharpe",
    "trial deflation",
)


def source_files() -> list[pathlib.Path]:
    return sorted(
        path
        for directory in ("src", "scripts", "examples")
        for path in (REPO / directory).rglob("*.py")
    )


def test_no_statistic_owned_by_a_sibling_is_implemented_here() -> None:
    """WHAT THIS CAN AND CANNOT SEE, said plainly rather than implied by a green tick.

    It reads the NAMES in the source: every function, class, argument and variable. A
    reimplementation of a sibling's statistic has a name that says so, because somebody has to
    call it. What this cannot detect is the same arithmetic written anonymously in the middle of
    another function, and no grep can.

    The first version searched raw lines and flagged the docstrings that EXPLAIN the boundary,
    which is the same failure as a workflow test satisfied by a comment: prose about a thing
    counted as the thing.
    """
    import ast

    offenders: list[str] = []
    for path in source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                names.append((node.lineno, node.name))
            elif isinstance(node, ast.Name):
                names.append((node.lineno, node.id))
            elif isinstance(node, ast.arg):
                names.append((node.lineno, node.arg))
            elif isinstance(node, ast.Attribute):
                names.append((node.lineno, node.attr))
        for line, name in names:
            lowered = name.lower().replace("_", " ")
            for owned in OWNED_ELSEWHERE:
                if owned in lowered:
                    offenders.append(f"{path.relative_to(REPO)}:{line}: {name}")
    assert offenders == [], (
        f"a statistic owned by a sibling repository is named in code here: {offenders}. "
        f"See docs/adr/0003"
    )


def test_the_boundary_is_explained_where_a_reader_will_meet_it() -> None:
    """A rule with no reason recorded is a rule the next person deletes."""
    adr = (REPO / "docs" / "adr" / "0003-the-block-permutation-is-not-imported.md").read_text(
        encoding="utf-8"
    )
    assert "stationary bootstrap" in adr.lower()
    assert "without replacement" in adr.lower()
    controls = " ".join((REPO / "src" / "quashz" / "controls.py").read_text("utf-8").split())
    assert "different object from a stationary bootstrap" in controls, (
        "controls.py no longer says why it is not the sibling's primitive, so the next reader "
        "meets a duplicate rather than a decision"
    )


def test_every_adr_is_numbered_and_reachable() -> None:
    """An ADR referenced from a file that does not exist is worse than no ADR."""
    adrs = sorted((REPO / "docs" / "adr").glob("*.md"))
    assert len(adrs) >= 3, f"only {len(adrs)} decisions are recorded"
    numbers = [int(path.name.split("-")[0]) for path in adrs]
    assert numbers == sorted(numbers) and len(set(numbers)) == len(numbers)
    for path in adrs:
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# "), f"{path.name} has no title"
        for heading in ("## Context", "## Decision", "## Consequences"):
            assert heading in text, f"{path.name} has no {heading} section"
