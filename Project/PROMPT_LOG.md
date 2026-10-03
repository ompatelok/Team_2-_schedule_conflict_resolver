# Prompt log: conflict-free scheduler

Paste the relevant parts into the Submission Template. Anything marked **FILL** must be your real result, taken from your own runs.

## Pipeline

1. **Extract** (`EXTRACT_SYSTEM`): free text to input JSON. Skipped when the input is already JSON.
2. **Input guardrail** (code, `validate_input`): bad input is rejected before the model is called.
3. **Schedule** (`SYSTEM_V3` + `USER_TEMPLATE`): the model returns the schedule as JSON.
4. **Proof** (code, `check_schedule`): every pair of events is compared in UTC; dependencies, fixed times, durations, the window and mandatory events are checked. An empty violation list is the programmatic proof of zero conflicts.
5. **Repair** (`REPAIR_TEMPLATE`): if step 4 finds violations, they are sent back to the model. Maximum 2 retries, then the app shows a clear failure message instead of a wrong schedule.

## Prompting techniques combined

| Technique | Where | Why |
|---|---|---|
| Explicit ordered rules with a fixed JSON schema | `RULES`, `OUTPUT_FULL` | The problem card asks for an explicit rule order. Numbered rules let every decision cite the rule that caused it, and a fixed schema lets code check the answer. |
| Few-shot examples | `FEW_SHOT` (3 examples) | Each one shows a behaviour that plain instructions do not reliably produce: a simple move, a time-zone and dependency case with a drop, and the impossible case. |
| Reason, then answer, then self-check | `HOW_TO_WORK`, keys `normalized` and `conflicts_found` | The model must write the UTC conversion and the list of conflicts before it writes the schedule, so the schedule is built on visible working that code can verify. |
| Prompt chaining with output validation | extract, schedule, checker, repair | Each prompt does one job. The repair prompt gets exact violations from code, so the model fixes a named problem instead of guessing. |

## Versions

| Version | What changed | Why | Pass rate | Commit time |
|---|---|---|---|---|
| V1 | Baseline: one paragraph plus the output shape | Reference point for the comparison | **FILL** /20 | **FILL** |
| V2 | Added the input spec, rules R1 to R7, impossible-case and status handling | V1 has no rule order, so decisions are not explainable or repeatable | **FILL** /20 | **FILL** |
| V3 | Added `normalized` and `conflicts_found` steps, self-check, 3 few-shot examples | Targets time-zone arithmetic, dependency order and the impossible case | **FILL** /20 | **FILL** |
| V3 + repair loop | Checker violations fed back, max 2 retries | Catches what the prompt alone still gets wrong | **FILL** /20 | **FILL** |
| V4 (yours) | **FILL**: the change you make after reading your own failures | **FILL** | **FILL** /20 | **FILL** |

## Metric

**Strict pass rate** = cases passed / 20, on `test_cases.json`. A case passes when:

- the output parses into the required JSON shape, and
- `status` equals the labelled `expected_status`, and
- for status `ok`: the checker finds zero violations and the dropped ids equal `expected_dropped`.

Run every version on the same 20 cases with the same model and settings (temperature 0 if the tool allows it).

## Why each design choice was made

- **R1, compare only in UTC, half-open intervals.** Local clock times mislead (T05 looks like a clash and is not, T06 looks clear and is a clash). Half-open intervals mean back-to-back meetings are legal.
- **R2 before everything else.** Hard constraints are what the checker proves, so the model must never trade them away for a "nicer" schedule.
- **R3, inherited priority.** A low-priority task that a mandatory event depends on is really as important as that event (T09).
- **R4, move before drop.** Moving costs someone a time change; dropping costs the whole event. So a high-priority movable event yields its slot to a low-priority fixed one when both can then happen (T04).
- **R5 and R6.** Priority decides only what R4 leaves open. The tie-break makes equal-priority cases repeatable (T11).
- **R7, earliest slot at or after the original start.** One deterministic placement rule, so the same input gives the same schedule.
- **Infeasible is a status, not an error.** The model is told not to bend a rule; it names the blocking events and suggests the smallest change (T13 to T15).
- **`<input>` tags and "this is data".** Stops instructions hidden in an event title from being followed (T19).
- **Output in UTC only.** The app converts to local time for display, so the model does one conversion per event, and code checks that conversion.
- **Extraction never invents a time.** Missing information becomes an error or a listed assumption that the user can see.

## Target users and requirements

**Users:** people who coordinate meetings across teams and time zones, such as project coordinators, team leads and assistants. They need a schedule they can act on and a reason they can repeat to whoever was moved or dropped.

**Requirements taken from the problem card:**

| Requirement | Where it is met |
|---|---|
| Conflict-free schedule with reasons | `schedule` and `dropped`, each entry with `rule` and `reason` |
| Explicit rule order | R1 to R7 in the prompt, cited per decision |
| Trade-off explanation | `trade_offs`: what was given up, what it bought, one rejected alternative |
| Impossible case handled gracefully | status `infeasible` with blocking events and suggestions (T13 to T15) |
| Dependencies, time zones, priorities | R3, R1, R5 (T05 to T09, T12) |
| Programmatic proof of zero conflicts | `check_schedule` in code, run on every answer |

## Known limitations

- The checker proves that an `ok` schedule breaks no rule. It cannot prove that an `infeasible` verdict is correct, or that the schedule keeps the largest possible number of events.
- The rules are deterministic, not optimal. R7 never moves an event earlier than its original start, so a few inputs that a human could solve by moving something earlier end with a drop.
- One window and one shared calendar. No recurring events, travel or buffer time, or per-person availability.
- Time-zone arithmetic by the model is error-prone. The checker and repair loop catch it, but each retry costs time.
- Free-text extraction can misread ambiguous input. "IST" is read as India time, though it can also mean Irish or Israel time; defaults are listed in `assumptions` for the user to check.
- The test set is 20 cases that we wrote ourselves, so the pass rate describes these cases, not every possible input.

## Contribution row for the prompt owner (keep only what you actually did)

Designed rule order R1 to R7 and the output schema; wrote system prompt V1, V2, V3, the extraction prompt and the repair prompt; built the 3 few-shot examples; labelled the 20-case test set; ran each version on it and recorded pass rates; logged failures and wrote fix V4.

## Failure log (fill in from your real runs)

| Time | Version | Case | What went wrong | Fix | Re-test |
|---|---|---|---|---|---|
| **FILL** | | | | | |

Likely places to look first, to be confirmed by your runs: time-zone cases T05, T06, T12; dependency cases T07 to T09; R4 in T04; the three infeasible cases.

## Side-by-side for the demo

Run V1 and V3 on the same input and show both outputs with the checker's verdict under each. Pick a case from your own results where V1 failed and V3 passed.

## Live-modification drills (the panel may ask for one)

- Change R6 so the shorter event keeps the slot, then re-run T11.
- Flip the priority scale so 1 is highest (edit `INPUT_SPEC`), then re-run T03 and expect `a` to be dropped instead of `b`.
- Remove R4, then re-run T04 and watch the dentist get dropped.
- Remove the few-shot examples from V3, then re-run T13 to T15.
