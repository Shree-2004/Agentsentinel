"""Runs under the RAG AI CHATBOT's OWN venv interpreter — stdlib + target
repo imports only, no dependency on the agentsentinel package (that venv
never has agentsentinel installed; see subprocess_base.py for why).

Builds the vector store from a small fixed fixture corpus (agentsentinel's
own testcases/fixtures/rag_corpus/*.md) rather than a real uploaded PDF, so
retrieval results are reproducible across runs/machines. FAISS persistence
is keyed by a fixed file_hash, so only the FIRST call in a fresh checkout
re-embeds — later calls load the cached index from the target repo's own
vector_store/ directory.

Known limitation: multi-turn conversation memory is not supported here —
each subprocess invocation is stateless (a fresh process per test case), so
chat_history is always empty. Fine for the current single-turn seed corpus;
would need a long-lived shim process (not per-call spawn) to support it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# agentsentinel/agentsentinel/adapters/shims/ -> GITHUB proj/
REPO_PATH = Path(__file__).resolve().parents[4] / "RAG AI CHATBOT"
FIXTURE_DIR = Path(__file__).resolve().parents[2] / "testcases" / "fixtures" / "rag_corpus"
FIXTURE_HASH = "agentsentinel-fixture-corpus-v1"


def main() -> None:
    payload = json.loads(sys.stdin.read())

    sys.path.insert(0, str(REPO_PATH))
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=REPO_PATH / ".env")

    from langchain_core.documents import Document

    from src.chunker import split_documents
    from src.embeddings import get_embedding_model
    from src.llm import get_llm
    from src.pipeline import ask
    from src.retriever import build_vector_store

    # The target repo hard-codes config.GEMINI_MODEL = "gemini-1.5-flash",
    # which Google has since retired (confirmed via a live 404 from the
    # generateContent API: "models/gemini-1.5-flash is not found"). This is
    # a real bug in the target repo's config, not a harness issue - flagged
    # to the user rather than fixed there, since that's a separate project.
    # Overridden here only so this adapter isn't permanently blocked by it.
    import config as target_config

    target_config.GEMINI_MODEL = "gemini-2.5-flash"

    try:
        documents = [
            Document(
                page_content=path.read_text(encoding="utf-8"),
                metadata={"source": path.name, "page": 1, "file_hash": FIXTURE_HASH},
            )
            for path in sorted(FIXTURE_DIR.glob("*.md"))
        ]
        if not documents:
            raise FileNotFoundError(f"No fixture documents found in {FIXTURE_DIR}")

        chunks = split_documents(documents)
        embeddings = get_embedding_model()
        vector_store = build_vector_store(chunks, embeddings, file_hash=FIXTURE_HASH)
        llm = get_llm(streaming=False)

        token_gen, source_chunks = ask(
            question=payload["input_text"],
            vector_store=vector_store,
            llm=llm,
            chat_history=[],
        )
        output_text = "".join(token_gen)
    except Exception as exc:  # noqa: BLE001 - report to parent, don't crash silently
        _emit({"error": f"{type(exc).__name__}: {exc}"})
        return

    sources = [
        {
            "content": c.get("content", ""),
            "source": c.get("source", ""),
            "page": c.get("page") if isinstance(c.get("page"), int) else None,
            "chunk_index": c.get("chunk_index") if isinstance(c.get("chunk_index"), int) else None,
            # retriever.py's similarity scores are numpy.float32, which
            # json.dumps can't serialize - coerce to a native Python float.
            "score": float(c["score"]) if c.get("score") is not None else None,
            "label": c.get("label"),
        }
        for c in source_chunks
    ]

    _emit(
        {
            "output_text": output_text,
            "tool_calls": [],
            "sources": sources,
            "raw_output": {"source_chunk_count": len(source_chunks)},
        }
    )


def _emit(result: dict) -> None:
    print(f"AGENTSENTINEL_RESULT:{json.dumps(result)}")


if __name__ == "__main__":
    main()
