# Copyright (c) 2026 Tejus Gupta
"""Chat protocol — maps uAgents messages to :class:`MessagePipeline`."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    EndStreamContent,
    MetadataContent,
    Resource,
    ResourceContent,
    StartSessionContent,
    StartStreamContent,
    TextContent,
    chat_protocol_spec,
)

from runtime.payload import chat_payload_from_message
from runtime.protocols.cards import try_parse_card_metadata
from runtime.protocols.mentions import strip_leading_agent_mention
from shared.db import InboundMessage
from shared.types import Resource as DevResource

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from runtime.agent import AgentRunner


async def extract_message_context(
    *,
    ctx: Context,
    sender: str,
    msg: ChatMessage,
    agent_address: str | None = None,
    agent_handle: str | None = None,
) -> tuple[str, list[dict[str, str]] | None, dict[str, Any] | None]:
    """Extract text, resources, and optional card selection from ``ChatMessage``.

    Returns:
        Tuple of text, resource dicts, optional card_selection dict.
    """
    text_parts: list[str] = []
    resources: list[dict[str, str]] = []
    card_selection: dict[str, Any] | None = None

    for item in msg.content:
        try:
            if isinstance(item, TextContent) and item.text:
                text_parts.append(item.text)
            elif isinstance(item, ResourceContent) and item.resource:
                wire_resources = (
                    [item.resource]
                    if isinstance(item.resource, Resource)
                    else list(item.resource)
                )
                for res in wire_resources:
                    try:
                        dev = DevResource(
                            uri=res.uri,
                            mime_type=res.metadata.get(
                                "mime_type", "application/octet-stream"
                            ),
                        )
                        resources.append({"uri": dev.uri, "mime_type": dev.mime_type})
                    except ValidationError:
                        ctx.logger.exception(
                            "Invalid resource URI sender=%s msg_id=%s uri=%s",
                            sender,
                            msg.msg_id,
                            res.uri,
                        )
            elif isinstance(item, MetadataContent) and item.metadata:
                card_selection = try_parse_card_metadata(item.metadata)
            elif isinstance(item, StartSessionContent):
                await ctx.send(
                    sender,
                    MetadataContent(metadata={"attachments": "true"}),
                )
            elif isinstance(item, EndSessionContent):
                ctx.logger.debug("End session content sender=%s", sender)
            elif isinstance(item, StartStreamContent):
                ctx.logger.debug(
                    "Start stream sender=%s stream_id=%s",
                    sender,
                    item.stream_id,
                )
            elif isinstance(item, EndStreamContent):
                ctx.logger.debug(
                    "End stream sender=%s stream_id=%s",
                    sender,
                    item.stream_id,
                )
        except Exception:
            ctx.logger.exception(
                "Error processing chat content sender=%s msg_id=%s",
                sender,
                msg.msg_id,
            )

    text = "\n".join(text_parts).strip()
    text = strip_leading_agent_mention(
        text,
        agent_address=agent_address,
        agent_handle=agent_handle,
    )
    return (
        text,
        resources or None,
        card_selection,
    )


def setup_chat_protocol(runner: AgentRunner) -> Protocol:
    """Wire chat protocol handlers to the shared message pipeline.

    Args:
        runner: Agent runner holding the pipeline (available after startup).

    Returns:
        Configured uAgents chat protocol.
    """
    protocol = Protocol(spec=chat_protocol_spec)

    @protocol.on_message(ChatMessage)
    async def on_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
        logger.info(
            "chat received sender=%s msg_id=%s session=%s content_blocks=%s",
            sender,
            msg.msg_id,
            ctx.session,
            len(msg.content),
        )
        text, resources, card_selection = await extract_message_context(
            ctx=ctx,
            sender=sender,
            msg=msg,
            agent_address=runner.agent.address,
            agent_handle=runner.settings.agent.handle,
        )
        logger.info(
            "chat extracted sender=%s msg_id=%s text_len=%s resources=%s has_card=%s",
            sender,
            msg.msg_id,
            len(text),
            len(resources) if resources else 0,
            card_selection is not None,
        )
        payload = chat_payload_from_message(text=text, resources=resources)
        if card_selection is not None:
            payload["card_selection"] = card_selection

        inbound = InboundMessage(
            message_id=str(msg.msg_id),
            user_id=sender,
            session_id=str(ctx.session),
            protocol="chat",
            payload_json=payload,
        )
        logger.info("chat dispatch pipeline msg_id=%s", msg.msg_id)
        if runner._pipeline is None:  # noqa: SLF001
            logger.error(
                "chat dropped — preflight not complete msg_id=%s sender=%s",
                msg.msg_id,
                sender,
            )
            return
        await runner.pipeline.process_inbound(ctx, sender, inbound)
        logger.info("chat done msg_id=%s", msg.msg_id)

    @protocol.on_message(ChatAcknowledgement)
    async def on_chat_acknowledgement(
        ctx: Context,
        sender: str,
        msg: ChatAcknowledgement,
    ) -> None:
        ctx.logger.debug(
            "chat ack sender=%s acknowledged_msg_id=%s",
            sender,
            msg.acknowledged_msg_id,
        )

    return protocol
