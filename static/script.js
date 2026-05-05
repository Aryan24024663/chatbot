
function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function formatBotMessage(message) {
    const blocks = message.split("\n\n").filter((block) => block.trim() !== "");

    return blocks
        .map((block) => {
            const escapedBlock = escapeHtml(block).replace(/\n/g, "<br>");

            if (block.startsWith("Source: ")) {
                return "<div class='bot-answer-source'>" + escapedBlock + "</div>";
            }

            return "<p class='bot-answer-paragraph'>" + escapedBlock + "</p>";
        })
        .join("");
}

function sendMessage(){

    let inputField = document.getElementById("userInput");
    let message = inputField.value;

    if(message.trim() === "") return;

    let chatbox = document.getElementById("chatbox");

    chatbox.innerHTML += "<div class='user'><b>You:</b> " + escapeHtml(message) + "</div>";

    fetch("/get", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: "msg=" + encodeURIComponent(message)
    })
    .then(response => response.text())
    .then(data => {

        chatbox.innerHTML += "<div class='bot'><b>Bot:</b> " + formatBotMessage(data) + "</div>";

        chatbox.scrollTop = chatbox.scrollHeight;
    });

    inputField.value = "";
}

document.addEventListener("DOMContentLoaded", function () {
    const inputField = document.getElementById("userInput");

    if (!inputField) return;

    inputField.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });
});
