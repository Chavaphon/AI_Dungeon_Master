"""The code and data release (WBS 11.11): the licence and attribution, which
files go in, the checks that refuse a wrong or missing file, and the archive.

The repository's own `LICENSE` and `NOTICE` are checked; everything else uses
small files in a temporary folder. No test reads the logs or calls a model.

Run: pytest tests/eval/test_release.py -v
"""

import io
import shutil
import zipfile
from pathlib import Path

import pytest

from adm.eval import release
from adm.eval.release import Annotation, ReleaseError

REPO = Path(__file__).resolve().parents[2]
LOG = b'{"run_id": "A_s01_cellar_2001"}\r\n{"turn_number": 1}\r\n'
LABELS = b'{"turn_id": "x", "annotator": "SD"}\n'
RATINGS = b'{"excerpt_id": "x", "rater": "SS"}\n'


def setup(tmp_path: Path) -> tuple[dict[str, str], list[Annotation]]:
    """A root with one log, two annotation files and the repository's licence files."""
    (tmp_path / "runs/A/s01_cellar").mkdir(parents=True)
    (tmp_path / "runs/A/s01_cellar/2001.jsonl").write_bytes(LOG)
    (tmp_path / "results").mkdir()
    (tmp_path / "results/m1_labels.jsonl").write_bytes(LABELS)
    (tmp_path / "results/m5_ratings_SS.jsonl").write_bytes(RATINGS)
    for name in ("LICENSE", "NOTICE"):
        shutil.copy(REPO / name, tmp_path / name)
    annotations = [
        Annotation("results/m1_labels.jsonl", release.sha256(LABELS), "labels", "doc"),
        Annotation("results/m5_ratings_SS.jsonl", release.sha256(RATINGS), "ratings", "doc"),
    ]
    logs = {"A/s01_cellar/2001.jsonl": release.sha256(LOG)}
    return release.pinned(logs, annotations), annotations


def test_the_repository_carries_the_licence_and_attribution() -> None:
    assert release.licence_errors(REPO) == []


def test_a_notice_without_the_attribution_is_refused(tmp_path) -> None:
    (tmp_path / "LICENSE").write_text((REPO / "LICENSE").read_text(encoding="utf-8"))
    (tmp_path / "NOTICE").write_text("AI Dungeon Master\nBuilt with Llama\n")
    errors = release.licence_errors(tmp_path)
    assert errors and all(e.startswith("NOTICE: ") for e in errors)
    assert any("Creative Commons Attribution 4.0" in e for e in errors)
    assert not any("Built with Llama" in e for e in errors)


def test_every_planned_annotation_has_a_full_pin_and_its_own_path() -> None:
    paths = [a.path for a in release.ANNOTATIONS]
    assert len(set(paths)) == len(paths)
    assert all(len(a.sha256) == 64 and int(a.sha256, 16) >= 0 for a in release.ANNOTATIONS)
    assert len({a.sha256 for a in release.ANNOTATIONS}) == len(paths)


def test_the_logs_come_from_the_checksum_file_under_runs(tmp_path) -> None:
    files, _ = setup(tmp_path)
    assert list(files) == [
        "results/m1_labels.jsonl",
        "results/m5_ratings_SS.jsonl",
        "runs/A/s01_cellar/2001.jsonl",
    ]
    checked = release.pinned(release.read_checksums(REPO / release.CHECKSUMS), [])
    assert len(checked) == 192 and all(p.startswith("runs/") for p in checked)


def test_a_missing_or_changed_file_is_named(tmp_path) -> None:
    files, _ = setup(tmp_path)
    assert release.problems(tmp_path, files) == []
    (tmp_path / "results/m1_labels.jsonl").unlink()
    (tmp_path / "runs/A/s01_cellar/2001.jsonl").write_bytes(LOG.replace(b"\r\n", b"\n"))
    got = release.problems(tmp_path, files)
    assert got[0] == "results/m1_labels.jsonl: missing"
    assert got[1].startswith("runs/A/s01_cellar/2001.jsonl: sha256 ")
    assert len(got) == 2


def test_a_file_under_another_files_name_is_pointed_out(tmp_path) -> None:
    files, _ = setup(tmp_path)
    (tmp_path / "results/m1_labels.jsonl").write_bytes(RATINGS)
    got = release.problems(tmp_path, files)
    assert got == [
        f"results/m1_labels.jsonl: sha256 {release.sha256(RATINGS)[:8]}... is not the pinned "
        f"{release.sha256(LABELS)[:8]}...; it is results/m5_ratings_SS.jsonl"
    ]


def test_the_archive_is_refused_with_every_problem(tmp_path) -> None:
    files, annotations = setup(tmp_path)
    (tmp_path / "NOTICE").unlink()
    (tmp_path / "results/m5_ratings_SS.jsonl").unlink()
    with pytest.raises(ReleaseError) as error:
        release.archive(tmp_path, files, annotations)
    assert str(error.value).splitlines() == [
        "results/m5_ratings_SS.jsonl: missing",
        "NOTICE: missing",
    ]


def test_the_archive_holds_the_files_unchanged_and_repeats_byte_for_byte(tmp_path) -> None:
    files, annotations = setup(tmp_path)
    data = release.archive(tmp_path, files, annotations)
    assert release.archive(tmp_path, files, annotations) == data
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert names == sorted(names)
        assert set(names) == set(files) | {
            "dataset/LICENSE",
            "dataset/NOTICE",
            "dataset/README.md",
            "dataset/SHA256SUMS",
        }
        assert zf.read("runs/A/s01_cellar/2001.jsonl") == LOG  # CRLF kept
        assert {i.date_time for i in zf.infolist()} == {release.STAMP}
        sums = zf.read("dataset/SHA256SUMS").decode().splitlines()
        assert len(sums) == len(names) - 1
        for line in sums:
            digest, path = line.split("  ")
            assert release.sha256(zf.read(path)) == digest
        text = zf.read("dataset/README.md").decode()
    assert release.TAG in text and "the 1 audit logs" in text and "Built with Llama" in text


def test_the_results_block_names_the_archive_and_each_pin(tmp_path) -> None:
    files, annotations = setup(tmp_path)
    data = release.archive(tmp_path, files, annotations)
    block = release.render(data, release.ARCHIVE, files, annotations)
    assert f"`{release.sha256(data)}`" in block and "| 7 |" in block
    assert f"`{release.sha256(LABELS)}`" in block and "The 1 logs match" in block
