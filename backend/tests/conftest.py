import os

# Mock agents sleep between steps; tests run them instantly.
os.environ["MOCK_AGENT_DELAY"] = "0"
# The API tests use default_agents(); keep them offline. Real agents are tested directly.
os.environ["MOCK_AGENTS"] = "1"
# httpx test clients use http://test as their base URL.
os.environ.setdefault("ALLOWED_HOSTS", "test,localhost,127.0.0.1")
