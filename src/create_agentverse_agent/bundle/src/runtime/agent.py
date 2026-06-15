# Copyright (c) 2026 Tejus Gupta
"""Agent runner: wires uAgents lifecycle, Postgres runtime, and protocol stubs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from shared.db import AgentRuntime, verify_schema
from shared.settings import SettingsError, get_settings
from uagents import Agent

from runtime.lifecycle.coordinator import coordinator_tick
from runtime.lifecycle.hooks import run_hooks
from runtime.payments.config import validate_payment_config
from runtime.payments.service import PaymentService
from runtime.pipeline import MessagePipeline
from runtime.protocols.chat import setup_chat_protocol
from runtime.protocols.payment import setup_payment_protocol
from runtime.registration import AGENTVERSE_README_PATH, register_agent_to_agentverse

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from shared.settings import Settings
    from shared.types import AgentDefinition
    from uagents import Context

_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class AgentRunner:
    """Wires developer :class:`AgentDefinition` into a runnable uAgents agent."""

    def __init__(
        self,
        definition: AgentDefinition,
        settings: Settings,
    ) -> None:
        """Initialize runner state (call :meth:`from_definition` to wire events).

        Args:
            definition: Developer agent hooks, handler, and scheduled tasks.
            settings: Loaded ``agent.yml`` and secrets.
        """
        self.definition = definition
        self.settings = settings
        self.worker_id = str(uuid4())
        self.runtime: AgentRuntime | None = None
        self._pipeline: MessagePipeline | None = None
        self.payment_service: PaymentService | None = None
        self._agent: Agent | None = None

    @classmethod
    def from_definition(
        cls,
        definition: AgentDefinition,
        settings: Settings | None = None,
    ) -> AgentRunner:
        """Build uAgents agent, protocols, lifecycle, and interval handlers.

        Args:
            definition: Developer agent definition.
            settings: Optional settings (loads ``agent.yml`` on first access).

        Returns:
            Wired runner ready for :meth:`run`.
        """
        resolved = settings or get_settings()
        runner = cls(definition=definition, settings=resolved)
        runner._build_agent()
        runner._wire_protocols()
        runner._wire_events()
        runner._wire_intervals()
        return runner

    @property
    def agent(self) -> Agent:
        """Underlying uAgents agent instance.

        Returns:
            The uAgents agent instance.

        Raises:
            RuntimeError: If the agent is not built.
        """
        if self._agent is None:
            msg = "Agent not built"
            raise RuntimeError(msg)
        return self._agent

    def _build_agent(self) -> None:

        agent_cfg = self.settings.agent
        runtime_cfg = self.settings.runtime

        agent_kwargs: dict[str, object] = {
            "name": agent_cfg.name,
            "port": agent_cfg.port,
            "seed": self.settings.secrets.AGENT_SEED,
            "handle": agent_cfg.handle,
            "description": agent_cfg.description,
            "avatar_url": agent_cfg.avatar_url,
            "banner_url": agent_cfg.banner_url,
            "log_level": _LOG_LEVELS[runtime_cfg.log_level],
            "network": runtime_cfg.network,
            "mailbox": runtime_cfg.mailbox,
            "handle_messages_concurrently": runtime_cfg.handle_messages_concurrently,
        }
        if AGENTVERSE_README_PATH.is_file():
            agent_kwargs["readme_path"] = str(AGENTVERSE_README_PATH)
        self._agent = Agent(**agent_kwargs)
        for log_namespace in ("runtime", "agent", "shared.db"):
            logging.getLogger(log_namespace).setLevel(
                _LOG_LEVELS[runtime_cfg.log_level]
            )

    @property
    def pipeline(self) -> MessagePipeline:
        """Message pipeline (available after :meth:`preflight`).

        Returns:
            The message pipeline.

        Raises:
            RuntimeError: If preflight has not completed.
        """
        if self._pipeline is None:
            msg = "Pipeline not initialized — call preflight() before run()"
            raise RuntimeError(msg)
        return self._pipeline

    async def preflight(self) -> None:
        """Open Postgres runtime and pipeline before uAgents accepts messages.

        Must complete before :meth:`run` so mailbox/chat handlers never see an
        uninitialized pipeline (uAgents starts receivers before ``on_startup``).

        Raises:
            RuntimeError: Payment configuration invalid or runtime init failed.
        """
        if self._pipeline is not None:
            logger.debug("preflight skipped — pipeline already initialized")
            return

        settings = self.settings
        agent = self.agent
        definition = self.definition

        logger.info(
            "preflight begin worker_id=%s agent=%s port=%s",
            self.worker_id,
            settings.agent.name,
            settings.agent.port,
        )
        logger.info("preflight step=open_runtime")
        self.runtime = await AgentRuntime.from_settings(
            worker_id=self.worker_id,
            settings=settings,
        )
        logger.info("preflight step=verify_schema")
        await verify_schema(self.runtime.pool)
        logger.info("preflight step=validate_payment")
        try:
            methods = validate_payment_config(settings)
        except SettingsError as exc:
            logger.exception("preflight step=validate_payment failed")
            msg = f"Payment configuration invalid: {exc}"
            raise RuntimeError(msg) from exc
        logger.info(
            "preflight step=validate_payment ok methods=%s",
            sorted(m.value for m in methods.allowed),
        )
        logger.info("preflight step=runtime_startup")
        worker = await self.runtime.startup()
        logger.info(
            "preflight step=runtime_ready worker_id=%s max_concurrent=%s draining=%s",
            worker.worker_id,
            worker.max_concurrent,
            worker.is_draining,
        )

        logger.info("preflight step=init_payment_service")
        self.payment_service = PaymentService(self.runtime)
        logger.info("preflight step=init_pipeline")
        self._pipeline = MessagePipeline(
            runtime=self.runtime,
            definition=definition,
            settings=settings,
            payment_service=self.payment_service,
            agent_address=agent.address,
            agent_wallet_address=str(agent.wallet.address()),
        )
        logger.info(
            "preflight complete worker_id=%s address=%s",
            self.worker_id,
            agent.address,
        )

    def _wire_protocols(self) -> None:
        self.agent.include(setup_chat_protocol(self), publish_manifest=True)
        self.agent.include(setup_payment_protocol(self), publish_manifest=True)

    def _wire_events(self) -> None:
        agent = self.agent
        definition = self.definition
        settings = self.settings
        runner = self

        async def on_startup(ctx: Context) -> None:
            logger.info(
                "startup begin worker_id=%s address=%s",
                runner.worker_id,
                agent.address,
            )

            logger.info("startup step=dev_hooks count=%s", len(definition.on_startup))
            await run_hooks(definition.on_startup)

            api_key = settings.secrets.AGENTVERSE_API_KEY
            if api_key:
                logger.info(
                    "startup step=agentverse_register handle=%s",
                    settings.agent.handle,
                )
                result = await register_agent_to_agentverse(
                    agent=agent,
                    user_token=api_key,
                    handle=settings.agent.handle,
                    settings=settings,
                )
                ctx.logger.info(
                    "Agentverse registration: action=%s success=%s detail=%s",
                    result.action,
                    result.success,
                    result.detail,
                )
            else:
                ctx.logger.info("AGENTVERSE_API_KEY not set — skipping registration")

            logger.info("startup complete worker_id=%s", runner.worker_id)

        async def on_shutdown(ctx: Context) -> None:
            logger.info("shutdown begin worker_id=%s", runner.worker_id)
            ctx.logger.info("Shutting down agent")
            logger.info("shutdown step=dev_hooks count=%s", len(definition.on_shutdown))
            await run_hooks(definition.on_shutdown, reverse=True)
            if runner.runtime is not None:
                try:
                    logger.info("shutdown step=runtime_drain")
                    await runner.runtime.shutdown(is_draining=True)
                    logger.info("shutdown step=runtime_drain complete")
                except Exception:
                    ctx.logger.exception(
                        "Runtime shutdown skipped — Postgres unavailable"
                    )
                logger.info("shutdown step=close_pool")
                await runner.runtime.close()
                runner.runtime = None
                runner._pipeline = None
                runner.payment_service = None
            logger.info("shutdown complete worker_id=%s", runner.worker_id)

        agent.on_event("startup")(on_startup)
        agent.on_event("shutdown")(on_shutdown)

    def _wire_intervals(self) -> None:
        agent = self.agent
        definition = self.definition
        coordinator_period = (
            self.settings.runtime.coordinator.heartbeat_interval_seconds
        )
        runner = self

        @agent.on_interval(period=coordinator_period)
        async def on_coordinator_tick(ctx: Context) -> None:
            if runner.runtime is None:
                logger.debug("coordinator tick skipped — runtime not ready")
                return
            await coordinator_tick(runner.runtime, ctx)

        for task in definition.scheduled:
            period = task.interval_seconds
            handler = task.handler
            task_name = task.name

            @agent.on_interval(period=period)
            async def on_scheduled_task(
                ctx: Context,
                _handler: Callable[..., object] = handler,
                _name: str | None = task_name,
            ) -> None:
                ctx.logger.debug("running scheduled task %s", _name)
                await run_hooks([_handler])

    def run(self) -> None:
        """Start the uAgents agent loop."""
        logger.info(
            "run begin agent=%s handle=%s worker_id=%s",
            self.settings.agent.name,
            self.settings.agent.handle,
            self.worker_id,
        )
        self.agent.run()


__all__ = ["AgentRunner"]
