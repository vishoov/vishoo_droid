import os
from flask import Flask, request, jsonify
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import InstallationStore, Installation
from slack_sdk import WebClient
from slack_sdk.oauth.state_store import FileOAuthStateStore
from slack_sdk.errors import SlackApiError
from functions import draft_email  # Import the draft_email function
from slack_bolt.middleware import RequestVerification



# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Set Slack API credentials
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")


def get_bot_user_id(team_id: str):
    try:
        latest_installation = installation_store.find_installation(team_id=team_id)
        if latest_installation and latest_installation.bot_token:
            slack_client = WebClient(token=latest_installation.bot_token)
            response = slack_client.auth_test()
            return response["user_id"]
    except Exception as e:
        print(f"Error getting bot ID: {e}")
    return None

# Set the bot user ID




# Flask app initialization
flask_app = Flask(__name__)

state_store = FileOAuthStateStore(
    expiration_seconds=600,
    base_dir="./states"  # Directory to store state files
)
# Dummy in-memory installation store
from typing import Optional

class DummyInstallationStore(InstallationStore):
    def __init__(self):
        self.installations = {}
    
    def save(self, installation: Installation):
        # Store both team and enterprise installations
        key = f"team_{installation.team_id}" if installation.team_id else f"ent_{installation.enterprise_id}"
        self.installations[key] = {
            "bot_token": installation.bot_token,
            "bot_id": installation.bot_id,
            "bot_user_id": installation.bot_user_id,
            "team_id": installation.team_id,
            "enterprise_id": installation.enterprise_id,
            "user_id": installation.user_id  # Critical for user context
        }

    def find_installation(self, **kwargs):
        team_id = kwargs.get("team_id")
        enterprise_id = kwargs.get("enterprise_id")
        key = f"team_{team_id}" if team_id else f"ent_{enterprise_id}"
        data = self.installations.get(key)
        return Installation(**data) if data else None

# Initialize the dummy installation store
installation_store = DummyInstallationStore()

# Configure OAuth settings with the custom installation store
oauth_settings = OAuthSettings(
    client_id=SLACK_CLIENT_ID,
    client_secret=SLACK_CLIENT_SECRET,
    scopes=[
        "app_mentions:read",
        "chat:write",
        "commands",
        "team:read"  # Required for workspace context
    ],
    installation_store=installation_store,
    state_store=state_store,
    redirect_uri_path="/slack/oauth_redirect",
    install_path="/slack/install",
    user_token_resolution="none",
    token_rotation_expiration_minutes=60,
    installation_store_bot_only=False
)




# Initialize the Slack app with OAuth settings
slack_app = App(
    signing_secret=SLACK_SIGNING_SECRET,
    oauth_settings=oauth_settings,
)


from slack_bolt.authorization import AuthorizeResult
from slack_bolt.response import BoltResponse
@slack_app.middleware
def handle_authorization(logger, req, next):
    try:
        context = req.context
        print(f"DEBUG: context.enterprise_id = {context.enterprise_id}, context.team_id = {context.team_id}, context.is_enterprise_install = {context.is_enterprise_install}") 
        installation = installation_store.find_installation(
            enterprise_id=context.enterprise_id,
            team_id=context.team_id,
            is_enterprise_install=context.is_enterprise_install
        )
        print(f"DEBUG: installation (in handle_authorization) = {installation}")
        
        if installation and installation.bot_token:
            print(f"DEBUG: installation.bot_token = {installation.bot_token}")  # ADD THIS LINE
            print(f"DEBUG: installation.bot_id = {installation.bot_id}")        # ADD THIS LINE
            print(f"DEBUG: installation.bot_user_id = {installation.bot_user_id}") # ADD THIS LINE
            # Verify token validity
            try:
                WebClient(token=installation.bot_token).auth_test()
            except SlackApiError as e:
                logger.error(f"Invalid bot token: {e}")
                installation_store.delete_installation(installation)
                raise ValueError("Bot token invalid")

            context.set_authorize_result(AuthorizeResult(
                enterprise_id=installation.enterprise_id,
                team_id=installation.team_id,
                bot_token=installation.bot_token,
                bot_id=installation.bot_id,
                bot_user_id=installation.bot_user_id
            ))
            return next()
        else:
            logger.error("No valid installation found")
            return BoltResponse(
                status=401,
                body="App not properly installed - reinstall required"
            )
    except Exception as e:
        logger.error(f"Authorization error: {str(e)}")
        return BoltResponse(
            status=500,
            body="Authorization system error"
        )



# SlackRequestHandler for Flask integration
handler = SlackRequestHandler(slack_app)

@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    # Parse the incoming JSON payload
    payload = request.json
    # print(f"DEBUG: payload = {payload}")
    # Check if this is a URL verification challenge
    if payload.get("type") == "url_verification":
        # Respond with the challenge token
        return jsonify({"challenge": payload["challenge"]})
    
    # Handle other event types here
    # ...
    # Pass the request to the Bolt app
    response = handler.handle(request)
    # Return a 200 OK for other event types
    return "", 200



@flask_app.route("/slack/install", methods=["GET"])
def slack_install():
    """
    Route for handling Slack app installations.
    Redirects users to Slack's OAuth flow.
    """
    return handler.handle(request)


from slack_sdk.oauth.token_rotation import TokenRotator

# Replace the current token rotation middleware with this:

from datetime import datetime, timedelta

@slack_app.middleware
def handle_token_rotation(logger, body, next):
    try:
        # Get installation data
        installation = installation_store.find_installation(
            team_id=body.get("team_id"),
            enterprise_id=body.get("enterprise_id")
        )
        
        if installation:
            # Check if rotation is needed (within 2 hours of expiration)
            if installation.bot_token_expires_at:
                expires_at = datetime.fromtimestamp(installation.bot_token_expires_at)
                if datetime.now() + timedelta(hours=2) > expires_at:
                    # Perform actual token rotation
                    refreshed = token_rotator.perform_token_rotation(
                        installation=installation,
                        minutes_before_expiration=120
                    )
                    if refreshed:
                        installation_store.save(refreshed)
            
            # Also check user token if needed
            if installation.user_token_expires_at:
                expires_at = datetime.fromtimestamp(installation.user_token_expires_at)
                if datetime.now() + timedelta(hours=2) > expires_at:
                    refreshed = token_rotator.perform_token_rotation(
                        installation=installation,
                        minutes_before_expiration=120
                    )
                    if refreshed:
                        installation_store.save(refreshed)

        return next()
    
    except Exception as e:
        logger.error(f"Token rotation error: {str(e)}")
        return BoltResponse(
            status=500,
            body="Token rotation failed"
        )


token_rotator = TokenRotator(
    client_id=SLACK_CLIENT_ID,
    client_secret=SLACK_CLIENT_SECRET
)


@flask_app.route("/slack/oauth_redirect", methods=["GET"])
def slack_oauth_redirect():
    try:
        return handler.handle(request)
    except Exception as e:
        print(f"OAuth error: {str(e)}")
        return "OAuth flow failed", 500


@slack_app.event("app_mention")
def handle_mentions(event, client, ack, req):
    ack()
    try:
        # print(f"DEBUG: Received app_mention event: {event}")  # Log the full event payload

        team_id = event.get("team_id")
        installation = req.context.authorize_result

        if not installation or not installation.bot_token:
            raise ValueError("Bot installation incomplete")

        bot_user_id = installation.bot_user_id
        print(f"DEBUG: Bot user ID: {bot_user_id}")  # Log bot user ID

        text = event["text"].strip()
        print(f"DEBUG: Mention text: {text}")  # Log the text of the mention

        response = draft_email(text, team_id)
        # response = "recieved"
        print(f"DEBUG: Draft email response: {response}")  # Log the response from draft_email

        client.chat_postMessage(
            channel=event["channel"],
            text=response,
        )
    except Exception as e:
        print(f"Error handling mention: {str(e)}")
        client.chat_postMessage(
            channel=event["channel"],
            text="Out of Credits"
        )




@slack_app.event("app_uninstalled")
def handle_uninstall(event, context):
    team_id = event.get("team_id")
    installation_store.delete_installation(
        enterprise_id=context.enterprise_id,
        team_id=team_id
    )

if __name__ == "__main__":
    flask_app.run(port=3000, debug=True)
