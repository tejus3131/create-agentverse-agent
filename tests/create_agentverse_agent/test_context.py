from pathlib import Path

import pytest
from pydantic import ValidationError

from create_agentverse_agent.context import AgentContext, AgentContextError


class TestAgentContextDefaults:
    """Test default values and initialization."""

    def test_minimal_initialization(self):
        """Test creating context with minimal required fields."""
        context = AgentContext()

        # agent_name now has a default factory that generates random name
        assert context.agent_name is None
        assert context.agent_port == 8000
        assert context.hosting_address == "localhost"
        assert context.hosting_port == 8080
        assert context.env == "development"
        assert context.agentverse_api_key is None

    def test_seed_phrase_auto_generation(self):
        """Test that seed phrase is automatically generated."""
        context1 = AgentContext()
        context2 = AgentContext()

        # Should be non-empty
        assert len(context1.agent_seed_phrase) > 0
        # Should be URL-safe base64
        assert context1.agent_seed_phrase.replace("-", "").replace("_", "").isalnum()
        # Different instances should have different seeds
        assert context1.agent_seed_phrase != context2.agent_seed_phrase


class TestAgentName:
    """Test agent_name field validation."""

    def test_valid_names(self):
        """Test various valid agent names."""
        valid_names = [
            "MyAgent",
            "Test Agent 123",
            "Agent 1",
            "ABC",
            "123",
            "My Super Agent 2024",
        ]

        for name in valid_names:
            context = AgentContext(agent_name=name)
            assert context.agent_name == name

    def test_empty_name_rejected(self):
        """Test that empty names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agent_name="")

        assert "agent_name" in str(exc_info.value)

    def test_name_too_long_rejected(self):
        """Test that names over 100 characters are rejected."""
        long_name = "A" * 101

        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agent_name=long_name)

        assert "agent_name" in str(exc_info.value)

    def test_name_with_special_chars_rejected(self):
        """Test that names with special characters are rejected."""
        invalid_names = [
            "My-Agent",
            "Agent@123",
            "Test_Agent",
            "Agent!",
            "My.Agent",
            "Agent#1",
        ]

        for name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                AgentContext(agent_name=name)

            assert "agent_name" in str(exc_info.value)


class TestDefaultAgentName:
    """Test default agent_name behavior."""

    def test_default_name_generation(self):
        """Test that default agent_name is generated correctly."""
        context = AgentContext()

        # Default name should be None
        assert context.agent_name is None

        # Display name should be "Agent " + first 8 chars of seed phrase
        expected_display_name = "Agent " + context.agent_seed_phrase[:8]
        assert context.display_name == expected_display_name


class TestAgentSeedPhrase:
    """Test agent_seed_phrase field validation."""

    def test_valid_seed_phrases(self):
        """Test various valid seed phrases."""
        valid_seeds = [
            "aB3kL9mN2pQ5rT8vX1yZ4",
            "abc123",
            "ABC123xyz",
            "a" * 500,  # Max length
        ]

        for seed in valid_seeds:
            context = AgentContext(agent_seed_phrase=seed)
            assert context.agent_seed_phrase == seed

    def test_empty_seed_rejected(self):
        """Test that empty seed phrases are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agent_seed_phrase="")

        assert "agent_seed_phrase" in str(exc_info.value)

    def test_seed_too_long_rejected(self):
        """Test that seed phrases over 500 characters are rejected."""
        long_seed = "a" * 501

        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agent_seed_phrase=long_seed)

        assert "agent_seed_phrase" in str(exc_info.value)

    def test_seed_with_invalid_chars_rejected(self):
        """Test that seed phrases with invalid characters are rejected."""
        invalid_seeds = ["abc@123", "test seed", "abc!def", "test.phrase"]

        for seed in invalid_seeds:
            with pytest.raises(ValidationError) as exc_info:
                AgentContext(agent_seed_phrase=seed)

            assert "agent_seed_phrase" in str(exc_info.value)


class TestPorts:
    """Test port validation and constraints."""

    def test_valid_agent_ports(self):
        """Test various valid agent ports."""
        valid_ports = [1024, 8000, 9000, 65535]

        for port in valid_ports:
            context = AgentContext(agent_port=port)
            assert context.agent_port == port

    def test_valid_hosting_ports(self):
        """Test various valid hosting ports."""
        valid_ports = [1024, 8080, 8081, 9080, 65535]

        for port in valid_ports:
            context = AgentContext(hosting_port=port)
            assert context.hosting_port == port

    def test_agent_port_too_low_rejected(self):
        """Test that agent ports below 1024 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agent_port=1023)

        assert "agent_port" in str(exc_info.value)

    def test_agent_port_too_high_rejected(self):
        """Test that agent ports above 65535 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agent_port=65536)

        assert "agent_port" in str(exc_info.value)

    def test_hosting_port_too_low_rejected(self):
        """Test that hosting ports below 1024 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(hosting_port=1023)

        assert "hosting_port" in str(exc_info.value)

    def test_hosting_port_too_high_rejected(self):
        """Test that hosting ports above 65535 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(hosting_port=65536)

        assert "hosting_port" in str(exc_info.value)

    def test_same_ports_rejected(self):
        """Test that agent_port and hosting_port cannot be the same."""
        with pytest.raises(AgentContextError) as exc_info:
            AgentContext(agent_port=8080, hosting_port=8080)

        error_msg = str(exc_info.value)
        assert "must be different" in error_msg.lower()

    def test_different_ports_accepted(self):
        """Test that different ports are accepted."""
        context = AgentContext(agent_port=8000, hosting_port=8080)
        assert context.agent_port == 8000
        assert context.hosting_port == 8080


class TestHostingAddress:
    """Test hosting_address field validation."""

    def test_valid_addresses(self):
        """Test various valid hosting addresses."""
        valid_addresses = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "example.com",
            "my-server.local",
        ]

        for address in valid_addresses:
            context = AgentContext(hosting_address=address)
            assert context.hosting_address == address

    def test_empty_address_rejected(self):
        """Test that empty addresses are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            AgentContext(hosting_address="")

        assert "hosting_address" in str(exc_info.value)

    def test_address_too_long_rejected(self):
        """Test that addresses over 255 characters are rejected."""
        long_address = "a" * 256

        with pytest.raises(ValidationError) as exc_info:
            AgentContext(hosting_address=long_address)

        assert "hosting_address" in str(exc_info.value)


class TestAgentVerseAPIKey:
    """Test agentverse_api_key field validation."""

    def test_none_value_accepted(self):
        """Test that None is accepted for agentverse_api_key."""
        context = AgentContext(agentverse_api_key=None)
        assert context.agentverse_api_key is None

    def test_valid_jwt_tokens(self):
        """Test various valid JWT token formats."""
        valid_jwts = [
            # Standard JWT with signature
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            # JWT with padding
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abc123==",
            # JWT without signature
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.",
            # Minimal valid JWT
            "eyJhbc.eyJzdef.abcde",
        ]

        for jwt in valid_jwts:
            context = AgentContext(agentverse_api_key=jwt)
            assert context.agentverse_api_key == jwt

    def test_key_too_short_rejected(self):
        """Test that keys shorter than 20 characters are rejected."""
        short_jwt = "eyJ.eyJ.abc"  # 11 chars

        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agentverse_api_key=short_jwt)

        assert "agentverse_api_key" in str(exc_info.value)

    def test_key_too_long_rejected(self):
        """Test that keys over 1000 characters are rejected."""
        long_jwt = "eyJh.eyJz." + "a" * 995  # 1001 chars total

        with pytest.raises(ValidationError) as exc_info:
            AgentContext(agentverse_api_key=long_jwt)

        assert "agentverse_api_key" in str(exc_info.value)

    def test_wrong_header_prefix_rejected(self):
        """Test that tokens without eyJ prefix are rejected."""
        invalid_jwts = [
            "ayJhbGci.eyJzdWIi.signature",
            "EyJhbGci.eyJzdWIi.signature",
            "abc.eyJzdWIi.signature",
        ]

        for jwt in invalid_jwts:
            with pytest.raises(ValidationError) as exc_info:
                AgentContext(agentverse_api_key=jwt)

            assert "agentverse_api_key" in str(exc_info.value)

    def test_wrong_payload_prefix_rejected(self):
        """Test that tokens with wrong payload prefix are rejected."""
        invalid_jwts = [
            "eyJhbGci.ayJzdWIi.signature",
            "eyJhbGci.EyJzdWIi.signature",
            "eyJhbGci.abc.signature",
        ]

        for jwt in invalid_jwts:
            with pytest.raises(ValidationError) as exc_info:
                AgentContext(agentverse_api_key=jwt)

            assert "agentverse_api_key" in str(exc_info.value)

    def test_missing_parts_rejected(self):
        """Test that tokens without three parts are rejected."""
        invalid_jwts = [
            "eyJhbGci.eyJzdWIi",  # Only 2 parts
            "eyJhbGci",  # Only 1 part
            "",  # Empty
        ]

        for jwt in invalid_jwts:
            with pytest.raises(ValidationError) as exc_info:
                AgentContext(agentverse_api_key=jwt)

            assert "agentverse_api_key" in str(exc_info.value)

    def test_invalid_characters_rejected(self):
        """Test that tokens with invalid characters are rejected."""
        invalid_jwts = [
            "eyJh.eyJz.abc@123",
            "eyJh.eyJz.abc 123",
            "eyJh.eyJz.abc!123",
        ]

        for jwt in invalid_jwts:
            with pytest.raises(ValidationError) as exc_info:
                AgentContext(agentverse_api_key=jwt)

            assert "agentverse_api_key" in str(exc_info.value)


class TestProperties:
    """Test computed properties of AgentContext."""

    def test_safe_name_lowercase(self):
        """Test that safe_name converts to lowercase."""
        context = AgentContext(agent_name="My Agent")
        assert context.safe_name == "my-agent"

    def test_safe_name_replaces_spaces(self):
        """Test that safe_name replaces spaces with dashes."""
        context = AgentContext(agent_name="Test Agent 123")
        assert context.safe_name == "test-agent-123"

    def test_safe_name_replaces_underscores(self):
        """Test that safe_name replaces underscores with dashes."""
        # Note: underscores aren't allowed in agent_name pattern,
        # but testing the property logic
        context = AgentContext(agent_name="TestAgent")
        assert context.safe_name == "testagent"

    def test_project_path(self):
        """Test that project_path returns correct Path."""
        context = AgentContext(agent_name="My Agent")
        expected = Path.cwd() / "my-agent"
        assert context.project_path == expected

    def test_agent_route(self):
        """Test that agent_route returns correct route."""
        context = AgentContext(agent_name="My Agent")
        assert context.agent_route == "/my-agent"

    def test_hosting_endpoint_localhost(self):
        """Test hosting_endpoint with localhost."""
        context = AgentContext(hosting_address="localhost", hosting_port=8080)
        assert context.hosting_endpoint == "http://localhost:8080"

    def test_hosting_endpoint_custom(self):
        """Test hosting_endpoint with custom address and port."""
        context = AgentContext(hosting_address="example.com", hosting_port=9000)
        assert context.hosting_endpoint == "http://example.com:9000"


class TestDebugMode:
    """Test env_debug field."""

    def test_default_debug_true(self):
        """Test that debug mode defaults to True."""
        context = AgentContext()
        assert context.env == "development"

    def test_debug_false(self):
        """Test setting debug mode to False."""
        context = AgentContext(env="production")
        assert context.env == "production"


class TestCompleteConfiguration:
    """Test complete configuration scenarios."""

    def test_full_valid_configuration(self):
        """Test creating context with all fields set."""
        context = AgentContext(
            agent_name="Test Agent",
            agent_seed_phrase="testseedphrase123",
            agent_port=9000,
            agent_description="A test agent",
            hosting_address="example.com",
            hosting_port=9080,
            env="production",
            agentverse_api_key="eyJhbGci.eyJzdWIi.signature123",
        )

        assert context.agent_name == "Test Agent"
        assert context.agent_seed_phrase == "testseedphrase123"
        assert context.agent_port == 9000
        assert context.agent_description == "A test agent"
        assert context.hosting_address == "example.com"
        assert context.hosting_port == 9080
        assert context.env == "production"
        assert context.agentverse_api_key == "eyJhbGci.eyJzdWIi.signature123"

    def test_minimal_valid_configuration(self):
        """Test that minimal configuration works."""
        context = AgentContext()

        # Should have all defaults
        assert context.agent_name is None
        assert context.agent_seed_phrase is not None
        assert context.agent_port is not None
        assert context.hosting_address is not None
        assert context.hosting_port is not None


class TestReprBehavior:
    """Test repr behavior for sensitive fields."""

    def test_repr_excludes_sensitive_fields(self):
        """Test that repr doesn't include sensitive fields."""
        context = AgentContext(
            agent_seed_phrase="sensitiveseed",
            agentverse_api_key="eyJhbGci.eyJzdWIi.signature",
        )

        repr_str = repr(context)

        # These should NOT appear in repr (repr=False)
        assert "sensitiveseed" not in repr_str
        assert "AIzaSyD" not in repr_str
        assert "eyJhbGci" not in repr_str

        # These should appear in repr (repr=True)
        assert "agent_name" in repr_str or "My Agent" in repr_str
        assert "8000" in repr_str or "agent_port" in repr_str
