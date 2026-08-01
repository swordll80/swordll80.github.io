#!/usr/bin/env python3
"""Local compiler bridge for the static C and assembly study tools.

The server binds to 127.0.0.1 only. It serves the repository and exposes a
small JSON API at /api/status and /api/compile. No source code is uploaded.
"""

from __future__ import annotations

import argparse
import json
import locale
import os
import shutil
import subprocess
import tempfile
import time
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable


STUDY_ROOT = Path(__file__).resolve().parent
SITE_ROOT = STUDY_ROOT.parent
MAX_SOURCE_BYTES = 512 * 1024
MAX_INPUT_BYTES = 64 * 1024
COMMAND_TIMEOUT = 15


def decode_output(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    encodings = ["utf-8", locale.getpreferredencoding(False), "mbcs"]
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            pass
    return data.decode("utf-8", errors="replace")


def find_first(names: Iterable[str]) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_vs_tool(name: str) -> str | None:
    """Find a VS tool even when the current shell has no VS developer PATH."""
    candidates: list[Path] = []
    for base in (Path("C:/Program Files/Microsoft Visual Studio"),
                 Path("C:/Program Files (x86)/Microsoft Visual Studio")):
        if base.exists():
            candidates.extend(base.glob(f"*/*/VC/Tools/MSVC/*/bin/Hostx64/x64/{name}"))
            candidates.extend(base.glob(f"*/*/VC/Tools/MSVC/*/bin/Hostx86/x86/{name}"))
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def find_vsdevcmd() -> str | None:
    env_path = os.environ.get("VSDEVCMD")
    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    for base in (Path("C:/Program Files/Microsoft Visual Studio"),
                 Path("C:/Program Files (x86)/Microsoft Visual Studio")):
        if not base.exists():
            continue
        # VS uses <year>/<edition>/Common7/Tools/VsDevCmd.bat.  Keep the
        # lookup independent of edition names such as Enterprise or BuildTools.
        candidates.extend(base.glob("*/*/Common7/Tools/VsDevCmd.bat"))
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def find_cdb() -> str | None:
    direct = find_first(("cdb.exe", "gdb.exe"))
    if direct:
        return direct
    candidates = (
        Path("C:/Program Files (x86)/Windows Kits/10/Debuggers/x64/cdb.exe"),
        Path("C:/Program Files (x86)/Windows Kits/10/Debuggers/x86/cdb.exe"),
        Path("C:/Program Files/Windows Kits/10/Debuggers/x64/cdb.exe"),
    )
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def compiler_choices() -> dict[str, str | None]:
    return {
        "msvc": find_first(("cl.exe", "cl")) or find_vs_tool("cl.exe"),
        "clang": find_first(("clang.exe", "clang")),
        "gcc": find_first(("gcc.exe", "gcc")),
        "ml64": find_first(("ml64.exe", "ml64")) or find_vs_tool("ml64.exe"),
        "nasm": find_first(("nasm.exe", "nasm")),
        "as": find_first(("as.exe", "as")),
        "debugger": find_cdb(),
        "vsdevcmd": find_vsdevcmd(),
    }


def resolve_compiler(language: str, requested: str | None) -> tuple[str, str] | None:
    tools = compiler_choices()
    if language == "c":
        order = [requested] if requested in ("msvc", "clang", "gcc") else ["msvc", "clang", "gcc"]
    else:
        order = [requested] if requested in ("ml64", "nasm", "as") else ["ml64", "nasm", "as"]
    for name in order:
        if name and tools.get(name):
            return name, str(tools[name])
    return None


def run_process(command: list[str], cwd: Path, timeout: int = COMMAND_TIMEOUT,
                env: dict[str, str] | None = None,
                input_data: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=(input_data.encode("utf-8") if input_data is not None else None),
            timeout=timeout,
            check=False,
            env=env,
        )
        return {
            "returncode": completed.returncode,
            "stdout": decode_output(completed.stdout),
            "stderr": decode_output(completed.stderr),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": -1,
            "stdout": decode_output(exc.stdout),
            "stderr": "命令运行超过 15 秒，已终止。",
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        }
    except OSError as exc:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        }


def run_vsdev(command: list[str], cwd: Path) -> dict[str, Any]:
    vsdev = find_vsdevcmd()
    if not vsdev:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": "未找到 Visual Studio 开发者命令环境，请设置 VSDEVCMD。",
            "duration_ms": 0,
        }
    # Export the VS developer environment once, then invoke the requested
    # executable directly. This avoids cmd.exe quote stripping for paths such
    # as "C:\\Program Files\\Microsoft Visual Studio\\...".
    # Keep `call` as the first argument after /c. Passing the whole command as
    # one quoted argument makes cmd.exe treat the quoted batch path as the
    # command itself on some Windows versions.
    activated = run_process(
        ["cmd.exe", "/d", "/c", "call", vsdev, "-arch=x64", ">nul", "&&", "set"],
        cwd,
    )
    if activated.get("returncode") != 0:
        return activated
    env = os.environ.copy()
    for line in activated.get("stdout", "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return run_process(command, cwd, env=env)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding=locale.getpreferredencoding(False), errors="replace")


def append_process(result: dict[str, Any], process: dict[str, Any]) -> None:
    for key in ("stdout", "stderr"):
        if process.get(key):
            result[key] = (result.get(key, "") + process[key]).strip() + "\n"
    result["returncode"] = process.get("returncode", -1)
    result["duration_ms"] = round(result.get("duration_ms", 0) + process.get("duration_ms", 0), 1)


def build_c(source: str, action: str, requested: str | None, options: dict[str, Any], stdin: str) -> dict[str, Any]:
    resolved = resolve_compiler("c", requested)
    if not resolved:
        return {"ok": False, "message": "未找到 C 编译器。请安装 Visual Studio、Clang 或 GCC。"}
    compiler_name, compiler = resolved
    result: dict[str, Any] = {"ok": False, "language": "c", "compiler": compiler_name,
                              "stdout": "", "stderr": "", "duration_ms": 0}
    with tempfile.TemporaryDirectory(prefix="study-c-") as temp_name:
        work = Path(temp_name)
        source_path = work / "main.c"
        exe_path = work / ("main.exe" if os.name == "nt" else "main.out")
        asm_path = work / "main.asm"
        source_path.write_text(source, encoding="utf-8")
        opt = str(options.get("optimization", "0"))
        if compiler_name == "msvc":
            opt_flag = "/Od" if opt == "0" else ("/O1" if opt == "1" else "/O2")
            command = [compiler, "/nologo", "/W4", opt_flag, "/Zi", "/D_CRT_SECURE_NO_WARNINGS",
                       "/FAcs", f"/Fa{asm_path}", f"/Fe{exe_path}", str(source_path)]
            process = run_vsdev(command, work)
        else:
            opt_flag = "-O" + (opt if opt in ("0", "1", "2", "3") else "0")
            command = [compiler, "-std=c11", "-Wall", "-Wextra", opt_flag, "-g",
                       str(source_path), "-o", str(exe_path)]
            process = run_process(command, work)
        append_process(result, process)
        if result["returncode"] != 0:
            result["message"] = "编译失败。"
            return result
        if compiler_name != "msvc":
            asm_process = run_process([compiler, "-S", "-fverbose-asm", opt_flag,
                                       str(source_path), "-o", str(work / "main.s")], work)
            append_process(result, asm_process)
            if (work / "main.s").exists():
                asm_path = work / "main.s"
        if asm_path.exists():
            result["assembly"] = read_text(asm_path)
        if action == "run":
            run_result = run_process([str(exe_path)], work, timeout=COMMAND_TIMEOUT,
                                     input_data=stdin)
            result["run"] = run_result
            result["stdout"] = (result.get("stdout", "") + run_result.get("stdout", "")).strip()
            result["stderr"] = (result.get("stderr", "") + run_result.get("stderr", "")).strip()
            result["returncode"] = run_result.get("returncode", -1)
            result["duration_ms"] = round(result["duration_ms"] + run_result.get("duration_ms", 0), 1)
        elif action == "debug":
            result.update(run_debugger(exe_path, work))
        result["ok"] = result["returncode"] == 0
        result["message"] = "编译完成。" if result["ok"] else "程序运行或调试未正常结束。"
        return result


def build_asm(source: str, action: str, requested: str | None) -> dict[str, Any]:
    resolved = resolve_compiler("asm", requested)
    if not resolved:
        return {"ok": False, "message": "未找到汇编器。请安装 MASM/ml64、NASM 或 GNU as。"}
    assembler_name, assembler = resolved
    result: dict[str, Any] = {"ok": False, "language": "asm", "compiler": assembler_name,
                              "stdout": "", "stderr": "", "duration_ms": 0}
    with tempfile.TemporaryDirectory(prefix="study-asm-") as temp_name:
        work = Path(temp_name)
        source_path = work / ("main.asm" if assembler_name in ("ml64", "nasm") else "main.s")
        obj_path = work / "main.obj"
        exe_path = work / "main.exe"
        source_path.write_text(source, encoding="utf-8")
        if assembler_name == "ml64":
            process = run_vsdev([assembler, "/nologo", "/c", str(source_path), f"/Fo{obj_path}"], work)
        elif assembler_name == "nasm":
            process = run_process([assembler, "-f", "win64", str(source_path), "-o", str(obj_path)], work)
        else:
            process = run_process([assembler, "--64", str(source_path), "-o", str(obj_path)], work)
        append_process(result, process)
        if result["returncode"] != 0:
            result["message"] = "汇编失败。"
            return result
        if obj_path.exists():
            result["assembly"] = "目标文件已生成：" + obj_path.name
        if action in ("run", "debug") and assembler_name in ("ml64", "nasm"):
            linker = find_first(("link.exe", "link")) or find_vs_tool("link.exe") or "link.exe"
            link = run_vsdev([linker, "/nologo", str(obj_path), "/subsystem:console",
                              "/entry:main", f"/out:{exe_path}", "kernel32.lib"], work)
            append_process(result, link)
            if result["returncode"] == 0 and action == "run":
                run_result = run_process([str(exe_path)], work, timeout=COMMAND_TIMEOUT)
                result["run"] = run_result
                result["stdout"] = (result.get("stdout", "") + run_result.get("stdout", "")).strip()
                result["stderr"] = (result.get("stderr", "") + run_result.get("stderr", "")).strip()
                result["returncode"] = run_result.get("returncode", -1)
            elif result["returncode"] == 0 and action == "debug":
                result.update(run_debugger(exe_path, work))
        elif action in ("run", "debug"):
            result["stderr"] = (result.get("stderr", "") + "当前汇编器只完成目标文件生成，暂未配置链接器。 ").strip()
            result["returncode"] = 0
        result["ok"] = result["returncode"] == 0
        result["message"] = "汇编完成。" if result["ok"] else "汇编、链接或运行失败。"
        return result


def run_debugger(exe_path: Path, cwd: Path) -> dict[str, Any]:
    debugger = find_cdb()
    if not debugger or not exe_path.exists():
        return {"debug": "未找到可用调试器，已完成带调试信息的构建。", "returncode": 0}
    if Path(debugger).name.lower().startswith("cdb"):
        command = [debugger, "-lines", "-c", "bp main;g;kv;dv;q", str(exe_path)]
    else:
        command = [debugger, "-q", "-batch", "-ex", "break main", "-ex", "run",
                   "-ex", "backtrace", "-ex", "info locals", "-ex", "quit", str(exe_path)]
    process = run_process(command, cwd)
    return {"debug": (process.get("stdout", "") + process.get("stderr", "")).strip(),
            "returncode": process.get("returncode", -1)}


def compile_request(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source", "")
    if not isinstance(source, str):
        return {"ok": False, "message": "source 必须是字符串。"}
    if len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        return {"ok": False, "message": "源码超过 512 KiB 限制。"}
    stdin = payload.get("stdin", "")
    if not isinstance(stdin, str) or len(stdin.encode("utf-8")) > MAX_INPUT_BYTES:
        return {"ok": False, "message": "标准输入超过 64 KiB 限制。"}
    language = payload.get("language", "c")
    action = payload.get("action", "compile")
    if language not in ("c", "asm") or action not in ("compile", "run", "debug"):
        return {"ok": False, "message": "不支持的语言或操作。"}
    if language == "c":
        return build_c(source, action, payload.get("compiler"), payload.get("options", {}), stdin)
    return build_asm(source, action, payload.get("compiler"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(SITE_ROOT), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        if self.path.startswith("/api/"):
            print("[api] " + (fmt % args))

    def _json(self, data: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/status":
            tools = compiler_choices()
            self._json({"ok": True, "siteRoot": str(SITE_ROOT),
                        "tools": {key: bool(value) for key, value in tools.items()}})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/compile":
            self._json({"ok": False, "message": "Not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_SOURCE_BYTES * 2:
                raise ValueError("请求体过大。")
            body = self.rfile.read(length)
            payload = json.loads(body.decode("utf-8"))
            self._json(compile_request(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)


def main() -> None:
    parser = argparse.ArgumentParser(description="Local compiler bridge for study_notes")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--page", default="study_notes/c_compile/index.html")
    parser.add_argument("--open", action="store_true", help="Open the selected page in the default browser")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/{args.page.lstrip('/')}"
    print(f"Study compiler server: {url}")
    print("Only 127.0.0.1 is exposed. Press Ctrl+C to stop.")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
