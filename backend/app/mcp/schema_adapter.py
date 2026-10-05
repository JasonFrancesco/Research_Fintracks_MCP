"""
Adapter schema: MCP tools/list -> format function-calling LLM.

LLM (Ollama lokal maupun provider cloud format OpenAI) mengharapkan daftar tool
dalam bentuk:

    {
        "type": "function",
        "function": {
            "name": ...,
            "description": ...,
            "parameters": { JSON Schema }
        }
    }

MCP mengembalikan tiap tool sebagai {name, description, inputSchema}, di mana
inputSchema SUDAH berupa JSON Schema. Jadi penerjemahannya tipis: pemetaan
inputSchema -> parameters. Yang penting, hasil ini DIBANGKITKAN dari server,
bukan ditulis tangan, sehingga tidak ada lagi duplikasi definisi tool.
"""
from typing import Any, Dict, List


# Parameter yang WAJIB diisi backend, bukan LLM. user_id menentukan kepemilikan
# data; membiarkan LLM mengisinya adalah risiko keamanan dan sumber kesalahan.
# Backend menyuntik user_id dari sesi login (sanitize_tool_args) sebelum tools/call,
# jadi parameter ini disembunyikan dari schema yang dilihat model.
_BACKEND_INJECTED_PARAMS = {"user_id"}


def mcp_tools_to_llm_schema(mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ubah daftar tool MCP menjadi daftar tool format function-calling LLM."""
    llm_tools: List[Dict[str, Any]] = []
    for tool in mcp_tools:  # proses satu per satu tiap tool dari server
        # inputSchema = bentuk argumen tool (sudah JSON Schema). Kalau kosong,
        # pakai schema object kosong sebagai cadangan agar tidak error.
        schema = tool.get("inputSchema") or {"type": "object", "properties": {}}

        # Salin agar tidak memutasi hasil list_tools, lalu buang parameter yang
        # disuntik backend dari properties maupun daftar required.
        parameters = dict(schema)
        props = dict(parameters.get("properties") or {})
        for hidden in _BACKEND_INJECTED_PARAMS:  # buang user_id dari daftar parameter
            props.pop(hidden, None)
        parameters["properties"] = props

        # user_id juga dibuang dari daftar "required", kalau tidak LLM dipaksa
        # mengisi parameter yang justru kita sembunyikan.
        required = [r for r in (parameters.get("required") or []) if r not in _BACKEND_INJECTED_PARAMS]
        if required:
            parameters["required"] = required
        else:
            parameters.pop("required", None)  # tak ada required tersisa -> hapus kuncinya

        # Bungkus jadi format function-calling yang dimengerti LLM.
        llm_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": parameters,
                },
            }
        )
    return llm_tools
