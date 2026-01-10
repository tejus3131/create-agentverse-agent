from create_agentverse_agent.core import greet


def test_greet_returns_string() -> None:
    result = greet()
    assert isinstance(result, str)


def test_greet_message() -> None:
    assert greet() == "Hello from create-agentverse-agent!"
