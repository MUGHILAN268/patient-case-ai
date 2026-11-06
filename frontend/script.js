let questionCount = 4;
let progress = 20;
let conversation = [];
const API_BASE = "http://127.0.0.1:8000";

async function checkBackend() {
    const status = document.querySelector(".status");

    if (!status) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();
        const configured = response.ok && data.gemini_configured;

        status.innerHTML = `<span></span>${configured ? "AI Online" : "Add Gemini API key"}`;
        status.classList.toggle("warning", !configured);
    } catch (error) {
        status.innerHTML = "<span></span>Start FastAPI";
        status.classList.add("warning");
    }
}

function handleEnter(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}

function voiceInput() {
    const input = document.getElementById("messageInput");
    input.value = "I have stomach pain since 2 days.";
    input.focus();
    sendMessage();
}

function addMessage(text, type) {
    const chat = document.getElementById("chat");
    const message = document.createElement("div");
    message.className = type === "user" ? "message user" : "message ai";

    if (type === "ai") {
        message.innerHTML = `
            <div class="bot-avatar">AI</div>
            <div class="bubble">
                ${escapeHTML(text)}
            </div>
        `;
    } else {
        message.innerHTML = `
            <div class="bubble">
                ${escapeHTML(text)}
            </div>
        `;
    }

    chat.appendChild(message);
    chat.scrollTop = chat.scrollHeight;
}

function escapeHTML(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function updateProgress(nextProgress, nextQuestionCount) {
    const progressBar = document.getElementById("progressBar");
    const progressText = document.getElementById("progressText");
    const questionCountEl = document.getElementById("questionCount");

    progress = nextProgress;
    questionCount = nextQuestionCount;

    progressBar.style.width = `${progress}%`;
    progressText.textContent = `${progress}%`;
    questionCountEl.textContent = questionCount;
}

function updateSummaryFromMessage(message) {
    const complaintEl = document.getElementById("complaint");
    const historySummaryEl = document.getElementById("historySummary");
    const historyDetailEl = document.getElementById("historyDetail");
    const symptomTag1 = document.getElementById("symptomTag1");
    const symptomTag2 = document.getElementById("symptomTag2");
    const medicationSummaryEl = document.getElementById("medicationSummary");
    const allergySummaryEl = document.getElementById("allergySummary");
    const alertTextEl = document.getElementById("alertText");

    const lower = message.toLowerCase();

    if (lower.includes("stomach") || lower.includes("abdomen") || lower.includes("pain")) {
        complaintEl.textContent = "Abdominal pain";
    }

    if (lower.includes("2 days") || lower.includes("since")) {
        historySummaryEl.textContent = "Started 2 days ago";
        historyDetailEl.textContent = "Intermittent pain in lower abdomen.";
    }

    if (lower.includes("fever")) {
        symptomTag1.textContent = "Mild fever";
        alertTextEl.textContent = "Mild fever reported. Doctor review recommended.";
    }

    if (lower.includes("appetite") || lower.includes("loss of appetite")) {
        symptomTag2.textContent = "↓ Appetite";
    }

    if (lower.includes("paracetamol") || lower.includes("medication")) {
        medicationSummaryEl.textContent = "Paracetamol · Occasional";
    }

    if (lower.includes("allergy") || lower.includes("allergic")) {
        allergySummaryEl.textContent = "Allergy history noted";
    }
}

async function sendMessage() {
    const input = document.getElementById("messageInput");
    const message = input.value.trim();

    if (!message) {
        return;
    }

    addMessage(message, "user");
    conversation.push({ role: "user", message: message });
    input.value = "";
    updateSummaryFromMessage(message);

    const nextProgress = Math.min(progress + 20, 100);
    updateProgress(nextProgress, Math.min(questionCount + 1, 9));

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message,
                conversation: conversation
            })
        });

        const data = await response.json();

        if (response.ok && data.reply) {
            addMessage(data.reply, "ai");
            conversation.push({ role: "assistant", message: data.reply });
        } else {
            addMessage(data.detail || "Sorry, I could not process that.", "ai");
        }
    } catch (error) {
        console.error(error);
        addMessage("Backend connection failed. Please check that FastAPI is running.", "ai");
    }

}

async function generateConversationSummary() {
    if (!conversation.length) {
        addMessage("Please answer at least one interview question first.", "ai");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/summary`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ conversation })
        });
        const data = await response.json();

        if (!response.ok || !data.summary) {
            throw new Error(data.detail || "Summary generation failed.");
        }

        addMessage("Case summary generated and ready for doctor review.", "ai");
        document.getElementById("historyDetail").textContent = data.summary;
    } catch (error) {
        console.error(error);
        addMessage(error.message, "ai");
    }
}

checkBackend();
