"""Cross-language protocol check using an ephemeral test key kept in memory."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from deploom_mcp import shared_records


def main():
    root = Path(__file__).resolve().parents[1]
    keys = Ed25519PrivateKey.generate()
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        public = directory / "public.hex"
        public.write_text(keys.public_key().public_bytes_raw().hex(), encoding="ascii")
        body = directory / "cache.json"
        sig = directory / "cache.sig"
        seed = shared_records.bundled()
        body.write_bytes(json.dumps(dict(schema=1, revision=25, **seed)).encode())
        pem = keys.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        subprocess.run(["node", str(root / "cache/sign-records.cjs"), str(body), str(sig), str(public)],
                       env={**os.environ, "DEPLOOM_RECORDS_SIGNING_KEY": base64.b64encode(pem).decode("ascii")},
                       check=True, capture_output=True)
        with patch.object(shared_records, "public_key_file", public):
            assert shared_records.verified(body.read_bytes(), sig.read_bytes())["history"] == seed["history"]
            try:
                shared_records.verified(body.read_bytes() + b" ", sig.read_bytes())
            except shared_records.InvalidSignature:
                return
            raise ValueError("Tampered snapshot was accepted")


if __name__ == "__main__":
    main()
