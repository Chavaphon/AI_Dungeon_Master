"""The code and data release (WBS 11.11): one archive of the main-grid dataset,
built from a fixed list of files, each checked against its recorded sha256.

    python -m adm.eval.release --checksums experiments/main_grid.sha256 --doc docs/release.md

**What goes in** (`docs/decisions.md`, 2026-11-20, "Code and data release"):
the 192 main-grid audit logs, pinned by `experiments/main_grid.sha256`; the
batch runner's attempt ledger; and every annotation file a reported number is
computed from, with the AI drafts the annotators reviewed, each pinned in
`ANNOTATIONS` by the sha256 its own record gives. Nothing the commands compute
from these (`results/m1.json`, `results/automated.jsonl` and the rest) is in
it: the code at the release tag recomputes them. The dry run, the smoke runs,
aborted attempts and Sponsor User sessions are not the dataset and are left out.

**Checks.** The archive is not built unless every file is present and has its
pinned bytes, and `LICENSE` and `NOTICE` carry the MIT licence, the SRD 5.1
attribution and the Llama 3.1 notice. A file found under the wrong name (the
two M5 raters' tools both write `m5_ratings.jsonl`) is named.

**The archive.** `dist/adm-dataset-v1.0.zip`, laid out as the repository
expects (`runs/...`, `results/...`), so it unpacks into a checkout of the tag;
the release's own files are under `dataset/`: a README, `LICENSE`, `NOTICE` and
`SHA256SUMS` of every other member. Members are in sorted order with a fixed
date and mode, and their bytes are copied unchanged: the logs keep the CRLF
line endings their checksums are of. The archive goes to the tag's GitHub
release; it is never committed.

`--doc` rewrites the results block of `docs/release.md` with the archive's
sha256 and the file list. The command never calls the model.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from adm.eval.integrity import read_checksums
from adm.eval.metrics import write_results

TAG = "release-v1.0"
ARCHIVE = Path("dist/adm-dataset-v1.0.zip")
CHECKSUMS = Path("experiments/main_grid.sha256")
STAMP = (2026, 11, 21, 0, 0, 0)  # the release date, on every member
MODE = 0o100644
UNIX = 3  # ZipInfo.create_system, so the bytes do not depend on the OS
FOLDER = "dataset"
INTEGRITY = (
    "python -m adm.eval.integrity --manifest experiments/main_grid.json"
    f" --checksums {CHECKSUMS.as_posix()}"
)
ATTRIBUTION = {
    "LICENSE": ("MIT License", "Permission is hereby granted, free of charge"),
    "NOTICE": (
        'This work includes material taken from the System Reference Document 5.1\n("SRD 5.1")'
        " by Wizards of the Coast LLC",
        "https://dnd.wizards.com/resources/systems-reference-document",
        "Creative Commons Attribution 4.0 International License",
        "https://creativecommons.org/licenses/by/4.0/legalcode",
        "Built with Llama",
        "Llama 3.1 is licensed under the Llama 3.1 Community License",
        "Copyright (c) Meta Platforms, Inc. All Rights Reserved.",
    ),
}


class ReleaseError(Exception):
    """The archive cannot be built: the problems are its lines."""


@dataclass(frozen=True)
class Annotation:
    path: str  # relative to the repository root, as in the archive
    sha256: str
    what: str
    pinned_in: str


ANNOTATIONS = (
    Annotation(
        "results/batch/attempts.jsonl",
        "b0340b8f8ceda0563ab61d5d38234a87a89ec48392dc578257f1a54dee189f03",
        "Batch runner's attempt ledger, one line per main-grid run (7.6, 9.3)",
        "decision log, 2026-11-20",
    ),
    Annotation(
        "results/m1_labels.jsonl",
        "53d74b6bd68400064fa83d8da1f60cc90087ece80918aba13f453362bb11138e",
        "M1 divergence labels, SD, 64 runs (9.5)",
        "docs/m1_annotation.md",
    ),
    Annotation(
        "results/m1_draft_claude.jsonl",
        "ad2a46bf43fe659d13d8eff8c9a01b5a3a9a0da970c182998a1b10d660a5c8c3",
        "AI draft SD reviewed for the M1 labels",
        "docs/m1_annotation.md",
    ),
    Annotation(
        "results/m1_labels_SS.jsonl",
        "dd0a2c8dd263710abe7cf1db249d1b3c05927142283694765de032230dd90285",
        "M1 overlap labels, SS, 16 runs (9.6)",
        "docs/m1_overlap.md",
    ),
    Annotation(
        "results/m1_overlap_draft_claude.jsonl",
        "6b7999245f753db1f1e6d979784f4c951830f3ef17c089bc5f02504387669d84",
        "AI draft SS reviewed for the overlap labels",
        "docs/m1_overlap.md",
    ),
    Annotation(
        "results/m3_intent.jsonl",
        "3561a33dd9b474372bc28bc6ef7b83d288b44d593d1d2389c1ec310c1c2ee8f5",
        "M3 intent-fidelity verdicts, CI, 242 turns (9.7)",
        "docs/m3_annotation.md",
    ),
    Annotation(
        "results/m3_draft_claude.jsonl",
        "8ab5e81b72e4c1d50cbce3d8365d93e78b04096a9e933f0f0970e46f64e51c52",
        "AI draft CI reviewed for the M3 verdicts",
        "docs/m3_annotation.md",
    ),
    Annotation(
        "results/m5_key.json",
        "2323457f4989117e1c1949eb80b362a1d424a39b4a8b0387845b345775676e34",
        "M5 key: each excerpt's run and window (8.15)",
        "decision log, 2026-11-20",
    ),
    Annotation(
        "results/m5_ratings.jsonl",
        "e4d987f6ca49539323c479dd54446d5f6ef0be03baa3613c0593c61127dfc45b",
        "M5 ratings, SD, 64 excerpts (9.9)",
        "docs/m5_rating_sd.md",
    ),
    Annotation(
        "results/m5_ratings_SS.jsonl",
        "52a7a8b34e0f3d3f10f2e97fd53d371e478c6c35be2812c2cf9f6ace72a42208",
        "M5 ratings, SS, 64 excerpts (9.8)",
        "docs/m5_rating_ss.md",
    ),
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned(logs: Mapping[str, str], annotations: Sequence[Annotation]) -> dict[str, str]:
    """Every released data file by its path in the archive, with its sha256."""
    files = {f"runs/{name}": digest for name, digest in logs.items()}
    files.update((a.path, a.sha256) for a in annotations)
    return dict(sorted(files.items()))


def licence_errors(root: Path) -> list[str]:
    """What `LICENSE` or `NOTICE` is missing of the licence and attribution."""
    errors = []
    for name, phrases in ATTRIBUTION.items():
        path = root / name
        if not path.is_file():
            errors.append(f"{name}: missing")
            continue
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        errors.extend(f"{name}: does not say {p!r}" for p in phrases if p not in text)
    return errors


def problems(root: Path, files: Mapping[str, str]) -> list[str]:
    """Why the archive cannot be built from `root`: missing files, bytes that
    are not the pinned ones, and gaps in the licence files."""
    owner = {digest: path for path, digest in files.items()}
    found = []
    for path, digest in files.items():
        where = root / path
        if not where.is_file():
            found.append(f"{path}: missing")
            continue
        got = sha256(where.read_bytes())
        if got == digest:
            continue
        hint = f"; it is {owner[got]}" if got in owner else ""
        found.append(f"{path}: sha256 {got[:8]}... is not the pinned {digest[:8]}...{hint}")
    return found + licence_errors(root)


def readme(files: Mapping[str, str], annotations: Sequence[Annotation]) -> str:
    logs = sum(1 for p in files if p.startswith("runs/"))
    rows = "\n".join(f"| `{a.path}` | {a.what} |" for a in annotations)
    return f"""# AI Dungeon Master: main-grid dataset

The dataset of the KMUTT project *AI Dungeon Master: A Hybrid Rule-Engine and
LLM-Based Game Master System*, released with the code at the git tag `{TAG}`
of https://github.com/Chavaphon/AI_Dungeon_Master.

- `runs/{{condition}}/{{scenario_id}}/{{seed}}.jsonl`: the {logs} audit logs of the
  main grid, 16 scenarios x 4 conditions x seeds 2001-2003, one JSON record per
  turn (`docs/audit_log.md`). Lines end in CRLF, as written; the checksums are
  of those bytes, so unpack as binary.
- The annotation files:

| File | What it is |
|---|---|
{rows}

Annotators are named by initials only. The labels, verdicts and overlap labels
began as AI drafts reviewed turn by turn; each line records whether the draft
was accepted or edited, and the drafts are included. The narration is output of
Llama 3.1 8B. The scripted player inputs were written by the team; no player
data is included.

## Use

Unpack into the root of a checkout of `{TAG}`, then, with `pip install -e ".[dev,analysis]"`:

    sha256sum -c {FOLDER}/SHA256SUMS
    {INTEGRITY}

The repository's `docs/report/appendix_a_release.md` gives the commands that
replay the logs' state and recompute every reported metric.

## Licence

MIT (`{FOLDER}/LICENSE`). The rules are adapted from the SRD 5.1 under CC-BY-4.0,
and the narration was generated with Llama 3.1 under the Llama 3.1 Community
License; see `{FOLDER}/NOTICE`. Built with Llama.
"""


def _member(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=STAMP)
    info.create_system = UNIX
    info.external_attr = MODE << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def archive(root: Path, files: Mapping[str, str], annotations: Sequence[Annotation]) -> bytes:
    """The archive's bytes. Raises `ReleaseError` with every problem first."""
    found = problems(root, files)
    if found:
        raise ReleaseError("\n".join(found))
    members = {path: (root / path).read_bytes() for path in files}
    members[f"{FOLDER}/LICENSE"] = (root / "LICENSE").read_bytes()
    members[f"{FOLDER}/NOTICE"] = (root / "NOTICE").read_bytes()
    members[f"{FOLDER}/README.md"] = readme(files, annotations).encode("utf-8")
    sums = "".join(f"{sha256(data)}  {path}\n" for path, data in sorted(members.items()))
    members[f"{FOLDER}/SHA256SUMS"] = sums.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path in sorted(members):
            zf.writestr(_member(path), members[path], compresslevel=9)
    return buffer.getvalue()


def render(
    data: bytes, out: Path, files: Mapping[str, str], annotations: Sequence[Annotation]
) -> str:
    logs = sum(1 for p in files if p.startswith("runs/"))
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        count = len(zf.namelist())
    rows = "\n".join(
        f"| `{a.path}` | {a.what} | `{a.sha256}` | {a.pinned_in} |" for a in annotations
    )
    return f"""| Archive | Size | Members | sha256 |
|---|---|---|---|
| `{out.as_posix()}` | {len(data):,} bytes | {count} | `{sha256(data)}` |

The {logs} logs match `experiments/main_grid.sha256`; the other files match their pins:

| File | What it is | sha256 | Pinned in |
|---|---|---|---|
{rows}

Every member's sha256 is in `{FOLDER}/SHA256SUMS` inside the archive."""


app = typer.Typer(add_completion=False)


@app.command()
def main(
    checksums: Annotated[
        Path, typer.Option(exists=True, dir_okay=False, help="The logs' sha256 file.")
    ] = CHECKSUMS,
    root: Annotated[Path, typer.Option(help="Where runs/ and results/ are.")] = Path("."),
    out: Annotated[Path, typer.Option(help="The archive to write.")] = ARCHIVE,
    doc: Annotated[Path | None, typer.Option(help="Doc whose results block is rewritten.")] = None,
) -> None:
    """Build the release archive from the pinned files."""
    files = pinned(read_checksums(checksums), ANNOTATIONS)
    try:
        data = archive(root, files, ANNOTATIONS)
    except ReleaseError as error:
        typer.echo(f"Not built: {len(str(error).splitlines())} problems")
        typer.echo(str(error))
        raise typer.Exit(1) from None
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    typer.echo(f"{out.as_posix()}: {len(data)} bytes, sha256 {sha256(data)}")
    if doc is not None:
        write_results(doc, render(data, out, files, ANNOTATIONS))
        typer.echo(f"Results: {doc}")


if __name__ == "__main__":
    app()
