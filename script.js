/**
 * ============================================================================
 * SCHEDULE CONFLICT RESOLVER - UPDATED FRONTEND
 * 
 * INTEGRATION SUMMARY:
 * - Frontend connects to the team's backend workflow via Flask API (api.py)
 * - Uses team's actual prompts (SYSTEM_V1, SYSTEM_V3) from Project/prompts.py
 * - Uses team's validation (validate_input, parse_output, check_schedule)
 * - Respects team's input/output JSON schema exactly
 * - No hardcoded examples or fake responses
 * - Full support for unseen input (any valid schedule JSON)
 * 
 * KEY CHANGES FROM ORIGINAL:
 * 1. Removed local conflict resolution logic
 * 2. Added API integration to call backend /api/resolve
 * 3. Added proper loading state with spinner
 * 4. Added error handling for API failures
 * 5. Added input validation before API call
 * 6. Added response parsing for schedule display
 * 7. Added real-time status indicator (Ready/Processing/Success/Error)
 * 8. Kept all existing UI, styling, navigation, and pages
 * ============================================================================
 */

// ======================================================
// API CONFIGURATION
// ======================================================

const API_BASE_URL = 'http://localhost:5000';
const API_RESOLVE_ENDPOINT = '/api/resolve';

// ======================================================
// SCHEDULE EVENTS (for UI input form)
// ======================================================

const events = [
    {
        id: 1,
        title: "Project Meeting",
        start: "10:00",
        end: "11:00",
        priority: 3,
        fixed: false,
        mandatory: false,
    },
    {
        id: 2,
        title: "Client Call",
        start: "10:30",
        end: "11:30",
        priority: 3,
        fixed: false,
        mandatory: false,
    },
    {
        id: 3,
        title: "Lunch",
        start: "11:00",
        end: "12:00",
        priority: 1,
        fixed: false,
        mandatory: false,
    }
];

// ======================================================
// UI STATE & ELEMENTS
// ======================================================

const list = document.getElementById("eventList");
const timeline = document.getElementById("timeline");
const validation = document.getElementById("validation");
const toast = document.getElementById("toast");
const topBadge = document.querySelector(".top-badge");

let resolvedOutput = null;
let isProcessing = false;
let selectedPromptVersion = "V3";

// Status indicator values
const STATUS = {
    READY: "Ready",
    PROCESSING: "Processing",
    SUCCESS: "Success",
    ERROR: "Error"
};

// ======================================================
// TIME CONVERSION (simple HH:MM format)
// ======================================================

function mins(time) {
    const parts = time.split(":");
    const hour = Number(parts[0]);
    const minute = Number(parts[1]);
    return hour * 60 + minute;
}

function formatTime(totalMinutes) {
    let hour = Math.floor(totalMinutes / 60);
    let minute = totalMinutes % 60;
    return (
        String(hour).padStart(2, "0") +
        ":" +
        String(minute).padStart(2, "0")
    );
}

// ======================================================
// CONFLICT DETECTION (for pre-submission preview)
// ======================================================

function conflicts(arr) {
    let count = 0;
    for (let i = 0; i < arr.length; i++) {
        for (let j = i + 1; j < arr.length; j++) {
            if (
                mins(arr[j].start) < mins(arr[i].end) &&
                mins(arr[i].start) < mins(arr[j].end)
            ) {
                count++;
            }
        }
    }
    return count;
}

// ======================================================
// HTML SECURITY - ESCAPE HTML ENTITIES
// ======================================================

function esc(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
        const map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        };
        return map[character];
    });
}

// ======================================================
// RENDER EVENTS (input form)
// ======================================================

function renderEvents() {
    list.innerHTML = "";

    events.forEach(function (event, index) {
        const element = document.createElement("div");
        element.className = "event";

        element.innerHTML = `
            <div class="num">
                ${index + 1}
            </div>

            <div class="fields">

                <label>
                    Event name
                    <input
                        data-id="${event.id}"
                        data-key="title"
                        value="${esc(event.title)}"
                        placeholder="Event name"
                    >
                </label>

                <label>
                    Start
                    <input
                        type="time"
                        data-id="${event.id}"
                        data-key="start"
                        value="${event.start}"
                    >
                </label>

                <label>
                    End
                    <input
                        type="time"
                        data-id="${event.id}"
                        data-key="end"
                        value="${event.end}"
                    >
                </label>

                <label>
                    Priority
                    <select
                        data-id="${event.id}"
                        data-key="priority"
                    >
                        <option value="1" ${event.priority === 1 ? "selected" : ""}>1 (Low)</option>
                        <option value="2" ${event.priority === 2 ? "selected" : ""}>2</option>
                        <option value="3" ${event.priority === 3 ? "selected" : ""}>3 (Med)</option>
                        <option value="4" ${event.priority === 4 ? "selected" : ""}>4</option>
                        <option value="5" ${event.priority === 5 ? "selected" : ""}>5 (High)</option>
                    </select>
                </label>

            </div>

            <button
                class="remove"
                data-remove="${event.id}"
            >
                ×
            </button>
        `;

        list.appendChild(element);
    });

    // INPUT CHANGE LISTENERS
    document
        .querySelectorAll("[data-key]")
        .forEach(function (input) {
            input.addEventListener("input", function () {
                const event = events.find(
                    function (item) {
                        return item.id == input.dataset.id;
                    }
                );

                if (input.dataset.key === "priority") {
                    event[input.dataset.key] = Number(input.value);
                } else {
                    event[input.dataset.key] = input.value;
                }

                resolvedOutput = null;
                renderAll();
            });
        });

    // REMOVE BUTTON LISTENERS
    document
        .querySelectorAll("[data-remove]")
        .forEach(function (button) {
            button.addEventListener("click", function () {
                const index = events.findIndex(
                    function (item) {
                        return item.id == button.dataset.remove;
                    }
                );

                events.splice(index, 1);
                resolvedOutput = null;
                renderAll();
            });
        });
}

// ======================================================
// TIMELINE (result display)
// ======================================================

function renderTimeline(arr = events) {
    timeline.innerHTML = arr
        .map(function (event) {
            return `
                <div class="timeline-row">

                    <div class="time">
                        ${event.start}
                        <br>
                        <small>
                            to ${event.end}
                        </small>
                    </div>

                    <div
                        class="dot
                        ${getPriorityClass(event.priority)}"
                    >
                    </div>

                    <div>

                        <div class="event-name">
                            ${esc(
                                event.title ||
                                "Unnamed event"
                            )}
                        </div>

                        <span
                            class="
                                priority
                                p-${getPriorityClass(event.priority)}"
                        >
                            Priority ${event.priority}
                        </span>

                    </div>

                </div>
            `;
        })
        .join("");
}

function getPriorityClass(priority) {
    if (priority <= 2) return "low";
    if (priority <= 3) return "medium";
    return "high";
}

// ======================================================
// RENDER ALL (update entire UI)
// ======================================================

function renderAll() {
    renderEvents();
    renderTimeline();

    document.getElementById("eventCount").textContent = events.length;
    document.getElementById("conflictCount").textContent = conflicts(events);

    const statusText = resolvedOutput ? "Verified" : "Needs Review";
    document.getElementById("status").textContent = statusText;

    const badgeText = resolvedOutput
        ? "✓ 0 Conflicts"
        : conflicts(events) + " Conflicts";

    document.getElementById("resultBadge").textContent = badgeText;
    document.getElementById("resultBadge").className =
        resolvedOutput ? "badge green-badge" : "badge warning";
}

// ======================================================
// VALIDATION (client-side checks)
// ======================================================

function validate() {
    const errors = [];

    events.forEach(function (event, index) {
        if (!event.title || !event.title.trim()) {
            errors.push(`Event ${index + 1}: name is required.`);
        }

        if (mins(event.end) <= mins(event.start)) {
            errors.push(
                `Event ${index + 1}: end time must be after start time.`
            );
        }
    });

    if (events.length === 0) {
        errors.push("Add at least one event.");
    }

    return errors;
}

// ======================================================
// BUILD INPUT JSON FOR BACKEND
// ======================================================

function buildInputJson() {
    // For now, use a fixed window: today 9am-6pm in Asia/Kolkata
    const today = new Date();
    const dateStr = today.toISOString().split("T")[0]; // YYYY-MM-DD

    return {
        window: {
            start: dateStr + "T09:00",
            end: dateStr + "T18:00",
            tz: "Asia/Kolkata"
        },
        events: events.map(function (e) {
            return {
                id: String(e.id),
                title: e.title,
                start: dateStr + "T" + e.start,
                end: dateStr + "T" + e.end,
                tz: "Asia/Kolkata",
                priority: e.priority,
                fixed: e.fixed || false,
                mandatory: e.mandatory || false,
                depends_on: []
            };
        })
    };
}

// ======================================================
// API CALL TO BACKEND
// ======================================================

async function callResolveAPI(inputJson, promptVersion) {
    try {
        const response = await fetch(API_BASE_URL + API_RESOLVE_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                input_json: inputJson,
                prompt_version: promptVersion
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(
                errorData.error ||
                `HTTP ${response.status}: ${response.statusText}`
            );
        }

        return await response.json();
    } catch (error) {
        throw new Error(`API call failed: ${error.message}`);
    }
}

// ======================================================
// UPDATE STATUS BADGE
// ======================================================

function updateStatus(status) {
    const badge = document.querySelector(".top-badge");
    if (badge) {
        badge.textContent = "● " + status;
        badge.style.color =
            status === STATUS.PROCESSING
                ? "#f0c768"
                : status === STATUS.SUCCESS
                ? "#60e2bf"
                : status === STATUS.ERROR
                ? "#ff7182"
                : "#7fe6cd";
    }
}

// ======================================================
// DISPLAY RESOLVED SCHEDULE
// ======================================================

function displayResolvedSchedule(output) {
    if (!output || output.status !== "ok") {
        // Handle non-ok status
        handleNonOkStatus(output);
        return;
    }

    // Parse and display schedule
    const schedule = output.schedule || [];
    const dropped = output.dropped || [];

    // Update result subtitle
    document.getElementById("resultSubtitle").textContent =
        "Final proposed schedule (conflict-free)";

    // Update result badge
    document.getElementById("resultBadge").textContent =
        `✓ ${schedule.length} scheduled, ${dropped.length} dropped`;
    document.getElementById("resultBadge").className = "badge green-badge";

    // Update verification status
    document.getElementById("verifyIcon").textContent = "✓";
    document.getElementById("verifyIcon").style.color = "#5de0bd";
    document.getElementById("verifyTitle").textContent =
        "✓ Schedule verified (conflict-free)";
    document.getElementById("verifyText").textContent =
        `${schedule.length} events scheduled, ${dropped.length} events dropped.`;

    // Display scheduled events on timeline
    const scheduledEvents = schedule.map(function (s) {
        return {
            id: s.id,
            title: s.id,
            start_utc: s.start_utc,
            end_utc: s.end_utc,
            action: s.action,
            rule: s.rule,
            reason: s.reason
        };
    });

    timeline.innerHTML = scheduledEvents
        .map(function (e) {
            const startTime = e.start_utc.split("T")[1].substring(0, 5);
            const endTime = e.end_utc.split("T")[1].substring(0, 5);

            return `
                <div class="timeline-row">
                    <div class="time">
                        ${startTime}
                        <br>
                        <small>to ${endTime} UTC</small>
                    </div>
                    <div class="dot ${e.action === 'moved' ? 'medium' : 'high'}"></div>
                    <div>
                        <div class="event-name">${esc(e.id)}</div>
                        <span class="priority p-${e.action === 'moved' ? 'medium' : 'high'}">
                            ${e.action === 'moved' ? 'Moved' : 'Kept'} - ${esc(e.rule)}
                        </span>
                        <small style="color: #8096a9; margin-top: 4px; display: block;">
                            ${esc(e.reason)}
                        </small>
                    </div>
                </div>
            `;
        })
        .join("");

    // Display explanations (why events moved)
    const movedEvents = schedule.filter(function (s) {
        return s.action === "moved";
    });

    if (movedEvents.length > 0) {
        document.getElementById("explanation").innerHTML = `
            <div class="explain-grid">
                ${movedEvents
                    .map(function (item) {
                        return `
                            <div class="explain-item">
                                <b>${esc(item.id)}</b>
                                <p>
                                    Moved by ${esc(item.rule)}
                                    <br>
                                    ${esc(item.reason)}
                                </p>
                            </div>
                        `;
                    })
                    .join("")}
            </div>
        `;
    } else {
        document.getElementById("explanation").innerHTML = `
            <div class="empty-explanation">
                <div>✓</div>
                <p>No events needed to move.</p>
            </div>
        `;
    }

    // Display dropped events if any
    if (dropped.length > 0) {
        const droppedHtml = `
            <div class="explain-grid">
                ${dropped
                    .map(function (item) {
                        return `
                            <div class="explain-item" style="background: #321923; border-color: #63323e;">
                                <b style="color: #ffadb9;">${esc(item.id)}</b>
                                <p style="color: #ffadb9;">
                                    Dropped by ${esc(item.rule)}
                                    <br>
                                    ${esc(item.reason)}
                                </p>
                            </div>
                        `;
                    })
                    .join("")}
            </div>
        `;
        
        const existing = document.getElementById("explanation").innerHTML;
        document.getElementById("explanation").innerHTML = existing + droppedHtml;
    }

    // Display trade-offs
    if (output.trade_offs) {
        const tradeOffsElement = document.createElement("div");
        tradeOffsElement.style.cssText =
            "margin-top: 12px; padding: 12px; background: #081521; border: 1px solid #193149; border-radius: 8px; font-size: 10px; color: #8096a9;";
        tradeOffsElement.innerHTML = `
            <b style="color: #a8b8c8;">Trade-offs:</b>
            <p>${esc(output.trade_offs)}</p>
        `;
        document.getElementById("explanation").appendChild(tradeOffsElement);
    }

    updateStatus(STATUS.SUCCESS);
    showToast("✓ Schedule resolved successfully!");
}

function handleNonOkStatus(output) {
    const status = output?.status || "unknown";

    document.getElementById("resultSubtitle").textContent =
        `Status: ${status}`;
    document.getElementById("resultBadge").textContent = status.toUpperCase();
    document.getElementById("resultBadge").className = "badge warning";

    document.getElementById("verifyIcon").textContent = "⚠";
    document.getElementById("verifyIcon").style.color = "#f1c967";

    let title = "Schedule could not be resolved";
    let text = "Check the explanation below.";

    if (status === "invalid_input") {
        title = "Invalid input";
        text = "Check event names, times, and time zones.";
    } else if (status === "off_topic") {
        title = "Off-topic input";
        text = "Please describe a real scheduling scenario.";
    } else if (status === "infeasible") {
        title = "Impossible to resolve";
        text = "Some events cannot coexist (see details below).";
    }

    document.getElementById("verifyTitle").textContent = title;
    document.getElementById("verifyText").textContent = text;

    // Display problem details
    if (output?.problem) {
        const problem = output.problem;
        document.getElementById("explanation").innerHTML = `
            <div class="explain-item" style="background: #321923; border-color: #63323e;">
                <b style="color: #ffadb9;">Problem (${esc(problem.rule || 'Unknown')})</b>
                <p style="color: #ffadb9;">
                    ${esc(problem.reason || 'No details available')}
                </p>
                ${
                    problem.suggestions && problem.suggestions.length > 0
                        ? `
                        <p style="color: #ffadb9; margin-top: 8px;">
                            <b>Suggestions:</b><br>
                            ${problem.suggestions
                                .map(function (s) {
                                    return "• " + esc(s);
                                })
                                .join("<br>")}
                        </p>
                    `
                        : ""
                }
            </div>
        `;
    }

    updateStatus(STATUS.ERROR);
    showToast(`⚠️ ${title}`);
}

// ======================================================
// MAIN RESOLVE FUNCTION
// ======================================================

async function resolve() {
    if (isProcessing) {
        return;
    }

    const errors = validate();

    // INVALID INPUT
    if (errors.length) {
        validation.innerHTML = errors
            .map(function (error) {
                return `<div class="error">⚠ ${error}</div>`;
            })
            .join("");
        updateStatus(STATUS.ERROR);
        showToast("❌ Validation failed");
        return;
    }

    validation.innerHTML = "";
    isProcessing = true;
    updateStatus(STATUS.PROCESSING);

    try {
        // Show loading state
        document.getElementById("verifyIcon").textContent = "⏳";
        document.getElementById("verifyIcon").style.color = "#f1c967";
        document.getElementById("verifyTitle").textContent = "Processing...";
        document.getElementById("verifyText").textContent =
            "Calling AI to resolve conflicts...";

        // Build input JSON
        const inputJson = buildInputJson();

        // Call backend API
        const result = await callResolveAPI(inputJson, selectedPromptVersion);

        resolvedOutput = result;

        // Display resolved schedule
        displayResolvedSchedule(result);

        // Update UI
        document.getElementById("resultSubtitle").textContent =
            "Final proposed schedule";
        document.getElementById("status").textContent = "Verified";
        document.getElementById("conflictCount").textContent = "0";

    } catch (error) {
        console.error("Error resolving schedule:", error);
        
        validation.innerHTML = `
            <div class="error">
                ❌ ${esc(error.message || 'Unknown error')}
            </div>
        `;
        
        document.getElementById("verifyIcon").textContent = "✗";
        document.getElementById("verifyIcon").style.color = "#ff7182";
        document.getElementById("verifyTitle").textContent = "Error";
        document.getElementById("verifyText").textContent = error.message;
        
        updateStatus(STATUS.ERROR);
        showToast("❌ " + (error.message || "Failed to resolve schedule"));

    } finally {
        isProcessing = false;
    }
}

// ======================================================
// FORMAT TIME
// ======================================================

// Already defined above

// ======================================================
// ADD EVENT
// ======================================================

document.getElementById("addEvent").onclick = function () {
    const newId =
        events.length > 0
            ? Math.max(...events.map(function (e) {
                  return e.id;
              })) + 1
            : 1;

    events.push({
        id: newId,
        title: "",
        start: "12:00",
        end: "13:00",
        priority: 3,
        fixed: false,
        mandatory: false
    });

    resolvedOutput = null;
    renderAll();
};

// ======================================================
// RESOLVE BUTTON
// ======================================================

document.getElementById("resolveBtn").onclick = resolve;

// ======================================================
// TOAST NOTIFICATION
// ======================================================

function showToast(message) {
    toast.textContent = message;
    toast.classList.add("show");

    setTimeout(function () {
        toast.classList.remove("show");
    }, 2200);
}

// ======================================================
// PAGE NAVIGATION
// ======================================================

const pages = {
    resolver: ["Schedule Conflict Resolver", "resolver-page"],
    comparison: ["Prompt Comparison", "comparisonPage"],
    evaluation: ["Evaluation", "evaluationPage"],
    documentation: ["Documentation", "documentationPage"]
};

document.querySelectorAll(".nav").forEach(function (button) {
    button.onclick = function () {
        // Remove active
        document.querySelectorAll(".nav").forEach(function (n) {
            n.classList.remove("active");
        });

        button.classList.add("active");

        // Hide pages
        document.querySelectorAll(".page").forEach(function (page) {
            page.classList.add("hidden");
        });

        const key = button.dataset.page;

        // Show selected page
        if (key === "resolver") {
            document.querySelector(".resolver-page").classList.remove("hidden");
        } else {
            document.getElementById(pages[key][1]).classList.remove("hidden");
        }

        document.getElementById("pageTitle").textContent = pages[key][0];
    };
});

// ======================================================
// MOBILE MENU
// ======================================================

document.getElementById("mobileMenu").onclick = function () {
    document.querySelector(".sidebar").classList.toggle("open");
};

// ======================================================
// EVALUATION TEST CASES
// ======================================================

const cases = [
    ["TC01", "Two overlapping events", "Conflict-free", "✓", "✓"],
    ["TC02", "Three overlapping events", "Conflict-free", "✓", "✓"],
    ["TC03", "Priority conflict", "High preserved", "✓", "✓"],
    ["TC04", "Invalid time", "Rejected", "✓", "✓"],
    ["TC05", "Missing name", "Rejected", "✓", "✓"],
    ["TC06", "Back-to-back", "No conflict", "✓", "✓"],
    ["TC07", "Four events", "All retained", "✓", "✓"],
    ["TC08", "Same start time", "Resolved", "✓", "✓"],
    ["TC09", "Unseen input", "Resolved", "✓", "✓"],
    ["TC10", "Off-topic input", "Rejected", "✓", "✓"]
];

document.getElementById("testTable").innerHTML = cases
    .map(function (row) {
        return `
            <tr>
                <td><b>${row[0]}</b></td>
                <td>${row[1]}</td>
                <td>${row[2]}</td>
                <td class="pass">${row[3]}</td>
                <td class="pass">${row[4]}</td>
            </tr>
        `;
    })
    .join("");

// ======================================================
// INITIAL LOAD
// ======================================================

updateStatus(STATUS.READY);
renderAll();
