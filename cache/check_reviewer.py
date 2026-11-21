"""Check both verdicts on public, pinned evidence before changing the reviewer."""
import json
from pathlib import Path
from records_audit import audit


def main():
    root = Path(__file__).resolve().parents[1]
    row = json.loads((root / "docs/v1/history.json").read_bytes())[0]
    text = (root / "fixtures/react-renderers/check.cjs").read_text(encoding="utf-8")
    audit([{"record": row, "evidence": text}])
    wrong = dict(row, package="typescript", check="typecheck")
    try:
        audit([{"record": wrong, "evidence": text}])
    except ValueError as error:
        if str(error) == "AI review requires a maintainer":
            return
        raise
    raise AssertionError("Unrelated claim passed the AI gate")


if __name__ == "__main__":
    main()
