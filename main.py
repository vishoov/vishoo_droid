import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler 
from dotenv import find_dotenv, load_dotenv
from flask import Flask, request, jsonify
from functions import draft_email


load_dotenv(find_dotenv())


SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_USER_ID = os.getenv("SLACK_BOT_USER_ID")


flask_app = Flask(__name__)


app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET) 
handler = SlackRequestHandler(app)


def get_bot_user_id():
    """
    Get the bot user ID using the Slack API.
    Returns:
        str: The bot user ID.
    """
    try:
        slack_client = WebClient(token=SLACK_BOT_TOKEN)
        response = slack_client.auth_test()
        print("user_id: ", response["user_id"])
        return response["user_id"]
    except SlackApiError as e:
        print(f"Error: {e}")


def my_function(text):
    """
    Custom function to process the text and return a response.
    In this example, the function converts the input text to uppercase.

    Args:
        text (str): The input text to process.

    Returns:
        str: The processed text.
    """
    response = text.upper()
    return response


@app.event("app_mention")
def handle_mentions(body, say):
    """
    Event listener for mentions in Slack.
    When the bot is mentioned, this function processes the text and sends a response.

    Args:
        body (dict): The event data received from Slack.
        say (callable): A function for sending a response to the channel.
    """
    text = body["event"]["text"]
    mention = f"<@{SLACK_BOT_USER_ID}>"
    text = text.replace(mention, "").strip()
    response = draft_email(text)
    say(response)


@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handles incoming Slack events, including the initial challenge."""
    if request.method == "POST":
       
        if "challenge" in request.json:
            return jsonify({"challenge": request.json["challenge"]})
        else:
            return handler.handle(request)


@flask_app.route("/") 
def hello_world():
    return "Hello, World! Flask is running."



# if __name__ == "__main__":
#    flask_app.run(debug=True, port=8000)
