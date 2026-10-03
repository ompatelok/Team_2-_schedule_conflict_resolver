# Schedule Conflict Resolver - Complete Documentation

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [What This Project Does](#what-this-project-does)
3. [Team & Contributions](#team--contributions)
4. [Architecture Overview](#architecture-overview)
5. [How It Works - Complete Flow](#how-it-works---complete-flow)
6. [Frontend Prototype Workflow](#frontend-prototype-workflow)
7. [Input & Output Format](#input--output-format)
8. [7 Decision Rules (R1-R7)](#7-decision-rules-r1-r7)
9. [Test Cases Summary](#test-cases-summary)
10. [Running the Project](#running-the-project)
11. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### For Users (Frontend Only)
```bash
# 1. Make sure backend is running on port 5000
# 2. Open in browser
http://localhost:5000

# 3. Add your events
# 4. Click "Resolve Conflicts"
# 5. See the conflict-free schedule
```

### For Developers (Full Stack)
```bash
# 1. Install dependencies
pip install flask flask-cors openai google-generativeai

# 2. Set environment variables
export LLM_PROVIDER=openai
export LLM_API_KEY=your_key_here
export FLASK_PORT=5000

# 3. Start the API backend
python api.py

# 4. Backend starts at http://localhost:5000
# 5. Frontend is served automatically at that URL
```

---

## 💡 What This Project Does

**Problem:** You have overlapping events with different priorities, time zones, and dependencies. You need a conflict-free schedule that explains every change.

**Solution:** This app uses AI to:
- Take overlapping events with priorities
- Apply 7 explicit rules (R1-R7) to resolve conflicts
- Suggest which events to move or drop
- Explain every decision
- Verify the result is truly conflict-free (using code)

**Key Features:**
- ✅ Handles multiple time zones
- ✅ Respects fixed/mandatory event flags
- ✅ Manages event dependencies
- ✅ Provides transparent reasoning
- ✅ Gracefully handles impossible scenarios
- ✅ Compares AI versions side-by-side

---

## 👥 Team & Contributions

| Member | Role | What They Built |
|--------|------|-----------------|
| **Yurica** | Prompt Engineer | Designed rules R1-R7, wrote prompts V1/V2/V3, created test cases |
| **Om** | Backend/Integration | Built Flask API, integrated all prompts, implemented verification |
| **Shiva** | QA & Testing | Designed 20 test cases, validated edge cases |
| **Tirth** (You) | Frontend/UI | Created HTML/CSS/JS prototype, integrated with backend |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE (Frontend)                     │
│              (HTML / CSS / JavaScript - Browser)                 │
│  - Event input form                                              │
│  - Timeline visualization                                        │
│  - Result display                                                │
│  - Status indicator                                              │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ HTTP POST /api/resolve
                       │ (JSON: events + priorities)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BACKEND API (Flask - Python)                    │
│                        (api.py)                                   │
│  - Receive user input                                            │
│  - Validate input format                                         │
│  - Call LLM to resolve                                           │
│  - Verify result (code-based proof)                              │
│  - Repair if needed                                              │
│  - Return JSON response                                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ (Uses)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│        TEAM'S CORE LOGIC (Project/ folder - Python)              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  prompts.py                                              │   │
│  │  - SYSTEM_V1 (baseline prompt)                           │   │
│  │  - SYSTEM_V3 (refined prompt with rules + examples)      │   │
│  │  - EXTRACT_SYSTEM (free text → JSON)                     │   │
│  │  - FEW_SHOT (3 examples)                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  checker.py                                              │   │
│  │  - validate_input() - checks before LLM call             │   │
│  │  - parse_output() - validates JSON shape                 │   │
│  │  - check_schedule() - proves zero conflicts              │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  test_cases.json                                         │   │
│  │  - 20 test cases covering all scenarios                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                       │
                       │ (Calls)
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│             EXTERNAL AI MODELS (OpenAI or Google)                │
│  - gpt-4 (or other latest model)                                 │
│  - gemini-pro                                                     │
│  (Resolves schedule using the prompt and rules)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 How It Works - Complete Flow

### Step 1: User Input
User enters events in the frontend form:
```
Event 1: "Project Meeting" 10:00-11:00, Priority 3
Event 2: "Client Call"    10:30-11:30, Priority 3
Event 3: "Lunch"          11:00-12:00, Priority 1
```

### Step 2: Frontend Validation
JavaScript checks:
- ✅ At least one event
- ✅ Event names not empty
- ✅ End time > Start time
- ✅ If valid, proceed to backend

### Step 3: Build Request
Frontend creates JSON matching the team's schema:
```json
{
  "window": {
    "start": "2026-10-12T09:00",
    "end": "2026-10-12T18:00",
    "tz": "Asia/Kolkata"
  },
  "events": [
    {
      "id": "1",
      "title": "Project Meeting",
      "start": "2026-10-12T10:00",
      "end": "2026-10-12T11:00",
      "tz": "Asia/Kolkata",
      "priority": 3,
      "fixed": false,
      "mandatory": false,
      "depends_on": []
    },
    ...
  ]
}
```

### Step 4: Send to Backend
Frontend calls:
```javascript
POST http://localhost:5000/api/resolve
Body: { input_json, prompt_version: "V3" }
```

### Step 5: Backend Input Validation
`checker.validate_input()` checks:
- ✅ Each event has id, title, start, end, tz, priority, fixed, mandatory, depends_on
- ✅ End time is after start time
- ✅ Priority is 1-5
- ✅ Time zone is valid (IANA)
- ✅ No duplicate IDs
- ✅ Dependencies reference valid event IDs

If invalid → return `status: "invalid_input"` with error list

### Step 6: Call AI Model (LLM)
Backend sends to OpenAI/Gemini:
- **System prompt:** Rules R1-R7, input spec, few-shot examples
- **User prompt:** The input JSON wrapped in `<input>` tags
- **Model response:** JSON with scheduled events

### Step 7: Parse & Verify
`checker.parse_output()` checks:
- ✅ Valid JSON with required fields
- ✅ Status is "ok", "infeasible", "invalid_input", or "off_topic"

`checker.check_schedule()` verifies (if status is "ok"):
- ✅ No two scheduled events overlap in UTC
- ✅ Fixed events didn't move
- ✅ Mandatory events weren't dropped
- ✅ Dependencies are ordered correctly
- ✅ All events stay in the window
- ✅ Durations unchanged

If violations found → **Repair loop**: send violations back to LLM (max 2 retries)

### Step 8: Return Response
Backend sends JSON to frontend:
```json
{
  "status": "ok",
  "schedule": [
    {
      "id": "1",
      "start_utc": "2026-10-12T04:30Z",
      "end_utc": "2026-10-12T05:30Z",
      "action": "kept",
      "rule": "R2",
      "reason": "Fixed and mandatory, so it keeps its exact time."
    },
    ...
  ],
  "dropped": [
    {
      "id": "3",
      "rule": "R5",
      "reason": "Lower priority; moved to make room for higher-priority events."
    }
  ],
  "trade_offs": "All three events are kept. The cost is that the lunch hour runs 90 minutes later...",
  "problem": null
}
```

### Step 9: Frontend Display
JavaScript renders:
- 🟢 Timeline with resolved events
- 📋 List of dropped events
- 💬 Explanations for why events moved
- 📊 Trade-off summary
- 🔄 "Ready" → "Processing" → "Success" status

---

## 🎨 Frontend Prototype Workflow

### User Journey

```
┌──────────────┐
│   PAGE LOAD  │
│  Status: ✓   │
│   Ready      │
└──────┬───────┘
       │
       ▼
┌──────────────────────────┐
│  RESOLVER PAGE (Tab 1)   │
│  ┌────────────────────┐  │
│  │ EVENT INPUT FORM   │  │
│  │ ┌────────────────┐ │  │
│  │ │ Event 1: ...   │ │  │
│  │ │ Event 2: ...   │ │  │
│  │ │ Event 3: ...   │ │  │
│  │ └────────────────┘ │  │
│  │ [+ Add Event]      │  │
│  │ [Resolve Conflicts]│  │
│  └────────────────────┘  │
└──────┬───────────────────┘
       │ User clicks "Resolve Conflicts"
       ▼
┌──────────────────────────┐
│  VALIDATION CHECK        │
│  (JavaScript)            │
│                          │
│  ✓ Events not empty?     │
│  ✓ Names filled?         │
│  ✓ End > Start?          │
│  ✓ All valid?            │
└──────┬───────────────────┘
       │ Valid input?
       ├─► NO  ─→ Show error messages
       │        Return to form
       │
       ├─► YES ─→ Continue
       │
       ▼
┌──────────────────────────┐
│  UPDATE STATUS           │
│  Status: ⏳              │
│  Processing...           │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  SEND TO API             │
│  POST /api/resolve       │
│                          │
│  {                       │
│   input_json: {...},     │
│   prompt_version: "V3"   │
│  }                       │
└──────┬───────────────────┘
       │
       ▼
┌──────────────────────────┐
│  WAIT FOR RESPONSE       │
│  (API processes)         │
│  - Validate              │
│  - Call LLM              │
│  - Verify result         │
│  - Return JSON           │
└──────┬───────────────────┘
       │ Response arrives
       ▼
┌──────────────────────────┐
│  CHECK STATUS            │
│  status = "ok"?          │
└──────┬───────────────────┘
       │
       ├─► OK ─────────────┐
       │                   │
       │                   ▼
       │          ┌──────────────────────┐
       │          │ DISPLAY RESULT       │
       │          │ ✓ Status: Success    │
       │          │ ┌────────────────┐   │
       │          │ │ Resolved Events│   │
       │          │ │ - Event A: OK  │   │
       │          │ │ - Event B: Mvd │   │
       │          │ │ - Event C: Drp │   │
       │          │ └────────────────┘   │
       │          │ Trade-offs: ...      │
       │          │ Explanations: ...    │
       │          └──────┬───────────────┘
       │                 │
       │                 ▼
       │          ┌──────────────────────┐
       │          │ Update UI:           │
       │          │ - Show timeline      │
       │          │ - Show explanations  │
       │          │ - Show trade-offs    │
       │          │ - Toast notification │
       │          │ Status: ✓ Success    │
       │          └──────────────────────┘
       │
       ├─► ERROR ──────────────────────┐
       │                               │
       │                               ▼
       │                      ┌──────────────────────┐
       │                      │ SHOW ERROR MESSAGE   │
       │                      │ ✗ Status: Error      │
       │                      │ Message: ...         │
       │                      │ Toast: ❌ Failed     │
       │                      └──────────────────────┘
       │
       └─► INFEASIBLE ─────────────────┐
              (impossible to solve)     │
                                        ▼
                               ┌──────────────────────┐
                               │ SHOW INFEASIBILITY   │
                               │ ⚠️ Status: Error     │
                               │ Problem: ...         │
                               │ Suggestions: ...     │
                               └──────────────────────┘
```

### UI Components Used

| Component | Where | Function |
|-----------|-------|----------|
| **Sidebar** | Left | Navigation between tabs (Resolver, Comparison, Evaluation, Documentation) |
| **Top Bar** | Top | Page title + Status badge (Ready/Processing/Success/Error) |
| **Event Form** | Center-left | Input fields for event name, start, end, priority |
| **Timeline** | Center-right | Visual display of events (input or resolved) |
| **Explanation** | Bottom | Why events moved (trade-offs and decisions) |
| **Validation** | Below form | Error messages for invalid input |
| **Toast** | Bottom-right | Quick notification (success or error) |

---

## 📥 Input & Output Format

### Input JSON Structure

```json
{
  "window": {
    "start": "YYYY-MM-DDTHH:MM",
    "end": "YYYY-MM-DDTHH:MM",
    "tz": "IANA/Timezone"
  },
  "events": [
    {
      "id": "string",
      "title": "Event name",
      "start": "YYYY-MM-DDTHH:MM",
      "end": "YYYY-MM-DDTHH:MM",
      "tz": "IANA/Timezone",
      "priority": 1-5,
      "fixed": boolean,
      "mandatory": boolean,
      "depends_on": ["id1", "id2"]
    }
  ]
}
```

**Field Meanings:**
- `window.tz` - Calendar's time zone (events are in their own tz)
- `priority` - 1 (low) to 5 (high)
- `fixed` - true = event cannot be moved
- `mandatory` - true = event cannot be dropped
- `depends_on` - This event starts only after these finish

### Output JSON Structure (Status: "ok")

```json
{
  "status": "ok",
  "normalized": [
    {
      "id": "1",
      "start_utc": "YYYY-MM-DDTHH:MMZ",
      "end_utc": "YYYY-MM-DDTHH:MMZ",
      "effective_priority": 1-5
    }
  ],
  "conflicts_found": [
    {
      "between": ["id1", "id2"],
      "type": "overlap" | "dependency"
    }
  ],
  "schedule": [
    {
      "id": "1",
      "start_utc": "YYYY-MM-DDTHH:MMZ",
      "end_utc": "YYYY-MM-DDTHH:MMZ",
      "action": "kept" | "moved",
      "rule": "R1-R7 or none",
      "reason": "Why this decision was made"
    }
  ],
  "dropped": [
    {
      "id": "3",
      "rule": "R5",
      "reason": "Why event was dropped"
    }
  ],
  "trade_offs": "What was given up, what it bought, one alternative rejected",
  "problem": null
}
```

### Output JSON Structure (Status: "infeasible")

```json
{
  "status": "infeasible",
  "schedule": [],
  "dropped": [],
  "trade_offs": "",
  "problem": {
    "rule": "R2",
    "ids": ["id1", "id2"],
    "reason": "Why this cannot be solved",
    "suggestions": [
      "Option 1 to make it solvable",
      "Option 2 to make it solvable"
    ]
  }
}
```

---

## 📋 7 Decision Rules (R1-R7)

### R1: Normalize to UTC
- Convert all event times to UTC using their time zone
- Use half-open intervals: [start, end)
- Back-to-back events don't conflict

**Why:** Comparing local times is unreliable across time zones. UTC is unambiguous.

---

### R2: Hard Constraints (Highest Priority)
- **Fixed events** keep their exact time
- **Mandatory events** are never dropped
- **Durations** never change
- **Window bounds** are respected

**Why:** These are non-negotiable. The code verifies them.

---

### R3: Dependencies & Inherited Priority
- Dependent event starts at or after its dependency ends
- If dependency is dropped, dependent is dropped too
- Dependent inherits the highest priority from its chain

**Why:** Some events need others to finish first. Cascading drops are necessary.

---

### R4: Move Before Drop
- Try moving a non-fixed event instead of dropping
- Drop only when no free slot exists

**Why:** A time change is better than losing an event entirely.

---

### R5: Priority-Based Resolution
- When both events in a conflict could move: **lower priority one moves**
- When one must be dropped: **lower priority one is dropped**

**Why:** Protects important work.

---

### R6: Tie-Break (Equal Priority)
Priority order for tie-breaking:
1. **Mandatory beats optional**
2. **Earlier original start time wins**
3. **Alphabetical ID order**

**Why:** Makes equal-priority cases repeatable and fair.

---

### R7: Placement (Deterministic Slot Finding)
Moved event goes to:
1. **Earliest free slot**
2. **At or after its original start time**
3. **At or after all dependencies end**

**Why:** One deterministic rule = same input always gives same output.

---

## 📊 Test Cases Summary

The project includes **20 test cases** covering all scenarios:

| Case | What It Tests | Expected Result |
|------|---------------|-----------------|
| **T01** | No conflict | Nothing moves ✓ |
| **T02** | Both movable | Lower priority moves (R5) |
| **T03** | Both fixed | Lower priority drops (R5) |
| **T04** | Move before drop | High-priority moves for fixed low-priority (R4) |
| **T05** | Time-zone false alarm | Same local time, different zones, no real conflict (R1) |
| **T06** | Hidden time-zone conflict | Clock times look apart but overlap in UTC (R1) |
| **T07** | Dependency broken | Dependent moves after dependency (R3) |
| **T08** | Cascade drop | Dropped dependency takes dependent with it (R3) |
| **T09** | Inherited priority | Low-prio event beats medium because mandatory depends on it (R3) |
| **T10** | No free slot | Movable event dropped because no space (R4, R7) |
| **T11** | Tie-break | Earlier original start keeps slot (R6) |
| **T12** | Full stretch | 3 time zones + dependency + 2 moves, nothing dropped |
| **T13** | Impossible overlap | 2 mandatory fixed events overlap (returns "infeasible") |
| **T14** | Dependency cycle | Circular depends_on (returns "infeasible") |
| **T15** | Impossible dependency | Mandatory fixed can't start after its fixed dependency (returns "infeasible") |
| **T16** | Invalid input | End before start (returns "invalid_input") |
| **T17** | Invalid dependency | depends_on names non-existent event (returns "invalid_input") |
| **T18** | Off-topic | Essay request (returns "off_topic") |
| **T19** | Prompt injection | Hidden instruction in event title (treated as data) |
| **T20** | Free-text extraction | Natural language input (extracted to JSON first) |

---

## ▶️ Running the Project

### Prerequisites
```bash
# Python 3.8+
python --version

# Install dependencies
pip install flask flask-cors openai google-generativeai python-dotenv
```

### Setup Environment

**Option 1: Using .env file**
```bash
# Create .env file
cat > .env << EOF
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-key-here
FLASK_PORT=5000
EOF
```

**Option 2: Export variables**
```bash
export LLM_PROVIDER=openai
export LLM_API_KEY=sk-your-key-here
export FLASK_PORT=5000
```

### Start Backend
```bash
python api.py
```

Output:
```
Starting Schedule Conflict Resolver API on port 5000...
LLM Provider: openai
Frontend: http://localhost:5000
API Health: http://localhost:5000/api/health
 * Running on http://0.0.0.0:5000
```

### Access Frontend
```bash
# Open browser
http://localhost:5000
```

### Alternative: Streamlit Version
The team also built a Streamlit version (for analysis/comparison):
```bash
streamlit run app.py
```

---

## 🔧 Troubleshooting

### "Backend not responding"
**Symptom:** Frontend shows error "API call failed"

**Fix:**
1. Check backend is running: `python api.py`
2. Check port 5000 is not blocked: `lsof -i :5000`
3. Check firewall

---

### "Invalid API key"
**Symptom:** `LLM call failed: Invalid API key`

**Fix:**
1. Verify key in environment: `echo $LLM_API_KEY`
2. Check key is valid on OpenAI/Google console
3. Verify provider matches key: `echo $LLM_PROVIDER`

---

### "Validation failed: end must be after start"
**Symptom:** Backend rejects input

**Fix:**
- In frontend form, ensure End time > Start time
- Check date format is YYYY-MM-DD

---

### "Response is not valid JSON"
**Symptom:** "LLM response was not valid JSON"

**Fix:**
1. LLM returned non-JSON or malformed JSON
2. Try again (model hallucinates occasionally)
3. Use `V3` prompt (better than V1)
4. Check API key quota

---

### "Schedule verification failed"
**Symptom:** Backend says "Unable to parse response"

**Fix:**
1. Backend is checking output—repair loop will retry
2. Wait ~30 seconds (model is being called again)
3. If persistent, check LLM model name (gpt-4 vs gpt-3.5)

---

## 📞 Support

### Common Questions

**Q: Can I add events with specific time zones?**
A: Yes! Each event has its own `tz` field. Supported IANA zones: `Asia/Kolkata`, `Europe/London`, `America/New_York`, etc.

**Q: Can I make an event "cannot be dropped"?**
A: Yes! Set `mandatory: true` when creating the event.

**Q: What if the schedule is impossible?**
A: Backend returns `status: "infeasible"` with suggestions on what to change.

**Q: How long does it take to resolve?**
A: 2-5 seconds (API call + LLM response). Longer on slower networks.

**Q: Can I use this for non-work scheduling?**
A: Yes! It works for any overlapping time slots with priorities.

---

## 📝 Summary

This project demonstrates **prompt engineering + AI + code verification**:
1. **Explicit rules** (R1-R7) make decisions repeatable
2. **Few-shot examples** teach edge cases
3. **Code verification** proves the result is correct
4. **Repair loop** fixes model mistakes
5. **Clean UI** makes scheduling easy

Built by Team 2 for SEMM 7 Hackathon. 🎉

---

**Version:** 1.0  
**Last Updated:** 2026-10-03  
**Repository:** ompatelok/Team_2-_schedule_conflict_resolver
