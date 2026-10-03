"""Code-side checks for the scheduler.

  validate_input(data)       -> list of problems   (app guardrail, run BEFORE calling the model)
  parse_output(text)         -> dict or None       (app guardrail for invalid model output)
  check_schedule(data, out)  -> list of violations (empty list = zero conflicts, proven by code)
  score_case(case, out)      -> True / False       (one test case)
  run_eval(pipeline, cases)  -> (pass_rate, per-case results)

The violation strings are written so they can be pasted straight into REPAIR_TEMPLATE.
Run `python checker.py` to self-test the few-shot examples.
On Windows, zoneinfo needs: pip install tzdata
"""
import json
from datetime import datetime, timezone
from itertools import combinations
from zoneinfo import ZoneInfo

FMT = "%Y-%m-%dT%H:%M"
STATUSES = {"ok", "infeasible", "invalid_input", "off_topic"}
OUTPUT_KEYS = {"status", "schedule", "dropped", "trade_offs", "problem"}
EVENT_FIELDS = {"id": str, "title": str, "start": str, "end": str, "tz": str,
                "priority": int, "fixed": bool, "mandatory": bool, "depends_on": list}


def to_utc(local, tz):
    return datetime.strptime(local, FMT).replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


def from_z(s):
    return datetime.strptime(s, FMT + "Z").replace(tzinfo=timezone.utc)


def z(dt):
    return dt.strftime(FMT + "Z")


def validate_input(data):
    """Problems with the input itself. Non-empty list -> show 'invalid_input' and do not call the model."""
    if not isinstance(data, dict) or not isinstance(data.get("events"), list) or not data["events"]:
        return ["input must be an object with a non-empty 'events' list"]
    errs = []
    try:
        w = data["window"]
        if not to_utc(w["start"], w["tz"]) < to_utc(w["end"], w["tz"]):
            errs.append("window: end must be after start")
    except Exception:
        errs.append("window: needs start, end (YYYY-MM-DDTHH:MM) and a valid IANA tz")
    ids = [e.get("id") for e in data["events"] if isinstance(e, dict)]
    for e in data["events"]:
        if not isinstance(e, dict):
            errs.append("each event must be an object")
            continue
        eid = e.get("id", "?")
        bad = [k for k, t in EVENT_FIELDS.items() if type(e.get(k)) is not t]
        if bad:
            errs.append(f"{eid}: missing or wrong type: {', '.join(bad)}")
            continue
        try:
            if not to_utc(e["start"], e["tz"]) < to_utc(e["end"], e["tz"]):
                errs.append(f"{eid}: end must be after start")
        except Exception:
            errs.append(f"{eid}: start/end must be YYYY-MM-DDTHH:MM and tz a valid IANA time zone")
        if not 1 <= e["priority"] <= 5:
            errs.append(f"{eid}: priority must be 1 to 5")
        if ids.count(eid) > 1:
            errs.append(f"{eid}: duplicate id")
        for d in e["depends_on"]:
            if d not in ids or d == eid:
                errs.append(f"{eid}: depends_on names an unknown id or itself: {d}")
    return errs


def parse_output(text):
    """Model text -> dict, or None if it is not the JSON shape we asked for."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        out = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        return None
    if not OUTPUT_KEYS <= set(out) or out["status"] not in STATUSES:
        return None
    if not isinstance(out["schedule"], list) or not isinstance(out["dropped"], list):
        return None
    return out


def check_schedule(data, out):
    """Violations of the hard rules. For status 'ok', an empty list = proven conflict-free."""
    ev = {e["id"]: e for e in data["events"]}
    orig = {i: (to_utc(e["start"], e["tz"]), to_utc(e["end"], e["tz"])) for i, e in ev.items()}
    w0 = to_utc(data["window"]["start"], data["window"]["tz"])
    w1 = to_utc(data["window"]["end"], data["window"]["tz"])
    if out.get("status") != "ok":  # nothing is scheduled; only the UTC working can be checked
        return _check_utc(orig, out)
    try:
        slot = {s["id"]: (from_z(s["start_utc"]), from_z(s["end_utc"])) for s in out["schedule"]}
        action = {s["id"]: s.get("action") for s in out["schedule"]}
        dropped = {d["id"] for d in out["dropped"]}
    except (KeyError, TypeError, ValueError) as ex:
        return [f"malformed output: {ex!r}"]

    v = []
    if len(slot) != len(out["schedule"]):
        v.append("an id appears more than once in schedule")
    for i in (set(slot) | dropped) - set(ev):
        v.append(f"{i}: not an event in the input")
    for i in ev:
        if (i in slot) == (i in dropped):
            v.append(f"{i}: must appear exactly once, either in schedule or in dropped")

    for i, (s, e) in slot.items():
        if i not in ev:
            continue
        o_s, o_e = orig[i]
        if e - s != o_e - o_s:
            v.append(f"{i}: duration changed (R2)")
        if ev[i]["fixed"] and s != o_s:
            v.append(f"{i}: is fixed but was moved from {z(o_s)} to {z(s)} (R2)")
        if s < o_s:
            v.append(f"{i}: moved earlier than its original start {z(o_s)} (R7)")
        if s < w0 or e > w1:
            v.append(f"{i}: lies outside the window {z(w0)} to {z(w1)} (R2)")
        if (action[i] == "moved") != (s != o_s):
            v.append(f"{i}: action says '{action[i]}' but the times say otherwise")
        for d in ev[i]["depends_on"]:
            if d not in slot:
                v.append(f"{i}: depends on {d}, which is not scheduled, so {i} must be dropped too (R3)")
            elif slot[d][1] > s:
                v.append(f"{i}: starts {z(s)}, before its dependency {d} ends {z(slot[d][1])} (R3)")

    for i in dropped:
        if i in ev and ev[i]["mandatory"]:
            v.append(f"{i}: is mandatory and cannot be dropped (R2)")

    for (a, (s1, e1)), (b, (s2, e2)) in combinations(sorted(slot.items(), key=lambda kv: kv[1]), 2):
        if s1 < e2 and s2 < e1:
            v.append(f"{a} and {b} overlap from {z(max(s1, s2))} to {z(min(e1, e2))} (R2)")

    return v + _check_utc(orig, out)


def _check_utc(orig, out):
    v = []
    for n in out.get("normalized") or []:
        i = n.get("id")
        if i in orig and (n.get("start_utc"), n.get("end_utc")) != (z(orig[i][0]), z(orig[i][1])):
            v.append(f"{i}: wrong UTC conversion, the correct value is {z(orig[i][0])} to {z(orig[i][1])} (R1)")
    return v


def score_case(case, out, data=None):
    """Pass = right status, and for 'ok': zero violations and exactly the expected events dropped."""
    data = data or case.get("input")
    if not isinstance(out, dict) or out.get("status") != case["expected_status"]:
        return False
    if out["status"] != "ok":
        return True
    return not check_schedule(data, out) and {d["id"] for d in out["dropped"]} == set(case["expected_dropped"])


def run_eval(pipeline, cases):
    """pipeline(case) -> (input_data_or_None, output_dict_or_None). Returns (pass_rate, {case_id: bool})."""
    results = {}
    for c in cases:
        data, out = pipeline(c)
        results[c["id"]] = score_case(c, out, data)
    return sum(results.values()) / len(results), results


if __name__ == "__main__":
    from prompts import FEW_SHOT
    for n, (inp, out) in enumerate(FEW_SHOT, 1):
        assert not validate_input(inp), validate_input(inp)
        problems = check_schedule(inp, out)
        print(f"few-shot example {n}: {'OK' if not problems else problems}")
