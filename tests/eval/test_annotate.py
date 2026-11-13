"""Annotation tool (WBS 8.15): blind and condition-shuffled. M5 excerpts are
chosen, identified and ordered as docs/narrative_quality.md says, and show only
the title, the inputs and the narration, so a rater cannot tell the condition
(the done-when of #92). M3 turns are drawn as docs/intent_fidelity.md section 2
says and show only what its section 3.2 allows, with the state the tool-call
prompt saw. Both write one line per rating and resume where a rater stopped.

No test calls a model: the condition D logs come from a scripted fake client.

Run: pytest tests/eval/test_annotate.py -v
"""

import hashlib
import json
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from adm.engine.audit import read_log, run_id
from adm.engine.combat import start_encounter
from adm.engine.dice import DiceRoller
from adm.engine.scenario import initial_state, load_scenario
from adm.eval import annotate
from adm.orchestration import prompt
from adm.orchestration.client import Message, ModelReply, Phase, load_model_config
from adm.orchestration.session import Session, new_run_log

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "scenarios"
SCENARIO = load_scenario(SCENARIOS / "s01_cellar.json")
LONG = load_scenario(SCENARIOS / "long01_border_road.json")
CONDITIONS = ("A", "B", "C", "D")
SEED = 2001

Doc = dict[str, Any]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- synthetic runs for M5 ---------------------------------------------------


def _record(condition: str, scenario_id: str, seed: int, index: int, failed: bool = False) -> Doc:
    return {
        "run_id": run_id(condition, scenario_id, seed),
        "condition": condition,
        "scenario_id": scenario_id,
        "seed": seed,
        "turn_number": index + 1,
        "input_index": index,
        "player_input": f"input {index}",
        "narration": None if failed else f"{condition} narration {index}",
        "narration_filtered": False,
        "turn_failure": "unparseable" if failed else None,
    }


def _runs(
    scenario_id: str = "s01_cellar",
    inputs: int = 26,
    seeds: Sequence[int] = (SEED,),
    conditions: Sequence[str] = CONDITIONS,
    failed: Sequence[tuple[int, int]] = (),
) -> dict[tuple[str, str, int], list[Doc]]:
    """One run per condition and seed; `failed` holds (seed, input_index) of D's failed turns."""
    return {
        (c, scenario_id, seed): [
            _record(c, scenario_id, seed, i, failed=c == "D" and (seed, i) in failed)
            for i in range(inputs)
        ]
        for c in conditions
        for seed in seeds
    }


def _first_window(scenario_id: str, inputs: int, bad: set[int] = frozenset()) -> int:
    windows = sorted(range(inputs - 4), key=lambda w: sha(f"m5-v1/{scenario_id}/window/{w}"))
    return next(w for w in windows if not bad & set(range(w, w + 5)))


def test_m5_takes_the_first_window_in_hash_order_for_every_condition() -> None:
    excerpts, skipped = annotate.select_excerpts(_runs(), {"s01_cellar": SCENARIO})
    w = _first_window("s01_cellar", 26)
    assert skipped == []
    assert sorted(e.run_id for e in excerpts) == [run_id(c, "s01_cellar", SEED) for c in CONDITIONS]
    for e in excerpts:
        assert e.w == w
        assert e.excerpt_id == sha(f"m5-v1/excerpt/{e.run_id}/{w}")[:8]
        assert e.title == SCENARIO.display_name
        cond = e.run_id[0]
        assert e.exchanges == tuple(
            (f"input {i}", f"{cond} narration {i}") for i in range(w, w + 5)
        )


def test_m5_skips_a_window_with_a_failed_turn_in_all_four_conditions() -> None:
    w = _first_window("s01_cellar", 26)
    runs = _runs(failed=[(SEED, w + 2)])
    excerpts, _ = annotate.select_excerpts(runs, {"s01_cellar": SCENARIO})
    expected = _first_window("s01_cellar", 26, bad={w + 2})
    assert {e.w for e in excerpts} == {expected} and expected != w


def test_m5_takes_the_first_seed_in_hash_order_that_has_a_usable_window() -> None:
    seeds = (2001, 2002, 2003)
    ordered = sorted(seeds, key=lambda s: sha(f"m5-v1/s01_cellar/seed/{s}"))
    # Every window of the first seed holds a failed D turn.
    failed = [(ordered[0], i) for i in range(0, 26, 4)]
    excerpts, _ = annotate.select_excerpts(
        _runs(seeds=seeds, failed=failed), {"s01_cellar": SCENARIO}
    )
    assert {e.run_id[-4:] for e in excerpts} == {str(ordered[1])}


def test_m5_skips_a_scenario_without_a_seed_run_in_all_four_conditions() -> None:
    runs = _runs(conditions=("A", "B", "D"))
    excerpts, skipped = annotate.select_excerpts(runs, {"s01_cellar": SCENARIO})
    assert excerpts == [] and skipped == ["s01_cellar"]


def test_m5_short_only_drops_the_long_sessions() -> None:
    runs = {**_runs(), **_runs(scenario_id=LONG.scenario_id, inputs=len(LONG.scripted_inputs))}
    scenarios = {"s01_cellar": SCENARIO, LONG.scenario_id: LONG}
    full, _ = annotate.select_excerpts(runs, scenarios)
    short, _ = annotate.select_excerpts(runs, scenarios, short_only=True)
    assert {e.run_id.split("_", 1)[1].rsplit("_", 1)[0] for e in full} == set(scenarios)
    assert {e.run_id for e in short} == {e.run_id for e in full if "_s01_" in e.run_id}


def test_m5_each_rater_has_their_own_hash_order() -> None:
    runs = {
        **_runs(),
        **_runs(scenario_id=LONG.scenario_id, inputs=len(LONG.scripted_inputs)),
    }
    excerpts, _ = annotate.select_excerpts(runs, {"s01_cellar": SCENARIO, LONG.scenario_id: LONG})
    ss = annotate.rater_order(excerpts, "SS")
    sd = annotate.rater_order(excerpts, "SD")
    assert [e.excerpt_id for e in ss] == sorted(
        (e.excerpt_id for e in excerpts), key=lambda i: sha(f"m5-v1/order/SS/{i}")
    )
    assert [e.excerpt_id for e in ss] != [e.excerpt_id for e in sd]


def test_an_m5_excerpt_shows_nothing_that_names_the_condition() -> None:
    w = _first_window("s01_cellar", 26)
    runs = _runs()
    for records in runs.values():  # the same narration in every condition
        for r in records:
            r["narration"] = f"narration {r['input_index']}"
    runs[("D", "s01_cellar", SEED)][w]["narration_filtered"] = True
    excerpts, _ = annotate.select_excerpts(runs, {"s01_cellar": SCENARIO})
    views = {e.run_id: annotate.render_excerpt(e) for e in excerpts}
    blind = {re.sub(r"Excerpt \w+", "Excerpt ?", v) for v in views.values()}
    assert len(blind) == 1, "the four conditions render identically apart from the id"
    for rid, view in views.items():
        assert rid not in view and str(SEED) not in view
        assert re.search(r"\b[ABCD]\b", view) is None
        assert "turn" not in view.lower() and "filtered" not in view.lower()
        assert SCENARIO.display_name in view
        assert all(f"input {i}" in view for i in range(w, w + 5))


def test_the_m5_key_is_written_kept_and_guarded(tmp_path: Path) -> None:
    excerpts, _ = annotate.select_excerpts(_runs(), {"s01_cellar": SCENARIO})
    key = tmp_path / "m5_key.json"
    annotate.sync_key(key, excerpts)
    data = json.loads(key.read_text(encoding="utf-8"))
    assert data == {e.excerpt_id: {"run_id": e.run_id, "w": e.w} for e in excerpts}
    annotate.sync_key(key, excerpts)  # the same selection: accepted
    with pytest.raises(annotate.KeyDrift):
        annotate.sync_key(key, excerpts[:2])


# --- condition D logs for M3 -------------------------------------------------

LOOK = json.dumps(
    {"tool": "skill_check", "arguments": {"actor_id": "pc_lyra", "skill": "perception", "dc": 12}}
)
ATTACK = json.dumps(
    {
        "tool": "attack",
        "arguments": {
            "attacker_id": "pc_lyra",
            "target_id": "npc_rat_01",
            "weapon_id": "item_short_sword",
        },
    }
)
NULL = json.dumps({"tool": None})
GARBLED = "Lyra should look around."
NARRATION = "Water laps at the barrels."
SUMMARY = "Lyra searched the cellar."


class SnapshotClient:
    """Answers toolcalls in order, and keeps the session's state at each turn's
    first toolcall: the state the model saw."""

    def __init__(self, *toolcalls: str) -> None:
        self.toolcalls = list(toolcalls)
        self.session: Session | None = None
        self.seen: list[Doc] = []

    def chat(self, messages: Sequence[Message], *, phase: Phase, seed: int) -> ModelReply:
        if phase != "toolcall":
            reply = NARRATION if phase == "narration" else SUMMARY
        else:
            if len(messages) == 2:  # first attempt: system and player input
                assert self.session is not None
                self.seen.append(self.session.state.to_dict())
            reply = self.toolcalls.pop(0)
        return ModelReply(reply, 3000, 40, 0, 0, "stop", 0)


def _seed_where_an_npc_goes_first() -> int:
    for seed in range(1000):
        trial = initial_state(SCENARIO, seed)
        start_encounter(trial, DiceRoller(seed), SCENARIO.encounters[0].combatant_ids)
        if trial.active_combatant_id != "pc_lyra":
            return seed
    raise AssertionError("no seed found")


def _d_run(runs: Path, seed: int) -> SnapshotClient:
    """Inputs 0-2 a check, 3 an attack (the encounter opens first), 4 no call
    (narration only), 5 a failed turn."""
    client = SnapshotClient(LOOK, LOOK, LOOK, ATTACK, NULL, NULL, GARBLED, GARBLED, GARBLED)
    log = new_run_log(runs, "D", SCENARIO.scenario_id, seed)
    session = Session.start(
        client, load_model_config(), prompt.load_templates(), SCENARIO, log, seed=seed
    )
    client.session = session
    for index, scripted in enumerate(SCENARIO.scripted_inputs[:6]):
        session.play(scripted.text, input_index=index, scripted=scripted)
    return client


@pytest.fixture
def d_runs(tmp_path: Path) -> tuple[Path, int, SnapshotClient]:
    seed = _seed_where_an_npc_goes_first()
    runs = tmp_path / "runs"
    return runs, seed, _d_run(runs, seed)


def test_m3_draws_ceil_rate_of_each_stratum_in_hash_order(
    d_runs: tuple[Path, int, SnapshotClient],
) -> None:
    runs_dir, seed, _ = d_runs
    _d_run(runs_dir, seed + 1)
    runs = annotate.load_runs(runs_dir)
    rid = [run_id("D", "s01_cellar", s) for s in (seed, seed + 1)]
    population = [(r, i) for r in rid for i in range(5)]  # input 5 failed in both
    key = {(r, i): sha(f"m3-v1/{r}/{i}") for r, i in population}

    items = annotate.draw_sample(runs, rate=0.15)
    expected = sorted(population, key=key.get)[: math.ceil(0.15 * 10)]
    assert [(t.run_id, t.input_index) for t in items] == sorted(expected, key=key.get)
    assert all(t.item_id == key[(t.run_id, t.input_index)][:8] for t in items)

    everything = annotate.draw_sample(runs, rate=1.0)
    assert sorted((t.run_id, t.input_index) for t in everything) == sorted(population)
    assert any(t.record["executed_call"] is None for t in everything), "no call is judged too"
    small = {(t.run_id, t.input_index) for t in annotate.draw_sample(runs, rate=0.10)}
    assert small <= {(t.run_id, t.input_index) for t in items}


def test_m3_ignores_conditions_other_than_d() -> None:
    runs = _runs()
    assert all(t.run_id.startswith("D_") for t in annotate.draw_sample(runs, rate=1.0))


def test_m3_state_is_the_state_the_toolcall_prompt_saw(
    d_runs: tuple[Path, int, SnapshotClient],
) -> None:
    runs_dir, seed, client = d_runs
    records = read_log(runs_dir / "D" / "s01_cellar" / f"{seed}.jsonl")
    # Five turns that reached the tool phase once each, then the failed turn.
    for index, seen in enumerate(client.seen):
        assert annotate.state_at_call(SCENARIO, seed, records, index) == seen
    opened = annotate.state_at_call(SCENARIO, seed, records, 3)
    assert opened["encounter_active"], "the encounter opens before the call"


def test_m3_refuses_a_log_that_does_not_replay(d_runs: tuple[Path, int, SnapshotClient]) -> None:
    runs_dir, seed, _ = d_runs
    records = read_log(runs_dir / "D" / "s01_cellar" / f"{seed}.jsonl")
    records[1]["state_diff"] = []
    with pytest.raises(annotate.LogMismatch):
        annotate.state_at_call(SCENARIO, seed, records, 3)


def test_an_m3_turn_shows_the_call_with_names_and_hides_the_rest(
    d_runs: tuple[Path, int, SnapshotClient],
) -> None:
    runs_dir, seed, _ = d_runs
    records = read_log(runs_dir / "D" / "s01_cellar" / f"{seed}.jsonl")
    view = annotate.render_turn(records[3], annotate.state_at_call(SCENARIO, seed, records, 3))
    assert SCENARIO.scripted_inputs[3].text in view
    assert "attack" in view
    assert re.search(r"npc_rat_01 \([^)]+\)", view)
    assert "item_short_sword (short sword)" in view
    assert "Encounter: active" in view
    assert "The Missing Ledger" in view and "the Keeper" in view
    assert NARRATION not in view
    assert run_id("D", "s01_cellar", seed) not in view
    assert "expected" not in view.lower()

    none = annotate.render_turn(records[4], annotate.state_at_call(SCENARIO, seed, records, 4))
    assert "no call" in none


# --- the command line --------------------------------------------------------


def _write_runs(root: Path, runs: dict[tuple[str, str, int], list[Doc]]) -> None:
    for (c, sid, seed), records in runs.items():
        path = root / c / sid / f"{seed}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _m5(tmp_path: Path, keys: str, *extra: str) -> tuple[int, str]:
    args = ["m5", "--rater", "SS", "--runs", str(tmp_path / "runs")]
    args += ["--scenarios", str(SCENARIOS), "--results", str(tmp_path / "results"), *extra]
    result = CliRunner().invoke(annotate.app, args, input=keys)
    return result.exit_code, result.output


def _lines(path: Path) -> list[Doc]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_m5_rates_every_excerpt_and_resumes(tmp_path: Path) -> None:
    _write_runs(tmp_path / "runs", _runs())
    # First excerpt: one invalid score of each kind is asked again. Then stop.
    code, out = _m5(tmp_path, "0\n6\nx\n4\n3\n5\n4\nhard to judge\nq\n")
    assert code == 0, out
    ratings = tmp_path / "results" / "m5_ratings.jsonl"
    [first] = _lines(ratings)
    assert first == {
        "excerpt_id": first["excerpt_id"],
        "rater": "SS",
        "coherence": 4,
        "vividness": 3,
        "tone": 5,
        "engagement": 4,
        "note": "hard to judge",
    }
    assert (tmp_path / "results" / "m5_key.json").exists()
    assert "D_s01_cellar" not in out and str(SEED) not in out

    code, out = _m5(tmp_path, "3\n3\n3\n3\n\n" * 3)
    assert code == 0, out
    lines = _lines(ratings)
    assert len(lines) == 4 and len({r["excerpt_id"] for r in lines}) == 4
    assert lines[0] == first, "the first rating is kept and not shown again"
    code, out = _m5(tmp_path, "")
    assert code == 0 and "4/4" in out


def test_m5_redo_replaces_the_line_and_needs_a_note(tmp_path: Path) -> None:
    _write_runs(tmp_path / "runs", _runs())
    _m5(tmp_path, "4\n4\n4\n4\n\nq\n")
    ratings = tmp_path / "results" / "m5_ratings.jsonl"
    [old] = _lines(ratings)
    code, out = _m5(tmp_path, "2\n2\n2\n2\n\nmisread excerpt 3\n", "--redo", old["excerpt_id"])
    assert code == 0, out
    [new] = _lines(ratings)
    assert new["coherence"] == 2 and new["note"] == "misread excerpt 3"


def test_m5_with_no_excerpt_says_so(tmp_path: Path) -> None:
    _write_runs(tmp_path / "runs", _runs(conditions=("D",)))
    code, out = _m5(tmp_path, "")
    assert code == 1 and "s01_cellar" in out


def _manifest(tmp_path: Path, seeds: Sequence[int]) -> Path:
    """A batch manifest planning s01_cellar under all four conditions."""
    path = tmp_path / "manifest.json"
    doc = {
        "scenarios": [str(SCENARIOS / "s01_cellar.json")],
        "conditions": ["A", "B", "C", "D"],
        "seeds": list(seeds),
    }
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _m3(tmp_path: Path, runs_dir: Path, seeds: Sequence[int], keys: str, *extra: str) -> Any:
    args = ["m3", "--annotator", "CI", "--runs", str(runs_dir), "--rate", "1.0"]
    args += ["--scenarios", str(SCENARIOS), "--results", str(tmp_path / "results")]
    args += ["--manifest", str(_manifest(tmp_path, seeds)), *extra]
    return CliRunner().invoke(annotate.app, args, input=keys)


def test_m3_records_a_verdict_with_a_reason_code(
    d_runs: tuple[Path, int, SnapshotClient], tmp_path: Path
) -> None:
    runs_dir, seed, _ = d_runs
    result = _m3(tmp_path, runs_dir, [seed], "n\nWRONG\nwrong_tool\n\ny\n\nq\n")
    assert result.exit_code == 0, result.output
    first, second = _lines(tmp_path / "results" / "m3_intent.jsonl")
    order = annotate.draw_sample(annotate.load_runs(runs_dir), rate=1.0)
    assert first == {
        "run_id": order[0].run_id,
        "input_index": order[0].input_index,
        "annotator": "CI",
        "faithful": False,
        "reason": "WRONG_TOOL",
        "note": "",
    }
    assert second["faithful"] is True and second["reason"] is None
    assert run_id("D", "s01_cellar", seed) not in result.output


def test_m3_draws_only_from_the_runs_the_manifest_plans(
    d_runs: tuple[Path, int, SnapshotClient], tmp_path: Path
) -> None:
    """A smoke log in runs/D at a seed the main grid does not plan is not in
    the population (docs/intent_fidelity.md section 2, rule 1)."""
    runs_dir, seed, _ = d_runs
    _d_run(runs_dir, seed + 1)
    result = _m3(tmp_path, runs_dir, [seed], "q\n")
    assert result.exit_code == 0, result.output
    assert "[1/5]" in result.output, "five turns of the one planned run, not ten"


def test_m3_refuses_a_population_with_a_planned_log_missing(
    d_runs: tuple[Path, int, SnapshotClient], tmp_path: Path
) -> None:
    runs_dir, seed, _ = d_runs
    result = _m3(tmp_path, runs_dir, [seed, seed + 1], "q\n")
    assert result.exit_code == 1
    assert run_id("D", "s01_cellar", seed + 1) in result.output
    assert not (tmp_path / "results" / "m3_intent.jsonl").exists()


# --- the AI draft for M3 (decision log 2026-11-12, WBS 9.7) ---------------------


def _m3_draft(sample: Sequence[annotate.Turn]) -> list[Doc]:
    """Every turn faithful, except the first: WRONG_TOOL with a note."""
    lines = [{"item_id": t.item_id, "faithful": True, "reason": None, "note": ""} for t in sample]
    lines[0] = {**lines[0], "faithful": False, "reason": "WRONG_TOOL", "note": "a check, not a hit"}
    return lines


def test_an_m3_draft_is_checked_against_the_sample(
    d_runs: tuple[Path, int, SnapshotClient],
) -> None:
    runs_dir, _, _ = d_runs
    sample = annotate.draw_sample(annotate.load_runs(runs_dir), rate=1.0)
    lines = _m3_draft(sample)
    draft = annotate.load_draft(lines, sample)
    assert set(draft) == {t.item_id for t in sample}
    assert draft[sample[0].item_id] == {
        "faithful": False,
        "reason": "WRONG_TOOL",
        "note": "a check, not a hit",
    }

    first = lines[0]
    for bad, message in [
        (lines[:-1], "no draft line"),
        ([*lines, first], "twice"),
        ([*lines, {**first, "item_id": "ffffffff"}], "not a sampled turn"),
        ([{**first, "reason": None}, *lines[1:]], "reason"),
        ([{**first, "reason": "WRONG"}, *lines[1:]], "reason"),
        ([{**first, "faithful": True}, *lines[1:]], "reason"),
        ([{**first, "faithful": "no"}, *lines[1:]], "faithful"),
    ]:
        with pytest.raises(annotate.DraftMismatch, match=message):
            annotate.load_draft(bad, sample)


def test_an_m3_draft_is_shown_and_accepted_or_edited(
    d_runs: tuple[Path, int, SnapshotClient], tmp_path: Path
) -> None:
    runs_dir, seed, _ = d_runs
    sample = annotate.draw_sample(annotate.load_runs(runs_dir), rate=1.0)
    draft_path = tmp_path / "draft.jsonl"
    draft_path.write_text(
        "".join(json.dumps(d) + "\n" for d in _m3_draft(sample)), encoding="utf-8"
    )
    # Accept the first turn's draft with Enter; edit the second to unfaithful, MISSED.
    keys = "\n" + "x\ne\nn\nmissed\nno call\n" + "q\n"
    result = _m3(tmp_path, runs_dir, [seed], keys, "--draft", str(draft_path))
    assert result.exit_code == 0, result.output
    assert "a check, not a hit" in result.output
    accepted, edited = _lines(tmp_path / "results" / "m3_intent.jsonl")
    assert accepted["run_id"] == sample[0].run_id and accepted["annotator"] == "CI"
    assert (accepted["faithful"], accepted["reason"], accepted["note"]) == (False, "WRONG_TOOL", "")
    assert accepted["review"] == "accepted"
    assert accepted["draft"] == {
        "faithful": False,
        "reason": "WRONG_TOOL",
        "note": "a check, not a hit",
    }
    assert (edited["faithful"], edited["reason"], edited["note"]) == (False, "MISSED", "no call")
    assert edited["review"] == "edited"
    assert edited["draft"] == {"faithful": True, "reason": None, "note": ""}


def test_m3_refuses_a_draft_that_does_not_fit(
    d_runs: tuple[Path, int, SnapshotClient], tmp_path: Path
) -> None:
    runs_dir, seed, _ = d_runs
    sample = annotate.draw_sample(annotate.load_runs(runs_dir), rate=1.0)
    draft_path = tmp_path / "draft.jsonl"
    draft_path.write_text(json.dumps(_m3_draft(sample)[0]) + "\n", encoding="utf-8")
    result = _m3(tmp_path, runs_dir, [seed], "", "--draft", str(draft_path))
    assert result.exit_code == 1 and "no draft line" in result.output
    assert not (tmp_path / "results" / "m3_intent.jsonl").exists()
