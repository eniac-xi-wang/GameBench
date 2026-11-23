from __future__ import annotations

import base64
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
TASK_FILE = ROOT / "tasks/celeste_100m.json"
BUTTONS = {"left": 1, "right": 2, "up": 4, "down": 8, "jump": 16, "dash": 32}
MAX_FRAMES = 600
PALETTE = bytes.fromhex("0000001d2b537e2553008751ab52365f574fc2c3c7fff1e8ff004dffa300ffec2700e43629adff83769cff77a8ffccaa")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def parse_script(script: dict) -> list[int]:
    if not isinstance(script, dict) or set(script) != {"version", "segments"} or type(script["version"]) is not int or script["version"] != 1:
        raise ValueError("script requires only version=1 and segments; task/seed overrides are forbidden")
    if not isinstance(script["segments"], list):
        raise ValueError("segments must be a list")
    result = []
    for part in script["segments"]:
        if not isinstance(part, dict) or set(part) != {"frames", "buttons"}:
            raise ValueError("each segment requires frames and buttons")
        n, buttons = part["frames"], part["buttons"]
        if type(n) is not int or not 1 <= n <= MAX_FRAMES:
            raise ValueError("frames must be an integer in 1..600")
        if not isinstance(buttons, list) or any(type(b) is not str or b not in BUTTONS for b in buttons) or len(set(buttons)) != len(buttons):
            raise ValueError("unknown or repeated button")
        result.extend([sum(BUTTONS[b] for b in buttons)] * n)
        if len(result) > MAX_FRAMES:
            raise ValueError("script exceeds 600 frames")
    if not result:
        raise ValueError("script cannot be empty")
    return result


def encode_script(masks: list[int]) -> dict:
    parts = []
    for mask in masks:
        if type(mask) is not int or not 0 <= mask <= 63:
            raise ValueError("invalid button mask")
        buttons = [b for b, bit in BUTTONS.items() if mask & bit]
        if parts and parts[-1]["buttons"] == buttons:
            parts[-1]["frames"] += 1
        else:
            parts.append({"frames": 1, "buttons": buttons})
    script = {"version": 1, "segments": parts}
    parse_script(script)
    return script


def splice(script: dict, start: int, delete: int, insert: list[dict]) -> dict:
    masks = parse_script(script)
    if type(start) is not int or type(delete) is not int or not 0 <= start <= len(masks) or not 0 <= delete <= len(masks)-start:
        raise ValueError("invalid zero-based splice range")
    replacement = parse_script({"version": 1, "segments": insert}) if insert else []
    return encode_script(masks[:start] + replacement + masks[start+delete:])


def source_hashes() -> dict:
    files = ["celeste-classic/celeste.c", "celeste-classic/celeste.h", "celeste-classic/tilemap.h", "celeste-classic/data/gfx.bmp", "celeste-classic/data/font.bmp", "tasbench/native/runner.cpp", "tasbench/core.py", "tasks/celeste_100m.json"]
    return {f: digest((ROOT / f).read_bytes()) for f in files}


def build() -> Path:
    folder = ROOT / ".tas-build"
    folder.mkdir(exist_ok=True)
    exe, stamp = folder / "celeste-runner", folder / "build.json"
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        raise RuntimeError("A C++ compiler is required")
    flags = ["-std=gnu++20", "-O2", "-fwrapv", "-Wno-narrowing"]
    metadata = {"sources": source_hashes(), "compiler": subprocess.check_output([compiler, "--version"], text=True).splitlines()[0], "flags": flags}
    old = json.loads(stamp.read_text()) if stamp.exists() else {}
    if not exe.exists() or any(old.get(k) != v for k, v in metadata.items()) or old.get("binary_sha256") != digest(exe.read_bytes()):
        subprocess.run([compiler, *flags, str(ROOT / "tasbench/native/runner.cpp"), "-o", str(exe)], check=True, capture_output=True, text=True)
        metadata["binary_sha256"] = digest(exe.read_bytes())
        save_json(stamp, metadata)
    return exe


def simulate(masks: list[int], out: Path) -> dict:
    exe = build()
    out.mkdir(parents=True, exist_ok=True)
    (out / "inputs.txt").write_text("\n".join(map(str, masks)) + "\n")
    process = subprocess.run([str(exe), str(ROOT / "celeste-classic/data"), str(out / "inputs.txt"), str(out)], capture_output=True, text=True, timeout=15, check=True)
    return json.loads(process.stdout)


def png(frame: bytes) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
    rows = b"".join(b"\0" + frame[y*128:(y+1)*128] for y in range(128))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB",128,128,8,3,0,0,0)) + chunk(b"PLTE", PALETTE) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def make_replay(out: Path, report: dict):
    raw = (out / "frames.bin").read_bytes()
    frames = [png(raw[i:i+16384]) for i in range(0,len(raw),16384)]
    (out / "start.png").write_bytes(frames[0])
    (out / "finish.png").write_bytes(frames[-1])
    trace = [json.loads(s) for s in (out / "trace.jsonl").read_text().splitlines()]
    payload = {"frames": [base64.b64encode(f).decode() for f in frames], "trace": trace, "report": report, "buttons": BUTTONS}
    template = (ROOT / "tasbench/replay.html").read_text()
    (out / "replay.html").write_text(template.replace("__DATA__", json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")))


def evaluate(script: dict, out: Path, replay=True) -> dict:
    masks = parse_script(script)
    if out.exists():
        raise ValueError(f"output already exists: {out}")
    out.mkdir(parents=True)
    canonical = encode_script(masks)
    save_json(out / "script.json", canonical)
    result = simulate(masks, out)
    result.update({"task": "celeste-classic-100m-v1", "completion_frames": result["frames"] if result["success"] else None,
                   "seconds": result["frames"] / 30, "script_frames": len(masks), "script_sha256": digest(bytes(masks)),
                   "trace_sha256": digest((out / "trace.jsonl").read_bytes()), "video_sha256": digest((out / "frames.bin").read_bytes()),
                   "provenance": json.loads((ROOT / ".tas-build/build.json").read_text())})
    save_json(out / "result.json", result)
    if replay:
        make_replay(out, result)
    return result


def verify(out: Path) -> dict:
    saved = json.loads((out / "result.json").read_text())
    masks = parse_script(json.loads((out / "script.json").read_text()))
    build()
    if saved["provenance"] != json.loads((ROOT / ".tas-build/build.json").read_text()):
        raise ValueError("evaluator provenance changed; this is a different benchmark build")
    with tempfile.TemporaryDirectory(prefix="tas-verify-") as tmp:
        result = simulate(masks, Path(tmp))
        checks = {"script": digest(bytes(masks)) == saved["script_sha256"],
                  "recorded_trace": digest((out/"trace.jsonl").read_bytes()) == saved["trace_sha256"],
                  "recorded_video": digest((out/"frames.bin").read_bytes()) == saved["video_sha256"],
                  "fresh_trace": digest((Path(tmp)/"trace.jsonl").read_bytes()) == saved["trace_sha256"],
                  "fresh_video": digest((Path(tmp)/"frames.bin").read_bytes()) == saved["video_sha256"],
                  "result": all(saved[k] == v for k,v in result.items()),
                  "completion": saved["completion_frames"] == (result["frames"] if result["success"] else None)}
    if not all(checks.values()):
        raise ValueError(f"replay verification failed: {checks}")
    return {"valid": True, "success": saved["success"], "completion_frames": saved["completion_frames"], "checks": checks}


class Session:
    """Append-only trials; only completed levels may replace the incumbent."""
    def __init__(self, path: Path, budget: int):
        if type(budget) is not int or not 1 <= budget <= 1000:
            raise ValueError("evaluation budget must be 1..1000")
        path.mkdir(parents=True, exist_ok=False)
        self.path, self.budget, self.count = path, budget, 0
        self.best, self.best_script = None, None
        build()
        self.provenance = json.loads((ROOT / ".tas-build/build.json").read_text())

    def trial(self, script: dict, reason: str) -> dict:
        if self.count >= self.budget:
            raise ValueError("evaluation budget exhausted")
        parse_script(script)
        build()
        if self.provenance != json.loads((ROOT / ".tas-build/build.json").read_text()):
            raise RuntimeError("evaluator changed during optimization; start a new session")
        self.count += 1
        name = f"trial-{self.count:04d}"
        report = evaluate(script, self.path/name)
        improved = report["success"] and (self.best is None or report["frames"] < self.best["frames"])
        if improved:
            self.best, self.best_script = report, encode_script(parse_script(script)[:report["frames"]])
            save_json(self.path/"best.json", self.best_script)
        summary = {"trial": name, "reason": reason, "success": report["success"], "frames": report["frames"], "deaths": report["deaths"], "improved": improved, "best_frames": self.best["frames"] if self.best else None}
        with (self.path/"history.jsonl").open("a") as f:
            f.write(json.dumps(summary, ensure_ascii=False)+"\n")
        save_json(self.path/"session.json", {"evaluations": self.count, "budget": self.budget, "best_frames": summary["best_frames"]})
        return summary

    def finish(self):
        if self.best_script is None:
            answer = {"valid_solution": False, "evaluations": self.count}
            save_json(self.path/"summary.json", answer)
            return answer
        final = self.path/"final"
        report = evaluate(self.best_script, final)
        verified = verify(final)
        answer = {"valid_solution": True, "evaluations": self.count, "best_frames": report["frames"], "verification": verified, "replay": str(final/"replay.html")}
        save_json(self.path/"summary.json", answer)
        history = [json.loads(line) for line in (self.path/"history.jsonl").read_text().splitlines()]
        rows = "".join(f'<tr><td><a href="{r["trial"]}/replay.html">{r["trial"]}</a></td><td>{html.escape(r["reason"])}</td><td>{r["frames"] if r["success"] else "未完成"}</td><td>{r["best_frames"]}</td><td>{"✓" if r["improved"] else ""}</td></tr>' for r in history)
        points = " ".join(f'{20+760*i/max(1,len(history)-1):.1f},{180-140*(history[0]["best_frames"]-r["best_frames"])/max(1,history[0]["best_frames"]-report["frames"]):.1f}' for i,r in enumerate(history) if r["best_frames"] is not None) if history[0]["best_frames"] is not None else ""
        (self.path/"index.html").write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>TAS 优化记录</title><style>body{{background:#111827;color:#e5e7eb;font:16px system-ui;max-width:1000px;margin:40px auto;padding:20px}}a{{color:#67e8f9}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #334155}}svg{{width:100%;background:#1e293b;border-radius:12px}}h1{{font-size:28px}}</style><h1>Celeste Classic · 100m 优化记录</h1><p>{self.count} 次试跑 · 最佳 {report["frames"]} 帧（{report["frames"]/30:.3f} 秒）· 独立复跑通过</p><p><a href="final/replay.html">查看最佳回放</a> · <a href="trial-0001/replay.html">查看初始回放</a> · <a href="best.json">最佳按键脚本</a></p><p>最佳成绩随试跑次数变化：起点 {history[0]["best_frames"]} → 终点 {report["frames"]} 帧</p><svg viewBox="0 0 800 210" role="img" aria-label="最佳完成帧数随试跑次数下降"><polyline points="{points}" fill="none" stroke="#67e8f9" stroke-width="3"/></svg><table><thead><tr><th>试跑 / 回放</th><th>修改假设</th><th>完成帧数</th><th>历史最佳</th><th>改进</th></tr></thead><tbody>{rows}</tbody></table></html>''')
        return answer
