from flask import Flask, render_template, request, jsonify
from chatbot import get_response

# Create the Flask application object that handles routes and requests.
app = Flask(__name__)


# Home page route. This loads the main landing page template.
@app.route("/")
def home():
    return render_template("home.html")


# Chatbot page route. This loads the page that contains the chat interface.
@app.route("/chatbot")
def index():
    return render_template("chatbot.html")


# Chat endpoint used by the frontend. It receives the user's message,
# sends it to the chatbot logic, and returns the chatbot's answer.
@app.route("/get", methods=["POST"])
def chat():

    # Read the message sent from the chat form.
    msg = request.form["msg"]

    # Generate a response using the document-aware chatbot function.
    response = get_response(msg)

    # Send the answer back to the browser as plain text.
    return str(response)


# Start the Flask development server when this file is run directly.
if __name__ == "__main__":
    app.run(debug=True)
