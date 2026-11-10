// ============================================================
// DeepFake AI - Frontend Application
// Same Website API Architecture
// ============================================================

// ------------------------------------------------------------
// DOM SELECTORS
// ------------------------------------------------------------

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);


// ------------------------------------------------------------
// APPLICATION STATE
// ------------------------------------------------------------

let mode = "image";
let selectedFile = null;

let token = localStorage.getItem("deepfake_token") || "";

let registerMode = false;


// ------------------------------------------------------------
// API CONFIGURATION
// ------------------------------------------------------------
//
// IMPORTANT:
//
// Production / FastAPI:
//     https://your-domain.com/api/...
//
// Local FastAPI:
//     http://127.0.0.1:8765/api/...
//
// Same website:
//     /api/...
//
// If index.html is opened directly with file://,
// automatically use local FastAPI.
// ------------------------------------------------------------

const API_BASE =
    window.location.protocol === "file:"
        ? "http://127.0.0.1:8765"
        : "";


// ------------------------------------------------------------
// API HELPER
// ------------------------------------------------------------

async function api(path, options = {}) {

    const url = `${API_BASE}${path}`;

    const headers = {
        ...(options.headers || {})
    };

    // Don't manually set Content-Type for FormData.
    // Browser will automatically create multipart boundary.
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    try {

        const response = await fetch(url, {
            ...options,
            headers
        });

        return response;

    } catch (error) {

        console.error("DeepFake API Error:", error);

        throw new Error(
            "Backend se connection nahi ho raha.\n\n" +
            "Please make sure DeepFake server is running:\n" +
            "http://127.0.0.1:8765"
        );
    }
}


// ------------------------------------------------------------
// SAFE JSON RESPONSE
// ------------------------------------------------------------

async function readResponse(response) {

    const contentType =
        response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {

        try {
            return await response.json();
        } catch {
            throw new Error("Server ne invalid JSON response diya.");
        }
    }

    const text = await response.text();

    return {
        detail: text || "Server ne empty response diya."
    };
}


// ------------------------------------------------------------
// AUTH UI
// ------------------------------------------------------------

function setAuthUI() {

    const loggedIn = Boolean(token);

    const loginButton = $("#openLogin");
    const logoutButton = $("#logoutBtn");

    if (loginButton) {
        loginButton.classList.toggle(
            "hidden",
            loggedIn
        );
    }

    if (logoutButton) {
        logoutButton.classList.toggle(
            "hidden",
            !loggedIn
        );
    }
}


// ------------------------------------------------------------
// INITIAL AUTH UI
// ------------------------------------------------------------

setAuthUI();


// ------------------------------------------------------------
// LOGIN MODAL
// ------------------------------------------------------------

if ($("#openLogin")) {

    $("#openLogin").onclick = () => {

        $("#loginOverlay").classList.remove("hidden");

    };
}


if ($("#closeLogin")) {

    $("#closeLogin").onclick = () => {

        $("#loginOverlay").classList.add("hidden");

    };
}


// ------------------------------------------------------------
// GOOGLE BUTTON
// ------------------------------------------------------------

if ($("#googleBtn")) {

    $("#googleBtn").onclick = () => {

        $("#authMsg").textContent =
            "Google OAuth is not configured yet. " +
            "Email and password login is available.";

    };
}


// ------------------------------------------------------------
// REGISTER / LOGIN MODE
// ------------------------------------------------------------

if ($("#registerMode")) {

    $("#registerMode").onclick = () => {

        registerMode = !registerMode;

        $("#registerMode").textContent =
            registerMode
                ? "Back to sign in"
                : "Create an account";

        $("#signinBtn").textContent =
            registerMode
                ? "Create account"
                : "Sign in";

        $("#authMsg").textContent = "";

    };
}


// ------------------------------------------------------------
// AUTHENTICATION
// ------------------------------------------------------------

if ($("#authForm")) {

    $("#authForm").onsubmit = async (event) => {

        event.preventDefault();

        const email =
            $("#email").value.trim();

        const password =
            $("#password").value;

        if (!email || !password) {

            $("#authMsg").textContent =
                "Email aur password enter karo.";

            return;
        }

        $("#signinBtn").disabled = true;

        $("#authMsg").textContent =
            registerMode
                ? "Creating account..."
                : "Signing in...";

        try {

            const endpoint =
                registerMode
                    ? "/api/register"
                    : "/api/login";

            const response = await api(
                endpoint,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        email,
                        password
                    })
                }
            );

            const data =
                await readResponse(response);

            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    `Authentication failed (${response.status})`
                );
            }

            if (!data.token) {

                throw new Error(
                    "Server ne login token return nahi kiya."
                );
            }

            token = data.token;

            localStorage.setItem(
                "deepfake_token",
                token
            );

            setAuthUI();

            $("#loginOverlay")
                .classList
                .add("hidden");

            $("#authMsg").textContent = "";

        } catch (error) {

            console.error(
                "Authentication error:",
                error
            );

            $("#authMsg").textContent =
                error.message ||
                "Authentication failed.";

        } finally {

            $("#signinBtn").disabled = false;

        }
    };
}


// ------------------------------------------------------------
// LOGOUT
// ------------------------------------------------------------

if ($("#logoutBtn")) {

    $("#logoutBtn").onclick = async () => {

        try {

            if (token) {

                await api(
                    "/api/logout",
                    {
                        method: "POST"
                    }
                );
            }

        } catch (error) {

            console.warn(
                "Logout API failed:",
                error
            );

        } finally {

            token = "";

            localStorage.removeItem(
                "deepfake_token"
            );

            setAuthUI();

        }
    };
}


// ------------------------------------------------------------
// HERO SCAN BUTTON
// ------------------------------------------------------------

if ($("#heroScan")) {

    $("#heroScan").onclick = () => {

        const detector =
            $("#detector");

        if (detector) {

            detector.scrollIntoView({
                behavior: "smooth"
            });

        }

        setTimeout(() => {

            if ($("#dropzone")) {
                $("#dropzone").click();
            }

        }, 500);

    };
}


// ------------------------------------------------------------
// IMAGE / VIDEO MODE
// ------------------------------------------------------------

$$(".mode-tabs button").forEach((button) => {

    button.onclick = () => {

        $$(".mode-tabs button")
            .forEach((item) => {

                item.classList.remove("active");

            });

        button.classList.add("active");

        mode =
            button.dataset.mode || "image";

        if ($("#fileInput")) {

            $("#fileInput").accept =
                mode === "image"
                    ? "image/*"
                    : "video/*";

        }

        resetFile();

    };

});


// ------------------------------------------------------------
// DROPZONE
// ------------------------------------------------------------

if ($("#dropzone")) {

    $("#dropzone").onclick = (event) => {

        if (event.target.closest("button")) {
            return;
        }

        $("#fileInput").click();

    };
}


// ------------------------------------------------------------
// BROWSE BUTTON
// ------------------------------------------------------------

if ($("#browseBtn")) {

    $("#browseBtn").onclick = (event) => {

        event.stopPropagation();

        $("#fileInput").click();

    };
}


// ------------------------------------------------------------
// FILE INPUT
// ------------------------------------------------------------

if ($("#fileInput")) {

    $("#fileInput").onchange = (event) => {

        const file =
            event.target.files[0];

        selectFile(file);

    };
}


// ------------------------------------------------------------
// DRAG ENTER / OVER
// ------------------------------------------------------------

["dragenter", "dragover"].forEach((eventName) => {

    if (!$("#dropzone")) return;

    $("#dropzone").addEventListener(
        eventName,
        (event) => {

            event.preventDefault();

            $("#dropzone")
                .classList
                .add("drag");

        }
    );

});


// ------------------------------------------------------------
// DRAG LEAVE / DROP
// ------------------------------------------------------------

["dragleave", "drop"].forEach((eventName) => {

    if (!$("#dropzone")) return;

    $("#dropzone").addEventListener(
        eventName,
        (event) => {

            event.preventDefault();

            $("#dropzone")
                .classList
                .remove("drag");

        }
    );

});


// ------------------------------------------------------------
// DROP FILE
// ------------------------------------------------------------

if ($("#dropzone")) {

    $("#dropzone").addEventListener(
        "drop",
        (event) => {

            const file =
                event.dataTransfer.files[0];

            selectFile(file);

        }
    );
}


// ------------------------------------------------------------
// FILE SELECTION
// ------------------------------------------------------------

function selectFile(file) {

    if (!file) return;

    const isImage =
        file.type.startsWith("image/");

    const isVideo =
        file.type.startsWith("video/");


    // Validate file type

    if (
        mode === "image" &&
        !isImage
    ) {

        alert(
            "Please choose an image file."
        );

        return;
    }


    if (
        mode === "video" &&
        !isVideo
    ) {

        alert(
            "Please choose a video file."
        );

        return;
    }


    selectedFile = file;


    // Update dropzone

    if ($("#dropzone")) {

        $("#dropzone")
            .classList
            .add("has-preview");

    }


    const previewWrap =
        $("#previewWrap");

    const imagePreview =
        $("#imagePreview");


    // Image preview

    if (mode === "image") {

        const previewURL =
            URL.createObjectURL(file);

        imagePreview.src =
            previewURL;

        previewWrap
            .classList
            .remove("hidden");

    }


    // Video

    else {

        imagePreview.removeAttribute(
            "src"
        );

        previewWrap
            .classList
            .remove("hidden");

    }


    // Badge

    if ($("#previewBadge")) {

        $("#previewBadge").textContent =
            mode === "image"
                ? "IMAGE READY"
                : "VIDEO READY";

    }


    // File information

    if ($("#fileMeta")) {

        const size =
            (
                file.size /
                1024 /
                1024
            ).toFixed(2);

        $("#fileMeta").textContent =
            `${file.name} · ${size} MB`;

        $("#fileMeta")
            .classList
            .remove("hidden");

    }


    // Enable analyze

    if ($("#analyzeBtn")) {

        $("#analyzeBtn").disabled = false;

    }


    resetSteps();

}


// ------------------------------------------------------------
// RESET FILE
// ------------------------------------------------------------

function resetFile() {

    if (
        $("#imagePreview") &&
        $("#imagePreview").src &&
        $("#imagePreview").src.startsWith("blob:")
    ) {

        URL.revokeObjectURL(
            $("#imagePreview").src
        );

    }


    if ($("#dropzone")) {

        $("#dropzone")
            .classList
            .remove(
                "has-preview",
                "scanning"
            );

    }


    if ($("#previewWrap")) {

        $("#previewWrap")
            .classList
            .add("hidden");

    }


    selectedFile = null;


    if ($("#fileInput")) {

        $("#fileInput").value = "";

    }


    if ($("#fileMeta")) {

        $("#fileMeta")
            .classList
            .add("hidden");

    }


    if ($("#analyzeBtn")) {

        $("#analyzeBtn").disabled = true;

    }


    resetSteps();

}


// ------------------------------------------------------------
// RESET PIPELINE
// ------------------------------------------------------------

function resetSteps() {

    $$(".step").forEach((step) => {

        step.classList.remove(
            "active",
            "done"
        );

        const status =
            step.querySelector("em");

        if (status) {

            status.textContent =
                "WAITING";

        }

    });


    if ($("#pipelineStatus")) {

        $("#pipelineStatus").textContent =
            "IDLE";

    }

}


// ------------------------------------------------------------
// PIPELINE DELAY
// ------------------------------------------------------------

function wait(ms) {

    return new Promise((resolve) => {

        setTimeout(resolve, ms);

    });

}


// ------------------------------------------------------------
// ANALYSIS
// ------------------------------------------------------------

async function analyze() {

    if (!selectedFile) {

        alert(
            "Please select an image or video first."
        );

        return;
    }


    if (!token) {

        $("#loginOverlay")
            .classList
            .remove("hidden");

        return;
    }


    if ($("#analyzeBtn")) {

        $("#analyzeBtn").disabled = true;

    }


    if ($("#dropzone")) {

        $("#dropzone")
            .classList
            .add("scanning");

    }


    const steps =
        $$(".step");


    if ($("#pipelineStatus")) {

        $("#pipelineStatus").textContent =
            "RUNNING";

    }


    try {

        // ----------------------------------------------------
        // STEP 1 - VALIDATE
        // ----------------------------------------------------

        await runStep(
            steps[0],
            "VALIDATING"
        );


        // ----------------------------------------------------
        // STEP 2 - FRAME EXTRACTION
        // ----------------------------------------------------

        await runStep(
            steps[1],
            "EXTRACTING"
        );


        // ----------------------------------------------------
        // STEP 3 - FACE LOCATION
        // ----------------------------------------------------

        await runStep(
            steps[2],
            "LOCATING"
        );


        // ----------------------------------------------------
        // STEP 4 - AI INFERENCE
        // ----------------------------------------------------

        await runStep(
            steps[3],
            "ANALYZING"
        );


        // ----------------------------------------------------
        // SEND ACTUAL FILE TO YOUR OWN API
        // ----------------------------------------------------

        const formData =
            new FormData();

        formData.append(
            "file",
            selectedFile
        );


        const endpoint =
            mode === "image"
                ? "/api/detect-image"
                : "/api/detect-video";


        if ($("#pipelineStatus")) {

            $("#pipelineStatus").textContent =
                "AI INFERENCE";

        }


        const response =
            await api(
                endpoint,
                {
                    method: "POST",
                    body: formData
                }
            );


        const data =
            await readResponse(response);


        if (!response.ok) {

            throw new Error(
                data.detail ||
                `Analysis failed (${response.status})`
            );

        }


        // ----------------------------------------------------
        // STEP 5 - VERDICT
        // ----------------------------------------------------

        if (steps[4]) {

            steps[4]
                .classList
                .add("done");

            const status =
                steps[4]
                    .querySelector("em");

            if (status) {

                status.textContent =
                    "DONE";

            }

        }


        if ($("#pipelineStatus")) {

            $("#pipelineStatus").textContent =
                "COMPLETE";

        }


        // ----------------------------------------------------
        // SHOW RESULT
        // ----------------------------------------------------

        showResult(data);

    }

    catch (error) {

        console.error(
            "DeepFake analysis error:",
            error
        );


        if ($("#pipelineStatus")) {

            $("#pipelineStatus").textContent =
                "ERROR";

        }


        $$(".step").forEach((step) => {

            step.classList.remove(
                "active"
            );

        });


        alert(
            error.message ||
            "Analysis failed."
        );

    }

    finally {

        if ($("#analyzeBtn")) {

            $("#analyzeBtn").disabled =
                false;

        }


        if ($("#dropzone")) {

            $("#dropzone")
                .classList
                .remove("scanning");

        }

    }

}


// ------------------------------------------------------------
// PIPELINE STEP ANIMATION
// ------------------------------------------------------------

async function runStep(step, runningText) {

    if (!step) return;

    step.classList.add("active");

    const status =
        step.querySelector("em");

    if (status) {

        status.textContent =
            runningText;

    }

    await wait(550);

    step.classList.remove("active");

    step.classList.add("done");

    if (status) {

        status.textContent =
            "DONE";

    }

}


// ------------------------------------------------------------
// ANALYZE BUTTON
// ------------------------------------------------------------

if ($("#analyzeBtn")) {

    $("#analyzeBtn").onclick =
        analyze;

}


// ------------------------------------------------------------
// RESULT MODAL
// ------------------------------------------------------------

function showResult(data) {

    if ($("#resultVerdict")) {

        $("#resultVerdict").textContent =
            data.verdict ||
            "Analysis complete";

    }


    if ($("#resultScore")) {

        const confidence =
            Number(data.confidence || 0);

        $("#resultScore").textContent =
            `${Math.round(
                confidence * 100
            )}%`;

    }


    if ($("#rMedia")) {

        $("#rMedia").textContent =
            data.media_type ||
            "-";

    }


    if ($("#rFrames")) {

        $("#rFrames").textContent =
            data.frames ??
            "-";

    }


    if ($("#rFaces")) {

        $("#rFaces").textContent =
            data.faces ??
            "-";

    }


    if ($("#rEngine")) {

        $("#rEngine").textContent =
            data.engine ||
            "-";

    }


    if ($("#rNote")) {

        $("#rNote").textContent =
            data.note ||
            "No additional forensic note.";

    }


    if ($("#resultModal")) {

        $("#resultModal")
            .classList
            .remove("hidden");

    }

}


// ------------------------------------------------------------
// CLOSE RESULT
// ------------------------------------------------------------

if ($("#closeResult")) {

    $("#closeResult").onclick = () => {

        $("#resultModal")
            .classList
            .add("hidden");

    };

}


if ($("#resultDone")) {

    $("#resultDone").onclick = () => {

        $("#resultModal")
            .classList
            .add("hidden");

    };

}


// ------------------------------------------------------------
// HISTORY
// ------------------------------------------------------------

if ($("#historyBtn")) {

    $("#historyBtn").onclick = async () => {

        if (!token) {

            $("#loginOverlay")
                .classList
                .remove("hidden");

            return;

        }


        $("#historyModal")
            .classList
            .remove("hidden");


        const historyBox =
            $("#historyList");


        historyBox.innerHTML =
            '<div class="history-empty">Loading...</div>';


        try {

            const response =
                await api(
                    "/api/history"
                );


            const data =
                await readResponse(response);


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Unable to load history."
                );

            }


            const rows =
                Array.isArray(data)
                    ? data
                    : [];


            if (!rows.length) {

                historyBox.innerHTML =
                    '<div class="history-empty">No scans yet.</div>';

                return;

            }


            historyBox.innerHTML =
                rows
                    .map((item) => {

                        return `
                            <div class="history-item">

                                <b>
                                    ${escapeHtml(
                                        item.filename
                                    )}
                                </b>

                                <small>
                                    ${escapeHtml(
                                        String(
                                            item.media_type ||
                                            ""
                                        ).toUpperCase()
                                    )}
                                    ·
                                    ${escapeHtml(
                                        item.verdict ||
                                        ""
                                    )}
                                    ·
                                    ${Math.round(
                                        Number(
                                            item.confidence ||
                                            0
                                        ) * 100
                                    )}%
                                    ·
                                    ${item.created_at
                                        ? new Date(
                                            item.created_at
                                        ).toLocaleString()
                                        : ""}
                                </small>

                            </div>
                        `;

                    })
                    .join("");

        }

        catch (error) {

            console.error(
                "History error:",
                error
            );


            historyBox.innerHTML = `
                <div class="history-empty">
                    ${escapeHtml(
                        error.message ||
                        "Unable to load history."
                    )}
                </div>
            `;

        }

    };

}


// ------------------------------------------------------------
// CLOSE HISTORY
// ------------------------------------------------------------

if ($("#closeHistory")) {

    $("#closeHistory").onclick = () => {

        $("#historyModal")
            .classList
            .add("hidden");

    };

}


// ------------------------------------------------------------
// HEALTH CHECK
// ------------------------------------------------------------

async function checkBackend() {

    try {

        const response =
            await api("/api/health");


        if (!response.ok) {

            console.warn(
                "DeepFake backend returned:",
                response.status
            );

            return false;

        }


        const data =
            await readResponse(response);


        console.log(
            "DeepFake backend:",
            data
        );


        return true;

    }

    catch (error) {

        console.warn(
            "DeepFake backend unavailable:",
            error.message
        );

        return false;

    }

}


// ------------------------------------------------------------
// HTML ESCAPE
// ------------------------------------------------------------

function escapeHtml(value) {

    return String(value)
        .replace(
            /[&<>'"]/g,
            (character) => {

                const entities = {

                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    "'": "&#39;",
                    '"': "&quot;"

                };

                return entities[character];

            }
        );

}


// ------------------------------------------------------------
// STARTUP
// ------------------------------------------------------------

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        setAuthUI();

        const backendOnline =
            await checkBackend();

        if (backendOnline) {

            console.log(
                "✓ DeepFake API connected"
            );

        } else {

            console.warn(
                "⚠ DeepFake API is offline"
            );

        }

    }
);