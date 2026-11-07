"""Tiny client for `rcad mcp` (stdio JSON-RPC). Each call returns the tool's parsed result."""
import json, subprocess, sys

class RCad:
    def __init__(self, exe, cwd=None, log=None):
        self.p = subprocess.Popen([exe, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, cwd=cwd, bufsize=1)
        self.n = 0
        self.log = log
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "croxy-build", "version": "1"}})
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")

    def _rpc(self, method, params):
        self.n += 1
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params}) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("rcad mcp exited")
            msg = json.loads(line)
            if msg.get("id") == self.n:
                return msg

    def __call__(self, tool, strict=True, **args):
        msg = self._rpc("tools/call", {"name": tool, "arguments": args})
        if "error" in msg:
            raise RuntimeError(f"{tool}: {msg['error']}")
        res = msg["result"]
        text = "".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
        try:
            out = json.loads(text)
        except Exception:
            out = {"text": text}
        if self.log:
            self.log.write(json.dumps({"tool": tool, "args": args, "result": out})[:4000] + "\n")
        if strict and (res.get("isError") or (isinstance(out, dict) and out.get("ok") is False)):
            raise RuntimeError(f"{tool} failed: {text[:2000]}")
        return out

    def close(self):
        self.p.stdin.close(); self.p.wait(timeout=30)
