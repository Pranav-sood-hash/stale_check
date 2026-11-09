import time

class MockGraph:
    def stream(self, inputs: dict, stream_mode: str = "updates"):
        text = inputs.get("text") or inputs.get("answer") or ""
        time.sleep(0.05)
        yield {
            "extract": {
                "claims": [
                    {
                        "id": 1,
                        "text": text[:80],
                        "category": "pricing",
                        "time_sensitive": True,
                        "query": f"verify {text[:40]}"
                    }
                ]
            }
        }
        time.sleep(0.05)
        yield {
            "search": {
                "evidence": [
                    {
                        "title": "Verification Source",
                        "url": "https://example.com/source1",
                        "content": "Verified information regarding the claim.",
                        "date": "2026-11-09"
                    }
                ]
            }
        }
        time.sleep(0.05)
        yield {
            "analyze": {
                "analysis": [
                    {
                        "id": 1,
                        "status": "current",
                        "current_fact": text[:80],
                        "reason": "Consistent with latest web findings.",
                        "sources": ["https://example.com/source1"]
                    }
                ]
            }
        }
        time.sleep(0.05)
        yield {
            "judge": {
                "results": [
                    {
                        "id": 1,
                        "text": text[:80],
                        "category": "pricing",
                        "verdict": "Fresh",
                        "score": 95,
                        "current_fact": text[:80],
                        "reason": "Consistent with latest web findings.",
                        "sources": ["https://example.com/source1"],
                        "cached": False
                    }
                ]
            }
        }
        time.sleep(0.05)
        yield {
            "rewrite": {
                "rewritten": text,
                "cached": 0
            }
        }

    def invoke(self, inputs: dict) -> dict:
        state = {}
        for update in self.stream(inputs):
            for k, v in update.items():
                if isinstance(v, dict):
                    state.update(v)
        return state

app_graph = MockGraph()

def local_answer(question: str) -> str:
    return f"Local LLM generated response to: {question}"
