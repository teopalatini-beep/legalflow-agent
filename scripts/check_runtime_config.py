from __future__ import annotations

import os


def print_status(name: str, required: bool = False) -> bool:
    value = os.getenv(name, "").strip()
    is_set = bool(value)
    prefix = "REQUIRED" if required else "OPTIONAL"
    state = "SET" if is_set else "MISSING"
    print(f"[{prefix}] {name}: {state}")
    return is_set


def main() -> None:
    required_ok = True
    required_ok &= print_status("LEGALFLOW_SSO_TOKEN", required=True)
    print_status("CURSOR_API_KEY")
    print_status("LEGALFLOW_ESIGN_ENDPOINT")
    print_status("LEGALFLOW_ESIGN_API_KEY")

    if required_ok:
        print("\nConfiguration check: PASS")
    else:
        print("\nConfiguration check: FAIL (missing required vars)")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
