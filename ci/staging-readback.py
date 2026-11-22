"""Read a signed staging snapshot through the published MCP's stdio entry point."""
import asyncio
import base64
import functools
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mcp import ClientSession, StdioServerParameters, stdio_client

# Keep the staging origin and trust root confined to this test process.
ENTRY = """
import runpy, sys
from pathlib import Path
from deploom_mcp import shared_records
shared_records.public_key_file = Path(sys.argv[1])
shared_records.BASE = sys.argv[2]
del sys.argv[1:]
runpy.run_module('deploom_mcp', run_name='__main__')
"""


async def verify(root, origin):
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    env["DEPLOOM_MCP_RECORDS_DIR"] = str(root / "consumer")
    server = StdioServerParameters(command=sys.executable, args=["-I", "-B", "-c", ENTRY,
                                  str(root / "test-public.hex"), origin], env=env)
    args = {"package": "react", "from_version": "18.2.0", "to_version": "18.3.1"}
    async with asyncio.timeout(30), stdio_client(server) as streams, ClientSession(*streams) as client:
        await client.initialize()
        while True:
            response = await client.call_tool("get_shared_migration_evidence", args)
            assert not response.is_error, response.content
            result = response.structured_content or json.loads(response.content[0].text)
            if result["snapshotSource"] == "verified-pages":
                break
            await asyncio.sleep(0.2)
        assert any(row["check"] == "test" and row["outcome"] == "passed" and
                   row["source"].endswith("/fixtures/react-ssr/check.cjs") for row in result["observations"]), result
        print("Verified staging SSR observation through the installed MCP")


def main(payload):
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        site = root / "site"
        site.mkdir()
        data = site / "cache.json"
        data.write_bytes(payload.read_bytes())
        key = Ed25519PrivateKey.generate()
        pin = root / "test-public.hex"
        pin.write_text(key.public_key().public_bytes_raw().hex(), encoding="ascii")
        priv = key.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        subprocess.run(["node", "cache/sign-records.cjs", str(data), str(site / "cache.sig"), str(pin)],
                       env={"PATH": os.environ["PATH"], "DEPLOOM_RECORDS_SIGNING_KEY": base64.b64encode(priv).decode()},
                       check=True, capture_output=True)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as listener:
            thread = threading.Thread(target=listener.serve_forever)
            thread.start()
            try:
                asyncio.run(verify(root, f"http://127.0.0.1:{listener.server_port}/"))
            finally:
                listener.shutdown()
                thread.join()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
