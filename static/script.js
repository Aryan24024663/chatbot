
function sendMessage(){

    let inputField = document.getElementById("userInput");
    let message = inputField.value;

    if(message.trim() === "") return;

    let chatbox = document.getElementById("chatbox");

    chatbox.innerHTML += "<div class='user'><b>You:</b> " + message + "</div>";

    fetch("/get", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: "msg=" + encodeURIComponent(message)
    })
    .then(response => response.text())
    .then(data => {

        chatbox.innerHTML += "<div class='bot'><b>Bot:</b> " + data + "</div>";

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
