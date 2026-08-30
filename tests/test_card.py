"""The facts the portfolio card states, checked against the repository rather than the file.

`docs/evidence/facts.json` is the one captured artefact CI does not compare byte for byte,
because it carries a capture date and a byte comparison of a date fails on the second morning.
That exemption is only defensible if its contents are checked another way.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import tomllib
from html import unescape
from typing import Any

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
FACTS = REPO / "docs" / "evidence" / "facts.json"


def facts() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(FACTS.read_text(encoding="utf-8"))
    return loaded


def card() -> str | None:
    """The published card, or None until there is one. A card is written at publication."""
    path = REPO / "site" / "index.html"
    return path.read_text(encoding="utf-8") if path.exists() else None


def demo() -> str:
    """The demo's captured stdout, which CI re-runs and diffs byte for byte."""
    return (REPO / "docs" / "evidence" / "demo.txt").read_text(encoding="utf-8")


def test_the_stated_test_total_counts_both_suites() -> None:
    """A total that counted only `tests` would understate this repository by every property test.

    The suites are split so that cloning and running pytest works with the dev group alone. That
    is an implementation detail of the rig, not of the repository, so the number a reader is
    shown covers both.
    """
    total = 0
    for directory in ("tests", "tests_verdict"):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", directory],
            capture_output=True,
            text=True,
            cwd=REPO,
            check=True,
        )
        total += sum(
            int(count) for _, count in re.findall(r"^(\S+): (\d+)$", result.stdout, re.MULTILINE)
        )
    assert total > 0
    assert facts()["tests"] == total, (
        f"the card states {facts()['tests']} tests and the two suites collect {total}. Re-run "
        f"scripts/capture_evidence.py"
    )


def test_the_stated_python_range_is_the_one_ci_runs() -> None:
    workflow = (REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    versions = re.findall(r'"(\d+\.\d+)"', workflow)
    assert versions
    assert facts()["python"] == f"{min(versions, key=float)} to {max(versions, key=float)}"


def test_the_stated_release_matches_the_package_version() -> None:
    version = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert facts()["release"].startswith(f"v{version}")


def test_the_capture_date_is_not_in_the_future() -> None:
    """Bounded rather than matched, because checking it against today fails tomorrow."""
    import datetime

    assert datetime.date.fromisoformat(facts()["captured"]) <= datetime.date.today()


def test_a_published_card_shows_the_captured_demo_and_no_banned_dash() -> None:
    """Only once one exists. A card is written at publication.

    THE WHOLE BLOCK, AND THIS COMPARED THE FIRST LINE OF IT. The card's own note tells the
    reader that a test fails when it stops matching a live run, and that was true of one line
    out of thirty-eight. Falsifying "2661 of 2808 decision dates" in the middle of the block
    left every test here green and the publish gate in pages.yml open, which checks the same
    first line.
    """
    html = card()
    if html is None:
        return
    blocks = [unescape(found).strip() for found in re.findall(r"<pre[^>]*>(.*?)</pre>", html, re.S)]
    assert demo().strip() in blocks, (
        "no terminal block on the card is the committed capture, line for line. The card is "
        "generated outside this repository from docs/evidence/demo.txt, so either it was built "
        "from an older capture or a line of it has been edited by hand"
    )
    # ESCAPES RATHER THAN THE CHARACTERS, and the first draft of this line used the characters
    # in the comment directly under a comment saying not to. The linter caught it.
    for dash in ("\u2014", "\u2013"):
        assert dash not in html, f"the published card contains {dash!r}"


def test_the_facts_strip_on_the_card_is_the_captured_facts_file() -> None:
    """The four figures at the top of the card, joined to the file they are generated from.

    `facts.json` is checked against this repository by everything above, and the card is built
    from `facts.json` somewhere else. Between those two there was nothing at all, so the strip
    could say anything: a test total of 417 passed every test in this file and the publish gate
    with it.
    """
    html = card()
    if html is None:
        return
    strip = dict(re.findall(r"<dt>([^<]+)</dt><dd>([^<]+)</dd>", html))
    assert strip, "the card has no facts strip, so the figures it leads with are unchecked"
    stated = {
        "Tests": str(facts()["tests"]),
        "Python": str(facts()["python"]),
        "Release": str(facts()["release"]),
    }
    wrong = {
        label: (strip.get(label), value)
        for label, value in stated.items()
        if strip.get(label) != value
    }
    assert wrong == {}, (
        f"the card and docs/evidence/facts.json disagree, as (card, capture): {wrong}. The card "
        f"is generated from that file outside this repository, so re-run capture_evidence.py "
        f"and regenerate the card"
    )


def test_the_claim_paragraph_states_the_lags_that_were_measured() -> None:
    """The one part of the card that is prose rather than a captured transcript.

    Every other figure on the page comes out of a file this repository regenerates. These four
    were written by hand into the manifest the card is built from, so they were the only numbers
    on it that nothing could contradict, and all four are about the measurement this repository
    exists to make. Each is compared inside the phrase that carries it rather than searched for
    on the page, because a page this long carries most small integers somewhere.
    """
    html = card()
    if html is None:
        return
    from quashz import corpus, frame

    lags = sorted(
        int(row["days_from_the_observation_label"])
        for row in corpus.knowable_from()
        if row["series"] == "GDPC1"
    )
    ordinary = [lag for lag in lags if lag <= 130]
    unusual = sorted(set(lags) - set(ordinary))
    leak = frame.quarterly_leak()

    found = re.search(r'class="claim">(.*?)</p>', html, re.S)
    assert found, "the card has no claim paragraph, so its headline argument is unchecked"
    prose = " ".join(unescape(found.group(1)).split())
    claims = {
        "the ordinary band": rf"{len(ordinary)} of {len(lags)} quarters",
        "the band itself": rf"between {min(ordinary)} and {max(ordinary)} days",
        "the two that took longer": rf"two took {unusual[0]} and {unusual[1]}",
        "the share that would read early": rf"on {leak.share * 100:.1f} per cent of decision",
    }
    missing = {name: pattern for name, pattern in claims.items() if not re.search(pattern, prose)}
    assert missing == {}, (
        f"the card's claim paragraph no longer states these as they were measured: {missing}. "
        f"That paragraph is generated from the shared manifest rather than from anything here, "
        f"so the figure is corrected there and the card regenerated"
    )


def test_the_readme_hero_image_shows_the_captured_demo() -> None:
    """The first thing on the README, regenerated by nobody here and compared with nothing.

    `docs/demo.svg` carries thirty lines of the same figures as the card, is referenced from one
    line of one file, and had no test whatsoever: any line of it could have said anything. It
    truncates the transcript by design, so what is asserted is that the lines it does show are
    the transcript's own in order, and that the count in its closing line is what it leaves out.
    """
    svg = (REPO / "docs" / "demo.svg").read_text(encoding="utf-8")
    nodes = [unescape(found) for found in re.findall(r"<text[^>]*>(.*?)</text>", svg, re.S)]
    assert len(nodes) > 3, "the hero image carries almost no text, so this is checking nothing"
    assert nodes[0].startswith("$ uv run python examples/what_was_knowable.py"), (
        f"the hero image opens on {nodes[0]!r} rather than on the command it illustrates"
    )
    assert nodes[1] == "", "the blank line under the command is gone, so the offsets below moved"
    shown, marker = nodes[2:-1], nodes[-1]
    assert shown == demo().splitlines()[: len(shown)], (
        "the lines in the hero image are not the committed capture's own, in order"
    )
    # COUNTED THE WAY THE IMAGE COUNTS, from `split` rather than `splitlines`, so the capture's
    # trailing newline is one of them. That is one more than a reader would count, and it is the
    # figure the image actually prints. What this asserts is that the figure tracks the capture,
    # which is the half of it that goes stale.
    hidden = len(demo().split("\n")) - len(shown)
    assert marker == f"... {hidden} more lines, in full on the card", (
        f"the hero image says {marker!r} and it leaves out {hidden} lines of the capture"
    )


def test_the_python_range_is_the_gating_matrix_and_orders_as_versions(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two latent defects in the function that publishes this number, neither of them visible.

    The range on the card is correct today. It was produced by a function that matched every
    quoted `x.y` anywhere in the workflow, so a quoted action version or a timeout would have
    landed on a published page, and that ordered with `float`, so `float("3.9") > float("3.13")`
    and a 3.9 leg would have published a range running backwards.

    A correct output from a broken mechanism is the thing this whole portfolio argues against, so
    the mechanism is tested rather than the output.
    """
    import json as _json
    import sys

    import yaml

    sys.path.insert(0, str(REPO / "scripts"))
    import capture_evidence

    workflow = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    gating: set[str] = set()
    for job in (workflow.get("jobs") or {}).values():
        if job.get("continue-on-error"):
            continue
        declared = (job.get("with") or {}).get("python-versions")
        if declared is None:
            continue
        gating.update(
            str(v) for v in (_json.loads(declared) if isinstance(declared, str) else declared)
        )

    assert gating, "no job gates on a Python version, so the published range verifies nothing"
    order = sorted(gating, key=lambda v: tuple(int(p) for p in v.split(".")))
    expected = f"{order[0]} to {order[-1]}"

    assert capture_evidence.python_range() == expected
    facts = _json.loads((REPO / "docs" / "evidence" / "facts.json").read_text("utf-8"))
    assert facts["python"] == expected, (
        f"the card says {facts['python']} and CI gates on {expected}"
    )

    # THE ORDERING RULE, DRIVEN THROUGH THE REAL FUNCTION rather than restated beside it.
    #
    # This matters because of how the defect hides. No matrix in this repository contains a 3.9,
    # so float ordering and version ordering agree on every version actually present, and
    # swapping the production line back to `key=float` changes no output and fails nothing. A
    # test that only asserted the rule as arithmetic would pin a fact and let the code revert.
    #
    # So the function is pointed at a workflow that DOES contain a 3.9, by moving its ROOT, and
    # asked what it returns. Under `key=float` that is "3.11 to 3.9", a range running backwards
    # on a published page.
    fake = tmp_path / ".github" / "workflows"
    fake.mkdir(parents=True)
    (fake / "ci.yml").write_text(
        'jobs:\n  checks:\n    with:\n      python-versions: \'["3.11", "3.9", "3.13"]\'\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(capture_evidence, "ROOT", tmp_path)
    assert capture_evidence.python_range() == "3.9 to 3.13", (
        "the version range is not ordered as versions. float('3.9') is greater than "
        "float('3.13'), so this publishes a range running backwards the day a 3.9 leg exists"
    )
