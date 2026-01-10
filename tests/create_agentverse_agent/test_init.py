import create_agentverse_agent


def test_package_imports() -> None:
    assert hasattr(create_agentverse_agent, "main")


def test_version_available() -> None:
    assert isinstance(create_agentverse_agent.__version__, str)


def test_entrypoint_runs():
    from create_agentverse_agent import main

    assert callable(main)
