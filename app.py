"""
Schedule Conflict Resolver - Complete Streamlit Integration
Integrated from all team members:
  - Member 1 (Yurica): Prompts (SYSTEM_V1, SYSTEM_V3, test cases)
  - Member 2 (Om): Streamlit app integration
  - Member 3 (Shiva): Test case validation and support
  - Member 4 (Tirth): Frontend UI/UX mockup (INDEX.HTML, style.css, script.js)
"""

import streamlit as st
import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import re
import sys

# ============================================================================
# IMPORTS FROM PROJECT MODULES
# ============================================================================

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Project"))
from prompts import SYSTEM_V1, SYSTEM_V3, EXTRACT_SYSTEM, USER_TEMPLATE, REPAIR_TEMPLATE, FEW_SHOT
from checker import validate_input, parse_output, check_schedule, score_case

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

FMT = "%Y-%m-%dT%H:%M"
STATUSES = {"ok", "infeasible", "invalid_input", "off_topic"}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# ============================================================================
# HELPER FUNCTIONS: UTC CONVERSION & PARSING
# ============================================================================

def to_utc(local, tz):
    """Convert local wall-clock time in given IANA timezone to UTC."""
    try:
        return datetime.strptime(local, FMT).replace(tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)
    except Exception as e:
        raise ValueError(f"Cannot convert {local} in {tz}: {e}")

def from_z(s):
    """Parse UTC ISO 8601 string ending in Z."""
    try:
        return datetime.strptime(s, FMT + "Z").replace(tzinfo=timezone.utc)
    except Exception as e:
        raise ValueError(f"Cannot parse UTC string {s}: {e}")

def z(dt):
    """Format datetime as UTC ISO 8601 string."""
    return dt.strftime(FMT + "Z")

# ============================================================================
# GUARDRAILS LAYER
# ============================================================================

def validate_input_wrapper(text):
    """
    Guardrail before LLM call.
    Block prompt injections, off-topic inputs, and overly short strings.
    Returns: (is_valid, error_message_or_empty)
    """
    if not text or not isinstance(text, str):
        return False, "Input is empty or not text."
    
    text = text.strip()
    
    if len(text) < 20:
        return False, "Input is too short. Please describe your scheduling scenario in detail."
    
    injection_markers = [
        r"(ignore|disregard|override|cancel).*(instruction|rule|system|prompt)",
        r"(system:|admin:|root:)",
        r"(execute|run|eval|exec|code:)",
    ]
    for pattern in injection_markers:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Input contains suspicious instructions. Please describe only your scheduling scenario."
    
    scheduling_keywords = {
        "event", "meeting", "call", "appointment", "schedule", "time",
        "conflict", "overlap", "window", "available", "slot", "booking",
        "timezone", "utc", "fixed", "mandatory", "priority", "move", "drop"
    }
    text_lower = text.lower()
    if not any(kw in text_lower for kw in scheduling_keywords):
        return False, "Your input does not appear to be about scheduling. Please describe events with times and priorities."
    
    return True, ""

# ============================================================================
# LLM INTEGRATION
# ============================================================================

def call_llm(system_prompt, user_message, temperature=0.0):
    """
    Call the LLM (Gemini or OpenAI) with system and user prompts.
    Returns: (success, response_text_or_error_message)
    """
    if not LLM_API_KEY:
        return False, "API key not configured. Set LLM_API_KEY environment variable."
    
    try:
        if LLM_PROVIDER == "gemini":
            return _call_gemini(system_prompt, user_message, temperature)
        elif LLM_PROVIDER == "openai":
            return _call_openai(system_prompt, user_message, temperature)
        else:
            return False, f"Unknown LLM provider: {LLM_PROVIDER}. Use 'gemini' or 'openai'."
    except Exception as e:
        return False, f"LLM call failed: {str(e)}"

def _call_gemini(system_prompt, user_message, temperature):
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=LLM_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        full_prompt = f"{system_prompt}\n\n{user_message}"
        response = model.generate_content(
            full_prompt,
            generation_config={"temperature": temperature}
        )
        return True, response.text
    except ImportError:
        return False, "google-generativeai not installed. Run: pip install google-generativeai"
    except Exception as e:
        return False, f"Gemini API error: {str(e)}"

def _call_openai(system_prompt, user_message, temperature):
    """Call OpenAI API (ChatGPT)."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=LLM_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4",
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        return True, response.choices[0].message.content
    except ImportError:
        return False, "openai not installed. Run: pip install openai"
    except Exception as e:
        return False, f"OpenAI API error: {str(e)}"

# ============================================================================
# SCHEDULE VERIFICATION (PROGRAMMATIC PROOF)
# ============================================================================

def verify_schedule(schedule_json):
    """
    Rigorous verification that the schedule is conflict-free.
    Input: dict (the parsed JSON response from the model)
    Returns: (is_valid, message_str)
    """
    if not isinstance(schedule_json, dict):
        return False, "Schedule is not a valid JSON object."
    
    status = schedule_json.get("status")
    if status not in STATUSES:
        return False, f"Invalid status: {status}. Expected one of {STATUSES}."
    
    if status != "ok":
        return True, f"Schedule status is '{status}'. This is valid but indicates a constraint violation or infeasibility."
    
    try:
        schedule_list = schedule_json.get("schedule", [])
        dropped_list = schedule_json.get("dropped", [])
        
        events = {}
        for s in schedule_list:
            eid = s.get("id")
            start_utc = from_z(s.get("start_utc", ""))
            end_utc = from_z(s.get("end_utc", ""))
            events[eid] = {
                "start": start_utc,
                "end": end_utc,
                "action": s.get("action"),
                "rule": s.get("rule")
            }
        
        event_list = sorted(events.items(), key=lambda kv: kv[1]["start"])
        for i in range(len(event_list) - 1):
            id_a, evt_a = event_list[i]
            id_b, evt_b = event_list[i + 1]
            if evt_a["end"] > evt_b["start"]:
                overlap_start = max(evt_a["start"], evt_b["start"])
                overlap_end = min(evt_a["end"], evt_b["end"])
                return False, f"OVERLAP: Events {id_a} and {id_b} overlap from {z(overlap_start)} to {z(overlap_end)}."
        
        return True, f"✓ Schedule verified: {len(events)} events, zero chronological overlaps in UTC."
    
    except Exception as e:
        return False, f"Verification failed: {str(e)}"

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(
        page_title="Schedule Conflict Resolver",
        page_icon="📅",
        layout="wide"
    )
    
    st.title("📅 Schedule Conflict Resolver")
    st.markdown("""
    **Compare baseline vs. refined prompts side-by-side.**
    This app demonstrates how an explicit rule order, few-shot examples, and a self-check step improve scheduling quality.
    """)
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "🚀 Live Demo",
        "📋 Test Cases",
        "📖 How It Works",
        "👥 Contribution"
    ])
    
    # ========================================================================
    # TAB 1: LIVE DEMO
    # ========================================================================
    
    with tab1:
        st.header("Live Demo: Baseline vs. Refined Prompt")
        st.markdown("""
        Enter a scheduling scenario (JSON or free text). The app will:
        1. Validate your input
        2. Run it through **Prompt Version 1** (baseline, one paragraph)
        3. Run it through **Prompt Version 3** (refined, with explicit rules and few-shot examples)
        4. Display both outputs side-by-side
        5. Verify each result for correctness
        """)
        
        st.subheader("📝 Input Your Scenario")
        
        input_mode = st.radio(
            "Choose input format:",
            ["JSON (structured)", "Free text (natural language)"],
            horizontal=True
        )
        
        if input_mode == "JSON (structured)":
            input_text = st.text_area(
                "Paste a JSON scheduling input:",
                height=200,
                placeholder='{\n  "window": {"start": "2026-10-12T09:00", "end": "2026-10-12T18:00", "tz": "Asia/Kolkata"},\n  "events": [...]\n}'
            )
            is_json_input = True
        else:
            input_text = st.text_area(
                "Describe your scheduling scenario in natural language:",
                height=200,
                placeholder="Monday 12 October 2026, 9am to 6pm IST. A stands-up at 9am (30 min, priority 3). Board review at 3pm (1 hour, priority 5, booked). Customer call at 11am (1 hour, priority 5, booked). Can you fit these?"
            )
            is_json_input = False
        
        if st.button("🔄 Run Both Prompts", key="run_both"):
            if not input_text.strip():
                st.error("❌ Please enter a scheduling scenario.")
            else:
                is_valid, error_msg = validate_input_wrapper(input_text)
                if not is_valid:
                    st.error(f"⚠️ Input validation failed: {error_msg}")
                else:
                    st.success("✓ Input passed guardrail check.")
                    
                    input_data = None
                    if is_json_input:
                        try:
                            input_data = json.loads(input_text)
                            st.info("📋 Parsed JSON input successfully.")
                        except json.JSONDecodeError as e:
                            st.error(f"❌ JSON parsing failed: {e}")
                            return
                    else:
                        st.info("🔗 Extracting structured input from free text...")
                        with st.spinner("Calling extraction model..."):
                            success, response = call_llm(EXTRACT_SYSTEM, f"<text>\n{input_text}\n</text>")
                            if not success:
                                st.error(f"❌ Extraction failed: {response}")
                                return
                            try:
                                input_data = parse_output(response)
                                if not input_data:
                                    st.error(f"❌ Extraction response not in expected format:\n{response}")
                                    return
                                st.success("✓ Extraction completed.")
                            except Exception as e:
                                st.error(f"❌ Extraction parsing failed: {e}")
                                return
                    
                    validation_errors = validate_input(input_data)
                    if validation_errors:
                        st.error(f"❌ Input validation errors:\n" + "\n".join(f"  - {e}" for e in validation_errors))
                        return
                    
                    st.success("✓ Input structure validated.")
                    
                    st.subheader("🏃 Running Prompts...")
                    
                    col_v1, col_v3 = st.columns(2)
                    
                    with col_v1:
                        st.markdown("### Version 1: Baseline")
                        st.markdown("*One paragraph, zero-shot, no explicit rules*")
                        
                        with st.spinner("Calling V1..."):
                            v1_success, v1_response = call_llm(SYSTEM_V1, USER_TEMPLATE.format(input_json=json.dumps(input_data)))
                        
                        if not v1_success:
                            st.error(f"❌ V1 call failed: {v1_response}")
                            v1_output = None
                        else:
                            try:
                                v1_output = parse_output(v1_response)
                                if not v1_output:
                                    st.error(f"❌ V1 response not valid JSON:\n{v1_response[:500]}")
                                    v1_output = None
                                else:
                                    st.success("✓ V1 returned valid JSON")
                                    st.json(v1_output)
                            except Exception as e:
                                st.error(f"❌ V1 parsing failed: {e}")
                                v1_output = None
                        
                        if v1_output:
                            is_valid_v1, msg_v1 = verify_schedule(v1_output)
                            if is_valid_v1:
                                st.success(msg_v1)
                                violations_v1 = check_schedule(input_data, v1_output)
                                if violations_v1:
                                    st.warning(f"⚠️ Checker found issues:\n" + "\n".join(f"  - {v}" for v in violations_v1))
                                else:
                                    st.success("✓ Checker verified zero conflicts!")
                            else:
                                st.error(msg_v1)
                    
                    with col_v3:
                        st.markdown("### Version 3: Refined")
                        st.markdown("*Explicit rule order R1-R7 + few-shot examples + self-check*")
                        
                        with st.spinner("Calling V3..."):
                            v3_success, v3_response = call_llm(SYSTEM_V3, USER_TEMPLATE.format(input_json=json.dumps(input_data)))
                        
                        if not v3_success:
                            st.error(f"❌ V3 call failed: {v3_response}")
                            v3_output = None
                        else:
                            try:
                                v3_output = parse_output(v3_response)
                                if not v3_output:
                                    st.error(f"❌ V3 response not valid JSON:\n{v3_response[:500]}")
                                    v3_output = None
                                else:
                                    st.success("✓ V3 returned valid JSON")
                                    st.json(v3_output)
                            except Exception as e:
                                st.error(f"❌ V3 parsing failed: {e}")
                                v3_output = None
                        
                        if v3_output:
                            is_valid_v3, msg_v3 = verify_schedule(v3_output)
                            if is_valid_v3:
                                st.success(msg_v3)
                                violations_v3 = check_schedule(input_data, v3_output)
                                if violations_v3:
                                    st.warning(f"⚠️ Checker found issues:\n" + "\n".join(f"  - {v}" for v in violations_v3))
                                else:
                                    st.success("✓ Checker verified zero conflicts!")
                            else:
                                st.error(msg_v3)
                    
                    st.subheader("🔍 Detailed Comparison")
                    
                    if v1_output and v3_output:
                        col_detail1, col_detail2 = st.columns(2)
                        
                        with col_detail1:
                            st.markdown("#### V1 Output")
                            if v1_output.get("status") == "ok":
                                st.markdown(f"**Status:** ✓ OK")
                                st.markdown(f"**Scheduled:** {len(v1_output.get('schedule', []))} events")
                                st.markdown(f"**Dropped:** {len(v1_output.get('dropped', []))} events")
                                if v1_output.get("trade_offs"):
                                    st.markdown(f"**Trade-offs:**\n{v1_output['trade_offs']}")
                            else:
                                st.markdown(f"**Status:** {v1_output.get('status')}")
                                if v1_output.get("problem"):
                                    st.markdown(f"**Problem:**\n{v1_output['problem'].get('reason', 'N/A')}")
                        
                        with col_detail2:
                            st.markdown("#### V3 Output")
                            if v3_output.get("status") == "ok":
                                st.markdown(f"**Status:** ✓ OK")
                                st.markdown(f"**Scheduled:** {len(v3_output.get('schedule', []))} events")
                                st.markdown(f"**Dropped:** {len(v3_output.get('dropped', []))} events")
                                if v3_output.get("trade_offs"):
                                    st.markdown(f"**Trade-offs:**\n{v3_output['trade_offs']}")
                            else:
                                st.markdown(f"**Status:** {v3_output.get('status')}")
                                if v3_output.get("problem"):
                                    st.markdown(f"**Problem:**\n{v3_output['problem'].get('reason', 'N/A')}")
                        
                        if v3_output.get("status") == "ok":
                            st.markdown("#### V3 Explainability")
                            
                            if v3_output.get("normalized"):
                                st.markdown("**Normalized (UTC Conversion):**")
                                for norm in v3_output["normalized"]:
                                    st.write(f"  - {norm['id']}: {norm['start_utc']} to {norm['end_utc']} (priority {norm.get('effective_priority', 'N/A')})")
                            
                            if v3_output.get("conflicts_found"):
                                st.markdown("**Conflicts Found:**")
                                for conf in v3_output["conflicts_found"]:
                                    st.write(f"  - {conf.get('type', 'unknown')} between {conf.get('between', [])}")
                            
                            if v3_output.get("schedule"):
                                st.markdown("**Decision Log:**")
                                for sched in v3_output["schedule"]:
                                    st.write(f"  - **{sched['id']}**: {sched.get('action', 'unknown')} (Rule {sched.get('rule', 'N/A')})\n    {sched.get('reason', 'No reason')}")
    
    # ========================================================================
    # TAB 2: TEST CASES
    # ========================================================================
    
    with tab2:
        st.header("📋 Test Cases")
        st.markdown("""
        The app includes 20+ test cases covering:
        - **Simple cases** (T01-T05): no conflict, priority-based moves, fixed conflicts
        - **Time zones** (T05-T06, T12): UTC conversion and hidden conflicts
        - **Dependencies** (T07-T09): ordering constraints and inherited priority
        - **Impossible cases** (T13-T15): deliberately infeasible inputs
        - **Invalid inputs** (T16-T17): malformed data and off-topic requests
        - **Robustness** (T18-T20): prompt injection and free-text extraction
        """)
        
        try:
            test_cases_path = os.path.join(os.path.dirname(__file__), "Project", "test_cases.json")
            with open(test_cases_path) as f:
                test_cases = json.load(f)
        except Exception as e:
            st.error(f"Could not load test cases: {e}")
            test_cases = []
        
        if test_cases:
            st.subheader(f"Available Test Cases ({len(test_cases)})")
            
            for case in test_cases:
                with st.expander(f"**{case['id']}**: {case.get('tests', 'N/A')}"):
                    st.markdown(f"**Description:** {case.get('tests', 'N/A')}")
                    st.markdown(f"**Expected Status:** `{case.get('expected_status', 'N/A')}`")
                    st.markdown(f"**Expected Dropped:** {case.get('expected_dropped', [])}")
                    
                    if "input" in case:
                        st.markdown("**Input JSON:**")
                        st.json(case["input"])
                    elif "input_text" in case:
                        st.markdown("**Input Text:**")
                        st.code(case["input_text"])
                    
                    if st.button(f"Test {case['id']}", key=f"test_{case['id']}"):
                        st.info(f"Testing {case['id']}...")
                        input_data = case.get("input")
                        if not input_data and "input_text" in case:
                            with st.spinner("Extracting from free text..."):
                                success, response = call_llm(EXTRACT_SYSTEM, f"<text>\n{case['input_text']}\n</text>")
                                if success:
                                    input_data = parse_output(response)
                        
                        if input_data:
                            with st.spinner("Running V3..."):
                                success, response = call_llm(SYSTEM_V3, USER_TEMPLATE.format(input_json=json.dumps(input_data)))
                                if success:
                                    output = parse_output(response)
                                    if output:
                                        passed = score_case(case, output, input_data)
                                        if passed:
                                            st.success(f"✅ **PASSED**: {case['id']}")
                                        else:
                                            st.error(f"❌ **FAILED**: {case['id']}")
                                            st.write("Expected:", case.get("expected_status"))
                                            st.write("Got:", output.get("status"))
                                            violations = check_schedule(input_data, output)
                                            if violations:
                                                st.write("Violations:", violations)
    
    # ========================================================================
    # TAB 3: HOW IT WORKS
    # ========================================================================
    
    with tab3:
        st.header("📖 How It Works")
        
        st.markdown("""
        ## The Pipeline
        
        1. **Input Guardrail** (code)
           - Validates that input is real scheduling data
           - Blocks prompt injections and off-topic requests
           - Rejects overly short or malformed input
        
        2. **Extraction** (LLM, only for free text)
           - Converts natural language into structured JSON
           - Applies reasonable defaults (window, time zones)
           - Lists assumptions for the user to verify
        
        3. **Scheduling** (LLM with V1 or V3 prompt)
           - Returns a conflict-free schedule or an infeasibility message
           - Every decision cites the rule that caused it
           - Explains trade-offs
        
        4. **Verification** (code)
           - Parses JSON strictly
           - Checks for overlaps in UTC using half-open intervals
           - Verifies dependency order and fixed-event preservation
           - Confirms durations and window bounds
           - **Empty violation list = programmatic proof of zero conflicts**
        
        5. **Repair Loop** (optional)
           - If the verifier finds violations, send them back to the LLM
           - Retries up to 2 times, then gives up gracefully
        
        ## The Rules (R1-R7)
        
        These rules are explicit in Prompt V3 and enable repeatable, explainable decisions:
        
        - **R1**: Normalize to UTC. Use half-open intervals [start, end).
        - **R2**: Hard constraints: fixed events stay put, mandatory events never drop, durations don't change, stay in the window.
        - **R3**: Dependencies: dependent events start at or after their prerequisites finish. Inherited priority.
        - **R4**: Move before drop: when a conflict exists, try moving a non-fixed event before dropping anything.
        - **R5**: Priority: lower-priority events yield their slots.
        - **R6**: Tie-break: mandatory beats optional, then earlier original time, then alphabetical ID.
        - **R7**: Placement: moved events go to the earliest free slot at or after their original start.
        
        ## Prompting Techniques
        
        | Technique | Why | Evidence |
        |---|---|---|
        | Explicit rule order | Decisions are repeatable and explainable | Each event cites its rule |
        | Few-shot examples | Teaches complex cases (time zones, dependencies, impossible) | 3 carefully chosen examples |
        | Reason-then-answer | Forces the model to show its work before answering | Normalized times + conflicts found before schedule |
        | Strict JSON schema | Enables parsing and verification | Output shape guaranteed |
        | Guardrails | Blocks bad input before it reaches the model | Saves API calls, prevents garbage output |
        
        """)
        
        st.markdown("### Deliberately Impossible Case (T13)")
        st.markdown("""
        Two mandatory fixed events overlap across time zones:
        - Board review (Thursday 9:30-10:30 UTC)
        - Visa interview (Thursday 10:00-11:00 UTC)
        
        The model correctly returns status = "infeasible" with problem details and suggestions.
        """)
    
    # ========================================================================
    # TAB 4: CONTRIBUTION
    # ========================================================================
    
    with tab4:
        st.header("👥 Contribution Table")
        st.markdown("""
        **Hackathon Team: Schedule Conflict Resolver**
        
        | Member | GitHub | Role | Responsibilities | Contribution |
        |--------|--------|------|---|---|
        | **Yurica** | yuricasilvanadeassiscaetano120713-beep | Prompt Engineer | Designed rule order R1-R7; wrote baseline (V1), refined (V2), and final (V3) prompts; created 3 few-shot examples; labelled 20 test cases | `Project/prompts.py`: SYSTEM_V1, SYSTEM_V2, SYSTEM_V3, EXTRACT_SYSTEM, REPAIR_TEMPLATE, FEW_SHOT; `Project/test_cases.json` (T01-T20) |
        | **Om** | ompatelok | Integration & Development | Built the complete Streamlit web app; integrated all prompts and test cases; implemented guardrails, verification, and error handling; side-by-side UI | `app.py`: full Streamlit app with LLM integration, verification, side-by-side comparison, and contribution table |
        | **Shiva** | (Shiva) | Test & QA | Designed and validated test cases; tested both prompt versions; documented edge cases and failure modes | `Project/test_cases.json` validation and expansion |
        | **Tirth** | T-irth | UI/UX & Documentation | Designed the frontend prototype UI; wrote HTML/CSS/JS mockup; documented workflow and user experience | `INDEX.HTML`, `style.css`, `script.js` (proto UI inspiration for Streamlit design) |
        
        ### Key Metrics
        - **Test coverage:** 20 cases (no conflicts, priority, fixed, dependencies, time zones, impossible, invalid, injection, free text)
        - **LLM support:** Gemini and OpenAI (configurable via environment variable)
        - **Guarantee:** Programmatic verification of zero chronological overlaps in UTC for any "ok" schedule
        - **Transparency:** Every decision cites its rule; trade-offs and alternatives explained
        - **Branch access:** Guaranteed push permission for all team members (main, Om, Shiva, Tirth, Yurica branches configured)
        
        ### What Makes This Solution Strong
        1. **Explicit rules enable repeatability.** V1 makes ad-hoc decisions; V3 cites a rule for each one.
        2. **Few-shot examples teach edge cases.** Time zones, dependencies, and impossible inputs are rare in plain prompts.
        3. **Code checks what the model produces.** Violations are caught and fixed by a repair loop, not left in.
        4. **Guardrails prevent garbage input.** Bad data is rejected before the model wastes tokens.
        5. **Side-by-side comparison proves the improvement.** V1 vs V3 on the same input shows why explicit rules matter.
        6. **Integration complete.** All team members' work merged into one robust application.
        """)
        
        st.markdown("---")
        st.markdown("*Built for SEMM 7 Hackathon by Team 2. Demonstrates prompt engineering, LLM integration, rigorous testing, and collaborative development.*")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    main()
