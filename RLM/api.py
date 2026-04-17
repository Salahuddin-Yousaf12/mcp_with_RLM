"""
RLM Service — FastAPI

Endpoints:
  POST /ask    { "query": "..." }                  → standalone agent mode
  POST /query  { "query": "...", "context": "..." } → context-based mode (tools/repl)
  GET  /health                                      → health check
"""

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="RLM Service", version="2.0.0")


class AskRequest(BaseModel):
    query: str


class QueryRequest(BaseModel):
    query: str
    context: str


class AnswerResponse(BaseModel):
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
def ask(req: AskRequest):
    """
    Standalone agent mode — no context needed.

    The LLM uses registered functions (search_reddit, etc.) to fetch
    its own data and answer the query.
    """
    try:
        from rlm import RLMAgent
        agent = RLMAgent(verbose=False, max_iterations=15)
        answer = agent.ask(req.query)
        return AnswerResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=AnswerResponse)
def query(req: QueryRequest):
    """
    Context-based mode — pass in your own context.

    Uses tools mode (Ollama tool calling) or repl mode depending on RLM_MODE.
    """
    mode = os.getenv("RLM_MODE", "tools")
    try:
        if mode == "tools":
            from rlm import RLMTools
            rlm = RLMTools(verbose=False, max_iterations=10, max_recursion_depth=0)
        else:
            from rlm import RLM
            rlm = RLM(verbose=False, max_iterations=10, max_recursion_depth=0)

        answer = rlm.query(req.query, req.context)
        return AnswerResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
