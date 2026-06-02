#!/usr/bin/env python3
"""
WattWise — AI-powered energy optimization suggestions via Gemini 2.5 Flash.
Accepts JSON via stdin: { source_code, blocks, api_key }
Outputs JSON list of suggestions via stdout.
"""

import json
import os
import sys
from pathlib import Path


def load_env_file():
    """Load .env file from the extension root (two levels up from this script)."""
    script_dir = Path(__file__).parent
    for env_path in [script_dir / ".env", script_dir.parent / ".env"]:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        os.environ.setdefault(key.strip(), value.strip())


def get_code_snippet(source_code: str, start_line: int, end_line: int) -> str:
    """Extract source lines for a block (1-indexed)."""
    lines = source_code.splitlines()
    snippet = lines[start_line - 1:end_line]
    return '\n'.join(snippet)


def build_prompt(code_snippet: str, block_type: str, start_line: int, end_line: int,
                 energy_joules: float, full_source: str) -> str:
    return f"""You are a Python energy efficiency expert. A static energy profiling tool has \
flagged the following Python {block_type} (lines {start_line}-{end_line}) as HIGH energy \
consumption (estimated {energy_joules:.2e} Joules).

--- FULL SOURCE FILE (for context) ---
```python
{full_source}
```
--- END OF FILE ---

--- TARGET BLOCK (lines {start_line}-{end_line}) ---
```python
{code_snippet}
```
--- END OF TARGET BLOCK ---

Using the full file as context (imports, data structures, how the block is called, etc.), \
suggest specific, actionable optimizations to reduce the energy footprint of the TARGET BLOCK. \
Focus on:
1. Algorithmic improvements (better time/space complexity)
2. Eliminating redundant or repeated computations
3. Using more efficient data structures or built-ins
4. Reducing memory allocations and garbage collection pressure
5. Leveraging vectorized operations (NumPy/Pandas) where applicable

Respond with ONLY a valid JSON object — no markdown fences, no extra text — with exactly these fields:
{{
  "explanation": "1-2 sentence explanation of why this block is energy-intensive",
  "suggestions": ["concrete suggestion 1", "concrete suggestion 2"],
  "improved_code": "complete optimized replacement for the target block only"
}}"""


def get_suggestions(source_code: str, blocks: list, api_key: str) -> list:
    try:
        from google import genai
    except ImportError:
        error_msg = (
            "google-genai package not installed. "
            "Run: pip install google-genai"
        )
        return [
            {
                "block_type": b.get("block_type", "unknown"),
                "start_line": b.get("start_line"),
                "end_line": b.get("end_line"),
                "error": error_msg,
                "explanation": "",
                "suggestions": [],
                "improved_code": ""
            }
            for b in blocks
        ]

    client = genai.Client(api_key=api_key)
    results = []

    for block in blocks:
        start_line = block.get("start_line", 1)
        end_line = block.get("end_line", 1)
        block_type = block.get("block_type", "code block")
        energy_joules = block.get("energy_joules", 0.0)

        code_snippet = get_code_snippet(source_code, start_line, end_line)
        prompt = build_prompt(code_snippet, block_type, start_line, end_line, energy_joules, source_code)

        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            response_text = response.text.strip()

            # Strip markdown code fences if the model wrapped the JSON anyway
            if response_text.startswith("```"):
                lines = response_text.splitlines()
                inner = [l for l in lines if not l.startswith("```")]
                response_text = "\n".join(inner).strip()

            suggestion_data = json.loads(response_text)
            results.append({
                "block_type": block_type,
                "start_line": start_line,
                "end_line": end_line,
                "explanation": suggestion_data.get("explanation", ""),
                "suggestions": suggestion_data.get("suggestions", []),
                "improved_code": suggestion_data.get("improved_code", "")
            })

        except json.JSONDecodeError:
            # Model returned non-JSON — surface the raw text as the explanation
            results.append({
                "block_type": block_type,
                "start_line": start_line,
                "end_line": end_line,
                "explanation": response_text,
                "suggestions": [],
                "improved_code": ""
            })
        except Exception as e:
            results.append({
                "block_type": block_type,
                "start_line": start_line,
                "end_line": end_line,
                "error": str(e),
                "explanation": "",
                "suggestions": [],
                "improved_code": ""
            })

    return results


def main():
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    source_code = input_data.get("source_code", "")
    blocks = input_data.get("blocks", [])
    api_key = input_data.get("api_key", "")

    # Fall back to .env file, then environment variable
    if not api_key:
        load_env_file()
        api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        print(json.dumps({"error": "Gemini API key not found. Set GEMINI_API_KEY env var or 'wattwise.geminiApiKey' in VS Code settings (WattWise) in VS Code settings."}))
        sys.exit(1)

    if not blocks:
        print(json.dumps([]))
        sys.exit(0)

    results = get_suggestions(source_code, blocks, api_key)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
