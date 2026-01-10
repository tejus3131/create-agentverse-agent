import create_agentverse_agent


def test_package_imports() -> None:
    assert hasattr(create_agentverse_agent, "greet")


def test_version_available() -> None:
    assert isinstance(create_agentverse_agent.__version__, str)
