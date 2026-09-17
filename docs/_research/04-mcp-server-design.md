# 04 — Designing an MCP Server to Drive Vivado and Vitis

**Status:** research / design note. Not an implementation.
**Date of writing:** 2026-09-17.
**Scope of the project:** an open-source repository whose purpose is to let an AI drive
AMD Vivado / Vitis through **MCP** (Model Context Protocol) and through "skills".
The MCP server is Python, stdio-first, installable by a non-specialist.
**Explicit non-goals:** this is *not* an FPGA project. No EDA tool is installed on the
machine that produced this note; nothing was installed; no code in this note was executed.
Every external API or configuration format cited below carries the URL it was verified
against, and the version concerned is stated.

**Verification legend used throughout:**
- `[V]` = verified by fetching the page cited in the same paragraph.
- `[S]` = seen in a search result summary, not fetched in full — treat as weaker.
- `[U]` = unverified / to be confirmed before implementation.

---

## 0. Version landscape (checked 2026-09-17)

| Component | Current version | Notes / source |
|---|---|---|
| MCP specification | **2026-07-28** (latest revision); previous: 2025-11-25, 2025-06-18 | `[V]` https://modelcontextprotocol.io/specification/latest — the page states the spec is based on `schema/2026-07-28/schema.ts` |
| MCP spec, previous revisions | 2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05 | `[V]` https://modelcontextprotocol.io/specification/2026-07-28/changelog ("since the previous revision, 2025-11-25") |
| Official Python SDK (`mcp` on PyPI) | **2.2.0** (released 2026-09-07); v2.0.0 released 2026-07-28 | `[V]` https://pypi.org/project/mcp/ |
| Python SDK v1 line | maintenance only; last release **1.28.1** (2026-06-26) per secondary source | `[S]` — v1 "is not going anywhere… keeps getting critical fixes"; pin `mcp>=1.28,<2` if you cannot migrate `[V]` https://py.sdk.modelcontextprotocol.io/whats-new/ |
| Standalone FastMCP (PrefectHQ) | **4.0.3** (2026-09-05); 3.0.0 GA 2026-02-18 | `[V]` https://pypi.org/project/fastmcp/ |
| FastMCP repo / docs | https://github.com/PrefectHQ/fastmcp , https://gofastmcp.com | `[V]` |
| Claude Desktop | reads `claude_desktop_config.json`; no version number in the docs | `[V]` https://modelcontextprotocol.io/quickstart/user |
| VS Code / Copilot | `mcp.json` (workspace or user profile), `inputs`, `envFile`, `dev.watch`, `sandboxEnabled` | `[V]` https://code.visualstudio.com/docs/agent-customization/mcp-servers and https://github.com/microsoft/vscode-docs/blob/main/docs/copilot/reference/mcp-configuration.md |
| Cline | `cline_mcp_settings.json` (extension), `~/.cline/mcp.json` (CLI) | `[V]` https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx |
| Hermes Agent | `mcp_servers:` block in `~/.hermes/config.yaml` | `[V]` https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference |
| Vivado / Vitis reference docs used | UG835 (Tcl commands, 2026.1), UG900 (logic simulation), UG973 (install/licence, 2026.1) | `[V]` URLs given in §1.4 and §2 |

**The single most important version fact for this project:** the protocol changed shape
between the revision most tutorials describe (2025-06-18 / 2025-11-25) and the current one
(2026-07-28). In 2026-07-28 the protocol is **stateless**: there is no `initialize`
handshake, no `Mcp-Session-Id`, no server-initiated requests; every request carries its own
protocol version and client capabilities in `_meta`, and servers must implement a
`server/discover` RPC `[V]` https://modelcontextprotocol.io/specification/2026-07-28/changelog.
A well-behaved SDK serves both eras from one server object, so this project should not have
to choose — but the note below flags where the two eras differ, because client compatibility
is the main risk (`[V]` https://py.sdk.modelcontextprotocol.io/whats-new/ — "One SDK, both
protocol eras").

---

## 1. MCP essentials that matter for an EDA-driving server

### 1.1 The three primitives, and which ones this project needs

MCP servers expose three feature types to clients `[V]` https://modelcontextprotocol.io/specification/latest:

- **Tools** — functions the *model* can invoke ("model-controlled"). Used for anything with
  a side effect or a parameterised query.
- **Resources** — context/data the client or model can read: file-like content addressed by
  URI, with resource templates for parameterised URIs.
- **Prompts** — reusable templates the *user* invokes, surfaced as slash-commands or menu
  entries in the host.

Mapping to this project:

| Need | Primitive | Why |
|---|---|---|
| read a VHDL file, read a log, read a report | **tool** *and* **resource** | A resource (`vivado://project/{path}`) lets the user attach a file to the conversation without a tool call; a tool (`read_project_file`) lets the model fetch it when it decides to. Ship both; keep the resource read-only. |
| run synthesis, program the FPGA, write a file | **tool** only | Side effects, parameters, approval UX. |
| "start a new project from scratch", "fix my timing" | **prompt** (optional) | Convenience for the human user; low priority for v1. |

Practical recommendation: **implement everything as tools first.** Resources are genuinely
useful for logs and reports (see §3.5 caching), and prompts are cheap to add, but tools are
the only primitive every client renders consistently.

### 1.2 Transports: stdio vs Streamable HTTP

The spec defines exactly two standard transports; clients **SHOULD** support stdio whenever
possible, and custom transports must preserve the JSON-RPC message format and lifecycle
`[V]` https://modelcontextprotocol.io/specification/2025-06-18/basic/transports.

**stdio**
- The client launches the server as a subprocess; JSON-RPC messages are newline-delimited on
  stdin/stdout, and **must not** contain embedded newlines.
- The server **MUST NOT** write anything to stdout that is not a valid MCP message; `stderr`
  is free for logging ("all types of logging", clarified in 2025-11-25) `[V]` same URL +
  https://modelcontextprotocol.io/specification/2025-11-25/changelog.
- One client, one process, no network surface, no auth needed.

**Streamable HTTP**
- Single endpoint path (e.g. `https://example.com/mcp`) supporting POST and GET; POST per
  message; optional SSE stream on the response; in the 2025-06-18 era a session ID was
  returned in `Mcp-Session-Id` and echoed back, and the negotiated version had to be sent in
  an `MCP-Protocol-Version` header on subsequent requests `[V]` same URL.
- 2026-07-28 removes the session ID header entirely: "Servers that need cross-call state use
  explicit, server-minted handles passed as ordinary tool arguments" `[V]`
  https://modelcontextprotocol.io/specification/2026-07-28/changelog — which is exactly the
  `job_id` design in §3.2.

**Decision for this project:** ship **stdio as the default and only supported transport in
v1**, with `--transport http` opt-in behind a localhost bind and a bearer token. Rationale:
(a) every desktop/IDE client launches stdio servers from a config file, which is the
audience; (b) an HTTP EDA server would expose "compile arbitrary code and program hardware"
to the network, which the spec's own security principles argue against `[V]`
https://modelcontextprotocol.io/specification/latest (Security and Trust & Safety).
Note that stdio is also a privileged escalation path in *proxy* scenarios — see §4.6.

Python SDK v2 note: transport configuration moved to `run()`; the FastMCP/MCPServer `run()`
signature takes `transport: Literal["stdio", "http", "sse"]`, with stdio the default `[V]`
https://gofastmcp.com/python-sdk/fastmcp-server-mixins-transport (FastMCP) and `[V]`
https://py.sdk.modelcontextprotocol.io/whats-new/ (SDK v2, "Transport configuration moved to
`run()`"). So `mcp.run(transport="stdio")` is valid but redundant on FastMCP; it is worth
writing explicitly for readability.

### 1.3 Capability negotiation

**Legacy era (≤ 2025-11-25).** The client sends `initialize` with its `protocolVersion`,
`capabilities` and `clientInfo`; the server answers with its own `capabilities` and
`serverInfo`; the client then sends `notifications/initialized`. A server supporting tools
**MUST** declare the `tools` capability, with an optional `listChanged` flag `[V]`
https://modelcontextprotocol.io/specification/2026-07-28/server/tools.

```json
{ "capabilities": { "tools": { "listChanged": true } } }
```

**Current era (2026-07-28).** The handshake is gone. Every request carries
`_meta` fields — `io.modelcontextprotocol/protocolVersion`,
`io.modelcontextprotocol/clientCapabilities`, and optionally
`io.modelcontextprotocol/clientInfo` — and servers identify themselves in each result's
`_meta` via `io.modelcontextprotocol/serverInfo`. Version mismatch returns
`UnsupportedProtocolVersionError`. Servers **MUST** implement `server/discover`, which
advertises supported protocol versions, capabilities and identity `[V]`
https://modelcontextprotocol.io/specification/2026-07-28/changelog.

**What this means concretely for the Vivado server:** declare the `tools` capability only.
Do not rely on client capabilities for anything mandatory — in particular, do **not** assume
the client supports sampling or elicitation, because for a 2026-07-28 client those travel as
multi-round-trip results, not as server-initiated requests `[V]` same URL (item 7). If the
design ever wants to ask the human "which board should I program?", implement it as an
ordinary tool argument, or use the Tasks extension's `input_required` status (§1.6), not as
an elicitation call.

At the client end, Hermes Agent exposes this explicitly with a `protocol` key:
`auto` (default — legacy handshake first, falling back to a `server/discover` stateless
probe), `stateless`, or `legacy` `[V]`
https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference. That is a useful
compat lever when debugging.

### 1.4 Tool discovery: what the client actually receives

Discovery is `tools/list`; invocation is `tools/call`. Per the current spec `[V]`
https://modelcontextprotocol.io/specification/2026-07-28/server/tools:

- Each tool carries `name`, optional `title`, `description`, optional `icons`,
  `inputSchema`, optional `outputSchema`, and optional `annotations`.
- `inputSchema` **MUST** be a valid JSON Schema object (not `null`); the default dialect is
  **JSON Schema 2020-12** when no `$schema` is declared. For a tool with no parameters the
  recommended form is `{"type": "object", "additionalProperties": false}`.
- Servers **SHOULD** return tools in a **deterministic order** — same order across requests
  when the tool set has not changed — so clients can cache and so prompt-cache hit rates stay
  high. *Practical rule: register tools in a fixed, hand-chosen order, never from a dict
  iteration or from filesystem discovery.*
- `tools/list` supports **pagination** (opaque cursor, `nextCursor`; clients must treat a
  missing cursor as end-of-list and cursors as opaque; invalid cursor → `-32602`) `[V]`
  https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination.
  Keep the catalogue under ~30 tools and no pagination will ever trigger.
- List/read results may carry cache hints `ttlMs` and `cacheScope` (SEP-2549, new in
  2026-07-28) `[V]` https://py.sdk.modelcontextprotocol.io/whats-new/ ; FastMCP exposes them
  as `cache_ttl` / `cache_scope` server options and `list_page_size` for paging `[V]`
  https://gofastmcp.com/servers/server.
- **Tool name guidance** was added in 2025-11-25 (SEP-986) `[V]`
  https://modelcontextprotocol.io/specification/2025-11-25/changelog. Names arrive at the
  model namespaced by the client (MCP itself notes clients may concatenate a server name,
  e.g. `web1___search_web`) `[V]`
  https://modelcontextprotocol.io/specification/2025-11-25/server/tools. Consequence:
  prefer `vivado_run_synthesis` over `run_synthesis`, because the model may see
  `vivado__vivado_run_synthesis` and will read the tool name as part of the description.

Also relevant: FastMCP dereferences `$ref` in generated schemas at serve time because some
clients (VS Code Copilot, Claude Desktop named explicitly) do not handle JSON Schema
references well `[V]` https://gofastmcp.com/servers/tools. Avoid deeply nested Pydantic
models in tool signatures for the same reason.

### 1.5 Writing tool descriptions an LLM will call correctly

The spec's own best-practices list `[V]`
https://modelcontextprotocol.io/specification/2025-11-25/server/tools: (1) clear descriptive
names and descriptions, (2) detailed JSON Schema for parameters, (3) **include examples in
the description**, (4) proper error handling and validation, (5) progress reporting for long
operations, (6) keep operations focused and atomic, (7) document the expected return
structure, (8) implement timeouts, (9) consider rate limiting, (10) log usage.

Concrete rules for the Vivado/Vitis catalogue, derived from those plus the EDA domain:

1. **State the side effect in the first sentence.** "Runs Vivado synthesis on the current
   project as a background job and returns immediately with a `job_id`." A model that
   believes a 20-minute synthesis is synchronous will chain calls wrongly.
2. **Say what the tool does *not* do.** "Does not open a new project; call
   `vivado_create_project` or `vivado_open_project` first."
3. **Document the return shape inline**, and mirror it in `outputSchema` so clients that
   support structured content can use it.
4. **Include one worked example with realistic arguments**, especially for anything with a
   path or a part number: `{"design": "datapath", "part": "xc7z020clg400-1"}`.
5. **Name the units and the failure mode** of numeric parameters: `timeout_s` (seconds),
   `jobs` (parallel synthesis jobs), `max_lines` (log truncation budget).
6. **Set annotations honestly** — `readOnlyHint`, `destructiveHint`, `idempotentHint`,
   `openWorldHint` `[V]` https://modelcontextprotocol.io/specification/2026-07-28/server/tools
   and https://modelcontextprotocol.io/specification/2025-11-25/server/tools (table of
   defaults). Clients surface these in approval UIs, so a wrong `destructiveHint: false` on
   `program_fpga` is a real safety bug — and note the spec's warning that annotations are
   *hints* obtained from a server and must be treated as untrusted for security decisions
   `[V]` https://modelcontextprotocol.io/specification/latest.
7. **Use `Literal[...]`/enums rather than free strings** for bounded choices
   (`step: Literal["synth","impl","bitstream"]`), so the schema constrains the model instead
   of the prose. FastMCP generates the enum into the schema `[V]`
   https://gofastmcp.com/servers/tools.
8. **Errors go inside the result, not as protocol errors**: set `isError: true` and put
   actionable text in `content`. The spec is explicit that clients **SHOULD** surface tool
   execution errors to the model to allow self-correction, while protocol errors are less
   recoverable `[V]`
   https://modelcontextprotocol.io/specification/2026-07-28/server/tools (Error Handling) and
   `[V]` https://modelcontextprotocol.io/specification/2025-11-25/changelog (SEP-1303:
   input-validation errors should be tool execution errors, not protocol errors). This is the
   most important behavioural rule in this whole document for an EDA workflow — see §5.
9. **Keep the catalogue small and orthogonal.** Every tool costs schema tokens on every
   turn. Do not expose `vivado_tcl` as the only tool "because the model can do anything with
   it": a raw Tcl escape hatch is valuable (see §2.14) but it produces unparseable errors and
   unverifiable state, so it belongs *alongside* typed tools, never instead of them.

**Anti-patterns observed in prior art to avoid:** a single `run_vivado(command: str)` tool
(the model then invents Tcl); tools whose description is the Python docstring of an internal
helper ("Open a session object and return its stats"); tools with `**kwargs`-like free-form
dicts (FastMCP rejects `*args`/`**kwargs` outright `[V]` https://gofastmcp.com/servers/tools).

### 1.6 Limits: payloads, timeouts, and long-running work

- **No fixed payload limit in the protocol.** MCP does not mandate a maximum message size;
  limits come from the implementation. The one concrete number verified: Streamable HTTP
  servers in SDK v2 **reject bodies over 4 MiB with HTTP 413** `[V]`
  https://pypi.org/project/mcp/ (v2.0.0 release notes). For stdio there is no such cap, but
  the practical cap is the model's context window. Design rule: **no tool result should ever
  return a raw EDA log.** Return a structured summary plus a bounded tail plus a path (§5.1).
- **Timeouts are enforced at three levels**, and they conflict:
  1. the *client's* per-call timeout (Hermes: `timeout`, documentation default 120 s in the
     `native-mcp` skill text, **300 s** in the config reference table `[V]`
     https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference — a
     discrepancy to confirm; treat 120–300 s as the realistic window),
  2. the *server framework's* per-tool timeout (FastMCP's `timeout=` decorator argument,
     added in 3.0.0; exceeding it returns an MCP error `[V]`
     https://gofastmcp.com/servers/tools),
  3. the *subprocess's* own timeout, which the server sets.
  Because a synthesis or implementation run takes minutes to hours, **no long EDA operation
  may be a blocking tool call.** Return a `job_id` immediately and let the model poll.
- **The Tasks extension** is the protocol-level answer to exactly this problem. It lets a
  server return a durable handle instead of blocking; the client polls `tasks/get`, supplies
  mid-flight input via `tasks/update`, and the task carries status
  (`working`, `input_required`, `completed`, `failed`, `cancelled`), a TTL and a suggested
  polling interval. The rationale is spelled out and matches this use case: "No long-lived
  connections… Crash resilience… Progress visibility" `[V]`
  https://modelcontextprotocol.io/specification/2026-07-28/basic/utilities/tasks.
  It is an **extension**, negotiated via `io.modelcontextprotocol/tasks`, so client support
  is not universal. **Design decision:** implement background jobs *in the server* (a
  `job_id` returned from a normal tool call), which works with every client; treat Tasks as a
  later, additive optimisation. FastMCP also exposes `tasks=True` on the server `[V]`
  https://gofastmcp.com/servers/server.
- **Progress notifications** (`ctx.report_progress`) and log messages via `ctx.info/warning/
  error` are the cheap middle ground: they are request-scoped and flow on the response stream
  `[V]` https://modelcontextprotocol.io/specification/2026-07-28/changelog and `[V]`
  https://gofastmcp.com/servers/tools. Use them for "synthesis: 40% (200/500 steps)" so the
  user sees motion during the *polling-free* part of a wait. Do not depend on them.

### 1.7 Known published servers for Vivado / Vitis / FPGA / EDA (prior art)

These are the closest existing implementations; the catalogue in §2 is informed by their
tool sets and by what they leave out.

| Project | URL | What it does | Notable design choice |
|---|---|---|---|
| `coreyhahn/vivado_mcp` | https://github.com/coreyhahn/vivado_mcp `[V]` | Session-managed Vivado: `start_session`, `open_project`, `run_synthesis`, `run_implementation`, `generate_bitstream`, `get_timing_summary`, `get_timing_paths`, `get_utilization`, `get_clocks`, hierarchy/ports/nets/cells queries, xsim control, raw TCL | Holds a **persistent Vivado Tcl session** via pexpect to avoid the ~30 s startup per command; stdio; MIT; Vivado 2023.2+ |
| `QingquanYao/vitis_mcp` | https://github.com/QingquanYao/vitis_mcp `[V]` | 28 tools for Vitis Unified IDE: `create_platform`, `create_app`, `import_sources`, `set_bsp_config`, `add_library`, `build_app`, `clean_app`, `list_components`, `get_build_log`, hardware debug (`hw_connect`, `hw_list_targets`, `hw_program_fpga`, `hw_program_elf`, memory/register access) | Persistent `vitis -i` Python REPL; **base64-encoded commands with a sentinel protocol, user params `repr()`-quoted, never interpolated**; multi-session via `session_id` |
| `slauzinho/vivado-mcp` | https://github.com/slauzinho/vivado-mcp `[S]` | Auto-detects Vivado installs (Windows/Linux/macOS), full flow, individual build steps, build status queries, clean builds | `VIVADO_PATH` / `VIVADO_VERSION` env vars in the client config |
| `lcapossio/fpgaZeroMCP` | https://github.com/lcapossio/fpgaZeroMCP/blob/main/README.md `[V]` | Open-source-toolchain FPGA server (Yosys, nextpnr, iverilog, Verilator, Verible, GHDL) + IP-core registry; lint, simulate, synthesise, P&R, program | **Concurrent requests** — `ping`, build status and cancel are answered while a slow call runs, and `notifications/cancelled` aborts an in-flight call; `structuredContent` on results; uniform `error_code` taxonomy for retry/fallback |
| `ssql2014/mcp4eda` | https://github.com/ssql2014/mcp4eda `[V]` | Collection of 8 EDA servers: Yosys, Verilator, Verible, GTKWave, KLayout, AnySilicon, RTL parser, supply chain | TypeScript/Node, Claude Desktop-oriented |
| `airry12/verilog-mcp-server` | https://github.com/airry12/verilog-mcp-server `[S]` | tree-sitter + pyslang semantic analysis of Verilog/SystemVerilog: module search, signal tracing, hierarchy, FSM detection, clock-domain analysis | Pure static analysis, no tool invocation |
| `kiranreddi/sentinel-dv` | listed at https://lobehub.com/mcp?q=SystemVerilog `[S]` | Verification-intelligence server (SystemVerilog/UVM/cocotb), security-first, external `config.yaml` for artifact roots and security limits | "Security-first" framing with redaction settings |

**Gap analysis.** Taken together, the existing Vivado servers cover the *flow* (session,
synth, impl, bitstream, reports) and the Vitis server covers *software* flows, but:

1. **None of them expose a first-class, resumable background-job model for long runs.**
   They either block the tool call or hold a REPL. fpgaZeroMCP is the only one that
   explicitly handles concurrency and cancellation `[V]` (same URL).
2. **None of them parse reports into structured JSON with a stable schema** — they return
   `get_timing_summary` as text. A model that has to regex a WNS number out of a text blob
   will eventually read the wrong number.
3. **cocotb is essentially absent** from the Vivado-oriented servers, and — importantly —
   **cocotb does not officially support the Vivado simulator.** The supported simulator list
   is Icarus, Verilator, VCS, Riviera-PRO, Active-HDL, Questa, ModelSim, Incisive, Xcelium,
   GHDL, NVC `[V]` https://docs.cocotb.org/en/stable/simulator_support.html. Running cocotb
   on `xsim` requires the third-party `vicoco` Vivado runner, which is what MIT 6.205 uses,
   and which restricts access to module input/output ports only (no internal signals)
   `[V]` https://fpga.mit.edu/6205/F25/documentation/vicoco. **This must be reflected in the
   tool contract: `run_cocotb_test` takes an explicit simulator parameter and reports
   honestly when the requested simulator is unsupported**, rather than pretending `xsim`
   works with cocotb.
4. **No shared "skills" surface.** The project's `skills.md` already defines an HTTP-ish
   pseudoconvention (`GET /vivado/...`, `POST /vivado/build`) that is *not* MCP and must not
   be confused with it — see §6.5 on reconciling the two.

---

## 2. Recommended tool catalogue

Notation: **In** = arguments, **Out** = result content, **When** = when the model should
reach for it. All tools return a JSON object in `structuredContent` plus a short text
rendering; all errors follow §5.1.

Grouping guidance: keep the prefix pattern `<domain>_<verb>_<noun>` and register the tools in
the listed order for deterministic `tools/list` output (§1.4).

### 2.1 Project file access (read / write / list)

**`read_project_file`**
- **In:** `path: str` (relative to the workspace root), `max_bytes: int = 200000`
- **Out:** `{path, content, truncated: bool, bytes, encoding}`
- **When:** any time the model needs source, constraints, Tcl scripts or a log it already
  knows the path of. Refuses paths outside the workspace (§4.2).
- **Annotations:** `readOnlyHint: true`, `openWorldHint: false`.
- **Notes:** never return a file larger than the budget silently — set `truncated` and tell
  the model to use `read_log` / `tail_log` for the rest.

**`write_project_file`**
- **In:** `path: str`, `content: str`, `overwrite: bool = false`
- **Out:** `{path, bytes_written, created: bool, sha256}`
- **When:** creating or editing HDL, XDC, Tcl, Makefiles, testbenches.
- **Annotations:** `readOnlyHint: false`, `destructiveHint: true`, `idempotentHint: true`.
- **Notes:** write atomically (temp file + `os.replace`, §4.4); refuse `overwrite` on an
  existing file unless explicitly true; return the hash so the model can detect a later
  accidental change. This is the tool most likely to be abused by a confused model, so it
  needs the tightest path checks.

**`list_project_files`**
- **In:** `glob: str = "**/*"`, `max_entries: int = 200`
- **Out:** `[{path, size, mtime}]`, sorted
- **When:** orienting in an unknown project, or before writing a Tcl script that must name
  real files.
- **Annotations:** `readOnlyHint: true`.

### 2.2 Project creation / opening

**`vivado_create_project`**
- **In:** `name: str`, `part: str` (e.g. `xc7z020clg400-1`), `dir: str`,
  `board_part: str|None = None`, `top: str|None = None`
- **Out:** `{project_path, part, created: bool}`
- **When:** starting a design. Not for reopening an existing one.
- **Implementation:** generated Tcl, run through `vivado -mode batch -source ...` with
  `create_project -force` semantics chosen by the caller (`overwrite: bool = false`).
- **Notes:** validate `part` against `part_regex` and, better, against a cached
  `get_parts`/`get_board_parts` listing so the model cannot invent a device.

**`vivado_open_project`**
- **In:** `xpr: str`
- **Out:** `{project_path, part, top, filesets}` — via `get_property` queries
- **When:** before any flow command on an existing `.xpr`.

### 2.3 Build steps (long jobs)

**`vivado_run_synthesis`**, **`vivado_run_implementation`**, **`vivado_run_bitstream`** —
or one tool with a `step` enum. Recommendation: **one tool, `vivado_run_step`**, with
`step: Literal["synth","impl","bitstream"]`, because the three differ only by the Tcl
command and the downstream artefact, and a `Literal` keeps the model inside the schema.

- **In:** `xpr: str`, `step: Literal["synth","impl","bitstream"]`, `jobs: int = 4`,
  `timeout_s: int = 3600`, `directives: str|None = None`
- **Out:** `{job_id, step, status: "running", log_path, run_dir}`
- **When:** after the project is created/opened and sources are registered. **Returns
  immediately**; the model then polls with `job_status` (§2.5).
- **Annotations:** `readOnlyHint: false`, `destructiveHint: true`, `idempotentHint: false`
  (re-running synthesis is not free), `openWorldHint: false`.
- **Notes:** the underlying Tcl is `launch_runs synth_1 -jobs N` / `wait_on_run` for project
  mode; `write_bitstream` reaches `write_hw_platform` territory (see `vivado_export_xsa`).
  Do **not** wrap `wait_on_run` inside the tool call: that is the blocking anti-pattern.

### 2.4 Python/HDL scripting escape hatch (bounded)

**`vivado_tcl`**
- **In:** `xpr: str|None`, `script: str`, `timeout_s: int = 600`, `job_id: str|None = None`
- **Out:** `{job_id, stdout_tail, log_path, exit_code}` (or a synchronous result for scripts
  that finish inside the timeout)
- **When:** advanced/edge cases the typed tools do not cover (querying a property, walking
  the hierarchy with a custom filter).
- **Annotations:** `destructiveHint: true`.
- **Notes:** this is the tool that makes the server usable *and* the one that makes it
  unsecurable if unbounded. Mitigations: run it in the same sandbox and workspace as every
  other tool, cap size and time, log the full script, and mark it explicitly in the tool
  description as "prefer the typed tools; use this only when no typed tool fits" (§4.3).

### 2.5 Job supervision

**`job_status`**
- **In:** `job_id: str`, `include_tail: int = 0`
- **Out:** `{job_id, kind, state: "queued"|"running"|"succeeded"|"failed"|"timeout"|"cancelled",
  started_at, elapsed_s, exit_code, log_path, progress: {step, percent}|None, tail: [str]}`
- **When:** the only correct way to wait for a build step. The model should poll, and the
  description must say so: "Poll every 20–60 s; do not poll in a tight loop."
- **Annotations:** `readOnlyHint: true`, `idempotentHint: true`.

**`list_jobs`** — `In: {state: str|None, limit: int = 20}` → `[{job_id, kind, state, started_at, elapsed_s, log_path}]`.
**`cancel_job`** — `In: {job_id, force: bool = false}` → `{job_id, state, killed: bool, signal}`.
- **When:** the user says "stop it", or a job exceeded its budget. Implemented as terminate
  (SIGTERM) then kill (SIGKILL) after a grace period, killing the process **group** (§3.2).
- **Annotations:** `cancel_job` is `destructiveHint: true`.

### 2.6 Log reading

**`read_log`**
- **In:** `path: str`, `severity: Literal["ERROR","CRITICAL WARNING","WARNING","INFO","ANY"] = "ERROR"`,
  `max_matches: int = 50`, `context: int = 0`, `offset: int = 0`
- **Out:** `{path, total_lines, matched: {ERROR: n, WARNING: n, INFO: n}, matches: [{line_no, severity, text, context_before, context_after}], truncated: bool}`
- **When:** after a failed job — **always before guessing at a cause**. This is the single
  highest-value tool in the whole catalogue, because it converts "synthesis failed" into a
  line-numbered, citable fact.
- **Annotations:** `readOnlyHint: true`, `idempotentHint: true`.
- **Notes:** Vivado severity tokens are literally `ERROR`, `CRITICAL WARNING`, `WARNING`,
  `INFO` (in `[ERROR]`, `[Common 17-39]` style prefixes); match the bracketed severity, not
  the bare word, to avoid catching the word "error" in an INFO message. Return **line
  numbers**, always: the model can then fetch exact context and the user can jump there.

**`tail_log`**
- **In:** `path: str`, `lines: int = 200`, `grep: str|None = None`
- **Out:** `{path, from_line, to_line, lines: [str], truncated_from: int|None}`
- **When:** watching a running job, or reading the last lines of any tool's output.
- **Annotations:** `readOnlyHint: true`, `idempotentHint: true`.
- **Notes:** bounded by `lines` (default 200, hard max ~2000) so it can never flood the
  context window; report `from_line` so the model knows what it *did not* see.

### 2.7 Report parsing

**`parse_timing_report`**
- **In:** `path: str` (a `*.rpt` or the job's run directory), `max_paths: int = 20`
- **Out:** structured:
  ```json
  {"wns_ns": -0.412, "tns_ns": -18.7, "whs_ns": 0.021, "ths_ns": 0.0,
   "met": false, "clock": "sys_clk",
   "failing_paths": [{"path_group": "sys_clk", "slack_ns": -0.412,
                      "from": "...", "to": "...", "logic_levels": 12,
                      "report_line": 1487}]}
  ```
- **When:** after implementation, before deciding whether timing is a problem. Also used to
  answer "is timing met?" without the model reading a 4000-line report.
- **Annotations:** `readOnlyHint: true`, `idempotentHint: true`.
- **Notes:** this is a **deterministic parser owned by the server**, not an LLM reading task.
  Anchor each number to a line number in the source report so the user can audit it. If the
  report cannot be parsed, return `isError: true` with the offending lines — never a
  partial/guessed number.

**`parse_utilization_report`**
- **In:** `path: str`
- **Out:** `{"part": "...", "resources": [{"name": "CLB LUTs", "used": 4123, "available": 53200,
  "pct": 7.75, "level": "LUT"}]}`
- **When:** when the model must reason about whether to duplicate a module (=resource cost)
  or whether the design fits.

**`parse_drc_report` / `vivado_report` (generic)**
- **In:** `xpr: str`, `report: Literal["timing_summary","utilization","drc","clocks","power","timing_paths"]`,
  `args: dict|None`
- **Out:** the structured form of the requested report (internally generating it into a
  scratch run directory first, then delegating to the parser).
- **When:** when the model needs a report that no previous job produced.

### 2.8 Simulation

**`vivado_run_xsim`**
- **In:** `sources: list[str]`, `top: str`, `sim_set: Literal["behavioral","post_synth","post_impl"] = "behavioral"`,
  `runtime: str|None` (e.g. `"10us"`), `timeout_s: int = 900`, `wdb: bool = true`
- **Out:** `{job_id, log_path, sim_dir}` then, on completion, `{state, errors: n, warnings: n,
  simulationFailed: bool, wdb_path}`
- **When:** quick functional simulation without a cocotb testbench, or when the user asks for
  a waveform.
- **Implementation:** `xvlog`/`xvhdl` → `xelab <top> -s <snap>` → `xsim <snap> -R`; the
  canonical batch form is `xelab top -s mysim; xsim mysim -R` (a `.prj` file can carry
  per-file language/library instead of listing files on the command line) `[V]`
  https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Compiling-and-Simulating.
- **Notes:** do not open the GUI (`-gui`) — see `DISPLAY` in §3.3; a headless server must not
  depend on an X server.

**`run_cocotb_test`**
- **In:** `test_dir: str` (the directory containing the cocotb testbench and Makefile),
  `sim: Literal["icarus","verilator","ghdl","questa","xcelium","vcs","riviera","nvc","vivado"] = "icarus"`,
  `testcase: str|None = None`, `timeout_s: int = 900`, `waves: bool = false`
- **Out:**
  ```json
  {"state": "failed", "sim": "icarus", "tests_run": 12, "passed": 11, "failed": 1,
   "failures": [{"testcase": "test_counter_wraps", "time_ns": 450,
                 "assertion": "Error: got 7 expected 9",
                 "traceback": "…File tb/test_counter.py, line 41, in test_counter_wraps…",
                 "log_line": 312}],
   "log_path": "…/results.xml", "stdout_path": "…/sim_build/…"}
  ```
- **When:** any verification task. The model should call this rather than reading a testbench
  and reasoning about it.
- **Annotations:** `readOnlyHint: false` (writes `sim_build/`, `results.xml`), `idempotentHint: true`.
- **Notes — the honest limitation:** cocotb's officially supported simulators do **not**
  include Vivado's `xsim` `[V]` https://docs.cocotb.org/en/stable/simulator_support.html;
  `SIM` accepts `icarus`, `verilator`, `vcs`, `riviera`, `activehdl`, `questa`, `modelsim`,
  `ius`, `xcelium`, `ghdl`, `nvc` (same URL). Using `xsim` requires the `vicoco` third-party
  runner, whose restrictions include "you can only access/write to signals that are
  inputs/outputs from the module you're simulating" `[V]`
  https://fpga.mit.edu/6205/F25/documentation/vicoco. The tool must therefore (a) accept
  `sim: "vivado"` only when `vicoco` is importable, (b) return a clear `isError` otherwise,
  and (c) document in the description that `icarus`/`ghdl`/`verilator` are the zero-cost
  defaults. Parse `results.xml` (cocotb's xUnit output) for pass/fail and the traceback, not
  the console text.

### 2.9 Design introspection

**`list_hdl_modules`**
- **In:** `root: str = "."`, `language: Literal["vhdl","verilog","sv","all"] = "all"`
- **Out:** `[{"name": "datapath", "kind": "entity", "file": "src/hdl/datapath.vhd", "line": 14,
  "ports": [{"name": "i_clk", "dir": "in", "type": "std_logic"}]}]`
- **When:** orienting in the project, checking a `port map` against the real entity, building
  a testbench, or answering "which module instantiates X".
- **Annotations:** `readOnlyHint: true`, `idempotentHint: true`.
- **Notes:** implement with a real parser (tree-sitter, `hdlConvertor`, `hierarchy_parser`),
  not regex — the whole point is that the answer is *more* reliable than what the model would
  infer from reading the files. Cache by (path, mtime, size).

### 2.10 Hardware platform export (XSA)

**`vivado_export_xsa`**
- **In:** `xpr: str`, `out: str`, `include_bit: bool = true`, `fixed_xsa: bool = false`
- **Out:** `{xsa_path, bytes, sha256, included_bit: bool}`
- **When:** only after a successful bitstream, and only when the user wants to move to Vitis.
- **Implementation:** `write_hw_platform -fixed -include_bit -force -file <out>` — the command
  "writes a Xilinx support archive (XSA) of the current design for use as a hardware
  platform" `[V]` https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_hw_platform
  (UG835, 2026.1 English).
- **Notes:** a common real-world failure is `-include_bit` not working in non-project mode, or
  generating a different XSA than expected in 2024.2 `[S]`
  https://adaptivesupport.amd.com/s/question/0D54U00008yWfX0SAK/ (forum). Verify the produced
  file exists and has plausible size before reporting success; return the hash.

### 2.11 Vitis: platform, application, build

**`vitis_create_platform`**
- **In:** `xsa: str`, `name: str`, `workspace: str`, `cpu: str|None = None`,
  `os: Literal["standalone","freertos","linux"] = "standalone"`
- **Out:** `{platform_path, components: [...], log_path}`
- **When:** after XSA export; creates the platform and builds its BSP.
- **Implementation:** Vitis Unified IDE can be driven from a `vitis -i` Python REPL /
  scripted session; the same capability set is available from `xsct` (Xilinx Software
  Command-line Tool), which is "an 'umbrella' tool that covers HSI, XSDB, Bootgen, and the
  debugger… everything we can achieve in the Vitis tool can be achieved on the command line"
  `[S]` https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841693/HSI+.

**`vitis_create_app`**
- **In:** `platform: str`, `name: str`, `domain: str`, `template: str|None = None`,
  `sources: list[str] = []`
- **Out:** `{app_path, elf_expected_path, log_path}`

**`vitis_build_app`**
- **In:** `app: str`, `jobs: int = 4`, `timeout_s: int = 1800`
- **Out:** `{job_id, log_path}` then `{state, elf_path, errors: n, warnings: n}`
- **When:** compiling bare-metal/FreeRTOS/Linux applications. Returns a `job_id` (long job).

**`vitis_build_log`** — thin wrapper over `read_log` with the Vitis severity vocabulary, or
simply reuse `read_log` and document where Vitis writes its log.

### 2.12 Board / hardware targets

**`list_hw_targets`**
- **In:** `url: str|None = None` (hardware server URL, e.g. `localhost:3121`)
- **Out:** `{targets: [{url, name, devices: [{name, part, idcode}]}], hw_server_url}`
- **When:** before programming anything, and whenever the user asks "is the board
  connected?".
- **Implementation:** in Vivado Tcl — `open_hw_manager`, `connect_hw_server -url …`,
  `get_hw_targets`, `open_hw_target`, `get_hw_devices`; these are the exact commands shown in
  the AMD/Xilinx readback workflow `[S]`
  https://centennialsoftwaresolutions.com/help/extract-read-back-configuration-data-from-a-zynq-7000-fpga
  (a third-party tutorial quoting the official command sequence; the commands themselves are
  standard Vivado Hardware Manager Tcl). For the Vitis/HW side, `xsct`/`xsdb` connect to a
  hardware server with `connect -url TCP:<host>:3121`, and targets can be selected
  deterministically with filters such as
  `targets -set -filter {jtag_cable_serial == "210357A7CB97A" && name == "PSU"}` `[S]`
  https://unlimited.ethz.ch/spaces/enzianwiki/pages/208869538/.
- **Annotations:** `readOnlyHint: true` — but note it has a side effect on the *hardware
  server's* state (it opens a target); `openWorldHint: true`.

**`program_fpga`** — **dangerous tool, see §4.5**
- **In:** `bitstream: str`, `device: str|None = None`, `target_url: str|None = None`,
  `confirm: Literal["yes"]|None = None`
- **Out:** `{programmed: true, device, bitstream, log_path}`
- **When:** only when the user has explicitly asked to load the design on hardware.
- **Annotations:** `readOnlyHint: false`, `destructiveHint: true`, `idempotentHint: true`
  (reprogramming the same bitstream is harmless *to the device*, but not to a running
  experiment), `openWorldHint: true`.
- **Notes:** default to a no-op requiring `confirm="yes"`, so an accidental call returns a
  clear refusal instead of a flashed board.

### 2.13 Housekeeping

**`clean_run`**
- **In:** `run_dir: str`, `keep: int = 2`, `confirm: bool = false`
- **Out:** `{deleted: [str], freed_bytes: int}`
- **When:** the user asks to free space, or at the start of a fresh flow. Dangerous tool:
  refuses anything outside the server's runs root, refuses the current run, and requires
  `confirm`.

---

## 3. Server architecture

### 3.1 File layout

```
vivado-mcp/
├── pyproject.toml              # fastmcp>=4,<5  (or mcp>=2.2,<3)
├── README.md
├── src/vivado_mcp/
│   ├── __init__.py
│   ├── __main__.py             # console entry: python -m vivado_mcp
│   ├── server.py               # FastMCP instance, instructions, tool registration order
│   ├── config.py               # workspace root, tool paths, env discovery, limits
│   ├── env.py                  # settings64.sh sourcing, PATH, DISPLAY, licences
│   ├── jobs.py                 # JobManager: subprocess launch, polling, kill, persistence
│   ├── safety.py               # allowlist, path jail, atomic write, size caps
│   ├── parsers/                # pure, deterministic, unit-testable
│   │   ├── timing.py           # *.rpt → JSON
│   │   ├── utilization.py
│   │   ├── severity.py         # [ERROR]/[WARNING] extraction with line numbers
│   │   └── cocotb_xml.py       # results.xml → pass/fail/traceback
│   ├── hdl.py                  # entity/module listing, port extraction
│   └── tools/
│       ├── fs_tools.py         # read_project_file, write_project_file, list_project_files
│       ├── vivado_tools.py     # create/open project, run_step, tcl, reports, xsa, xsim
│       ├── vitis_tools.py      # platform, app, build
│       ├── hw_tools.py         # list_hw_targets, program_fpga
│       └── job_tools.py        # job_status, list_jobs, cancel_job, read_log, tail_log
└── tests/
    ├── test_parsers.py         # parsers run against checked-in report fixtures
    └── test_safety.py          # path jail + allowlist, must be exhaustive
```

Design rule: **`parsers/` and `safety.py` must not import `fastmcp`.** They are the parts you
can test without an EDA toolchain and without a protocol, and they are where correctness
actually lives.

### 3.2 Running EDA commands as background jobs

The core object is a `JobManager` (one per server process) holding a dict
`job_id -> Job` with `job_id` being a server-minted opaque handle
(`run-20260917-1a3f9c`), which is exactly the pattern the 2026-07-28 spec prescribes for
cross-call state: "Servers that need cross-call state use explicit, server-minted handles
passed as ordinary tool arguments" `[V]`
https://modelcontextprotocol.io/specification/2026-07-28/changelog.

```python
@dataclass
class Job:
    job_id: str
    kind: str               # "vivado_step" | "xsim" | "cocotb" | "vitis_build" | "tcl"
    run_dir: Path           # per-job working directory
    log_path: Path          # full stdout+stderr, unbounded, on disk
    proc: subprocess.Popen | None
    state: str              # queued|running|succeeded|failed|timeout|cancelled
    exit_code: int | None
    started_at: float
    deadline: float         # started_at + timeout_s
    progress: dict | None   # parsed opportunistically from the log
```

Launch, in one worker thread per job (not on the MCP event loop):

```python
def _spawn(self, job: Job, argv: list[str], cwd: Path, env: dict[str, str]) -> None:
    # argv is a LIST. shell=True is never used (safety.shell_forbidden()).
    # start_new_session=True puts the job in its own process group so that
    # killing the group kills Vivado's children (vivado spawns child processes).
    job.log_fh = open(job.log_path, "ab", buffering=0)
    job.proc = subprocess.Popen(
        argv,
        cwd=str(cwd), env=env,
        stdin=subprocess.DEVNULL,
        stdout=job.log_fh, stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    threading.Thread(target=self._supervise, args=(job,), daemon=True).start()
```

Supervision loop — this is where timeout, incremental progress and cleanup live:

```python
def _supervise(self, job: Job) -> None:
    while True:
        rc = job.proc.poll()
        if rc is not None:
            job.exit_code = rc
            job.state = "succeeded" if rc == 0 else "failed"
            break
        if time.time() > job.deadline:
            self._kill_group(job.proc)
            job.state = "timeout"
            job.exit_code = -9
            break
        job.progress = progress_sniffer(job.log_path)   # cheap tail scan
        self._persist(job)                              # sqlite upsert
        time.sleep(2.0)
    job.log_fh.close()
    self._persist(job)
```

Key points:

- **Incremental output** exists because stdout+stderr go straight to `job.log_path`; the log
  is the source of truth and is readable *while the job runs*. `tail_log` never needs a lock
  beyond reading a file that is being appended to.
- **Progress** is derived, not reported: scan the last N KB of the log for the known Vivado
  step markers and map them to an integer. Any EDA tool that prints "Step 3 of 12" gives the
  same free progress bar.
- **Timeout** is a wall-clock deadline checked every 2 s, not a `proc.wait(timeout)` on the
  event loop.
- **Kill** must be group-wide. Vivado and Vitis both fork children; `Popen.terminate()` alone
  leaves orphans holding the licence:

  ```python
  def _kill_group(proc, grace: float = 10.0) -> None:
      pgid = os.getpgid(proc.pid)
      os.killpg(pgid, signal.SIGTERM)          # ask nicely: lets Vivado flush logs
      try:
          proc.wait(timeout=grace)
      except subprocess.TimeoutExpired:
          os.killpg(pgid, signal.SIGKILL)      # last resort
  ```
- **Cancellation on disconnect**: if the client disconnects (stdio pipe closes) the job
  should *not* be killed blindly — a 40-minute synthesis survives a chat restart. Persist it
  and let `list_jobs` recover it after restart. (Contrast: fpgaZeroMCP does abort an in-flight
  call on `notifications/cancelled` `[V]`
  https://github.com/lcapossio/fpgaZeroMCP/blob/main/README.md — reasonable for a 5-second
  lint, wrong for a 4-hour P&R.)
- **Never `shell=True`.** Commands are built as `argv` lists; Tcl scripts are written to a
  file in the run directory and passed with `-source <abs path>`, never inlined into a shell
  string.
- **Concurrency cap**: a single global semaphore (configurable, default 2 concurrent EDA
  jobs) plus a per-kind cap. Two simultaneous implementation runs on the same project
  directory is the fastest way to corrupt a `.runs` tree; take a lock on the `xpr` path.

Reference commands the jobs wrap (subject to the installed release):
`vivado -mode batch -source <script.tcl>`, `xvlog`/`xvhdl` → `xelab` → `xsim [snapshot] -R`
`[V]` https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Compiling-and-Simulating,
`xsct <script>`, and the Vitis Python/REPL interface.

### 3.3 Environment management

The AMD tools are not on `PATH` by default; the documented requirement is: "Design tools must
source the `settings64.(c)sh` file from their installation directory to configure the
environment to reference the installed location" `[V]`
https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Install-the-Vivado-Design-Tools-on-a-Linux-Client-Network
(UG973, 2026.1).

Implementation rules:

1. **Resolve the tool once at startup, cache it.** Look for candidates in a configured list of
   roots (`/opt/Xilinx/Vivado/*`, `/tools/Xilinx/Vitis/*`, `~/Xilinx/...`, Windows
   `C:\Xilinx\...`) — this is what `slauzinho/vivado-mcp` does `[S]`
   https://github.com/slauzinho/vivado-mcp. Expose the chosen version in the server
   `instructions` so the model knows which release it is targeting.
2. **Do not try to `source` a shell script from Python and hope.** `settings64.sh` is a shell
   script; the robust approach is to run one small probe command through `bash -lc
   'source <settings64.sh> && env -0'` **once at startup**, parse the resulting NUL-separated
   environment, and cache it as the base environment for every job. Re-sourcing per job is
   wasteful but acceptable; re-implementing the settings logic by hand is not.
3. **`DISPLAY`.** UG973 explicitly ties remote use to an X display manager and a `DISPLAY`
   variable `[V]` same URL. A headless server must therefore either (a) never launch GUI
   modes — use `-mode batch`, `xsim ... -R`, `-nograph` where applicable — or (b) set
   `DISPLAY=:0`/`dummy` deliberately. `[S]` one lab wiki shows the idiom
   `DISPLAY=dummy xsdb` https://unlimited.ethz.ch/spaces/enzianwiki/pages/208869538/.
   Document that GUI/waveform tools are unavailable in headless mode; the server should
   return a clear error rather than hanging on a missing X server.
4. **Licensing.** Long jobs hold licence seats. Consequences: (a) always kill the process
   *group* so the seat returns (regression-tested behaviour, §3.2); (b) `cancel_job` must
   report whether the process actually died; (c) never launch speculative parallel builds —
   the concurrency cap is a licence-management feature, not just a performance one. Some
   flows also consult `XILINXD_LICENSE_FILE` / `LM_LICENSE_FILE`; pass the parent
   environment through unchanged unless the user configures an override.
5. **Locale and reproducibility**: pin `LC_ALL=C` for parser stability (log/report formats),
   and record the tool version in every run record so a parse failure can be attributed to a
   release change.

### 3.4 Isolation per project

- One **workspace root** per server instance, configured once
  (`VIVADO_MCP_WORKSPACE=/path/to/project`), enforced by `safety.resolve_within()` on *every*
  path argument (§4.2).
- One **run directory per job**:
  `<workspace>/.vivado-mcp/runs/<job_id>/{script.tcl, job.log, stdout.txt, reports/, sim_build/}`.
  Per-job directories are what make `parse_timing_report` and `tail_log` unambiguous: a tool
  never has to guess which run a report belongs to.
- Vivado's own `*.runs/` tree stays inside the workspace; the server never writes into
  `src/` except through `write_project_file`.
- **No shared mutable state between jobs** other than the `xpr` project lock. Two jobs that
  must touch the same project run serially.

### 3.5 Report caching and minimal persistence

- **In-process cache**: `(abs_path, mtime_ns, size) -> parsed_object`, LRU-bounded. Reports
  are large and re-parsed constantly ("what's the WNS?" asked three times); the mtime key
  makes it correct by construction.
- **Exposure as resources**: register `@mcp.resource("vivado://run/{job_id}/log")` and
  `vivado://report/{run_id}/{name}` so a user can attach the artefact without a tool call
  (`[V]` https://gofastmcp.com/servers/server for the `@mcp.resource` API), and use the
  caching hints `ttlMs`/`cacheScope` so clients can cache the reads (`[V]`
  https://py.sdk.modelcontextprotocol.io/whats-new/).
- **Minimal persistence**: a single SQLite file at `<workspace>/.vivado-mcp/state.db` (or
  JSONL if you want zero dependencies). Schema:

  ```sql
  CREATE TABLE IF NOT EXISTS runs (
    job_id     TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    xpr        TEXT,
    step       TEXT,
    state      TEXT NOT NULL,
    exit_code  INTEGER,
    started_at REAL NOT NULL,
    ended_at   REAL,
    timeout_s  INTEGER NOT NULL,
    run_dir    TEXT NOT NULL,
    log_path   TEXT NOT NULL,
    tool_version TEXT,
    progress   TEXT             -- JSON blob
  );
  CREATE INDEX IF NOT EXISTS runs_started ON runs(started_at DESC);
  ```

  Purpose: after a server restart (or a chat/session restart), `list_jobs` and `job_status`
  still answer, `read_log` still works, and the model can reconnect to a synthesis that was
  launched before the crash. This is the cheap, client-independent version of what the Tasks
  extension provides (`[V]`
  https://modelcontextprotocol.io/specification/2026-07-28/basic/utilities/tasks — "Crash
  resilience. A task ID is a durable handle"). SQLite in WAL mode, one writer, no ORM.
- **Retention**: default `clean_run` policy keeps the last N runs per project and deletes run
  directories older than X days at startup — but never deletes the log of a *failed* run
  until the user has seen it.

---

## 4. Security

The spec's own principles are the starting point: users must explicitly consent to and
understand all data access and operations; **tools represent arbitrary code execution and must
be treated with appropriate caution**; tool descriptions and annotations are **untrusted**
unless obtained from a trusted server; hosts must obtain explicit user consent before invoking
any tool `[V]` https://modelcontextprotocol.io/specification/latest. The dedicated security
page covers confused-deputy attacks, token passthrough, state-handle hijacking, stdio
transport escalation in proxy scenarios, localhost redirect-URI impersonation and scope
minimisation `[V]`
https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices.

### 4.1 Binary allowlist

Every subprocess is launched from a fixed allowlist, resolved to an absolute path at startup,
never from a model-supplied string:

```python
ALLOWED_BINARIES = {
    "vivado", "vivado_lab", "xvlog", "xvhdl", "xelab", "xsim",
    "xsct", "xsdb", "vitis", "make", "python", "bash",   # bash only for the settings probe
}
```

Any tool that accepts an executable name (e.g. `run_cocotb_test(sim=...)`) maps a `Literal`
enum to a fixed argv, never to a free string. `vivado_tcl(script=...)` runs a script — a
script, not a shell command — so it cannot choose a binary at all.

Note the honest limit: **Vivado Tcl is itself a Turing-complete language with filesystem and
process access** (`exec`, `open`, `file delete`). The allowlist bounds the *entry point*, not
the *capability*. Align with the environment isolation in §3.4 (container / dedicated user /
`bwrap`) if the threat model includes a hostile model or a hostile repository. Say this
plainly in the README rather than claiming sandboxing you do not have.

### 4.2 Path jail

- One function, used everywhere, no exceptions:

  ```python
  def resolve_within(workspace: Path, candidate: str) -> Path:
      p = (workspace / candidate).resolve() if not os.path.isabs(candidate) \
          else Path(candidate).resolve()
      if not p.is_relative_to(workspace.resolve()):
          raise ToolError(f"path outside workspace: {candidate!r}")
      # also reject symlinks that escape, and any path whose realpath leaves the root
      return p
  ```
- Reject: absolute paths, `..` traversal, symlinks whose target escapes, `/proc`, `/sys`,
  `/dev`, and (belt and braces) any component starting with `.ssh`/`.config` unless the
  workspace *is* one of those.
- The workspace root itself is configuration, not a tool argument. A model must never be able
  to widen its own sandbox by calling a tool.

### 4.3 No shell, ever

- `subprocess.Popen(argv_list, shell=False)` only. `os.system`, `shell=True`,
  `subprocess.getoutput`, and string-formatted command lines are banned in review.
- Model- or user-supplied strings are never interpolated into a shell line. Where a value must
  reach a Tcl script, use Tcl-safe quoting (`[list ...]` / brace-quoting) in the generated
  script, or write the value to a file in the run directory and have the script read it —
  this is the idea behind Vitis MCP's "commands are base64-encoded with a sentinel protocol,
  user parameters are `repr()`-quoted, never interpolated into raw code strings" `[V]`
  https://github.com/QingquanYao/vitis_mcp. Adopt the same discipline.
- An expensive-but-simple alternative for generated Tcl: emit every user value as a
  `set x {…}` line with a brace-count-safe encoder, then fail the job if the encoder cannot
  represent the value.

### 4.4 Output limits and atomic writes

- **Cap every tool result.** Hard caps in `safety.py`: `max_lines` 2000, `max_bytes` 200 kB,
  `max_matches` 200. When a cap bites, return `truncated: true` plus the on-disk path so the
  model can narrow its next query. The Streamable HTTP 4 MiB body limit in SDK v2 `[V]`
  https://pypi.org/project/mcp/ is the extreme case; the real limit is context budget.
- **Atomic writes**: write to `path.tmp-<uuid>` in the same directory, `fsync`, then
  `os.replace(tmp, dst)`. Never truncate the destination first: a crash mid-write must not
  destroy the user's VHDL. Also copy the previous version to
  `.vivado-mcp/backups/<ts>/<path>` before overwriting a non-generated file.
- **Log rotation** on the server's own log, not the EDA jobs' logs (those are evidence).

### 4.5 "Dangerous tool" pattern

Tools whose *side effect escapes the workspace or touches physical hardware* must be
individually approvable.

1. **Annotate honestly** — `destructiveHint: true`, `readOnlyHint: false`,
   `openWorldHint: true` for `program_fpga`. Annotations drive the client's approval UI
   `[V]` https://modelcontextprotocol.io/specification/2025-11-25/server/tools, but remember
   the spec calls them hints and says hosts must obtain explicit user consent regardless
   `[V]` https://modelcontextprotocol.io/specification/latest.
2. **Require an explicit confirmation argument** server-side: `program_fpga(..., confirm="yes")`
   and `clean_run(..., confirm=True)`. The tool description states that calling without
   `confirm` is a dry run that returns exactly what *would* happen. This makes the dangerous
   path an explicit, two-step decision by the *user*, not by the model — and it protects users
   of clients with auto-approval enabled.
3. **Client-side allowlisting is the second layer.** Cline has an `autoApprove` array listing
   tool names it may run without asking (empty array = approve every call) `[V]`
   https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx; Hermes has an explicit
   allow/deny:
   ```yaml
   tools:
     include: [...]
     exclude: [program_fpga, clean_run]
   ```
   `[V]` https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference. Document
   the recommended `exclude` list in the README: `program_fpga`, `clean_run`, `vivado_tcl`.
4. **Log every invocation** of a dangerous tool with arguments, timestamp and outcome
   (`audit` table in the SQLite file) — the spec's access-control guidance explicitly lists
   "audit tool usage" `[V]`
   https://modelcontextprotocol.io/specification/2025-11-25/server/tools.

### 4.6 Why this server must not be exposed unauthenticated

- The tools are, collectively, **arbitrary code execution plus hardware control**: write a
  file → run `vivado -mode batch -source` on it → flash the result onto a physical board. An
  unauthenticated Streamable HTTP endpoint turns any process that can reach the port into a
  tool-user with the server's OS privileges.
- The spec's security page describes the escalation path for exactly this shape: a local
  proxy spawning stdio servers can be driven to Remote Code Execution with user privileges if
  a client-side vulnerability (e.g. XSS) exists, and recommends additional controls on stdio
  server spawning in proxy deployments `[V]`
  https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices.
- Cross-request state must be a handle, not an ambient session: "State Handle Hijacking" is a
  named attack, mitigated by treating server-minted handles as ordinary arguments that the
  server validates per request `[V]` same URL. Our `job_id` design is compatible — but the
  server must verify that a `job_id` presented by a client actually belongs to that client's
  workspace, otherwise one user can read another's logs.
- Concrete rules for this project: bind HTTP to `127.0.0.1` only; require a bearer token if
  HTTP is enabled at all; default to stdio; never add a "no auth" flag; document in the
  README that running the server as root or with a workspace of `/` is unsupported.

---

## 5. Reliability: making failures usable by the model

### 5.1 The error contract

The spec requires tool errors to be reported **inside the result** with `isError: true`, not
as protocol errors, "to enable model self-correction" `[V]`
https://modelcontextprotocol.io/specification/2026-07-28/server/tools and `[V]`
https://modelcontextprotocol.io/specification/2025-11-25/changelog (SEP-1303). A failed
synthesis is not a protocol error; it is a normal result the model must read.

The server's error payload is deliberately verbose and **machine-shaped**:

```json
{
  "isError": true,
  "error_code": "EDA_NONZERO_EXIT",
  "summary": "vivado exited 1 during synthesis (step 5/8)",
  "exit_code": 1,
  "stderr": "…last non-empty stderr lines, ≤ 20 lines…",
  "log_path": "/abs/path/.vivado-mcp/runs/run-20260917-1a3f9c/job.log",
  "report_paths": ["/abs/path/…/vivado.log"],
  "errors": [{"line_no": 1432, "severity": "ERROR", "text": "[Synth 8-5857] illegal reference to …"}],
  "last_log_lines": ["…", "…", "…"],
  "hint": "Fix the ERROR at job.log:1432, then re-run vivado_run_step(step=\"synth\")."
}
```

Rules behind it:

1. **Always include both `stderr` and `exit_code`.** Both, even when one is empty.
2. **Always include the 40 last lines of the log** (the task's requirement; 40 is a good
   number — long enough to catch a Vivado summary block, short enough to be cheap). The
   example above uses `last_log_lines`; keep the count configurable via
   `VIVADO_MCP_TAIL_ON_ERROR`, default 40.
3. **Always include the full log path**, and make it absolute. The model cannot `cd`.
4. **Always extract the ERROR/CRITICAL WARNING lines with their line numbers** — the concrete
   `[Synth 8-5857]` at a known line is worth more than a page of context.
5. **Add a `hint`** naming the next tool call. Models recover much faster when handed the
   retry verb.
6. **Use a small, stable `error_code` taxonomy** for programmatic decisions — prior art
   (`fpgaZeroMCP`) does exactly this "for retry/fallback decisions" `[V]`
   https://github.com/lcapossio/fpgaZeroMCP/blob/main/README.md. Suggested set:
   `WORKSPACE_VIOLATION`, `PATH_NOT_FOUND`, `TOOL_NOT_INSTALLED`, `LICENSE_UNAVAILABLE`,
   `EDA_NONZERO_EXIT`, `EDA_TIMEOUT`, `JOB_NOT_FOUND`, `JOB_ALREADY_RUNNING`,
   `PARSE_FAILED`, `CONFIRMATION_REQUIRED`, `UNSUPPORTED_SIMULATOR`.
7. **Never swallow the tool's own output.** Streaming the raw log to disk and returning a
   bounded digest is what makes (2) and (4) possible at all.

### 5.2 Retry

- **Retry the infrastructure, not the design.** Safe to retry automatically (once, after a
  short backoff): starting a subprocess that failed to spawn, connecting to a hardware server,
  reading a file that was momentarily being written. **Never** auto-retry a synthesis,
  implementation or bitstream run: it costs minutes to hours and, on a licence-constrained
  machine, can starve other users.
- Classify retryability in the `error_code`: `EDA_TIMEOUT` and `EDA_NONZERO_EXIT` are
  *design/tool* failures → no automatic retry, tell the model to fix something.
  `TOOL_NOT_INSTALLED`, `LICENSE_UNAVAILABLE` → environment failures, retry later.
- Tell the model the retry policy in the tool description ("Returns immediately; if it fails
  with `JOB_ALREADY_RUNNING`, poll `job_status` instead of re-running"), because the model is
  the retry controller in practice.

### 5.3 Idempotence

| Operation | Idempotent? | Treatment |
|---|---|---|
| read file / log / report | yes | annotate `idempotentHint: true` |
| write file | yes, given identical content | atomic write; return hash so a no-op write is detectable |
| create project | only with `-force` | require `overwrite: true`; otherwise fail with an explicit code |
| synth / impl / bitstream | **no** | `idempotentHint: false`; a second call while the first runs returns `JOB_ALREADY_RUNNING` with the existing `job_id` — the model then polls instead of duplicating work |
| export XSA | yes (overwrite) | annotate `idempotentHint: true`, but return a hash so the model can tell whether the platform changed |
| program FPGA | yes, physically | annotate `idempotentHint: true`; still confirmation-gated |
| cancel job | yes | cancelling a finished job is a no-op success, not an error |

The `JOB_ALREADY_RUNNING`-returns-the-existing-id rule is worth implementing carefully: it is
the difference between a model that recovers and a model that launches four synthesis runs
because the first three "didn't return quickly".

### 5.4 Run cleanup

- Retention policy in `config.py`: `keep_last_runs: int = 10`, `max_run_age_days: int = 30`,
  `max_total_run_bytes: int = 20 GiB`.
- Cleanup runs **at startup** and on explicit `clean_run`, never mid-job, and it never
  deletes: the currently running job's directory, the newest run of each kind, or the log of
  any run whose state is `failed` until the user acknowledges it (expose
  `list_jobs(state="failed")` as the acknowledgement surface).
- Deleting a run invalidates any `job_id` aliases pointing at it; `job_status` on a deleted
  run must return `JOB_NOT_FOUND` with the retention policy in the message, not a crash.
- The `state.db` audit rows outlive the run directories: keep the metadata, drop the bulk
  (this is what makes `list_jobs` cheap after a big cleanup).

---

## 6. Client integration

### 6.1 Claude Desktop (and Claude Code)

Config file locations, per the official quickstart: macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`, Windows
`%APPDATA%\Claude\claude_desktop_config.json` `[V]`
https://modelcontextprotocol.io/quickstart/user. Linux (`~/.config/Claude/claude_desktop_config.json`)
appears in third-party guides `[S]` — verify on the target install; Claude Desktop is
distributed for macOS and Windows per the official page.

Exact shape — one top-level key `mcpServers`, each entry a `command` + `args` + optional
`env` `[V]` same URL:

```json
{
  "mcpServers": {
    "vivado": {
      "command": "/home/user/vivado-mcp/.venv/bin/python",
      "args": ["-m", "vivado_mcp"],
      "env": {
        "VIVADO_MCP_WORKSPACE": "/home/user/projects/fpga_uart",
        "PATH": "/opt/Xilinx/Vivado/2024.2/bin:/usr/local/bin:/usr/bin:/bin",
        "DISPLAY": ":0"
      }
    }
  }
}
```

Operational details that matter and are documented: Claude Desktop launches servers in a
**restricted shell that does not inherit your terminal `PATH`** — use an absolute path in
`command`, or a full `PATH` in `env`, or you get `spawn ENOENT` while the same command works
in your shell `[S]` (multiple client-setup guides; the mechanism is standard: the config
supplies the child environment). Full quit-and-restart is required after editing (the official
quickstart says so explicitly `[V]` same URL). JSON does not allow trailing commas — a
trailing comma makes the whole file silently ignored `[S]`.

Claude Code uses the same `mcpServers` object, either in `~/.claude.json` (user scope) or a
project `.mcp.json` `[S]` (https://github.com/justinwlin/claude-mcp-guide), and the official
reference documents `claude mcp add` for the CLI flow `[V]`
https://docs.claude.com/en/docs/claude-code/mcp. The existing `coreyhahn/vivado_mcp` README
uses exactly the `~/.claude/claude_desktop_config.json` / project `.mcp.json` paths `[V]`
https://github.com/coreyhahn/vivado_mcp.

### 6.2 VS Code / GitHub Copilot

VS Code stores MCP configuration in `mcp.json`, either workspace (`.vscode/mcp.json`, meant to
be committed and shared) or user profile (`MCP: Open User Configuration`) `[V]`
https://code.visualstudio.com/docs/agent-customization/mcp-servers. The file has two sections:
`servers` and `inputs` `[V]` same URL. Per-field reference: `type`, `command`, `args`, `env`,
`envFile`, and for remote servers `type`/`url`/`headers` `[V]`
https://github.com/microsoft/vscode-docs/blob/main/docs/copilot/reference/mcp-configuration.md.

```json
{
  "inputs": [
    { "type": "promptString", "id": "vivado-workspace", "description": "Absolute path of the FPGA project root" }
  ],
  "servers": {
    "vivado": {
      "type": "stdio",
      "command": "/home/user/vivado-mcp/.venv/bin/python",
      "args": ["-m", "vivado_mcp"],
      "env": {
        "VIVADO_MCP_WORKSPACE": "${input:vivado-workspace}",
        "PATH": "/opt/Xilinx/Vivado/2024.2/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

Notes verified in the VS Code docs: `${workspaceFolder}` is usable in server configuration;
`envFile` loads additional variables; `dev: { watch: "<glob>", debug: ... }` enables
development mode (Python debugging is supported); `sandboxEnabled: true` enables server
sandboxing with a top-level `sandbox` object for filesystem/network rules `[V]` same URLs.
VS Code **requires the user to confirm they trust a server** the first time it starts, and
warns that starting a server directly from `mcp.json` skips that prompt `[V]`
https://code.visualstudio.com/docs/agent-customization/mcp-servers. For Copilot *Agent Host*
sessions the `.vscode/mcp.json` file is not read directly — use a workspace `.mcp.json` or
`~/.copilot/mcp-config.json` `[V]`
https://github.com/microsoft/vscode-docs/blob/main/docs/agent-customization/mcp-servers.md.

### 6.3 Cline

Cline stores settings in `cline_mcp_settings.json` (open it via the MCP Servers icon →
Configure tab → Configure MCP Servers); the standalone CLI uses `~/.cline/mcp.json` `[V]`
https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx. Top-level key is
`mcpServers`; local servers declare `command`/`args`/`env`, remote servers declare
`url`/`headers`, and Cline adds two keys other clients do not have: `disabled` and
`autoApprove` `[V]` same URL.

```json
{
  "mcpServers": {
    "vivado": {
      "command": "/home/user/vivado-mcp/.venv/bin/python",
      "args": ["-m", "vivado_mcp"],
      "env": {
        "VIVADO_MCP_WORKSPACE": "/home/user/projects/fpga_uart",
        "PATH": "/opt/Xilinx/Vivado/2024.2/bin:/usr/local/bin:/usr/bin:/bin"
      },
      "disabled": false,
      "autoApprove": ["read_project_file", "list_project_files", "job_status", "read_log", "tail_log"]
    }
  }
}
```

`autoApprove` is the client-side half of the dangerous-tool pattern: list only read-only tools
there and leave `program_fpga`, `clean_run` and `vivado_tcl` out, so they always prompt. For
remote servers in Cline the transport type must be written `"streamableHttp"` (camelCase);
`"streamable-http"` or an omitted type falls back to SSE and yields a `405` `[V]`
https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-cline.md.

### 6.4 Hermes Agent

Hermes reads MCP configuration from `~/.hermes/config.yaml` under the `mcp_servers` key `[V]`
https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference. Minimal stdio
example from the official docs `[V]`
https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp:

```yaml
mcp_servers:
  vivado:
    command: "/home/user/vivado-mcp/.venv/bin/python"
    args: ["-m", "vivado_mcp"]
    env:
      VIVADO_MCP_WORKSPACE: "/home/user/projects/fpga_uart"
      PATH: "/opt/Xilinx/Vivado/2024.2/bin:/usr/local/bin:/usr/bin:/bin"
    timeout: 300
    connect_timeout: 60
    supports_parallel_tool_calls: false
    protocol: auto
    tools:
      include:
        - read_project_file
        - list_project_files
        - list_hdl_modules
        - vivado_open_project
        - vivado_run_step
        - job_status
        - list_jobs
        - read_log
        - tail_log
        - parse_timing_report
        - parse_utilization_report
        - run_cocotb_test
      exclude:
        - program_fpga
        - clean_run
      resources: true
      prompts: false
```

Documented keys relevant here: `command`/`args`/`env` (stdio) or `url`/`headers` (HTTP);
`enabled`; `timeout` (per-tool-call, reference table says default **300**); `connect_timeout`
(default 60); `protocol` = `auto` | `stateless` | `legacy` (protocol-era negotiation);
`supports_parallel_tool_calls`; `tools.include`/`exclude`; `resources`; `prompts`; plus TLS
keys for HTTP and `idle_timeout_seconds` / `max_lifetime_sec…` for stdio lifecycle `[V]`
https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference. Environment
variable references like `${VAR}` / `${env:VAR}` are resolved (Cursor-style SecretRef syntax
is accepted, so Cursor snippets paste in unchanged) `[V]`
https://hermes-agent.nousresearch.com/docs/user-guide/configuration. Hermes also ships a
`native-mcp` skill and a `mcp-fastmcp` optional skill; the latter's documented loop is
`fastmcp run` → `fastmcp list` → `fastmcp call` → integrate `[V]`
https://hermes-agent.nousresearch.com/docs/user-guide/skills/optional/mcp/mcp-fastmcp.

**Inconsistency to resolve before publishing docs:** the Hermes config *reference* table gives
`timeout` default 300 s, while the `native-mcp` skill text gives 120 s `[V]`/`[S]`. Test the
actual timeout on the target install and set `timeout` explicitly rather than relying on the
default. `[U]`

### 6.5 The "no MCP available" fallback: CLI/Tcl script generation

This is the most important robustness feature of the project, because most LLM interactions
with Vivado today happen without MCP — a chat window, a local model, a CI runner, a copilot
without tool access. In that mode the model cannot call tools; it can only emit text that a
human or a shell runs. The server design should therefore treat script generation as a
**first-class output mode of the same tool catalogue**, not as a separate product.

Design rules for the fallback:

1. **One tool contract, two renderings.** For every tool, the server can emit either (a) an
   MCP tool call, or (b) a self-contained script plus the exact command line to run it. Make
   this explicit with a `render` mode used by a CLI subcommand, e.g.
   `python -m vivado_mcp render vivado_run_step --step synth --xpr proj.xpr` printing the
   generated `synth.tcl` and `vivado -mode batch -source synth.tcl`. The skill document then
   shows the model the *same* shapes it would get from MCP.
2. **Teach the shape of the artefacts, not just the commands.** The existing `skills.md` in
   this repository already does this: a full flow
   (`create_project` → `add_files` → `add_files -fileset constrs_1` → `set_property top` →
   `run_synthesis` → `run_implementation` → `launch_runs -to_step write_bitstream`), the
   cocotb testbench idiom (`Clock`, `cocotb.start_soon`, assertion after N `RisingEdge`s), the
   naming conventions (`i_*`/`o_*`/`s_*`/`C_*`/`p_*`), the project layout, the error
   catalogue. Keep it, but make it *generated from the same source of truth* as the tool
   descriptions, so the two cannot drift. Note that it currently contains at least one
   inaccuracy worth fixing: `write_hw_def` is not the AMD command for export — the documented
   command is `write_hw_platform` `[V]`
   https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_hw_platform — and the Vitis
   hand-off in the real flow takes an **XSA**, not a `.hwdef`.
3. **Always emit runnable, idempotent scripts.** Each generated script should: `set` its paths
   as variables at the top, wrap risky commands in `if {[catch {…} err]} { puts "ERROR: $err";
   exit 1 }`, print a machine-greppable sentinel on success
   (`puts "VIVADO_MCP_OK <step>"`), and be safe to re-run. The `skills.md` in this repo
   already recommends `-force` on `create_project` and `catch`-wrapping — keep those.
4. **Give the model a self-check loop that works without tools:** script → run → grep the log
   for `ERROR`/`CRITICAL WARNING` with line numbers → fix → re-run. Provide a tiny helper
   script (`scripts/parse_log.py`) that the model can ask the user to run when it has no tool
   access; it is the CLI twin of `read_log` and produces the same JSON.
5. **Be explicit about what is lost.** Without MCP the model cannot poll a job: the shell
   blocks for the whole synthesis. So the fallback scripts should be *foreground* and print a
   monotonic progress line, or write to a log the user can `tail`, and the skill should say
   so. Do not pretend the background-job semantics survive the fallback.
6. **Keep the "pseudoconvention" clearly labelled.** The
   `GET /vivado/...` / `POST /vivado/build` block at the end of the current `skills.md` is
   *not* MCP and would mislead a model that knows the MCP spec. Either delete it or mark it as
   illustrative-only, and replace it with the real MCP tool names from §2 so the model learns
   one vocabulary.

---

## 7. Python skeleton

Two viable targets; **recommendation: the standalone FastMCP (v4.x)**, because the decorator
API is the same one the official SDK shipped as `FastMCP` for two years, the docs are the
best of the two, and it adds the pieces this project needs (tool `timeout`, `mask_error_details`,
`tasks`, structured output, `Client` for tests). Note the naming hazard: the *official SDK's*
class was renamed `FastMCP` → `MCPServer` in SDK v2 with no alias `[V]`
https://py.sdk.modelcontextprotocol.io/whats-new/, so `from mcp.server import MCPServer` and
`from fastmcp import FastMCP` are different classes — pin one and document it.

### 7.1 Entry point

```python
# src/vivado_mcp/server.py
from fastmcp import FastMCP

from .config import Settings
from .jobs import JobManager
from .tools import fs_tools, job_tools, hw_tools, vivado_tools, vitis_tools

SETTINGS = Settings.from_env()

mcp = FastMCP(
    name="vivado-mcp",
    instructions=(
        "Drives AMD Vivado and Vitis for an FPGA/VHDL project rooted at "
        f"{SETTINGS.workspace}. "
        "Long operations (synthesis, implementation, bitstream, Vitis builds, simulations) "
        "return a job_id immediately: call job_status() to poll, read_log() to inspect "
        "failures, and cancel_job() to stop. Prefer the typed tools over vivado_tcl(). "
        "program_fpga and clean_run require explicit user confirmation."
    ),
)

mgr = JobManager(SETTINGS)

# Registration order is fixed on purpose: tools/list must be deterministic.
fs_tools.register(mcp, SETTINGS)
vivado_tools.register(mcp, SETTINGS, mgr)
vitis_tools.register(mcp, SETTINGS, mgr)
hw_tools.register(mcp, SETTINGS)
job_tools.register(mcp, SETTINGS, mgr)

if __name__ == "__main__":
    # FastMCP's default transport is stdio; state it for readers.
    mcp.run(transport="stdio")
```

`__main__.py` is just `from .server import mcp; mcp.run()` so `python -m vivado_mcp` works —
that is the form the client configs above use.

### 7.2 A complete `run_vivado`-style tool

This is the reference implementation of the whole architecture in §3.2: argv (no shell),
allowlisted binary, per-job run directory, generated Tcl written to disk, streamed log,
background thread, persisted job, bounded return.

```python
# src/vivado_mcp/tools/vivado_tools.py
from pathlib import Path
from typing import Literal

from fastmcp import Context

from ..jobs import JobManager
from ..safety import resolve_within, write_text_atomic   # path jail + atomic write

STEP_CMD = {
    "synth":     'launch_runs synth_1 -jobs {jobs}\nwait_on_run synth_1',
    "impl":      'launch_runs impl_1 -jobs {jobs}\nwait_on_run impl_1',
    "bitstream": 'launch_runs impl_1 -to_step write_bitstream -jobs {jobs}\nwait_on_run impl_1',
}


def register(mcp, settings, mgr: JobManager) -> None:

    @mcp.tool(
        name="vivado_run_step",
        title="Run a Vivado build step",
        description=(
            "Start a Vivado build step (synthesis, implementation or bitstream) on an "
            "existing project, as a BACKGROUND JOB. Returns immediately with a job_id. "
            "Poll it with job_status(job_id); inspect failures with read_log(); stop it "
            "with cancel_job(job_id).\n\n"
            "Does NOT create or open a project, and does NOT add sources or constraints: "
            "call vivado_create_project / vivado_open_project first.\n\n"
            "A second call for the same step on the same project while one is running "
            "returns error_code JOB_ALREADY_RUNNING together with the existing job_id "
            "(do not re-run; poll instead).\n\n"
            "Returns: {job_id, step, state, log_path, run_dir}.\n\n"
            "Example: vivado_run_step(xpr=\"proj/top.xpr\", step=\"synth\", jobs=4)"
        ),
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,     # a build step is expensive and stateful
            "openWorldHint": False,
        },
        timeout=60,                      # only the LAUNCH is bounded; the job is not
    )
    async def vivado_run_step(
        xpr: str,
        step: Literal["synth", "impl", "bitstream"],
        jobs: int = 4,
        timeout_s: int = 3600,
        ctx: Context | None = None,
    ) -> dict:
        # 1. Path jail: the project must live inside the configured workspace.
        project = resolve_within(settings.workspace, xpr)
        if project.suffix != ".xpr" or not project.exists():
            return mgr.error("PATH_NOT_FOUND", f"no such project: {project}")

        # 2. Serialise per project: two writers on one .runs tree corrupt it.
        running = mgr.find_running(xpr=project)
        if running:
            return mgr.error(
                "JOB_ALREADY_RUNNING",
                f"step already running for {project.name}",
                job_id=running.job_id,
            )

        # 3. One run directory per job: everything this job writes lives in it.
        job = mgr.new_job(kind=f"vivado_{step}", xpr=project, timeout_s=timeout_s,
                          tool_version=settings.vivado_version)

        # 4. Generate a Tcl script. Values are emitted as Tcl variables, never
        #    interpolated into a shell string; the script is a FILE on disk.
        tcl = (
            "# generated by vivado-mcp — do not edit\n"
            f'set_project_path {{{project}}}\n'
            f"open_project $project_path\n"
            f'set jobs {{{int(jobs)}}}\n'
            f"if {{[catch {{\n        {STEP_CMD[step].format(jobs=int(jobs))}\n"
            "} err]} {\n"
            '    puts "VIVADO_MCP_ERROR: $err"\n'
            "    exit 1\n"
            "}\n"
            f'puts "VIVADO_MCP_OK {step}"\n'
            "exit 0\n"
        )
        script = job.run_dir / f"{step}.tcl"
        write_text_atomic(script, tcl)

        # 5. argv list, allowlisted binary, settings64.sh-derived env, no shell.
        argv = [settings.vivado_bin, "-mode", "batch", "-notrace",
                "-source", str(script), "-log", str(job.run_dir / "vivado.log"),
                "-journal", str(job.run_dir / "vivado.jou")]
        mgr.launch(job, argv, cwd=job.run_dir, env=settings.eda_env())

        if ctx is not None:
            await ctx.info(f"started {step} as {job.job_id}")

        # 6. Bounded return: identity + where to look, never the output.
        return {
            "job_id": job.job_id,
            "step": step,
            "state": job.state,          # "running"
            "log_path": str(job.log_path),
            "run_dir": str(job.run_dir),
        }
```

`JobManager.error(...)` is the single constructor for the §5.1 error payload, so every tool
fails in the same shape: it reads the job's log tail, extracts the severity lines, and returns
`{"isError": True, "error_code": ..., "last_log_lines": [...40 lines...], "log_path": ...}`.
FastMCP turns a returned dict into structured content; alternatively raise a `ToolError` with
the same JSON serialised, which FastMCP also surfaces as a tool error.

### 7.3 A complete `tail_log` tool

```python
# src/vivado_mcp/tools/job_tools.py
from collections import deque
from pathlib import Path
import re

from ..safety import resolve_within

# Vivado/Vitis severities, in the bracketed form they actually appear in:
#   ERROR: [Synth 8-5857] ...        WARNING: [Vivado 12-7128] ...
#   CRITICAL WARNING: [Vivado 12-1790] ...
SEVERITY_RE = re.compile(r"\b(ERROR|CRITICAL WARNING|WARNING|INFO)\b\s*:")


def register(mcp, settings, mgr) -> None:

    @mcp.tool(
        name="tail_log",
        title="Read the end of a file or job log",
        description=(
            "Return the last N lines of a file inside the workspace (typically a job log "
            "or an EDA report), optionally filtered by a regular expression. Use it to "
            "watch a running job or to look at the end of a failed run.\n\n"
            "Output is bounded: at most `lines` lines (default 200, max 2000) and 200 kB. "
            "The result tells you the first line number returned, so you know what you "
            "did not see. For ERROR/WARNING extraction with line numbers use read_log(); "
            "for structured report values use parse_timing_report().\n\n"
            "Returns: {path, from_line, to_line, total_lines, matched, lines, truncated}.\n\n"
            "Example: tail_log(path=\".vivado-mcp/runs/run-20260917-1a3f9c/job.log\", "
            "lines=80, grep=\"ERROR|CRITICAL\")"
        ),
        annotations={"readOnlyHint": True, "idempotentHint": True, "openWorldHint": False},
        timeout=15,
    )
    def tail_log(path: str, lines: int = 200, grep: str | None = None) -> dict:
        target = resolve_within(settings.workspace, path)      # path jail, no exceptions
        if not target.is_file():
            return mgr.error("PATH_NOT_FOUND", f"no such file: {target}")

        n = max(1, min(int(lines), 2000))                       # hard cap
        pattern = re.compile(grep) if grep else None            # invalid regex → caller error

        tail: deque[tuple[int, str]] = deque(maxlen=n)
        total = 0
        with target.open("r", encoding="utf-8", errors="replace") as fh:
            for total, raw in enumerate(fh, start=1):
                line = raw.rstrip("\n")
                if pattern is None or pattern.search(line):
                    tail.append((total, line))

        rows = list(tail)
        first = rows[0][0] if rows else total + 1
        last = rows[-1][0] if rows else total
        body = [f"{no}: {text}" for no, text in rows]
        return {
            "path": str(target),
            "from_line": first,
            "to_line": last,
            "total_lines": total,                # so the model knows how much it skipped
            "matched": len(rows),
            "lines": body,
            "truncated": bool(rows) and first > 1,
        }
```

Two details worth copying: iterating the file line-by-line with a fixed-size `deque` reads a
multi-hundred-megabyte log in constant memory, and `total_lines` gives the model a correct
sense of scale ("this is 4 % of the log") instead of the false impression that it has seen
everything.

### 7.4 Server-side self-consistency rules

- All four tools of §7 must work when the EDA tools are absent: `read_project_file`,
  `list_project_files`, `tail_log`, `list_hdl_modules` need no Vivado at all. This makes the
  server installable and testable anywhere — which matters for a repository whose CI has no
  licence.
- Every parser gets a checked-in fixture and a unit test. `tests/test_parsers.py` is the only
  file that must pass in CI on a machine with no AMD tools, and it is the file that protects
  the number the model will read.

---

## 8. Open questions to resolve before implementation

1. **FastMCP 4.x vs `mcp` 2.x.** Both work; FastMCP has more batteries (timeout, tasks,
   masking, structured output, `Client` for tests) but adds a dependency and a third naming
   scheme. Decide and pin. `[U]` — a spike is cheap: write the same `tail_log` tool twice.
2. **Persistent Vivado session vs one process per job.** Prior art (`coreyhahn/vivado_mcp`,
   `QingquanYao/vitis_mcp`) holds a long-lived REPL to avoid ~30 s startup per command — a
   real win for interactive queries, a real risk for the background-job model (a hung REPL
   blocks everything, and a killed REPL loses state). A hybrid is plausible: one-shot batch
   for build steps, an optional persistent Tcl session for introspection. `[U]` — measure the
   startup cost on the target install first.
3. **Which Vitis interface to script against** in the target release: the `vitis -i` Python
   REPL used by `QingquanYao/vitis_mcp` `[V]` or `xsct` `[S]`
   https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841693/HSI+. The 2026.1 release
   notes mention that "from the 2026.1 release onwards, AMD Vitis integrates with HLS" and
   that the 2026.1 `settings.sh` scripts handle the changed folder layout, which implies
   setup-script churn across releases `[V]`
   https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Installer.
   Pin the supported release range in the README and detect it at startup.
4. **Windows.** All the client configs in §6 assume POSIX paths in places. Vivado on Windows
   uses `.bat` wrappers (`vitis.bat` appears in the Vitis MCP config `[V]`
   https://github.com/QingquanYao/vitis_mcp) and `settings64.bat`. The `start_new_session`
   process-group kill does not exist as such on Windows — `CREATE_NEW_PROCESS_GROUP` +
   `Job Objects` is the equivalent. Decide whether v1 is POSIX-only. `[U]`
5. **Board/part validation source.** Whether to ship a static list of parts/boards or query
   the installed tool (`get_parts`, `get_board_parts`) and cache it. Querying is correct;
   shipping is faster to boot. `[U]`
6. **Hermes `timeout` default (120 vs 300)** — see §6.4. `[U]`

---

## 9. Sources

Protocol and SDKs
- MCP specification (latest, 2026-07-28 core): https://modelcontextprotocol.io/specification/latest
- 2026-07-28 key changes: https://modelcontextprotocol.io/specification/2026-07-28/changelog
- 2025-11-25 key changes: https://modelcontextprotocol.io/specification/2025-11-25/changelog
- Transports (stdio, Streamable HTTP, custom): https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- Tools, current revision (schemas, annotations, error handling, determinism, `x-mcp-header`): https://modelcontextprotocol.io/specification/2026-07-28/server/tools
- Tools, 2025-11-25 (best practices, tool-name conflicts, annotations table, security considerations): https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- Pagination: https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/pagination
- Tasks extension (long-running operations): https://modelcontextprotocol.io/specification/2026-07-28/basic/utilities/tasks
- Security best practices: https://modelcontextprotocol.io/specification/2026-07-28/basic/security_best_practices
- Quickstart, connect a local server (Claude Desktop config, its exact file paths and shape): https://modelcontextprotocol.io/quickstart/user
- Quickstart, build a server: https://modelcontextprotocol.io/quickstart/server
- Official Python SDK repo: https://github.com/modelcontextprotocol/python-sdk
- `mcp` on PyPI (v2.2.0, 2026-09-07; 4 MiB HTTP body limit; v1→v2 renames): https://pypi.org/project/mcp/
- Python SDK docs, "What's new in v2": https://py.sdk.modelcontextprotocol.io/whats-new/
- FastMCP repo: https://github.com/PrefectHQ/fastmcp — docs: https://gofastmcp.com
- FastMCP on PyPI (4.0.3, 2026-09-05): https://pypi.org/project/fastmcp/
- FastMCP tools (`@mcp.tool` arguments, timeout, annotations, thread affinity, `$ref` dereferencing): https://gofastmcp.com/servers/tools
- FastMCP server (`instructions`, `list_page_size`, `tasks`, `cache_ttl`, `mask_error_details`, resources/prompts): https://gofastmcp.com/servers/server
- FastMCP running a server (transports, `run()`/`run_async()`, CLI, `--reload`): https://gofastmcp.com/deployment/running-server
- FastMCP transport mixin (transport literal `"stdio" | "http" | "sse"`): https://gofastmcp.com/python-sdk/fastmcp-server-mixins-transport

Clients
- Claude Code MCP reference: https://docs.claude.com/en/docs/claude-code/mcp
- VS Code, add and manage MCP servers: https://code.visualstudio.com/docs/agent-customization/mcp-servers
- VS Code MCP configuration reference (`servers`, `inputs`, `envFile`, `dev`, `sandboxEnabled`): https://github.com/microsoft/vscode-docs/blob/main/docs/copilot/reference/mcp-configuration.md
- GitHub Copilot, extend Copilot Chat with MCP: https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp
- Cline MCP overview (`cline_mcp_settings.json`, `disabled`, `autoApprove`, `streamableHttp`): https://github.com/cline/cline/blob/main/docs/mcp/mcp-overview.mdx
- Cline remote-server transport-type pitfall: https://github.com/github/github-mcp-server/blob/main/docs/installation-guides/install-cline.md
- Hermes Agent, MCP feature guide: https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
- Hermes Agent, MCP config reference (`mcp_servers` keys, `protocol`, `timeout`): https://hermes-agent.nousresearch.com/docs/reference/mcp-config-reference
- Hermes Agent, configuration (`~/.hermes/`, `.env`, SecretRef `${env:VAR}`): https://hermes-agent.nousresearch.com/docs/user-guide/configuration

AMD Vivado / Vitis
- UG835, `write_hw_platform` (XSA export), 2026.1: https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_hw_platform
- UG900, compiling and simulating (`xelab`/`xsim`, `.prj` files): https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation/Compiling-and-Simulating
- UG973, installing on a Linux client network (`settings64.(c)sh`, `DISPLAY`), 2026.1: https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Install-the-Vivado-Design-Tools-on-a-Linux-Client-Network
- UG973, installer / 2026.1 `settings.sh` change: https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Installer
- Hardware Manager / xsct target selection and programming (`connect -url TCP:host:3121`, `targets -set -filter`, `fpga <bit>`, `open_hw_manager`, `get_hw_targets`, `get_hw_devices`): https://unlimited.ethz.ch/spaces/enzianwiki/pages/208869538/ and https://centennialsoftwaresolutions.com/help/extract-read-back-configuration-data-from-a-zynq-7000-fpga (third-party tutorials quoting the command sequences)
- XSCT/HSI as the command-line umbrella for Vitis: https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18841693/HSI+

cocotb and prior art
- cocotb simulator support (supported `SIM` values; `xsim` absent): https://docs.cocotb.org/en/stable/simulator_support.html
- Vicoco, the Vivado-`xsim` runner for cocotb, and its port-only access limitation: https://fpga.mit.edu/6205/F25/documentation/vicoco
- `coreyhahn/vivado_mcp`: https://github.com/coreyhahn/vivado_mcp
- `QingquanYao/vitis_mcp`: https://github.com/QingquanYao/vitis_mcp
- `slauzinho/vivado-mcp`: https://github.com/slauzinho/vivado-mcp
- `lcapossio/fpgaZeroMCP` (concurrency, cancellation, error taxonomy, structured content): https://github.com/lcapossio/fpgaZeroMCP/blob/main/README.md
- `ssql2014/mcp4eda`: https://github.com/ssql2014/mcp4eda
- `airry12/verilog-mcp-server`: https://github.com/airry12/verilog-mcp-server

In-repository context
- `VIVADO/VITIS QUICK PROMPT POUR LLM LOCAL` (flow, Tcl practices, cocotb idiom, VHDL
  conventions, project layout, MCP endpoint sketch) — `skills.md` at the repository root.
