"""
agent.py
--------
LangGraph StateGraph with three nodes:

    planner  →  tool_executor  →  synthesiser
                    ↑_______________|
                (loop until done)

State machine:
  - planner:       reads the listing, decides which tools to call next
  - tool_executor: executes the chosen tool, stores the result in state
  - synthesiser:   once all tools are done, writes the final JSON report

Planner prompt is at Iteration 1 — log improvements in:
    prompt_logs/agent_prompt_log.md
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Annotated, Any

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from tools import analyse_images, rag_query

logger = logging.getLogger(__name__)


def _patch_langgraph_checkpoint_versions_seen() -> None:
    """Fix KeyError: '__start__' in langgraph 0.1.x with checkpoint.base package.

    `empty_checkpoint` / `copy_checkpoint` use a plain dict for ``versions_seen``, but
    ``_prepare_next_tasks`` indexes every process name without ``setdefault``. The
    older ``checkpoint/base.py`` path used ``defaultdict(dict)``. Wrap both helpers
    on the ``pregel`` module (where they are bound) until LangGraph is upgraded.
    """
    from collections import defaultdict

    import langgraph.pregel as _pregel

    _orig_empty = _pregel.empty_checkpoint

    def empty_checkpoint():  # noqa: ANN202
        cp = _orig_empty()
        vs = cp.get("versions_seen")
        if type(vs) is dict and not isinstance(vs, defaultdict):
            cp["versions_seen"] = defaultdict(dict, vs)
        return cp

    _orig_copy = _pregel.copy_checkpoint

    def copy_checkpoint(checkpoint):  # noqa: ANN001, ANN202
        cp = _orig_copy(checkpoint)
        vs = cp.get("versions_seen")
        if type(vs) is dict and not isinstance(vs, defaultdict):
            cp["versions_seen"] = defaultdict(dict, vs)
        return cp

    _pregel.empty_checkpoint = empty_checkpoint
    _pregel.copy_checkpoint = copy_checkpoint


_patch_langgraph_checkpoint_versions_seen()


def _parse_llm_json_blob(raw: str) -> dict | None:
    """
    Parse JSON from LLM output. Gemini often wraps JSON in ```json ... ``` fences.
    """
    text = (raw or "").strip()
    if not text:
        return None

    fenced = re.match(
        r"^```(?:json)?\s*\r?\n?(.*?)\r?\n?```\s*$",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass
    return None


def _titles_from_similar_listings(raw: list | None) -> list[str]:
    """Normalise RAG similar_listings (strings or dicts) to title strings."""
    out: list[str] = []
    if not raw:
        return out
    for item in raw:
        if isinstance(item, str):
            t = item.strip()
            if t:
                out.append(t)
        elif isinstance(item, dict):
            title = str(item.get("title") or "").strip()
            if not title:
                title = str(item.get("id") or item.get("listing_id") or "").strip()
            if title:
                out.append(title)
    return out


def _merge_rag_into_report(report: dict[str, Any], rag: dict[str, Any] | None) -> dict[str, Any]:
    """
    Carry RAG payloads into the final report — the synthesiser LLM sometimes drops insight
    or omits similar_listings when they are structured objects.
    """
    if rag is None or not isinstance(report, dict):
        return report

    retrieved = int(rag.get("retrieved_count") or 0)
    rag_similar = rag.get("similar_listings")
    if not isinstance(rag_similar, list):
        rag_similar = []

    # Successful RAG JSON always wins over synthesiser for these fields.
    if rag_similar:
        if all(isinstance(x, dict) for x in rag_similar):
            report["similar_listings"] = list(rag_similar)
        else:
            titles = _titles_from_similar_listings(rag_similar)
            if titles:
                report["similar_listings"] = titles
            else:
                report["similar_listings"] = list(rag_similar)

    insight = str(rag.get("insight") or "").strip()
    if insight:
        report["rag_insight"] = insight
    elif retrieved == 0 and not str(report.get("rag_insight") or "").strip():
        report["rag_insight"] = "No similar listings found in the knowledge base."

    report["rag_retrieved"] = retrieved
    kb = rag.get("knowledge_base_documents")
    if kb is not None:
        report["knowledge_base_documents"] = kb

    return report


# ---------------------------------------------------------------------------
# LLM setup
# ---------------------------------------------------------------------------

_LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")   # "openai" or "gemini" or "local"
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

def _build_llm():
    if _LLM_PROVIDER == "openai":
        return ChatOpenAI(
            model=_OPENAI_MODEL,
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY", ""),
        )

    elif _LLM_PROVIDER == "gemini":
        return ChatGoogleGenerativeAI(
            model=_GEMINI_MODEL,
            temperature=0,
            google_api_key=os.getenv("GOOGLE_API_KEY", ""),
        )

    elif _LLM_PROVIDER == "local":
        # Local fallback: llama-cpp-python via OpenAI-compatible server
        # (run: python -m llama_cpp.server --model ./models/mistral.gguf --port 8080)
        
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "mistral"),
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            temperature=0,
        )

        # from langchain_openai import ChatOpenAI as LocalChat
        # return LocalChat(
        #     model="mistral",
        #     base_url=os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1"),
        #     api_key="not-needed",
        #     temperature=0,
        # )
    else:
        raise ValueError(f"Invalid LLM provider: {_LLM_PROVIDER}")


# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    # Full message history (LangGraph merges via add_messages)
    messages: Annotated[list, add_messages]

    # Inputs
    description:  str
    image_urls:   list[str]

    # Accumulated tool results
    rag_result:   dict | None
    image_result: dict | None

    # Control
    tools_done:   bool

    # Final output
    report:       dict | None


# ---------------------------------------------------------------------------
# Prompts (Iteration 1)
# ---------------------------------------------------------------------------

PLANNER_SYSTEM = """\
You are a senior property analyst assistant.
You receive a new property listing and must gather all information needed
to write a structured analysis report.

You have access to exactly two tools:
  1. rag_query       — retrieves similar past listings and comparative insight
  2. analyse_images  — classifies room types and scores condition from image URLs

Rules:
  - Always call rag_query first with the full listing description.
  - If image_urls are provided, call analyse_images with the full list as a JSON array.
  - Call each tool at most ONCE per run.
  - When you have called all relevant tools, reply with the single word: DONE
  - Do not attempt to answer or summarise — just collect data.
"""

SYNTHESISER_SYSTEM = """\
You are a senior property analyst writing a structured triage report.

Using the listing description and the tool results provided, produce a JSON
object with EXACTLY these fields — no extras, no missing fields:

{
  "property_type":      string,   // apartment | house | villa | office | retail | industrial | other
  "routing_decision":   string,   // "residential" or "commercial"
  "location":           string,   // as mentioned in the listing
  "price_ils":          number | null,   // numeric ILS value or null if not stated
  "num_rooms":          number | null,
  "key_features":       [string],  // up to 5 items
  "image_scores": [
    {
      "url":             string,
      "room_type":       string,
      "condition_score": number,   // 1.0–5.0
      "confidence":      number
    }
  ],
  "similar_listings":   [string],  // titles of retrieved similar listings
  "rag_insight":        string,    // the insight from the RAG service
  "enrichment_notes":   string,    // your own 2–3 sentence analysis
  "confidence":         number     // 0.0–1.0, your overall confidence in this report
}

Rules:
  - Do NOT invent prices, certifications, room counts, or features not in the source data.
  - Use null for numeric fields that are not mentioned.
  - enrichment_notes must be grounded only in the listing and tool results.
  - Copy the RAG service "insight" field verbatim into rag_insight when it is provided (including the text that no listings were retrieved).
  - For similar_listings, use listing titles only — take each entry's title from the RAG JSON or use plain string entries; never invent comparisons.
  - Return ONLY the JSON object — no markdown fences, no preamble.
"""


# ---------------------------------------------------------------------------
# Node: planner
# ---------------------------------------------------------------------------

async def planner_node(state: AgentState) -> dict:
    """
    Decides which tool to call next.
    Returns ToolCall messages or sets tools_done=True.
    """
    llm = _build_llm()
    tools = [rag_query, analyse_images]
    llm_with_tools = llm.bind_tools(tools)

    # Build context message
    context = (
        f"Listing description:\n{state['description']}\n\n"
        f"Image URLs: {json.dumps(state['image_urls'])}\n\n"
        f"RAG result collected: {'yes' if state['rag_result'] else 'no'}\n"
        f"Image result collected: {'yes' if state['image_result'] else 'no'}"
    )

    messages = [
        {"role": "system",  "content": PLANNER_SYSTEM},
        {"role": "user",    "content": context},
    ]
    # Include prior tool messages so the planner knows what's been done
    messages += [m for m in state["messages"] if isinstance(m, (AIMessage, ToolMessage))]

    response = await llm_with_tools.ainvoke(messages)

    # If the model replied "DONE" or has no tool calls, signal completion
    content = response.content if hasattr(response, "content") else ""
    if "DONE" in str(content).upper() or not getattr(response, "tool_calls", []):
        return {"tools_done": True, "messages": [response]}

    return {"tools_done": False, "messages": [response]}


# ---------------------------------------------------------------------------
# Node: tool_executor
# ---------------------------------------------------------------------------

async def tool_executor_node(state: AgentState) -> dict:
    """
    Executes the tool call chosen by the planner and stores the result.
    """
    last_message = state["messages"][-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"tools_done": True}

    tool_call = last_message.tool_calls[0]
    tool_name  = tool_call["name"]
    tool_input = tool_call["args"]

    logger.info("Executing tool: %s | args: %s", tool_name, tool_input)

    updates: dict[str, Any] = {}

    if tool_name == "rag_query":
        raw = await rag_query.ainvoke(tool_input.get("description", state["description"]))
        try:
            updates["rag_result"] = json.loads(raw)
        except json.JSONDecodeError:
            updates["rag_result"] = {"error": raw}

    elif tool_name == "analyse_images":
        urls_arg = tool_input.get("image_urls", json.dumps(state["image_urls"]))
        raw = await analyse_images.ainvoke(urls_arg)
        try:
            updates["image_result"] = json.loads(raw)
        except json.JSONDecodeError:
            updates["image_result"] = {"error": raw}

    else:
        logger.warning("Unknown tool requested: %s", tool_name)

    # Append a ToolMessage so the planner sees the result
    tool_msg = ToolMessage(
        content=raw,
        tool_call_id=tool_call["id"],
    )
    updates["messages"] = [tool_msg]
    return updates


# ---------------------------------------------------------------------------
# Node: synthesiser
# ---------------------------------------------------------------------------

async def synthesiser_node(state: AgentState) -> dict:
    """
    Produces the final structured JSON report from all collected data.
    """
    llm = _build_llm()

    # Always fetch RAG once here with the exact listing description from the API.
    # The planner sometimes skips rag_query or passes wrong args — that left similar_listings empty
    # even when Chroma had matches. This is the single source of truth for the final report + API counts.
    rag_authoritative: dict[str, Any] = {}
    raw_rag = ""
    try:
        raw_rag = await rag_query.ainvoke(state["description"])
        parsed = json.loads(raw_rag)
        rag_authoritative = parsed if isinstance(parsed, dict) else {"error": str(parsed)}
    except json.JSONDecodeError:
        rag_authoritative = {"error": raw_rag or "invalid JSON from RAG tool"}
    except Exception as exc:
        logger.exception("Authoritative RAG fetch failed")
        rag_authoritative = {"error": str(exc)}

    context_parts = [
        f"Listing description:\n{state['description']}",
        f"\nImage URLs provided: {json.dumps(state['image_urls'])}",
        f"\nRAG service result (authoritative — use this for similar_listings and rag_insight):\n"
        f"{json.dumps(rag_authoritative, indent=2)}",
    ]

    if state.get("image_result"):
        context_parts.append(f"\nImage analyser result:\n{json.dumps(state['image_result'], indent=2)}")
    else:
        context_parts.append("\nImage analyser result: no images provided or not available")

    messages = [
        {"role": "system", "content": SYNTHESISER_SYSTEM},
        {"role": "user",   "content": "\n".join(context_parts)},
    ]

    response = await llm.ainvoke(messages)

    raw_content = response.content
    if isinstance(raw_content, list):
        raw_content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in raw_content
        )
    raw_content = str(raw_content).strip()

    report = _parse_llm_json_blob(raw_content)
    if report is None:
        logger.warning("Synthesiser returned non-JSON — wrapping as error")
        report = {"error": "Synthesiser returned invalid JSON", "raw": raw_content}
    else:
        report = _merge_rag_into_report(report, rag_authoritative)

    return {
        "report": report,
        "messages": [response],
        "rag_result": rag_authoritative,
    }


# ---------------------------------------------------------------------------
# Routing function
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> str:
    """Route back to planner or forward to synthesiser."""
    if state.get("tools_done"):
        return "synthesiser"
    return "tool_executor"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> Any:
    graph = StateGraph(AgentState)

    graph.add_node("planner",       planner_node)
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("synthesiser",   synthesiser_node)

    graph.set_entry_point("planner")

    graph.add_conditional_edges(
        "planner",
        should_continue,
        {
            "tool_executor": "tool_executor",
            "synthesiser":   "synthesiser",
        },
    )

    graph.add_edge("tool_executor", "planner")   # loop back for next tool
    graph.add_edge("synthesiser",   END)

    return graph.compile()


# Singleton compiled graph — loaded once at service startup
compiled_graph = build_graph()
