from dana.config import Settings
from dana.doctor import _masked_token, connection_url


def test_masked_token_does_not_expose_full_secret():
    assert _masked_token("abcdefghijkl") == "abcd...ijkl"


def test_local_connector_url_is_masked_by_default():
    settings = Settings(
        auth_token="abcdefghijkl",
        public_host="node.tailnet.ts.net",
        public_port=443,
        deployment_mode="local",
    )
    assert connection_url(settings) == "https://node.tailnet.ts.net/abcd...ijkl/mcp"


def test_local_connector_url_can_be_shown_explicitly():
    settings = Settings(
        auth_token="abcdefghijkl",
        public_host="node.tailnet.ts.net",
        public_port=443,
        deployment_mode="local",
    )
    assert connection_url(settings, show_url=True) == "https://node.tailnet.ts.net/abcdefghijkl/mcp"


def test_server_connector_url_has_no_token():
    settings = Settings(
        auth_token="abcdefghijkl",
        public_host="mcp.example.com",
        deployment_mode="server",
    )
    assert connection_url(settings) == "https://mcp.example.com/mcp"
