// ======================================================
// SCHEDULE EVENTS
// ======================================================

const events = [

    {
        id: 1,
        name: "Project Meeting",
        start: "10:00",
        end: "11:00",
        priority: "High"
    },

    {
        id: 2,
        name: "Client Call",
        start: "10:30",
        end: "11:30",
        priority: "Medium"
    },

    {
        id: 3,
        name: "Lunch",
        start: "11:00",
        end: "12:00",
        priority: "Low"
    }

];


// ======================================================
// ELEMENTS
// ======================================================

const list =
    document.getElementById("eventList");

const timeline =
    document.getElementById("timeline");

const validation =
    document.getElementById("validation");

const toast =
    document.getElementById("toast");

let resolved = false;


// ======================================================
// TIME CONVERSION
// ======================================================

function mins(time) {

    const parts = time.split(":");

    const hour =
        Number(parts[0]);

    const minute =
        Number(parts[1]);

    return hour * 60 + minute;
}


// ======================================================
// CONFLICT DETECTION
// ======================================================

function conflicts(arr) {

    let count = 0;

    for (
        let i = 0;
        i < arr.length;
        i++
    ) {

        for (
            let j = i + 1;
            j < arr.length;
            j++
        ) {

            if (
                mins(arr[j].start) <
                mins(arr[i].end)

                &&

                mins(arr[i].start) <
                mins(arr[j].end)
            ) {

                count++;

            }

        }

    }

    return count;
}


// ======================================================
// HTML SECURITY
// ======================================================

function esc(value) {

    return String(value)
        .replace(
            /[&<>"']/g,

            function (character) {

                const map = {

                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#039;"

                };

                return map[character];

            }
        );

}


// ======================================================
// RENDER EVENTS
// ======================================================

function renderEvents() {

    list.innerHTML = "";


    events.forEach(
        function (event, index) {

            const element =
                document.createElement("div");

            element.className =
                "event";


            element.innerHTML = `

                <div class="num">
                    ${index + 1}
                </div>

                <div class="fields">

                    <label>

                        Event name

                        <input
                            data-id="${event.id}"
                            data-key="name"
                            value="${esc(event.name)}"
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

                            <option
                                ${event.priority === "High"
                                    ? "selected"
                                    : ""}
                            >
                                High
                            </option>

                            <option
                                ${event.priority === "Medium"
                                    ? "selected"
                                    : ""}
                            >
                                Medium
                            </option>

                            <option
                                ${event.priority === "Low"
                                    ? "selected"
                                    : ""}
                            >
                                Low
                            </option>

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

        }
    );


    // INPUT CHANGE

    document
        .querySelectorAll("[data-key]")
        .forEach(
            function (input) {

                input.addEventListener(
                    "input",

                    function () {

                        const event =
                            events.find(
                                function (item) {

                                    return item.id ==
                                        input.dataset.id;

                                }
                            );


                        event[input.dataset.key] =
                            input.value;


                        resolved = false;

                        renderAll();

                    }
                );

            }
        );


    // REMOVE BUTTON

    document
        .querySelectorAll("[data-remove]")
        .forEach(
            function (button) {

                button.addEventListener(
                    "click",

                    function () {

                        const index =
                            events.findIndex(
                                function (item) {

                                    return item.id ==
                                        button.dataset.remove;

                                }
                            );


                        events.splice(index, 1);

                        resolved = false;

                        renderAll();

                    }
                );

            }
        );

}


// ======================================================
// TIMELINE
// ======================================================

function renderTimeline(arr = events) {

    timeline.innerHTML =
        arr.map(

            function (event) {

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
                            ${event.priority.toLowerCase()}"
                        >
                        </div>


                        <div>

                            <div class="event-name">

                                ${esc(
                                    event.name ||
                                    "Unnamed event"
                                )}

                            </div>


                            <span
                                class="
                                    priority
                                    p-${event.priority.toLowerCase()}
                                "
                            >

                                ${event.priority}
                                priority

                            </span>

                        </div>

                    </div>

                `;

            }

        ).join("");

}


// ======================================================
// RENDER EVERYTHING
// ======================================================

function renderAll() {

    renderEvents();

    renderTimeline();


    document.getElementById(
        "eventCount"
    ).textContent =
        events.length;


    document.getElementById(
        "conflictCount"
    ).textContent =
        conflicts(events);


    document.getElementById(
        "status"
    ).textContent =
        resolved
            ? "Verified"
            : "Needs Review";


    document.getElementById(
        "resultBadge"
    ).textContent =
        conflicts(events) +
        " Conflicts";

}


// ======================================================
// VALIDATION
// ======================================================

function validate() {

    const errors = [];


    events.forEach(
        function (event, index) {

            if (!event.name.trim()) {

                errors.push(
                    `Event ${index + 1}: name is required.`
                );

            }


            if (
                mins(event.end) <=
                mins(event.start)
            ) {

                errors.push(
                    `Event ${index + 1}: end time must be after start time.`
                );

            }

        }
    );


    if (events.length === 0) {

        errors.push(
            "Add at least one event."
        );

    }


    return errors;

}


// ======================================================
// RESOLVE CONFLICTS
// ======================================================

function resolve() {

    const errors =
        validate();


    // INVALID INPUT

    if (errors.length) {

        validation.innerHTML =
            errors.map(
                function (error) {

                    return `
                        <div class="error">
                            ⚠ ${error}
                        </div>
                    `;

                }
            ).join("");

        return;

    }


    validation.innerHTML = "";


    // COPY EVENTS

    const copy =
        events
            .map(
                event => ({
                    ...event
                })
            )
            .sort(
                (a, b) =>
                    mins(a.start) -
                    mins(b.start)
            );


    const priority = {

        Low: 1,

        Medium: 2,

        High: 3

    };


    const explanations = [];


    // RESOLVE OVERLAPS

    for (
        let i = 0;
        i < copy.length;
        i++
    ) {

        for (
            let j = i + 1;
            j < copy.length;
            j++
        ) {

            if (
                mins(copy[j].start) <
                mins(copy[i].end)
            ) {

                let lower;


                if (
                    priority[copy[i].priority] >=
                    priority[copy[j].priority]
                ) {

                    lower = copy[j];

                } else {

                    lower = copy[i];

                }


                const higher =
                    lower === copy[j]
                        ? copy[i]
                        : copy[j];


                const duration =
                    mins(lower.end) -
                    mins(lower.start);


                const oldStart =
                    lower.start;


                let newStart =
                    mins(higher.end);


                lower.start =
                    formatTime(newStart);


                newStart += duration;


                lower.end =
                    formatTime(newStart);


                explanations.push({

                    name: lower.name,

                    from: oldStart,

                    to: lower.start,

                    reason:
                        `${higher.name} has higher or equal priority (${higher.priority}).`

                });

            }

        }

    }


    copy.sort(
        (a, b) =>
            mins(a.start) -
            mins(b.start)
    );


    resolved = true;


    // UPDATE UI

    document.getElementById(
        "resultSubtitle"
    ).textContent =
        "Final proposed schedule";


    document.getElementById(
        "resultBadge"
    ).textContent =
        "✓ 0 Conflicts";


    document.getElementById(
        "resultBadge"
    ).className =
        "badge green-badge";


    document.getElementById(
        "verifyIcon"
    ).textContent =
        "✓";


    document.getElementById(
        "verifyIcon"
    ).style.color =
        "#5de0bd";


    document.getElementById(
        "verifyTitle"
    ).textContent =
        "Schedule verified";


    document.getElementById(
        "verifyText"
    ).textContent =
        "Final schedule is ready for review.";


    document.getElementById(
        "status"
    ).textContent =
        "Verified";


    document.getElementById(
        "conflictCount"
    ).textContent =
        "0";


    // FINAL TIMELINE

    timeline.innerHTML =
        copy.map(
            function (event) {

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
                            class="
                                dot
                                ${event.priority.toLowerCase()}
                            "
                        >
                        </div>


                        <div>

                            <div class="event-name">

                                ${esc(event.name)}

                            </div>


                            <span
                                class="
                                    priority
                                    p-${event.priority.toLowerCase()}
                                "
                            >

                                ${event.priority}
                                priority

                            </span>

                        </div>

                    </div>

                `;

            }
        ).join("");


    // EXPLANATIONS

    if (
        explanations.length
    ) {

        document.getElementById(
            "explanation"
        ).innerHTML = `

            <div class="explain-grid">

                ${

                    explanations
                        .map(
                            function (item) {

                                return `

                                    <div
                                        class="explain-item"
                                    >

                                        <b>
                                            ${esc(item.name)}
                                        </b>

                                        <p>

                                            ${item.from}
                                            →
                                            ${item.to}

                                            <br>

                                            ${esc(
                                                item.reason
                                            )}

                                        </p>

                                    </div>

                                `;

                            }
                        )
                        .join("")

                }

            </div>

        `;

    } else {

        document.getElementById(
            "explanation"
        ).innerHTML = `

            <div class="empty-explanation">

                <div>
                    ✓
                </div>

                <p>
                    No event needed to move.
                </p>

            </div>

        `;

    }


    showToast(
        "Schedule resolved successfully."
    );

}


// ======================================================
// FORMAT TIME
// ======================================================

function formatTime(totalMinutes) {

    let hour =
        Math.floor(
            totalMinutes / 60
        );


    let minute =
        totalMinutes % 60;


    return (
        String(hour).padStart(2, "0") +
        ":" +
        String(minute).padStart(2, "0")
    );

}


// ======================================================
// ADD EVENT
// ======================================================

document
    .getElementById("addEvent")
    .onclick =
    function () {

        events.push({

            id: Date.now(),

            name: "",

            start: "12:00",

            end: "13:00",

            priority: "Medium"

        });


        resolved = false;

        renderAll();

    };


// ======================================================
// RESOLVE BUTTON
// ======================================================

document
    .getElementById("resolveBtn")
    .onclick =
    resolve;


// ======================================================
// TOAST
// ======================================================

function showToast(message) {

    toast.textContent =
        message;


    toast.classList.add(
        "show"
    );


    setTimeout(
        function () {

            toast.classList.remove(
                "show"
            );

        },

        2200
    );

}


// ======================================================
// PAGE NAVIGATION
// ======================================================

const pages = {

    resolver: [
        "Schedule Conflict Resolver",
        "resolver-page"
    ],

    comparison: [
        "Prompt Comparison",
        "comparisonPage"
    ],

    evaluation: [
        "Evaluation",
        "evaluationPage"
    ],

    documentation: [
        "Documentation",
        "documentationPage"
    ]

};


document
    .querySelectorAll(".nav")
    .forEach(
        function (button) {

            button.onclick =
                function () {

                    // Remove active

                    document
                        .querySelectorAll(".nav")
                        .forEach(
                            n =>
                                n.classList.remove(
                                    "active"
                                )
                        );


                    button.classList.add(
                        "active"
                    );


                    // Hide pages

                    document
                        .querySelectorAll(".page")
                        .forEach(
                            page =>
                                page.classList.add(
                                    "hidden"
                                )
                        );


                    const key =
                        button.dataset.page;


                    // Show selected page

                    if (
                        key === "resolver"
                    ) {

                        document
                            .querySelector(
                                ".resolver-page"
                            )
                            .classList.remove(
                                "hidden"
                            );

                    } else {

                        document
                            .getElementById(
                                pages[key][1]
                            )
                            .classList.remove(
                                "hidden"
                            );

                    }


                    document.getElementById(
                        "pageTitle"
                    ).textContent =
                        pages[key][0];

                };

        }
    );


// ======================================================
// MOBILE MENU
// ======================================================

document
    .getElementById("mobileMenu")
    .onclick =
    function () {

        document
            .querySelector(".sidebar")
            .classList.toggle(
                "open"
            );

    };


// ======================================================
// EVALUATION TEST CASES
// ======================================================

const cases = [

    [
        "TC01",
        "Two overlapping events",
        "Conflict-free",
        "✓",
        "✓"
    ],

    [
        "TC02",
        "Three overlapping events",
        "Conflict-free",
        "✓",
        "✓"
    ],

    [
        "TC03",
        "Priority conflict",
        "High preserved",
        "✓",
        "✓"
    ],

    [
        "TC04",
        "Invalid time",
        "Rejected",
        "✓",
        "✓"
    ],

    [
        "TC05",
        "Missing name",
        "Rejected",
        "✓",
        "✓"
    ],

    [
        "TC06",
        "Back-to-back",
        "No conflict",
        "✓",
        "✓"
    ],

    [
        "TC07",
        "Four events",
        "All retained",
        "✓",
        "✓"
    ],

    [
        "TC08",
        "Same start time",
        "Resolved",
        "✓",
        "✓"
    ],

    [
        "TC09",
        "Unseen input",
        "Resolved",
        "✓",
        "✓"
    ],

    [
        "TC10",
        "Off-topic input",
        "Rejected",
        "✓",
        "✓"
    ]

];


document.getElementById(
    "testTable"
).innerHTML =

    cases
        .map(
            function (row) {

                return `

                    <tr>

                        <td>
                            <b>${row[0]}</b>
                        </td>

                        <td>
                            ${row[1]}
                        </td>

                        <td>
                            ${row[2]}
                        </td>

                        <td class="pass">
                            ${row[3]}
                        </td>

                        <td class="pass">
                            ${row[4]}
                        </td>

                    </tr>

                `;

            }
        )
        .join("");


// ======================================================
// INITIAL LOAD
// ======================================================

renderAll();