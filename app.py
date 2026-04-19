from flask import Flask, render_template, request, jsonify
from chatbot import get_response

app = Flask(__name__)


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/chatbot")
def index():
    return render_template("chatbot.html")


@app.route("/get", methods=["POST"])
def chat():

    msg = request.form["msg"]

    response = get_response(msg)

    return str(response)


if __name__ == "__main__":
    app.run(debug=True)