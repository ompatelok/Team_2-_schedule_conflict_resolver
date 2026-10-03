"""
SCHEDULE CONFLICT RESOLVER - COMPLETE WORKING BACKEND
Merges all team contributions into one unified Flask API

Team Integration:
  - Yurica (Member 1): prompts.py (SYSTEM_V1, V3, V4, extraction)
  - Shiva (Member 3): test_cases.json validation
  - Tirth (Member 4): INDEX.HTML, script.js, style.css (frontend)
  - Om (Member 2): api.py + integration + verification logic
  
This backend serves the frontend and calls the LLM with the team's actual prompts.
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import sys
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import traceback

# Add Project directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Project"))

try:
    from prompts import SYSTEM_V1, SYSTEM_V3, SYSTEM_V4, EXTRACT_SYSTEM, USER_TEMPLATE, REPAIR_TEMPLATE
    from checker import validate_input, parse_output, check_schedule
except ImportError as e:
    print(f"Warning: Could not import project modules: {e}")
    SYSTEM_V1 = SYSTEM_V3 = SYSTEM_V4 = EXTRACT_SYSTEM = USER_TEMPLATE = REPAIR_TEMPLATE = ""

# ============================================================================
# FLASK SETUP
# ============================================================================

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ============================================================================
# CONFIGURATION
# ============================================================================

FMT = "%Y-%m-%dT%H:%M"
STATUSES = {"ok", "infeasible", "invalid_input", "off_topic"}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

print(f"[API] LLM Provider: {LLM_PROVIDER}")
print(f"[API] LLM Key configured: {bool(LLM_API_KEY)}")

# ============================================================================
# HELPER FUNCTIONS: UTC CONVERSION
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
# GUARDRAILS: INPUT VALIDATION
# ============================================================================

def validate_input_wrapper(text):
    """
    Guardrail before LLM call.
    Block prompt injections, off-topic inputs, overly short strings.
    Returns: (is_valid, error_message_or_empty)
    """
    if not text or not isinstance(text, str):
        return False, "Input is empty or not text."
    
    text = text.strip()
    
    if len(text) < 20:
        return False, "Input is too short. Describe your scheduling scenario in detail."
    
    injection_markers = [
        r"(ignore|disregard|override|cancel).*(instruction|rule|system|prompt)",
        r"(system:|admin:|root:)",
        r"(execute|run|eval|exec|code:)",
    ]
    for pattern in injection_markers:
        if re.search(pattern, text, re.IGNORECASE):
            return False, "Input contains suspicious instructions."
    
    scheduling_keywords = {
        "event", "meeting", "call", "appointment", "schedule", "time",
        "conflict", "overlap", "window", "available", "slot", "booking",
        "timezone", "utc", "fixed", "mandatory", "priority", "move", "drop"
    }
    if not any(kw in text.lower() for kw in scheduling_keywords):
        return False, "Input does not appear to be about scheduling."
    
    return True, ""

# ============================================================================
# LLM INTEGRATION
# ============================================================================

def call_llm(system_prompt, user_message, temperature=0.0):
    """Call LLM (Gemini or OpenAI)."""
    if not LLM_API_KEY:
        return False, "API key not configured. Set LLM_API_KEY environment variable."
    
    try:
        if LLM_PROVIDER == "gemini":
            return _call_gemini(system_prompt, user_message, temperature)
        elif LLM_PROVIDER == "openai":
            return _call_openai(system_prompt, user_message, temperature)
        else:
            return False, f"Unknown provider: {LLM_PROVIDER}"
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
        return False, "google-generativeai not installed"
    except Exception as e:
        return False, f"Gemini error: {str(e)}"

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
        return False, "openai not installed"
    except Exception as e:
        return False, f"OpenAI error: {str(e)}"

# ============================================================================
# SCHEDULE VERIFICATION (PROGRAMMATIC PROOF)
# ============================================================================

def verify_schedule(schedule_json):
    """Rigorous verification of conflict-free schedule."""
    if not isinstance(schedule_json, dict):
        return False, "Schedule is not a JSON object."
    
    status = schedule_json.get("status")
    if status not in STATUSES:
        return False, f"Invalid status: {status}"
    
    if status != "ok":
        return True, f"Status '{status}' indicates a constraint violation."
    
    try:
        schedule_list = schedule_json.get("schedule", [])
        
        events = {}
        for s in schedule_list:
            eid = s.get("id")
            start_utc = from_z(s.get("start_utc", ""))
            end_utc = from_z(s.get("end_utc", ""))
            events[eid] = {"start": start_utc, "end": end_utc}
        
        # Check for overlaps using half-open intervals [start, end)
        event_list = sorted(events.items(), key=lambda kv: kv[1]["start"])
        for i in range(len(event_list) - 1):
            id_a, evt_a = event_list[i]
            id_b, evt_b = event_list[i + 1]
            if evt_a["end"] > evt_b["start"]:
                return False, f"OVERLAP: Events {id_a} and {id_b} overlap."
        
        return True, f"✓ Verified: {len(events)} events, zero overlaps in UTC."
    
    except Exception as e:
        return False, f"Verification failed: {str(e)}"

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "service": "Schedule Conflict Resolver",
        "llm_provider": LLM_PROVIDER,
        "llm_configured": bool(LLM_API_KEY)
    }), 200

@app.route('/api/resolve', methods=['POST'])
def resolve():
    """
    Main resolve endpoint.
    
    Request:
    {
      "input_json": {...},  // structured JSON, OR
      "input_text": "...",  // natural language text
      "prompt_version": "V1" | "V3" | "V4"  // default: V3
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                "status": "invalid_input",
                "error": "Request body must be JSON"
            }), 400
        
        # Parse input mode
        input_text = data.get("input_text", "").strip()
        input_json = data.get("input_json")
        prompt_version = data.get("prompt_version", "V3").upper()
        
        if not input_text and not input_json:
            return jsonify({
                "status": "invalid_input",
                "error": "Provide either 'input_text' or 'input_json'"
            }), 400
        
        if prompt_version not in ["V1", "V3", "V4"]:
            return jsonify({
                "status": "invalid_input",
                "error": f"prompt_version must be V1, V3, or V4"
            }), 400
        
        # === EXTRACT FREE TEXT IF NEEDED ===
        if input_text:
            is_valid, error_msg = validate_input_wrapper(input_text)
            if not is_valid:
                return jsonify({
                    "status": "invalid_input",
                    "error": f"Input validation: {error_msg}"
                }), 400
            
            # Call extraction model
            success, response = call_llm(EXTRACT_SYSTEM, f"<text>\n{input_text}\n</text>")
            if not success:
                return jsonify({
                    "status": "error",
                    "error": f"Extraction failed: {response}"
                }), 500
            
            try:
                input_json = parse_output(response)
                if not input_json:
                    return jsonify({
                        "status": "error",
                        "error": "Extraction response not in expected format"
                    }), 500
            except Exception as e:
                return jsonify({
                    "status": "error",
                    "error": f"Extraction parsing failed: {e}"
                }), 500
        
        # === VALIDATE INPUT STRUCTURE ===
        if isinstance(input_json, str):
            try:
                input_json = json.loads(input_json)
            except json.JSONDecodeError as e:
                return jsonify({
                    "status": "invalid_input",
                    "error": f"JSON parsing failed: {e}"
                }), 400
        
        validation_errors = validate_input(input_json) if validate_input else []
        if validation_errors:
            return jsonify({
                "status": "invalid_input",
                "errors": validation_errors
            }), 400
        
        # === CHOOSE PROMPT VERSION ===
        if prompt_version == "V1":
            system_prompt = SYSTEM_V1
        elif prompt_version == "V4":
            system_prompt = SYSTEM_V4
        else:  # V3
            system_prompt = SYSTEM_V3
        
        # === CALL LLM TO RESOLVE ===
        success, response = call_llm(
            system_prompt,
            USER_TEMPLATE.format(input_json=json.dumps(input_json))
        )
        
        if not success:
            return jsonify({
                "status": "error",
                "error": f"LLM call failed: {response}"
            }), 500
        
        # === PARSE OUTPUT ===
        output = parse_output(response) if parse_output else None
        if not output:
            try:
                output = json.loads(response)
            except:
                return jsonify({
                    "status": "error",
                    "error": "LLM response was not valid JSON"
                }), 500
        
        # === VERIFY IF OK STATUS ===
        if output.get("status") == "ok":
            is_valid, msg = verify_schedule(output)
            if not is_valid:
                # Try repair loop
                violations = check_schedule(input_json, output) if check_schedule else []
                if violations:
                    repair_prompt = REPAIR_TEMPLATE.format(violations="\n".join(violations))
                    success, repair_response = call_llm(system_prompt, repair_prompt)
                    if success:
                        repaired_output = parse_output(repair_response) if parse_output else None
                        if repaired_output:
                            output = repaired_output
        
        return jsonify(output), 200
    
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": f"Internal error: {str(e)}"
        }), 500

# ============================================================================
# STATIC FILE SERVING
# ============================================================================

@app.route('/', methods=['GET'])
def serve_index():
    """Serve frontend HTML."""
    return send_from_directory('.', 'INDEX.HTML')

@app.route('/<path:filename>', methods=['GET'])
def serve_static(filename):
    """Serve static assets (CSS, JS, images)."""
    return send_from_directory('.', filename)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv("FLASK_PORT", 5000))
    print(f"\n{'='*70}")
    print(f"Schedule Conflict Resolver API")
    print(f"{'='*70}")
    print(f"Frontend:  http://localhost:{port}")
    print(f"API Health: http://localhost:{port}/api/health")
    print(f"API Resolve: POST http://localhost:{port}/api/resolve")
    print(f"{'='*70}\n")
    
    app.run(debug=True, port=port, host='0.0.0.0')
