"""
Simple Flask API wrapper for local testing of bedrock-prompt-messager Lambda function.
This provides an HTTP interface that calls the Lambda handler directly.
"""

import json
import logging

from flask import Flask, request
from flask_cors import CORS
from main import lambda_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class MockLambdaContext:
    def __init__(self):
        self.function_name = "bedrock-prompt-messager"
        self.function_version = "1"
        self.remaining_time_in_millis = 30000
        self.aws_request_id = "local-test"


@app.route("/call-llm", methods=["POST", "OPTIONS"])
def call_llm():
    if request.method == "OPTIONS":
        response = (
            "",
            200,
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
                "Access-Control-Max-Age": "86400",
            },
        )
        return response

    try:
        # Create Lambda event from request
        event = {
            "httpMethod": "POST",
            "body": json.dumps(request.get_json()) if request.is_json else "{}",
            "headers": dict(request.headers),
        }

        context = MockLambdaContext()

        # Call Lambda handler
        response = lambda_handler(event, context)

        # Extract response
        status_code = response.get("statusCode", 200)
        body = response.get("body", "{}")

        # Parse body if it's a JSON string
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                pass

        return body, status_code

    except Exception as e:
        logger.exception(f"Error in call_llm: {e}")
        return {"error": str(e)}, 500


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "service": "bedrock-prompt-messager"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
