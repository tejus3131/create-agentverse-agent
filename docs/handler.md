---
layout: default
title: Handler Guide
nav_order: 8
---

# Handler Guide

Your agent logic lives in **`src/agent/handler.py`**. The runtime imports your `AgentDefinition` and calls it for each message.

Do not edit `src/runtime/` unless you are extending the framework.

---

## Minimal handler

```python
from shared import AgentDefinition, HandlerRequest, HandlerResponse, TextReply

def on_message(
    *, user_id: str, session_id: str, message_id: str, request: HandlerRequest
) -> HandlerResponse:
    text = getattr(request, "text", "") or ""
    return TextReply(text=f"You said: {text}")

definition = AgentDefinition(on_message=on_message)
```

The scaffold generates a fuller example with startup/shutdown hooks.

---

## AgentDefinition

```python
@dataclass
class AgentDefinition:
    on_message: MessageHandler
    on_startup: list[StartupHook] = []
    on_shutdown: list[ShutdownHook] = []
    scheduled: list[ScheduledTask] = []
```

| Field | Purpose |
|-------|---------|
| `on_message` | Handle inbound chat/payment updates (required) |
| `on_startup` | Run once when the agent starts |
| `on_shutdown` | Run once on graceful shutdown |
| `scheduled` | Periodic tasks (`ScheduledTask(interval, callback, name=...)`) |

Handlers can be sync or async. Sync handlers run in a thread pool.

---

## Inbound: HandlerRequest

`HandlerRequest` is `ChatInput | PaymentUpdate`.

### ChatInput

User chat message:

```python
class ChatInput:
    text: str | None
    resources: list[Resource] | None
    card_selection: CardSelection | None
```

Use `request.primary_text` for simple echo handlers. For interactive cards, see `shared/types.py` in your project.

### PaymentUpdate

Result after a payment flow:

```python
class PaymentUpdate:
    approved: bool
    reason: str | None
    transaction_id: str | None
```

Type guards: `is_chat_input(request)`, `is_payment_update(request)`.

---

## Outbound: HandlerResponse

`HandlerResponse` is `TextReply | PaymentRequest`.

### TextReply

```python
TextReply(
    text="Hello!",
    resources=None,   # optional attachments
    card=None,        # optional interactive card
)
```

### PaymentRequest

Ask the user to pay before continuing:

```python
PaymentRequest(
    amount=1.0,
    currency="FET",
    description="Premium feature",
    product_name="feature_x",
    service="my-agent",
)
```

Type guards: `is_text_reply(response)`, `is_payment_request(response)`.

---

## Where to look in your project

| File | Contents |
|------|----------|
| `src/agent/handler.py` | Your code (start here) |
| `src/shared/types.py` | Full type definitions, card models |
| `src/agent/__init__.py` | `from agent.handler import agent as definition` |

---

## Next steps

- [Configuration](configuration.md) — rate limits and payment methods
- [Architecture](architecture.md) — how the runtime calls your handler
