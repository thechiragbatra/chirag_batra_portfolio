import os

# Mock agents sleep between steps; tests run them instantly.
os.environ["MOCK_AGENT_DELAY"] = "0"
