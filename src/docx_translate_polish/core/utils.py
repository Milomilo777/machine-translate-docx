"""Shared utility functions."""
import tiktoken

def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text using cl100k_base encoding."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def calculate_openai_cost(response_json: dict) -> dict:
    """Calculate the cost of an OpenAI API call based on the response."""
    model = response_json.get("model", "")
    usage = response_json.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)

    PRICES = {
        "gpt-5.4": {"input": 2.50, "output": 15.00},
        "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
        "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
        "gpt-5.2": {"input": 1.75, "output": 14.00},
        "gpt-5-pro": {"input": 15, "output": 120},
        "gpt-5.1": {"input": 1.25, "output": 10.00},
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60}
    }

    # Find matching model price tier (partial match supported)
    price = next((v for k, v in PRICES.items() if k in model), None)

    if price is None:
        # Returning zero cost as fallback with implicit warning (handled by logger)
        return {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "unknown_model": True
        }

    input_cost = (prompt_tokens / 1_000_000) * price["input"]
    output_cost = (completion_tokens / 1_000_000) * price["output"]
    total_cost = input_cost + output_cost

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": total_cost,
        "unknown_model": False
    }
