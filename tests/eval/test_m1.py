"""M1 annotation (WBS 9.5, 9.6): whole runs, paired by seed, blind to condition.

The sample is one seed per scenario, all four conditions at it, fixed with no
RNG; the overlap is ceil(20%) of each condition; each annotator has their own
run order. A turn shows its checker candidates and nothing that names the
condition, run or seed. The tool writes one line per turn, resumes, and
replaces a line on `--redo`.

No test calls a model: the logs are written by the real harnesses with a fake
client, as in tests/eval/test_checker_validation.py.

Run: pytest tests/eval/test_m1.py -v
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from typer.testing import CliRunner

from adm.engine.audit import run_id
from adm.engine.scenario import load_scenario
from adm.eval import annotate, m1
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.narration_only import NarrationOnlyStart
from adm.orchestration.session import Session, new_run_log, run_script

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "scenarios"
CELLAR = load_scenario(SCENARIOS / "s01_cellar.json")
TEXTS = prompt.load_templates()
CONFIG = load_model_config()
SEED = 2001
NULL = json.dumps({"tool": None})

PHANTOM = "You raise your lantern, and a hooded stranger steps out."
CLEAN = "Water drips down the cellar stairs and pools around the barrels."


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- the sample --------------------------------------------------------------


def _keys(scenarios: Sequence[str], seeds: Sequence[int], conditions: str = "ABCD") -> list:
    return [(c, s, seed) for s in scenarios for seed in seeds for c in conditions]


def test_one_seed_per_scenario_all_four_conditions_in_hash_order() -> None:
    keys = _keys(["s01_cellar", "s02_toll_bridge"], [2001, 2002, 2003])
    sample = m1.draw_runs(keys)
    assert len(sample) == 8
    for scenario_id in ("s01_cellar", "s02_toll_bridge"):
        want = min((2001, 2002, 2003), key=lambda s: sha(f"m1-v1/{scenario_id}/{s}"))
        assert {k for k in sample if k[1] == scenario_id} == {
            (c, scenario_id, want) for c in "ABCD"
        }
    assert m1.draw_runs(list(reversed(keys))) == sample


def test_a_seed_missing_a_condition_is_not_drawn() -> None:
    keys = _keys(["s01_cellar"], [2001, 2002, 2003])
    best = min((2001, 2002, 2003), key=lambda s: sha(f"m1-v1/s01_cellar/{s}"))
    keys.remove(("B", "s01_cellar", best))
    keys += [("D", "s01_cellar", 1001)]  # a smoke log: condition D only
    sample = m1.draw_runs(keys)
    assert len(sample) == 4 and best not in {k[2] for k in sample}
    assert 1001 not in {k[2] for k in sample}
    assert m1.draw_runs([("D", "s01_cellar", 2001)]) == []


def test_the_main_grid_gives_64_runs_and_a_16_run_overlap() -> None:
    scenarios = [f"s{i:02d}" for i in range(1, 13)] + [f"long{i:02d}" for i in range(1, 5)]
    sample = m1.draw_runs(_keys(scenarios, [2001, 2002, 2003]))
    assert len(sample) == 64
    overlap = m1.overlap_runs(sample)
    assert len(overlap) == 16 and set(overlap) <= set(sample)
    assert {c: sum(1 for k in overlap if k[0] == c) for c in "ABCD"} == dict.fromkeys("ABCD", 4)
    assert m1.overlap_runs(sample) == overlap


def test_each_annotator_has_their_own_run_order() -> None:
    sample = m1.draw_runs(_keys([f"s{i:02d}" for i in range(1, 13)], [2001]))
    sd, ss = m1.annotator_order(sample, "SD"), m1.annotator_order(sample, "SS")
    assert sorted(sd) == sorted(ss) == sample
    assert sd != ss
    # Conditions are interleaved, not in blocks.
    assert [k[0] for k in sd] != sorted(k[0] for k in sd)


# --- answers -------------------------------------------------------------------


def test_confirmed_candidates_are_parsed() -> None:
    assert m1.parse_confirmed("", 3) == set()
    assert m1.parse_confirmed("a", 3) == {1, 2, 3}
    assert m1.parse_confirmed("1 3", 3) == {1, 3}
    assert m1.parse_confirmed("1,2", 3) == {1, 2}
    for bad in ("0", "4", "x", "1 x"):
        with pytest.raises(ValueError):
            m1.parse_confirmed(bad, 3)


def test_category_letters_and_phrases() -> None:
    assert m1.parse_category("p") == "PHANTOM"
    assert m1.parse_category("L") == "RELATION"
    assert m1.parse_category("u") == "RULE"
    assert m1.parse_category("") is None
    with pytest.raises(ValueError):
        m1.parse_category("X")
    assert m1.find_phrase("You raise your Lantern.", "lantern") == [15, 22]
    for bad in ("", "torch"):
        with pytest.raises(ValueError):
            m1.find_phrase("You raise your lantern.", bad)


# --- the tool on real logs -----------------------------------------------------


class FakeClient:
    """Narrates `narrations` in turn, then CLEAN; proposes `{"tool": null}`."""

    def __init__(self, narrations: Sequence[str]) -> None:
        self.narrations = list(narrations)

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase == "toolcall":
            reply = NULL
        elif phase == "narration":
            reply = self.narrations.pop(0) if self.narrations else CLEAN
        else:
            reply = "Lyra searched the cellar."
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One cellar run per condition at SEED; A's first narration has a phantom."""
    runs = tmp_path_factory.mktemp("m1") / "runs"
    for condition in "ABC":
        log = new_run_log(runs, condition, CELLAR.scenario_id, SEED)
        narrations = [PHANTOM] if condition == "A" else []
        start = NarrationOnlyStart(condition.lower())
        run_script(start(FakeClient(narrations), CONFIG, TEXTS, CELLAR, log, seed=SEED))
    log = new_run_log(runs, "D", CELLAR.scenario_id, SEED)
    run_script(Session.start(FakeClient([]), CONFIG, TEXTS, CELLAR, log, seed=SEED))
    return runs


def _items(runs: Path, annotator: str = "SD") -> list[m1.M1Turn]:
    logs = annotate.load_runs(runs)
    order = m1.annotator_order(m1.draw_runs(sorted(logs)), annotator)
    return list(m1.sample_turns(order, logs, {CELLAR.scenario_id: CELLAR}))


def test_a_turn_shows_its_candidates_and_nothing_that_names_the_condition(runs: Path) -> None:
    items = _items(runs)
    assert len({i.turn_id for i in items}) == len(items) == 4 * len(CELLAR.scripted_inputs)
    phantom = next(i for i in items if PHANTOM in i.turn.narration)
    shown = m1.render(phantom)
    assert "Checker candidates:" in shown and "[1] PHANTOM" in shown and "lantern" in shown
    for item in items:
        shown = m1.render(item)
        assert "Player input:" in shown and "Narration:" in shown
        for hidden in ("_s01_cellar_", str(SEED), "Condition", "condition", "entity_mention"):
            assert hidden not in shown
    # A run's turns are shown together, in play order.
    first_run = [i for i in items if i.run_id == items[0].run_id]
    assert [i.input_index for i in first_run] == sorted(i.input_index for i in first_run)
    assert items[: len(first_run)] == first_run


def _m1(tmp_path: Path, runs: Path, keys: str, *extra: str) -> tuple[int, str]:
    args = ["m1", "--annotator", "SD", "--runs", str(runs)]
    args += ["--scenarios", str(SCENARIOS), "--results", str(tmp_path / "results"), *extra]
    result = CliRunner().invoke(annotate.app, args, input=keys)
    return result.exit_code, result.output


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_m1_records_confirmations_and_additions_and_resumes(tmp_path: Path, runs: Path) -> None:
    items = _items(runs)
    first, second = items[0], items[1]
    answer = "1\n" if first.candidates else ""
    phrase = first.turn.narration.split()[0]
    # First turn: confirm candidate 1 if there is one; a bad letter and a phrase
    # not in the narration are asked again; add a RESOURCE phrase. Then stop.
    keys = answer + f"X\nr\nnot in it\n{phrase}\n\nlooks off\nq\n"
    code, out = _m1(tmp_path, runs, keys)
    assert code == 0, out
    labels = tmp_path / "results" / "m1_labels.jsonl"
    [line] = _lines(labels)
    assert line["turn_id"] == first.turn_id and line["annotator"] == "SD"
    assert line["run_id"] == first.run_id and line["input_index"] == first.input_index
    assert [c["confirmed"] for c in line["candidates"]] == [
        n == 1 for n in range(1, len(first.candidates) + 1)
    ]
    assert line["added"] == [{"category": "RESOURCE", "phrase": phrase, "span": [0, len(phrase)]}]
    assert line["note"] == "looks off"
    for hidden in ("_s01_cellar_", run_id("A", "s01_cellar", SEED)):
        assert hidden not in out

    # Resume: the next turn shown is the second.
    keys = ("\n" if second.candidates else "") + "\n\nq\n"
    code, out = _m1(tmp_path, runs, keys)
    assert code == 0, out
    assert [r["turn_id"] for r in _lines(labels)] == [first.turn_id, second.turn_id]
    assert f"2/{len(items)} annotated" in out


def test_m1_redo_replaces_the_line_and_needs_a_note(tmp_path: Path, runs: Path) -> None:
    items = _items(runs)
    first = items[0]
    skip = "\n" if first.candidates else ""
    _m1(tmp_path, runs, skip + "\n\nq\n")
    keys = skip + "\n\n" + "misread the band\n"  # the empty note is asked again
    code, out = _m1(tmp_path, runs, keys, "--redo", first.turn_id)
    assert code == 0, out
    [line] = _lines(tmp_path / "results" / "m1_labels.jsonl")
    assert line["note"] == "misread the band"
    code, out = _m1(tmp_path, runs, "", "--redo", items[1].turn_id)
    assert code == 1 and "not annotated" in out


def test_m1_overlap_takes_a_fifth_of_each_condition(tmp_path: Path, runs: Path) -> None:
    code, out = _m1(tmp_path, runs, "q\n", "--overlap")
    assert code == 0, out
    assert out.startswith("4 runs,")


def test_m1_with_no_whole_scenario_says_so(tmp_path: Path) -> None:
    code, out = _m1(tmp_path, tmp_path / "empty", "")
    assert code == 1 and "four conditions" in out
