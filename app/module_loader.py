import http.client
import ipaddress
import os
import socket
import ssl
import urllib.parse
from typing import Optional


ALLOWED_EXTENSIONS = {".pdf"}
ALLOWED_UPLOAD_MIME_TYPES = {"application/pdf", "application/octet-stream"}
ALLOWED_REMOTE_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}


def resolve_public_addresses(hostname: str, port: Optional[int] = None) -> tuple[str, ...]:
    addresses = {address_info[4][0] for address_info in socket.getaddrinfo(hostname, port)}
    public_addresses = []
    for address in addresses:
        if not ipaddress.ip_address(address).is_global:
            return ()
        public_addresses.append(address)
    return tuple(public_addresses)


def is_private_host(hostname: str) -> bool:
    try:
        return not resolve_public_addresses(hostname)
    except socket.gaierror:
        return True


def validate_remote_url(url: str):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None, "Only http/https URLs are allowed."
    if not parsed.hostname:
        return None, "URL must include a hostname."
    if parsed.username or parsed.password:
        return None, "URLs with credentials are not allowed."
    try:
        port = parsed.port
    except ValueError:
        return None, "URL contains an invalid port."
    if not resolve_public_addresses(parsed.hostname, port):
        return None, "Private or local network addresses are not allowed."
    return parsed.geturl(), None


def is_allowed_filename(filename: str) -> bool:
    return os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS


def is_allowed_mime_type(content_type: Optional[str]) -> bool:
    return not content_type or content_type.split(";")[0].strip().lower() in ALLOWED_UPLOAD_MIME_TYPES


def looks_like_pdf(path: str) -> bool:
    with open(path, "rb") as uploaded_file:
        return uploaded_file.read(5) == b"%PDF-"


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int):
        super().__init__(host, port=port, timeout=timeout)
        self._address = address

    def connect(self):
        self.sock = socket.create_connection((self._address, self.port), self.timeout)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, port: int, address: str, timeout: int):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self._address = address

    def connect(self):
        raw_socket = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


def open_pinned_response(url: str, timeout_seconds: int):
    parsed = urllib.parse.urlparse(url)
    if not parsed.hostname:
        raise ValueError("URL must include a hostname.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    addresses = resolve_public_addresses(parsed.hostname, port)
    if not addresses:
        raise ValueError("Private or local network addresses are not allowed.")

    target = urllib.parse.urlunparse(("", "", parsed.path or "/", "", parsed.query, ""))
    host_header = parsed.hostname if parsed.port is None else f"{parsed.hostname}:{parsed.port}"
    last_error = None
    for address in addresses:
        connection_class = PinnedHTTPSConnection if parsed.scheme == "https" else PinnedHTTPConnection
        connection = connection_class(parsed.hostname, port, address, timeout_seconds)
        try:
            connection.request("GET", target, headers={"Host": host_header, "User-Agent": "DungeonHarness/1.0"})
            return connection, connection.getresponse()
        except OSError as error:
            connection.close()
            last_error = error
    raise ValueError("Remote server could not be reached.") from last_error


def download_remote_file(validated_url: str, temp_path: str, timeout_seconds: int, max_bytes: int):
    current_url = validated_url
    for _ in range(4):
        connection = None
        try:
            connection, response = open_pinned_response(current_url, timeout_seconds)
            if response.status in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location:
                    raise ValueError("Remote server returned an invalid redirect.")
                current_url, validation_error = validate_remote_url(urllib.parse.urljoin(current_url, location))
                if validation_error:
                    raise ValueError(validation_error)
                continue
            if not 200 <= response.status < 300:
                raise ValueError("Remote server returned an unsuccessful status.")

            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type and content_type not in ALLOWED_REMOTE_CONTENT_TYPES:
                raise ValueError("Remote file content type is not allowed.")

            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise ValueError("Remote file exceeds configured size limit.")
                except ValueError as error:
                    if str(error) == "Remote file exceeds configured size limit.":
                        raise
                    raise ValueError("Remote server returned an invalid content length header.") from error

            bytes_read = 0
            with open(temp_path, "wb") as output_file:
                while chunk := response.read(64 * 1024):
                    bytes_read += len(chunk)
                    if bytes_read > max_bytes:
                        raise ValueError("Remote file exceeds configured size limit.")
                    output_file.write(chunk)
            return
        finally:
            if connection:
                connection.close()
    raise ValueError("Too many redirects.")
