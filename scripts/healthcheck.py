from __future__ import annotations

import os
import urllib.request


def main() -> None:
    port = os.getenv("PORT", "8080")
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
        if response.status // 100 != 2:
            raise SystemExit(1)
        print(response.read().decode())


if __name__ == "__main__":
    main()
