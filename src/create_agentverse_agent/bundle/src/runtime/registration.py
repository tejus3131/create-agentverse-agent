# Copyright (c) 2026 Tejus Gupta
"""Smart Agentverse registration: fetch, compare, fill missing, or connect."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import aiohttp
from pydantic import BaseModel
from shared.settings import PROJECT_ROOT
from uagents.mailbox import AgentverseConnectRequest, register_in_agentverse
from uagents_core.registration import AgentProfile, RegistrationRequest

if TYPE_CHECKING:
    from uagents import Agent
    from uagents_core.config import AgentverseConfig
    from uagents_core.identity import Identity
    from uagents_core.types import AddressPrefix, AgentEndpoint

    from shared.settings import Settings


Action = Literal["noop", "registered", "updated", "failed"]

AGENTVERSE_README_PATH = PROJECT_ROOT / "AGENTVERSE.md"


def load_agentverse_readme(path: Path | None = None) -> str:
    """Load Agentverse profile readme from ``AGENTVERSE.md`` at project root."""
    readme_path = path or AGENTVERSE_README_PATH
    if not readme_path.is_file():
        return ""
    return readme_path.read_text(encoding="utf-8")


class AgentverseRegistrationDetails(BaseModel):
    """Desired Agentverse profile fields for an agent."""

    name: str
    handle: str | None = None
    description: str = ""
    readme: str = ""
    avatar_url: str = ""
    banner_url: str = ""
    metadata: dict[str, Any] | None = None
    agent_type: str = "mailbox"
    require_mailbox: bool = True


@dataclass
class AgentverseRegistrationResult:
    """Outcome of a smart Agentverse registration attempt."""

    action: Action
    success: bool
    detail: str | None = None
    missing_before: list[str] = field(default_factory=list)
    filled_fields: list[str] = field(default_factory=list)
    profile: dict[str, Any] | None = None


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _profile_from_record(record: dict[str, Any]) -> dict[str, Any]:
    profile = record.get("profile")
    return profile if isinstance(profile, dict) else {}


def list_missing_fields(
    record: dict[str, Any],
    desired: AgentverseRegistrationDetails,
) -> list[str]:
    """Return dotted field paths that are missing on Agentverse but desired locally."""
    missing: list[str] = []
    profile = _profile_from_record(record)

    if _is_blank(record.get("name")) and not _is_blank(desired.name):
        missing.append("name")
    if _is_blank(record.get("handle")) and not _is_blank(desired.handle):
        missing.append("handle")
    if desired.require_mailbox and _is_blank(record.get("redirect_url")):
        missing.append("redirect_url")

    profile_checks = {
        "profile.description": (profile.get("description"), desired.description),
        "profile.readme": (profile.get("readme"), desired.readme),
        "profile.avatar_url": (profile.get("avatar_url"), desired.avatar_url),
        "profile.banner_url": (profile.get("banner_url"), desired.banner_url),
    }
    for path, (current, target) in profile_checks.items():
        if _is_blank(current) and not _is_blank(target):
            missing.append(path)

    return missing


def is_registered(
    record: dict[str, Any], desired: AgentverseRegistrationDetails
) -> bool:
    """True when the remote record has the required Agentverse identity fields.

    Args:
        record: The remote record to check.
        desired: The desired registration details.

    Returns:
        True when the remote record has the required Agentverse identity fields.
    """
    if _is_blank(record.get("address")):
        return False
    if _is_blank(record.get("name")):
        return False
    if not _is_blank(desired.handle) and _is_blank(record.get("handle")):
        return False
    return not (desired.require_mailbox and _is_blank(record.get("redirect_url")))


def build_update_payload(
    record: dict[str, Any],
    desired: AgentverseRegistrationDetails,
) -> tuple[dict[str, Any], list[str]]:
    """Merge desired values into the remote record, filling only blank fields.

    Args:
        record: The remote record to update.
        desired: The desired registration details.

    Returns:
        A tuple containing the updated payload and the fields that were filled.
    """
    profile = _profile_from_record(record)
    filled: list[str] = []

    name = record.get("name") or desired.name
    if _is_blank(record.get("name")) and not _is_blank(desired.name):
        filled.append("name")

    handle = record.get("handle") or desired.handle
    if _is_blank(record.get("handle")) and not _is_blank(desired.handle):
        filled.append("handle")

    merged_profile = {
        "description": profile.get("description") or desired.description,
        "readme": profile.get("readme") or desired.readme,
        "avatar_url": profile.get("avatar_url") or desired.avatar_url,
        "banner_url": profile.get("banner_url") or desired.banner_url,
    }
    for key, current in profile.items():
        if key not in merged_profile and not _is_blank(current):
            merged_profile[key] = current

    for path, key, desired_value in (
        ("profile.description", "description", desired.description),
        ("profile.readme", "readme", desired.readme),
        ("profile.avatar_url", "avatar_url", desired.avatar_url),
        ("profile.banner_url", "banner_url", desired.banner_url),
    ):
        if _is_blank(profile.get(key)) and not _is_blank(desired_value):
            filled.append(path)

    payload = {
        "address": record["address"],
        "name": name,
        "handle": handle,
        "profile": merged_profile,
    }
    return payload, filled


async def fetch_agentverse_profile(
    session: aiohttp.ClientSession,
    agents_api: str,
    address: str,
    user_token: str,
) -> tuple[int, dict[str, Any] | None, str | None]:
    """Fetch an Agentverse profile. Returns status, body, and error detail.

    Args:
        session: The aiohttp ClientSession to use.
        agents_api: The URL of the Agentverse API.
        address: The address of the agent to fetch.
        user_token: The user token to use for authentication.

    Returns:
        A tuple containing the status, body, and error detail.
    """
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }
    async with session.get(f"{agents_api}/{address}", headers=headers) as response:
        text = await response.text()
        if response.status == 404:
            return response.status, None, "Agent not found"
        try:
            body = json.loads(text) if text else None
        except json.JSONDecodeError:
            return response.status, None, text
        if response.status != 200 or not isinstance(body, dict):
            detail = body.get("detail") if isinstance(body, dict) else text
            return response.status, None, str(detail)
        return response.status, body, None


async def update_agentverse_profile(
    session: aiohttp.ClientSession,
    agents_api: str,
    address: str,
    user_token: str,
    payload: dict[str, Any],
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Update an existing Agentverse profile via PUT.

    Args:
        session: The aiohttp ClientSession to use.
        agents_api: The URL of the Agentverse API.
        address: The address of the agent to update.
        user_token: The user token to use for authentication.
        payload: The payload to update the agentverse profile with.

    Returns:
        A tuple containing the success, error detail, and the updated record.
    """
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }
    async with session.put(
        f"{agents_api}/{address}",
        headers=headers,
        data=json.dumps(payload),
    ) as response:
        text = await response.text()
        if response.status != 200:
            try:
                body = json.loads(text)
                detail = body.get("detail") if isinstance(body, dict) else text
            except json.JSONDecodeError:
                detail = text
            return False, str(detail), None
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            return True, None, None
        return True, None, body if isinstance(body, dict) else None


def build_registration_request(
    *,
    address: str,
    desired: AgentverseRegistrationDetails,
    endpoints: list[AgentEndpoint],
    protocols: list[str],
    endpoint_url: str | None,
) -> RegistrationRequest:
    """Build the payload used by the full Agentverse connect flow.

    Args:
        address: The address of the agent to register.
        desired: The desired registration details.
        endpoints: The endpoints of the agent.
        protocols: The protocols of the agent.
        endpoint_url: The URL of the endpoint to use.

    Returns:
        The payload used by the full Agentverse connect flow.
    """
    return RegistrationRequest(
        address=address,
        name=desired.name,
        handle=desired.handle,
        url=endpoint_url,
        agent_type=desired.agent_type,
        profile=AgentProfile(
            description=desired.description,
            readme=desired.readme,
            avatar_url=desired.avatar_url,
            banner_url=desired.banner_url,
        ),
        endpoints=endpoints,
        protocols=protocols,
        metadata=desired.metadata,
    )


async def register_to_agentverse(
    *,
    identity: Identity,
    prefix: AddressPrefix,
    agentverse: AgentverseConfig,
    endpoints: list[AgentEndpoint],
    protocols: list[str],
    user_token: str,
    desired: AgentverseRegistrationDetails,
    endpoint_url: str | None = None,
    session: aiohttp.ClientSession | None = None,
) -> AgentverseRegistrationResult:
    """Register or reconcile an agent on Agentverse.

    Flow:
    1. GET current profile
    2. If not found -> full connect/register flow
    3. If found but missing required/mailbox fields -> full connect/register flow
    4. If found and only profile fields missing -> PUT fill-blanks update
    5. If complete -> noop

    Args:
        identity: The identity of the agent.
        prefix: The prefix of the agent.
        agentverse: The agentverse config.
        endpoints: The endpoints of the agent.
        protocols: The protocols of the agent.
        user_token: The user token to use for authentication.
        desired: The desired registration details.
        endpoint_url: The URL of the endpoint to use.
        session: The aiohttp ClientSession to use.

    Returns:
        The result of the registration.
    """
    owns_session = session is None
    client = session or aiohttp.ClientSession()
    address = identity.address
    endpoint = endpoint_url or (endpoints[0].url if endpoints else None)

    try:
        status, record, fetch_detail = await fetch_agentverse_profile(
            client,
            agentverse.agents_api,
            address,
            user_token,
        )
        if status not in {200, 404}:
            return AgentverseRegistrationResult(
                action="failed",
                success=False,
                detail=fetch_detail or f"Unexpected fetch status {status}",
            )

        if record is None:
            registration = build_registration_request(
                address=address,
                desired=desired,
                endpoints=endpoints,
                protocols=protocols,
                endpoint_url=endpoint,
            )
            connect_request = AgentverseConnectRequest(
                user_token=user_token,
                agent_type=desired.agent_type,
                endpoint=endpoint,
            )
            response = await register_in_agentverse(
                request=connect_request,
                identity=identity,
                prefix=prefix,
                agentverse=agentverse,
                agent_details=registration,
            )
            if not response.success:
                return AgentverseRegistrationResult(
                    action="failed",
                    success=False,
                    detail=response.detail,
                )
            _, fresh_record, _ = await fetch_agentverse_profile(
                client,
                agentverse.agents_api,
                address,
                user_token,
            )
            return AgentverseRegistrationResult(
                action="registered",
                success=True,
                missing_before=["agent"],
                filled_fields=["agent"],
                profile=fresh_record,
            )

        missing = list_missing_fields(record, desired)
        if not missing:
            return AgentverseRegistrationResult(
                action="noop",
                success=True,
                profile=record,
            )

        needs_connect = any(
            field_name in missing for field_name in ("name", "handle", "redirect_url")
        )
        if needs_connect or not is_registered(record, desired):
            registration = build_registration_request(
                address=address,
                desired=desired,
                endpoints=endpoints,
                protocols=protocols,
                endpoint_url=endpoint,
            )
            connect_request = AgentverseConnectRequest(
                user_token=user_token,
                agent_type=desired.agent_type,
                endpoint=endpoint,
            )
            response = await register_in_agentverse(
                request=connect_request,
                identity=identity,
                prefix=prefix,
                agentverse=agentverse,
                agent_details=registration,
            )
            if not response.success:
                return AgentverseRegistrationResult(
                    action="failed",
                    success=False,
                    detail=response.detail,
                    missing_before=missing,
                )
            _, fresh_record, _ = await fetch_agentverse_profile(
                client,
                agentverse.agents_api,
                address,
                user_token,
            )
            return AgentverseRegistrationResult(
                action="registered",
                success=True,
                missing_before=missing,
                filled_fields=missing,
                profile=fresh_record,
            )

        payload, filled_fields = build_update_payload(record, desired)
        updated, detail, updated_record = await update_agentverse_profile(
            client,
            agentverse.agents_api,
            address,
            user_token,
            payload,
        )
        if not updated:
            return AgentverseRegistrationResult(
                action="failed",
                success=False,
                detail=detail,
                missing_before=missing,
            )
        return AgentverseRegistrationResult(
            action="updated",
            success=True,
            missing_before=missing,
            filled_fields=filled_fields,
            profile=updated_record,
        )
    finally:
        if owns_session:
            await client.close()


def details_from_agent(
    agent: Agent,
    *,
    handle: str | None = None,
    settings: Settings | None = None,
) -> AgentverseRegistrationDetails:
    """Build desired registration details from settings and a uAgents Agent.

    Profile fields prefer ``agent.yml`` when *settings* is provided; readme comes
    from ``AGENTVERSE.md`` at project root, then the agent's loaded readme.

    Args:
        agent: The agent to build the registration details from.
        handle: The handle to use for the registration.
        settings: Loaded ``agent.yml`` config (recommended).

    Returns:
        The desired registration details.
    """
    agent_cfg = settings.agent if settings is not None else None
    resolved_handle = handle or (agent_cfg.handle if agent_cfg is not None else None)
    agent_readme = getattr(agent, "_readme", None) or ""
    readme = load_agentverse_readme() or agent_readme
    if agent_cfg is not None:
        return AgentverseRegistrationDetails(
            name=agent_cfg.name,
            handle=resolved_handle,
            description=agent_cfg.description,
            readme=readme,
            avatar_url=agent_cfg.avatar_url or "",
            banner_url=agent_cfg.banner_url or "",
            metadata=getattr(agent, "metadata", None) or None,
            agent_type="mailbox" if getattr(agent, "_use_mailbox", False) else "uagent",
            require_mailbox=bool(getattr(agent, "_use_mailbox", False)),
        )
    return AgentverseRegistrationDetails(
        name=agent.name,
        handle=resolved_handle,
        description=getattr(agent, "_description", None) or "",
        readme=readme,
        avatar_url=getattr(agent, "_avatar_url", None) or "",
        banner_url=getattr(agent, "_banner_url", None) or "",
        metadata=getattr(agent, "metadata", None) or None,
        agent_type="mailbox" if getattr(agent, "_use_mailbox", False) else "uagent",
        require_mailbox=bool(getattr(agent, "_use_mailbox", False)),
    )


async def register_agent_to_agentverse(
    agent: Agent,
    user_token: str,
    *,
    handle: str | None = None,
    settings: Settings | None = None,
    session: aiohttp.ClientSession | None = None,
) -> AgentverseRegistrationResult:
    """Convenience wrapper around register_to_agentverse for a uAgents Agent.

    Args:
        agent: The agent to register.
        user_token: The user token to use for authentication.
        handle: The handle to use for the registration.
        settings: Loaded ``agent.yml`` config for profile fields and readme path.
        session: The aiohttp ClientSession to use.

    Returns:
        The result of the registration.
    """
    desired = details_from_agent(agent, handle=handle, settings=settings)
    endpoint_url = agent._endpoints[0].url if agent._endpoints else None
    return await register_to_agentverse(
        identity=agent._identity,
        prefix=agent._prefix,
        agentverse=agent._agentverse,
        endpoints=agent._endpoints,
        protocols=list(agent.protocols.keys()),
        user_token=user_token,
        desired=desired,
        endpoint_url=endpoint_url,
        session=session,
    )
