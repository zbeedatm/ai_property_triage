"""
app.py
------
Gradio WebUI with two tabs:

  Tab 1 — Chat Assistant
      Real estate Q&A powered by Ollama (cloud or local).
      Uses the system prompt from chat_client.py (Iteration 1).

  Tab 2 — Submit Listing
      Form that POSTs to the n8n webhook and displays the triage report.

Run locally:
    python app.py

Run with Docker:
    docker compose up --build
"""

import asyncio
import logging
import os
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import gradio as gr
import gradio_client.utils as _gc_utils

# Pydantic v2 JSON schemas may use boolean `additionalProperties` (e.g. `true`).
# gradio_client 1.0.x then recurses with schema `True`, breaks `get_type`, or ends
# in APIInfoParseError (see gradio #10792 / #10798). Normalize before delegating.
_orig_gc_json_schema_to_python_type = _gc_utils._json_schema_to_python_type


def _gc_json_schema_to_python_type(schema, defs):
    if isinstance(schema, bool):
        return "Any"
    if isinstance(schema, dict):
        ap = schema.get("additionalProperties")
        if ap is True:
            schema = {**schema, "additionalProperties": {"type": "string"}}
        elif ap is False:
            schema = {k: v for k, v in schema.items() if k != "additionalProperties"}
    return _orig_gc_json_schema_to_python_type(schema, defs)


_gc_utils._json_schema_to_python_type = _gc_json_schema_to_python_type

from chat_client   import ChatClient
from webhook_client import format_report_for_display, submit_listing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

chat_client = ChatClient()

APP_TITLE   = os.getenv("APP_TITLE",   "Property Triage Platform")
SERVER_PORT = int(os.getenv("PORT",    "7860"))
SERVER_HOST = os.getenv("HOST",        "0.0.0.0")
# Gradio tunnel (temporary public URL). Set GRADIO_SHARE=1 only if you want that.
GRADIO_SHARE = os.getenv("GRADIO_SHARE", "").strip().lower() in ("1", "true", "yes")

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Tab 1 — Chat logic
# ---------------------------------------------------------------------------

def _history_to_ollama(history: list) -> list[dict]:
    """Convert Gradio chatbot history → Ollama message list.

    `history` is left untyped in the public handler (see `chat`) because nested
    generics in annotations make Pydantic emit JSON Schema that older Gradio
    clients mishandle (`additionalProperties: true` as a bool).
    """
    messages = []
    for user_msg, assistant_msg in history:
        if user_msg:
            messages.append({"role": "user",      "content": user_msg})
        if assistant_msg:
            messages.append({"role": "assistant", "content": assistant_msg})
    return messages


async def chat(user_message: str, history: list):
    """
    Gradio chat handler — streams tokens one by one.
    Yields (history, "") to update the chatbot component progressively.
    """
    if not user_message.strip():
        yield history, ""
        return

    # Append user turn with empty assistant placeholder
    history = history + [[user_message, ""]]
    yield history, ""

    ollama_history = _history_to_ollama(history[:-1])  # exclude current turn
    ollama_history.append({"role": "user", "content": user_message})

    try:
        response = await chat_client.stream_response(ollama_history)
        history[-1][1] = response
        yield history, ""
    except Exception as exc:
        error_msg = (
            f"⚠️ Could not reach Ollama at `{chat_client.base_url}`.\n\n"
            "For **Ollama Cloud**: set `OLLAMA_HOST=https://ollama.com`, `OLLAMA_API_KEY`, "
            "and `OLLAMA_MODEL` in the environment (see `docker/examples/webui.env.example`).\n\n"
            "For **local Ollama**: run `ollama serve`, set `OLLAMA_HOST` to that host, "
            "and `ollama pull <model>`.\n\n"
            f"Error: {exc}"
        )
        history[-1][1] = error_msg
        yield history, ""


def clear_chat():
    return [], ""


# ---------------------------------------------------------------------------
# Tab 2 — Submission logic
# ---------------------------------------------------------------------------

def _save_uploaded_files(uploaded_files: list | None) -> list[str]:
    """
    Copy Gradio temp files into uploads/ with unique names.
    Returns a list of relative paths like "uploads/<uuid>.<ext>".
    """
    if not uploaded_files:
        return []
    saved = []
    for filepath in uploaded_files:
        src = Path(filepath)
        if not src.is_file():
            continue
        ext = src.suffix.lower() or ".jpg"
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
        shutil.copy2(src, dest)
        saved.append(str(dest.relative_to(Path(__file__).resolve().parent)))
    return saved


async def submit_form(
    agent_name: str,
    description: str,
    image_urls_raw: str,
    uploaded_files,
) -> tuple[str, str]:
    """
    Validate inputs, POST to n8n, and return (status_message, formatted_report).
    Combines manually entered URLs with uploaded image files.
    """
    # --- Validation ---
    if not agent_name.strip():
        yield "⚠️ Please enter your name.", ""
        return
    if not description.strip():
        yield "⚠️ Please enter a property description.", ""
        return
    if len(description.strip()) < 20:
        yield "⚠️ Description is too short. Please provide more detail.", ""
        return

    # Parse manually entered image URLs (one per line)
    image_urls = [
        line.strip()
        for line in (image_urls_raw or "").splitlines()
        if line.strip().startswith("http")
    ]

    # Convert uploaded files to URLs served by this app
    local_paths = _save_uploaded_files(uploaded_files)
    file_base_url = os.getenv("FILE_BASE_URL", f"http://127.0.0.1:{SERVER_PORT}")
    for rel_path in local_paths:
        image_urls.append(f"{file_base_url}/file={rel_path}")

    n_urls = len(image_urls) - len(local_paths)
    n_uploads = len(local_paths)
    parts = []
    if n_urls:
        parts.append(f"{n_urls} URL(s)")
    if n_uploads:
        parts.append(f"{n_uploads} uploaded file(s)")
    img_summary = " + ".join(parts) if parts else "no images"

    status = f"⏳ Submitting listing for **{agent_name}** with {img_summary}..."
    yield status, ""

    result = await submit_listing(
        description=description,
        image_urls=image_urls,
        agent_name=agent_name,
    )

    if result.get("human_review"):
        msg = (result.get("message") or "").strip()
        fr = (result.get("flag_reason") or "").strip()
        banner = "### ⏸️ Human review required\n\n"
        if msg:
            banner += f"{msg}\n\n"
        if fr:
            banner += f"**Guardrails output check:** {fr}\n\n"
        banner += "---\n\n#### Draft triage (not released)\n\n"
        draft_md = format_report_for_display(result.get("report") or {})
        yield "⏸️ Held for human review — draft report below (not a final release).", banner + draft_md
        return

    if result["success"]:
        report_md = format_report_for_display(result["report"])
        yield "✅ Report received.", report_md
    else:
        yield f"❌ Submission failed: {result['error']}", ""


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

with gr.Blocks(
    title=APP_TITLE,
    theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
    css="""
        .report-box { font-size: 0.95rem; }
        footer { display: none !important; }
    """,
) as demo:

    gr.Markdown(f"# 🏢 {APP_TITLE}")
    gr.Markdown(
        "A two-step pipeline: chat with a local AI assistant or submit a listing "
        "for automated triage via the n8n pipeline."
    )

    with gr.Tabs():

        # ── Tab 1: Chat ────────────────────────────────────────────────────
        with gr.TabItem("💬 Chat Assistant"):
            gr.Markdown(
                "Ask any real estate question. Powered by **Ollama** "
                "(configure `OLLAMA_MODEL` — default is a cloud model such as **gpt-oss:120b**)."
            )

            chatbot = gr.Chatbot(
                label="Real Estate Assistant",
                height=460,
                bubble_full_width=False,
                show_copy_button=True,
            )

            with gr.Row():
                chat_input = gr.Textbox(
                    placeholder="e.g. What should I look for when pricing a penthouse in Tel Aviv?",
                    label="Your question",
                    scale=8,
                    lines=2,
                    autofocus=True,
                )
                with gr.Column(scale=1, min_width=80):
                    send_btn  = gr.Button("Send", variant="primary")
                    clear_btn = gr.Button("Clear")

            # Streaming chat
            send_btn.click(
                fn=chat,
                inputs=[chat_input, chatbot],
                outputs=[chatbot, chat_input],
            )
            chat_input.submit(
                fn=chat,
                inputs=[chat_input, chatbot],
                outputs=[chatbot, chat_input],
            )
            clear_btn.click(fn=clear_chat, outputs=[chatbot, chat_input])

        # ── Tab 2: Submit Listing ──────────────────────────────────────────
        with gr.TabItem("📋 Submit Listing"):
            gr.Markdown(
                "Submit a new property listing for automated AI triage. "
                "The pipeline will retrieve similar listings, analyse any images, "
                "and return a structured report."
            )

            with gr.Row():
                with gr.Column(scale=1):
                    agent_name_input = gr.Textbox(
                        label="Agent name",
                        placeholder="e.g. Sarah Cohen",
                    )
                    description_input = gr.Textbox(
                        label="Property description",
                        placeholder=(
                            "e.g. 3-bedroom apartment in Tel Aviv, Florentin. "
                            "110sqm, fully renovated kitchen, two bathrooms, "
                            "balcony with city view. Asking 4,200,000 ILS."
                        ),
                        lines=4,
                    )
                    gr.Markdown("**Property images** *(optional — use either or both)*")
                    image_upload_input = gr.File(
                        label="Upload images",
                        file_count="multiple",
                        file_types=["image"],
                        type="filepath",
                        height=80,
                    )
                    image_urls_input = gr.Textbox(
                        label="Or paste image URLs (one per line)",
                        placeholder=(
                            "https://example.com/kitchen.jpg\n"
                            "https://example.com/living_room.jpg"
                        ),
                        lines=3,
                    )
                    submit_btn = gr.Button("Submit for Triage", variant="primary", size="lg")

                with gr.Column(scale=1):
                    status_output = gr.Markdown(label="Status")
                    report_output = gr.Markdown(
                        label="Triage Report",
                        elem_classes=["report-box"],
                    )

            submit_btn.click(
                fn=submit_form,
                inputs=[agent_name_input, description_input, image_urls_input, image_upload_input],
                outputs=[status_output, report_output],
                show_progress="minimal",
            )

    gr.Markdown(
        "---\n"
        "**Chat:** Ollama (cloud or local) &nbsp;|&nbsp; "
        "**Pipeline:** n8n → Guardrails → RAG → Image Analyser → LangGraph → Report"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    demo.launch(
        server_name=SERVER_HOST,
        server_port=SERVER_PORT,
        share=GRADIO_SHARE,
        show_api=False,
        allowed_paths=[str(UPLOAD_DIR)],
        quiet=True,
    )