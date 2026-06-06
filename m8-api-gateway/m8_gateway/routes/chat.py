"""OpenAI-compatible chat completions route.

WHAT: POST /v1/chat/completions endpoint that provides an OpenAI-compatible
      API surface. Accepts standard chat completion requests and forwards
      them to the M5 QA Engine for RAG-augmented responses.

WHY: OpenAI SDK compatibility is the primary API surface for M8. Any LLM
     client that supports custom base_url (OpenAI Python/JS SDKs, LangChain,
     LiteLLM, etc.) can point to M8 and use the Marine & Offshore Expert
     System without code changes — just swap the API key and base URL.

     The conversion from Pydantic schemas to contract dataclasses isolates
     M8's API surface from internal contract changes. If the contract
     evolves, only this conversion layer needs updating.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from contracts.qa_engine import ChatRequest, ChatResponse, Message

from m8_gateway.auth.key_manager import APIKey
from m8_gateway.auth.middleware import check_rate_limit, get_api_key
from m8_gateway.models.schemas import ChatCompletionRequest

router = APIRouter(tags=["Chat Completions"])


def _to_contract_request(schema: ChatCompletionRequest) -> ChatRequest:
    """Convert a Pydantic ChatCompletionRequest to a contract ChatRequest dataclass.

    WHAT: Maps each field from the Pydantic schema (used by FastAPI for request
          body validation) to the contract ChatRequest dataclass (used by the
          QA Engine). Also converts nested MessageSchema objects to contract
          Message dataclasses.

    WHY: FastAPI needs Pydantic models for validation, but the QA Engine
         protocol expects contract dataclasses. This conversion isolates
         the route layer from the engine layer — neither needs to know
         about the other's data representation.

    Args:
        schema: The validated Pydantic request body.

    Returns:
        A contract ChatRequest dataclass ready for the QA Engine.
    """
    return ChatRequest(
        model=schema.model,
        messages=[
            Message(role=m.role, content=m.content) for m in schema.messages
        ],
        stream=schema.stream,
        temperature=schema.temperature,
        max_tokens=schema.max_tokens,
        top_p=schema.top_p,
        frequency_penalty=schema.frequency_penalty,
        presence_penalty=schema.presence_penalty,
        user=schema.user,
        conversation_id=schema.conversation_id,
        domain_filter=schema.domain_filter,
        vessel_type_filter=schema.vessel_type_filter,
        web_search_enabled=schema.web_search,
    )


@router.post("/v1/chat/completions")
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    api_key: APIKey = Depends(get_api_key),
    rate_ok: bool = Depends(check_rate_limit),
):
    """OpenAI-compatible chat completion endpoint.

    WHAT: Authenticates the API key (via get_api_key dependency), checks the
          rate limit (via check_rate_limit dependency), converts the Pydantic
          request body to a contract ChatRequest, and forwards it to the
          M5 QA Engine. Returns the ChatResponse in OpenAI-compatible format.

    WHY: This is the primary endpoint for all external API access. The
         dependency chain ensures auth and rate limiting happen before
         any business logic, protecting the QA Engine from unauthorized
         or excessive traffic.

    Request body (JSON):
        {
            "model": "marine-rag",
            "messages": [{"role": "user", "content": "What is DNV Pt.4 Ch.3?"}],
            "stream": false,
            "temperature": 0.7,
            "max_tokens": 4096
        }

    Headers:
        Authorization: Bearer sk-m8-xxxxxxxxxxxxxxxx

    Returns:
        ChatResponse: OpenAI-compatible chat completion with choices,
                      usage statistics, and optional citations.

    Raises:
        HTTPException(401): Invalid or missing API key.
        HTTPException(429): Rate limit exceeded.
        HTTPException(500): QA Engine not initialized.
    """
    # Access the QA Engine from app state (injected by create_app factory).
    # Using request.app.state instead of a global singleton ensures that
    # tests can inject isolated mock engines per test case.
    engine = request.app.state.qa_engine
    if engine is None:
        raise HTTPException(
            status_code=500,
            detail="QA Engine not initialized. "
                   "Set app.state.qa_engine before accepting requests.",
        )

    # Convert the Pydantic schema to a contract dataclass for the engine
    chat_req: ChatRequest = _to_contract_request(body)

    # Call the QA Engine and return its response directly.
    # FastAPI's jsonable_encoder handles the ChatResponse dataclass
    # (with nested Choice, Message, Usage, Citation dataclasses) and
    # converts them to JSON-serializable dicts automatically.
    response: ChatResponse = await engine.chat(chat_req)
    return response
