"""Command-line interface for the claw-code workers port."""
from __future__ import annotations

import argparse

from .execution import execute_command, execute_tool
from .manifest import build_port_manifest
from .permissions import ToolPermissionContext
from .query_engine import QueryEnginePort
from .registry import (
    command_registry,
    get_command,
    get_commands,
    get_tool,
    get_tools,
    tool_registry,
)
from .reports import (
    assemble_tool_pool,
    build_bootstrap_graph,
    build_command_graph,
    run_deep_link,
    run_direct_connect,
    run_parity_audit,
    run_remote_mode,
    run_ssh_mode,
    run_teleport_mode,
)
from .routing import PortRuntime
from .session import load_session
from .setup import run_setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimized Python porting workspace for the Claude Code rewrite effort"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="render a Markdown summary")
    sub.add_parser("manifest", help="print the current Python workspace manifest")
    sub.add_parser("parity-audit", help="compare against the captured archive snapshot")
    sub.add_parser("setup-report", help="render the startup/prefetch setup report")
    sub.add_parser("command-graph", help="show command graph segmentation")
    sub.add_parser("tool-pool", help="show assembled tool pool")
    sub.add_parser("bootstrap-graph", help="show bootstrap/runtime graph stages")

    p = sub.add_parser("subsystems", help="list current Python modules")
    p.add_argument("--limit", type=int, default=32)

    p = sub.add_parser("commands", help="list mirrored command entries")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--query")
    p.add_argument("--no-plugin-commands", action="store_true")
    p.add_argument("--no-skill-commands", action="store_true")

    p = sub.add_parser("tools", help="list mirrored tool entries")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--query")
    p.add_argument("--simple-mode", action="store_true")
    p.add_argument("--no-mcp", action="store_true")
    p.add_argument("--deny-tool", action="append", default=[])
    p.add_argument("--deny-prefix", action="append", default=[])

    p = sub.add_parser("route", help="route a prompt across inventories")
    p.add_argument("prompt")
    p.add_argument("--limit", type=int, default=5)

    p = sub.add_parser("bootstrap", help="build a runtime session report")
    p.add_argument("prompt")
    p.add_argument("--limit", type=int, default=5)

    p = sub.add_parser("turn-loop", help="run a stateful turn loop")
    p.add_argument("prompt")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--max-turns", type=int, default=3)
    p.add_argument("--structured-output", action="store_true")

    p = sub.add_parser("flush-transcript", help="persist and flush a transcript")
    p.add_argument("prompt")

    p = sub.add_parser("load-session", help="load a persisted session")
    p.add_argument("session_id")

    for name, helptext in (
        ("remote-mode", "simulate remote-control branching"),
        ("ssh-mode", "simulate SSH branching"),
        ("teleport-mode", "simulate teleport branching"),
        ("direct-connect-mode", "simulate direct-connect branching"),
        ("deep-link-mode", "simulate deep-link branching"),
    ):
        mp = sub.add_parser(name, help=helptext)
        mp.add_argument("target")

    p = sub.add_parser("show-command", help="show one command entry by name")
    p.add_argument("name")
    p = sub.add_parser("show-tool", help="show one tool entry by name")
    p.add_argument("name")

    p = sub.add_parser("exec-command", help="execute a command shim")
    p.add_argument("name")
    p.add_argument("prompt")
    p = sub.add_parser("exec-tool", help="execute a tool shim")
    p.add_argument("name")
    p.add_argument("payload")
    return parser


_MODE_HANDLERS = {
    "remote-mode": run_remote_mode,
    "ssh-mode": run_ssh_mode,
    "teleport-mode": run_teleport_mode,
    "direct-connect-mode": run_direct_connect,
    "deep-link-mode": run_deep_link,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cmd = args.command
    manifest = build_port_manifest()

    if cmd == "summary":
        print(QueryEnginePort(manifest).render_summary())
    elif cmd == "manifest":
        print(manifest.to_markdown())
    elif cmd == "parity-audit":
        print(run_parity_audit().to_markdown())
    elif cmd == "setup-report":
        print(run_setup().as_markdown())
    elif cmd == "command-graph":
        print(build_command_graph().as_markdown())
    elif cmd == "tool-pool":
        print(assemble_tool_pool().as_markdown())
    elif cmd == "bootstrap-graph":
        print(build_bootstrap_graph().as_markdown())
    elif cmd == "subsystems":
        for s in manifest.top_level_modules[: args.limit]:
            print(f"{s.name}\t{s.file_count}\t{s.notes}")
    elif cmd == "commands":
        if args.query:
            print(command_registry().render_index(limit=args.limit, query=args.query))
        else:
            commands = get_commands(
                include_plugin_commands=not args.no_plugin_commands,
                include_skill_commands=not args.no_skill_commands,
            )
            lines = [f"Command entries: {len(commands)}", ""]
            lines.extend(f"- {m.name} — {m.source_hint}" for m in commands[: args.limit])
            print("\n".join(lines))
    elif cmd == "tools":
        if args.query:
            print(tool_registry().render_index(limit=args.limit, query=args.query))
        else:
            ctx = ToolPermissionContext.from_iterables(args.deny_tool, args.deny_prefix)
            tools = get_tools(
                simple_mode=args.simple_mode, include_mcp=not args.no_mcp, permission_context=ctx
            )
            lines = [f"Tool entries: {len(tools)}", ""]
            lines.extend(f"- {m.name} — {m.source_hint}" for m in tools[: args.limit])
            print("\n".join(lines))
    elif cmd == "route":
        matches = PortRuntime().route_prompt(args.prompt, limit=args.limit)
        if not matches:
            print("No mirrored command/tool matches found.")
        else:
            for m in matches:
                print(f"{m.kind}\t{m.name}\t{m.score}\t{m.source_hint}")
    elif cmd == "bootstrap":
        print(PortRuntime().bootstrap_session(args.prompt, limit=args.limit).as_markdown())
    elif cmd == "turn-loop":
        results = PortRuntime().run_turn_loop(
            args.prompt,
            limit=args.limit,
            max_turns=args.max_turns,
            structured_output=args.structured_output,
        )
        for idx, result in enumerate(results, start=1):
            print(f"## Turn {idx}")
            print(result.output)
            print(f"stop_reason={result.stop_reason}")
    elif cmd == "flush-transcript":
        engine = QueryEnginePort.from_workspace()
        engine.submit_message(args.prompt)
        print(engine.persist_session())
        print(f"flushed={engine.transcript_store.flushed}")
    elif cmd == "load-session":
        session = load_session(args.session_id)
        print(
            f"{session.session_id}\n{len(session.messages)} messages\n"
            f"in={session.input_tokens} out={session.output_tokens}"
        )
    elif cmd in _MODE_HANDLERS:
        print(_MODE_HANDLERS[cmd](args.target).as_text())
    elif cmd == "show-command":
        module = get_command(args.name)
        if module is None:
            print(f"Command not found: {args.name}")
            return 1
        print("\n".join([module.name, module.source_hint, module.responsibility]))
    elif cmd == "show-tool":
        module = get_tool(args.name)
        if module is None:
            print(f"Tool not found: {args.name}")
            return 1
        print("\n".join([module.name, module.source_hint, module.responsibility]))
    elif cmd == "exec-command":
        result = execute_command(args.name, args.prompt)
        print(result.message)
        return 0 if result.handled else 1
    elif cmd == "exec-tool":
        result = execute_tool(args.name, args.payload)
        print(result.message)
        return 0 if result.handled else 1
    else:  # pragma: no cover - argparse enforces valid subcommands
        build_parser().error(f"unknown command: {cmd}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
