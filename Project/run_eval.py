"""Test a prompt version against test_cases.json.

  python run_eval.py V1                 all 20 cases with prompt V1
  python run_eval.py V3 T06 T12         only these cases
  python run_eval.py V3 --repair        with the repair loop (max 2 retries)
  python run_eval.py V3 --no-guard      skip the code input check, so the model must catch bad input itself
  python run_eval.py show T06           print the exact user message for a case (to paste into a chat tool)
  python run_eval.py check T06 out.txt  score an answer you copied from a chat tool into out.txt

Every run is saved with its raw model outputs in runs/, which is your evidence for the failure log.
"""
import json
import sys
import time
from pathlib import Path

from checker import check_schedule, parse_output, score_case, validate_input
from prompts import (EXTRACT_SYSTEM, EXTRACT_USER_TEMPLATE, REPAIR_TEMPLATE, USER_TEMPLATE, VERSIONS)

CASES = {c["id"]: c for c in json.load(open(Path(__file__).with_name("test_cases.json")))}


def call_model(system, messages):
    """Send a system prompt and a list of {"role": "user"|"assistant", "content": str}; return the reply text.
    FILL THIS IN for the model your team is permitted to use. Use temperature 0 if the API allows it."""
    raise NotImplementedError("Fill in call_model() in run_eval.py for your permitted model.")


def stop(status, reason):
    return {"status": status, "schedule": [], "dropped": [], "trade_offs": "",
            "problem": {"rule": "guardrail", "ids": [], "reason": reason, "suggestions": []}}


def violations(data, out):
    try:
        return check_schedule(data, out)
    except Exception as ex:  # malformed input reached the checker (only possible with --no-guard)
        return [f"checker could not run: {ex!r}"]


def run_case(case, system, repair=False, guard=True):
    """Returns (input_data, output_dict_or_None, trace). trace holds every raw model reply."""
    trace, data = [], case.get("input")
    if data is None:  # free text goes through the extraction prompt first
        raw = call_model(EXTRACT_SYSTEM, [{"role": "user", "content": EXTRACT_USER_TEMPLATE.format(text=case["input_text"])}])
        trace.append({"step": "extract", "raw": raw})
        try:
            data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        except ValueError:
            return None, stop("invalid_input", "could not read the events from the text"), trace
        if "error" in data:
            return None, stop("off_topic" if data["error"] == "off_topic" else "invalid_input", data["error"]), trace
    if guard:
        errs = validate_input(data)
        if errs:
            return data, stop("invalid_input", "; ".join(errs)), trace

    messages = [{"role": "user", "content": USER_TEMPLATE.format(input_json=json.dumps(data))}]
    out = None
    for attempt in range(3 if repair else 1):
        raw = call_model(system, messages)
        trace.append({"step": f"schedule attempt {attempt + 1}", "raw": raw})
        out = parse_output(raw)
        problems = ["the reply was not the required JSON object"] if out is None else violations(data, out)
        if not problems:
            break
        trace[-1]["violations"] = problems
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": REPAIR_TEMPLATE.format(violations="\n".join("- " + p for p in problems))}]
    return data, out, trace


def explain(case, out, data):
    """One line saying why a case failed."""
    if out is None:
        return "output was not valid JSON in the required shape"
    if out.get("status") != case["expected_status"]:
        return f"status was '{out.get('status')}', expected '{case['expected_status']}'"
    v = violations(data, out)
    if v:
        return "; ".join(v)
    got = sorted(d["id"] for d in out["dropped"])
    return f"dropped {got}, expected {sorted(case['expected_dropped'])}"


def main(argv):
    if not argv:
        sys.exit(__doc__)
    if argv[0] == "show":
        c = CASES[argv[1]]
        print(USER_TEMPLATE.format(input_json=json.dumps(c["input"], indent=1)) if "input" in c
              else EXTRACT_USER_TEMPLATE.format(text=c["input_text"]))
        return
    if argv[0] == "check":
        c, out = CASES[argv[1]], parse_output(open(argv[2], encoding="utf-8").read())
        ok = score_case(c, out)
        print(argv[1], "PASS" if ok else "FAIL: " + explain(c, out, c.get("input")))
        return

    version = argv[0]
    flags = {a for a in argv[1:] if a.startswith("--")}
    ids = [a for a in argv[1:] if not a.startswith("--")] or list(CASES)
    results, log = {}, []
    for cid in ids:
        c = CASES[cid]
        data, out, trace = run_case(c, VERSIONS[version], repair="--repair" in flags, guard="--no-guard" not in flags)
        results[cid] = score_case(c, out, data)
        why = "" if results[cid] else explain(c, out, data)
        print(f"{cid} {'PASS' if results[cid] else 'FAIL'}  {c['tests']}" + (f"\n      -> {why}" if why else ""))
        log.append({"id": cid, "pass": results[cid], "why": why, "trace": trace, "output": out})
    passed = sum(results.values())
    print(f"\n{version}{' ' + ' '.join(sorted(flags)) if flags else ''}: {passed}/{len(results)} passed ({passed / len(results):.0%})")
    Path("runs").mkdir(exist_ok=True)
    path = Path("runs") / f"{version}_{time.strftime('%H%M%S')}.json"
    json.dump({"version": version, "flags": sorted(flags), "passed": passed, "total": len(results), "cases": log},
              open(path, "w"), indent=1)
    print("saved", path)


if __name__ == "__main__":
    main(sys.argv[1:])
