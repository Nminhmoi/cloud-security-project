"""Read-only HTTPS and security smoke test for a deployed CloudBox instance."""

import argparse
import http.cookiejar
import json
import socket
import ssl
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPCookieProcessor,
    HTTPSHandler,
    Request,
    build_opener,
)


class SmokeTestError(RuntimeError):
    """Raised when a deployment does not meet the smoke-test contract."""


def validate_security_headers(headers, require_https=True):
    required = {
        "Content-Security-Policy": "default-src",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=()",
    }
    if require_https:
        required["Strict-Transport-Security"] = "max-age="

    missing = []
    for name, expected in required.items():
        value = headers.get(name, "")
        if expected.casefold() not in value.casefold():
            missing.append(name)
    if missing:
        raise SmokeTestError("Missing or invalid security headers: " + ", ".join(missing))


def validate_session_cookies(cookies, require_https=True):
    session_cookies = [cookie for cookie in cookies if "session" in cookie.name.casefold()]
    if not session_cookies:
        raise SmokeTestError("No Flask session cookie was issued")
    for cookie in session_cookies:
        if not cookie.has_nonstandard_attr("HttpOnly"):
            raise SmokeTestError("Session cookie is missing HttpOnly")
        if require_https and not cookie.secure:
            raise SmokeTestError("Session cookie is missing Secure")
        same_site = cookie.get_nonstandard_attr("SameSite")
        if same_site not in {"Lax", "Strict"}:
            raise SmokeTestError("Session cookie is missing a safe SameSite policy")


def inspect_tls(hostname, port=443, timeout=10, minimum_valid_days=14):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as connection:
            with context.wrap_socket(connection, server_hostname=hostname) as tls_socket:
                certificate = tls_socket.getpeercert()
                protocol = tls_socket.version()
    except (OSError, ssl.SSLError) as error:
        raise SmokeTestError(f"TLS connection failed: {error}") from error

    if protocol not in {"TLSv1.2", "TLSv1.3"}:
        raise SmokeTestError(f"Unsupported TLS protocol negotiated: {protocol}")
    expires_at = datetime.fromtimestamp(
        ssl.cert_time_to_seconds(certificate["notAfter"]),
        tz=timezone.utc,
    )
    remaining_days = (expires_at - datetime.now(timezone.utc)).days
    if remaining_days < minimum_valid_days:
        raise SmokeTestError(
            f"TLS certificate expires too soon: {remaining_days} day(s) remaining"
        )
    return protocol, expires_at


def _get(opener, url, timeout):
    try:
        response = opener.open(
            Request(url, headers={"User-Agent": "cloudbox-smoke-test/1.0"}),
            timeout=timeout,
        )
    except HTTPError as error:
        raise SmokeTestError(f"{url} returned HTTP {error.code}") from error
    except URLError as error:
        raise SmokeTestError(f"Cannot reach {url}: {error.reason}") from error
    if response.status >= 400:
        raise SmokeTestError(f"{url} returned HTTP {response.status}")
    return response


def run_smoke_test(base_url, timeout=10, allow_http=False):
    base_url = base_url.rstrip("/") + "/"
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SmokeTestError("URL must include an http:// or https:// hostname")
    require_https = not allow_http
    if require_https and parsed.scheme != "https":
        raise SmokeTestError("HTTPS is required; use --allow-http only for local/dev tests")

    tls_details = None
    if parsed.scheme == "https":
        tls_details = inspect_tls(parsed.hostname, parsed.port or 443, timeout)

    cookie_jar = http.cookiejar.CookieJar()
    opener = build_opener(
        HTTPSHandler(context=ssl.create_default_context()),
        HTTPCookieProcessor(cookie_jar),
    )
    login_response = _get(opener, urljoin(base_url, "login"), timeout)
    try:
        login_status = login_response.status
        final_scheme = urlparse(login_response.geturl()).scheme
        if require_https and final_scheme != "https":
            raise SmokeTestError("Request was redirected away from HTTPS")
        validate_security_headers(login_response.headers, require_https=require_https)
    finally:
        login_response.close()

    http_redirect = None
    if require_https:
        http_url = f"http://{parsed.hostname}/"
        redirect_response = _get(opener, http_url, timeout)
        try:
            redirected = urlparse(redirect_response.geturl())
            if redirected.scheme != "https" or redirected.hostname != parsed.hostname:
                raise SmokeTestError("Plain HTTP does not redirect to the HTTPS hostname")
            http_redirect = "ok"
        finally:
            redirect_response.close()

    csrf_response = _get(opener, urljoin(base_url, "api/v1/csrf-token"), timeout)
    try:
        csrf_status = csrf_response.status
        csrf_payload = json.loads(csrf_response.read().decode("utf-8"))
        csrf_token = csrf_payload["data"]["csrf_token"]
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SmokeTestError("CSRF endpoint returned an invalid payload") from error
    finally:
        csrf_response.close()
    if not isinstance(csrf_token, str) or len(csrf_token) < 20:
        raise SmokeTestError("CSRF endpoint returned an invalid token")
    validate_session_cookies(cookie_jar, require_https=require_https)

    return {
        "base_url": base_url,
        "login_status": login_status,
        "csrf_status": csrf_status,
        "https": parsed.scheme == "https",
        "http_redirect": http_redirect,
        "tls_protocol": tls_details[0] if tls_details else None,
        "certificate_expires_at": tls_details[1].isoformat() if tls_details else None,
        "security_headers": "ok",
        "secure_session_cookie": require_https,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="CloudBox base URL")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument(
        "--allow-http",
        action="store_true",
        help="Permit HTTP only for local/development smoke tests",
    )
    args = parser.parse_args()
    try:
        result = run_smoke_test(args.url, args.timeout, args.allow_http)
    except SmokeTestError as error:
        raise SystemExit(f"FAILED: {error}") from error
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
