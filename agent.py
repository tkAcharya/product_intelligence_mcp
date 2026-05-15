import asyncio
import json
import os
import subprocess
import sys
import time
import re
from pathlib import Path

import httpx
import google.generativeai as genai
from dotenv import load_dotenv
from fastmcp import Client
from prefab_client import push_custom_html
from models import ComparisonPayload

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MCP_SERVER_URL = "http://127.0.0.1:8090/mcp"
MAX_WAIT_SEC = 15

load_dotenv()

# Initialize Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Please set GEMINI_API_KEY in your .env file.")
    sys.exit(1)

genai.configure(api_key=api_key)
# Using gemini-3-flash-preview as requested
model = genai.GenerativeModel('gemini-3-flash-preview')

# ---------------------------------------------------------------------------
# System Prompt & Parsing
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """
You are an intelligent Product Comparison AI Assistant.
Your goal is to help users compare products by gathering data, fetching reviews, saving the data, and generating visual dashboards using the `prefab_ui` library.

## Your Workflow
For every product comparison request:
1. Call `search_product` to get retailer data.
2. Call `get_product_reviews` for each retailer to get pros/cons and summaries.
3. Call `save_comparison_to_file` to persist the data.
4. After saving, write a complete `build_html(initial_data)` Python function using `prefab_ui` components to design a beautiful dashboard for the data. Output this as a ```python code block. The system will automatically execute it and open the browser.

## prefab_ui Component Reference
- **Layout**: Column(gap, css_class), Row(css_class)
- **Content**: H3(text), H4(text), Text(text), Muted(text), Badge(text, variant), Link(text, href, target)
- **Cards**: Card(css_class), CardContent(css_class), CardFooter()
- **Control Flow**: ForEach(rx_list), If(rx_condition)
- **Reactive State**: Rx("data.path"), ITEM["field"], RESULT, SetInterval, Fetch, SetState
- **App**: PrefabApp(title, state, on_mount)

## Example `build_html` function:
```python
from prefab_ui.app import PrefabApp
from prefab_ui.actions import Fetch, SetInterval, SetState
from prefab_ui.components import Column, Row, Card, CardContent, H3, H4, Text, Badge, Link, Muted, CardFooter
from prefab_ui.components.control_flow import ForEach, If
from prefab_ui.rx import Rx, ITEM, RESULT

POLL_MS = 3000

def build_html(initial_data: dict) -> str:
    product_name = Rx("data.product_name")
    comparison_data = Rx("data.comparison_data")
    with PrefabApp(
        title="Product Comparison",
        state={{"data": initial_data}},
        on_mount=SetInterval(POLL_MS, on_tick=Fetch.get("/api/data", on_success=SetState("data", RESULT))),
    ) as app:
        with Column(gap=6, css_class="max-w-7xl mx-auto px-8 py-6"):
            H3(product_name)
            with Row(css_class="flex-wrap gap-4"):
                with ForEach(comparison_data):
                    with Card(css_class="min-w-64 max-w-xs flex-1"):
                        with CardContent():
                            H3(ITEM["retailer"])
                            H4(ITEM["price_raw"])
                            with If(ITEM["rating_str"]):
                                Muted(ITEM["rating_str"])
                        with CardFooter():
                            Link("View Deal →", href=ITEM["link"], target="_blank")
    return app.html()
```

IMPORTANT: Always use double curly braces {{}} for dict literals inside the code block to avoid formatting issues.

## Tool Calling
If you need to use a tool, respond ONLY with this strict JSON format:
{{
  "tool_name": "the_name_of_the_tool",
  "tool_arguments": {{
    "arg1": "value1"
  }}
}}

If you do not need to use a tool, respond with normal text. Do not wrap normal text in JSON.

AVAILABLE TOOLS:
{tool_descriptions}
"""

def parse_llm_response(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_server(url: str, timeout: int = MAX_WAIT_SEC) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def _result(tool_output) -> dict | list:
    if hasattr(tool_output, "data") and tool_output.data is not None:
        return tool_output.data

    content = getattr(tool_output, "content", None)
    if content:
        text = getattr(content[0], "text", None) or str(content[0])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    return {}

def _try_execute_ui_code(response_text: str, data: dict) -> bool:
    """Extract a build_html code block from LLM response, execute it, and push the UI.

    Returns True if a valid build_html function was found and executed successfully.
    """
    # Match ```python ... ``` blocks containing 'def build_html'
    pattern = r"```python\s*(.*?)```"
    matches = re.findall(pattern, response_text, re.DOTALL)

    for code in matches:
        if "def build_html" not in code:
            continue
        try:
            # Build a namespace pre-loaded with all prefab_ui imports
            ns: dict = {}
            exec(
                "from prefab_ui.app import PrefabApp\n"
                "from prefab_ui.actions import Fetch, SetInterval, SetState\n"
                "from prefab_ui.components import (\n"
                "    Badge, Card, CardContent, CardFooter, Column,\n"
                "    H3, H4, Link, Muted, Row, Text\n"
                ")\n"
                "from prefab_ui.components.control_flow import ForEach, If\n"
                "from prefab_ui.rx import ITEM, RESULT, Rx\n",
                ns,
            )
            exec(code, ns)
            build_html = ns.get("build_html")
            if not callable(build_html):
                continue

            html = build_html(data)
            product_name = data.get("product_name", "Product Comparison")
            push_custom_html(product_name, html)
            print("\n[UI] LLM-generated prefab_ui dashboard rendered and opened in browser!")
            return True
        except Exception as e:
            print(f"[UI] Failed to execute LLM-generated build_html: {e}")
    return False

def _print_tokens(response, label: str = "") -> None:
    """Print token usage from a Gemini response's usage_metadata."""
    try:
        meta = response.usage_metadata
        prompt = getattr(meta, "prompt_token_count", "?")
        candidates = getattr(meta, "candidates_token_count", "?")
        total = getattr(meta, "total_token_count", "?")
        tag = f" {label}" if label else ""
        print(f"[Tokens{tag}] prompt={prompt}  response={candidates}  total={total}")
    except Exception:
        pass  # silently skip if metadata unavailable

# ---------------------------------------------------------------------------
# Main Agent Loop
# ---------------------------------------------------------------------------

async def run_agent_loop():
    print("[MCP] Connecting to MCP server...")
    async with Client(MCP_SERVER_URL) as client:
        # Dynamically fetch tools from the server
        try:
            tools_response = await client.list_tools()
            tools_list = getattr(tools_response, "tools", tools_response)
            
            tool_desc_lines = []
            for i, t in enumerate(tools_list, 1):
                name = getattr(t, "name", t.get("name") if isinstance(t, dict) else "unknown")
                desc = getattr(t, "description", t.get("description", "") if isinstance(t, dict) else "")
                
                # Handle input schema securely whether it's an object or dict
                schema = getattr(t, "inputSchema", t.get("inputSchema", {}) if isinstance(t, dict) else {})
                if not isinstance(schema, dict):
                    schema = getattr(schema, "model_dump", lambda: vars(schema))() if hasattr(schema, "model_dump") else getattr(schema, "dict", lambda: getattr(schema, "__dict__", {}))()
                
                properties = schema.get("properties", {})
                args_preview = {k: v.get("type", "any") for k, v in properties.items()}
                args_str = json.dumps(args_preview)
                
                tool_desc_lines.append(f"{i}. {name}")
                tool_desc_lines.append(f"   Description: {desc}")
                tool_desc_lines.append(f"   Arguments: {args_str}\n")
                
            tool_descriptions = "\n".join(tool_desc_lines)
        except Exception as e:
            print(f"[WARNING] Failed to fetch tools from MCP: {e}")
            tool_descriptions = "No tools available."

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(tool_descriptions=tool_descriptions)

        print("[READY] You can now chat with the Product Comparison Agent.")
        print("Type 'exit' to quit.\n")
        
        chat = model.start_chat(history=[])
        init_resp = chat.send_message(system_prompt)
        _print_tokens(init_resp, label="[system prompt]")

        # Tracks the most recent enriched comparison data for UI rendering
        _last_comparison: dict = {}
        
        while True:
            try:
                user_message = input("\nUser: ")
                if user_message.strip().lower() in ['exit', 'quit']:
                    break
                    
                time.sleep(3)  # avoid rate limits
                response = chat.send_message(user_message)
                _print_tokens(response)
                
                while True:
                    parsed = parse_llm_response(response.text)
                    
                    if parsed and "tool_name" in parsed:
                        tool_name = parsed["tool_name"]
                        tool_args = parsed.get("tool_arguments", {})
                        
                        print(f"\n[Agent] Calling tool '{tool_name}' with args {tool_args}...")
                        
                        try:
                            raw_result = await client.call_tool(tool_name, tool_args)
                            tool_result = _result(raw_result)
                            print(f"[Agent] Tool returned successfully (data length: {len(str(tool_result))})")

                            # Cache + validate comparison data after save
                            if tool_name == "save_comparison_to_file":
                                try:
                                    _last_comparison = ComparisonPayload(
                                        product_name=tool_args.get("product_name", ""),
                                        comparison_data=tool_args.get("comparison_data", []),
                                    )
                                    print(f"[Validation] ComparisonPayload OK — {len(_last_comparison.comparison_data)} retailers")
                                except Exception as ve:
                                    print(f"[Validation] ComparisonPayload failed: {ve}")
                                    _last_comparison = None
                        except Exception as e:
                            print(f"[Agent] Tool execution failed: {e}")
                            tool_result = {"error": str(e)}
                        
                        feedback_msg = f"Tool Result ({tool_name}):\n{json.dumps(tool_result)[:4000]}\n\nBased on the tool result, please provide your response or call the next tool. If you pass data to the next tool, make sure you match the required argument schemas."
                        time.sleep(3)  # avoid rate limits
                        response = chat.send_message(feedback_msg)
                        _print_tokens(response)
                    else:
                        print(f"\nAgent: {response.text}")

                        # Auto-detect and execute any build_html code block in the LLM response
                        if _last_comparison and "def build_html" in response.text:
                            _try_execute_ui_code(response.text, _last_comparison.to_dict())

                        break
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    venv_python = str(Path(__file__).parent / "venv310" / "Scripts" / "python.exe")
    run_server = str(Path(__file__).parent / "run_server.py")

    print(f"[START] Launching MCP server (run_server.py) ...")
    proc = subprocess.Popen(
        [venv_python, run_server],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    print(f"[WAIT]  Waiting for MCP server to be ready at {MCP_SERVER_URL} ...")
    if not _wait_for_server(MCP_SERVER_URL, MAX_WAIT_SEC):
        print("[ERROR] MCP server did not start in time.")
        proc.terminate()
        sys.exit(1)
        
    try:
        asyncio.run(run_agent_loop())
    finally:
        print("\n[STOP] Stopping MCP server ...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("[DONE] Exited.")

if __name__ == "__main__":
    main()
