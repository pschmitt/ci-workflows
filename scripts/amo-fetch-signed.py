#!/usr/bin/env python3
"""Download the AMO-signed XPI of a version that AMO already has.

AMO signs a version only once. When a release run uploaded it and then lost
the connection (or failed later), the next run gets "Version X already
exists" from `web-ext sign`; this fetches that signed file instead, waiting
until AMO has signed it. The caller verifies it against the source.

Credentials come from WEB_EXT_API_KEY and WEB_EXT_API_SECRET, as for web-ext.
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

API = "https://addons.mozilla.org/api/v5"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def jwt(key: str, secret: str) -> str:
    now = int(time.time())
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(
        json.dumps({"iss": key, "jti": str(uuid.uuid4()), "iat": now, "exp": now + 60}).encode()
    )
    signature = hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256)
    return f"{header}.{payload}.{b64(signature.digest())}"


def get(url: str, key: str, secret: str) -> bytes:
    request = urllib.request.Request(url, headers={"Authorization": f"JWT {jwt(key, secret)}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def version_detail(guid: str, version: str, key: str, secret: str) -> dict:
    addon = urllib.parse.quote(guid, safe="@")
    # AMO takes a version number with a "v" prefix (a bare number is an id).
    for ref in (f"v{version}", version):
        url = f"{API}/addons/addon/{addon}/versions/{urllib.parse.quote(ref)}/"
        try:
            return json.loads(get(url, key, secret))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
    raise SystemExit(f"AMO has no version {version} of {guid}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, help="unpacked Firefox extension")
    parser.add_argument("--out", required=True, help="where to write the signed XPI")
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for signing")
    args = parser.parse_args()

    key = os.environ["WEB_EXT_API_KEY"]
    secret = os.environ["WEB_EXT_API_SECRET"]
    with open(os.path.join(args.source_dir, "manifest.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    version = manifest["version"]
    settings = manifest.get("browser_specific_settings") or manifest.get("applications") or {}
    guid = settings.get("gecko", {}).get("id")
    if not guid:
        raise SystemExit("manifest.json has no gecko id")

    deadline = time.monotonic() + args.timeout
    while True:
        detail = version_detail(guid, version, key, secret)
        file = detail.get("file") or {}
        status = file.get("status")
        if status == "public" and file.get("url"):
            break
        if status in ("disabled", "deleted"):
            raise SystemExit(f"AMO {status} version {version} of {guid}")
        if time.monotonic() > deadline:
            raise SystemExit(f"AMO has not signed version {version} yet (status: {status})")
        print(f"Waiting for AMO to sign {version} (status: {status})", file=sys.stderr)
        time.sleep(15)

    data = get(file["url"], key, secret)
    with open(args.out, "wb") as fh:
        fh.write(data)
    print(f"Downloaded the signed {guid} {version} from AMO ({len(data)} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
