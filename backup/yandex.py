"""Private encrypted-file transfer. No plaintext, redirects or secret diagnostics."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

API = "https://cloud-api.yandex.net/v1/disk/resources"
FOLDERS = {"app:/clients-backups", "app:/clients-backups-test"}
NAME = re.compile(r"clients-(\d{8}T\d{6}Z)\.dump\.age")
MAX_BYTES = 2 * 1024**3


class BackupError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BackupError("HTTP_REDIRECT_REFUSED")


class DownloadRedirect(urllib.request.HTTPRedirectHandler):
    """Only unauthenticated GET, HTTPS, reviewed storage hosts, at most 3 hops."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.get_method() != "GET" or any(
                key.lower() in ("authorization", "proxy-authorization", "cookie")
                for key in req.headers):
            raise BackupError("AUTHENTICATED_REDIRECT_REFUSED")
        storage_url(newurl)
        count = getattr(req, "_client_redirect_count", 0) + 1
        if count > 3:
            raise BackupError("TOO_MANY_DOWNLOAD_REDIRECTS")
        # Copy no source headers; especially never forward credentials/cookies.
        redirected = urllib.request.Request(newurl, method="GET")
        redirected._client_redirect_count = count
        return redirected


def storage_url(url):
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ""
    if (p.scheme != "https" or p.username or p.password or p.fragment
            or p.port not in (None, 443) or "\\" in url
            or not (host.endswith(".disk.yandex.net")
                    or host.endswith(".storage.yandex.net")
                    or host == "downloader.disk.yandex.ru")):
        raise BackupError("UNTRUSTED_STORAGE_URL")
    return url


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def archive_check(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or not NAME.fullmatch(p.name):
        raise BackupError("INVALID_ARCHIVE")
    if not 0 < p.stat().st_size <= MAX_BYTES:
        raise BackupError("INVALID_ARCHIVE_SIZE")
    with p.open("rb") as f:
        if f.read(22) != b"age-encryption.org/v1\n":
            raise BackupError("AGE_HEADER_REQUIRED")
    return p


class Disk:
    def __init__(self, token, folder):
        if not token or "\n" in token or "\r" in token:
            raise BackupError("TOKEN_REQUIRED")
        if folder not in FOLDERS:
            raise BackupError("FOLDER_NOT_ALLOWED")
        self.token, self.folder = token, folder
        self.opener = urllib.request.build_opener(NoRedirect())
        self.download_opener = urllib.request.build_opener(DownloadRedirect())

    def request(self, url, method="GET", data=None, authenticated=True):
        headers = {"Content-Type": "application/json"}
        if authenticated:
            if not url.startswith(API):
                raise BackupError("AUTH_DESTINATION_REFUSED")
            headers["Authorization"] = "OAuth " + self.token
        else:
            storage_url(url)
            headers = {}
            if hasattr(data, "fileno"):
                headers["Content-Length"] = str(os.fstat(data.fileno()).st_size)
        opener = self.download_opener if not authenticated and method == "GET" else self.opener
        return opener.open(urllib.request.Request(
            url, data=data, method=method, headers=headers), timeout=60)

    def api(self, suffix="", method="GET", payload=None, **query):
        url = API + suffix + "?" + urllib.parse.urlencode(query)
        data = json.dumps(payload).encode() if payload is not None else None
        with self.request(url, method, data) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise BackupError("API_RESPONSE_TOO_LARGE")
            return json.loads(raw) if raw else {}

    def remote(self, name):
        if not NAME.fullmatch(name):
            raise BackupError("INVALID_ARCHIVE_NAME")
        return self.folder + "/" + name

    def ensure_folder(self):
        try:
            meta = self.api(path=self.folder)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            self.api(method="PUT", path=self.folder)
            meta = self.api(path=self.folder)
        if meta.get("type") != "dir" or meta.get("public_url") or meta.get("public_key"):
            raise BackupError("PRIVATE_FOLDER_REQUIRED")

    def download(self, name, destination, expected_hash):
        if not re.fullmatch(r"[a-f0-9]{64}", expected_hash):
            raise BackupError("EXPECTED_SHA256_REQUIRED")
        dest = Path(destination)
        if dest.exists() or dest.is_symlink():
            raise BackupError("EXISTING_DESTINATION_REFUSED")
        meta = self.api(path=self.remote(name))
        size = meta.get("size")
        if (meta.get("type") != "file" or meta.get("public_url") or meta.get("public_key")
                or not isinstance(size, int) or not 0 < size <= MAX_BYTES):
            raise BackupError("INVALID_REMOTE_ARCHIVE")
        href = storage_url(self.api("/download", path=self.remote(name))["href"])
        # Exclusive temporary file in same directory; no overwrite or symlink-following.
        fd, temp = tempfile.mkstemp(prefix=".clients-download-", dir=dest.parent)
        try:
            h, total = hashlib.sha256(), 0
            with os.fdopen(fd, "wb") as output, self.request(href, authenticated=False) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > size:
                        raise BackupError("DOWNLOAD_SIZE_MISMATCH")
                    h.update(chunk)
                    output.write(chunk)
            if total != size or h.hexdigest() != expected_hash:
                raise BackupError("DOWNLOAD_INTEGRITY_FAILED")
            # Check header separately: temp name intentionally differs from archive name.
            with open(temp, "rb") as f:
                if f.read(22) != b"age-encryption.org/v1\n":
                    raise BackupError("AGE_HEADER_REQUIRED")
            os.link(temp, dest)  # atomic, fails if another writer created dest
        finally:
            os.unlink(temp)

    def upload(self, path):
        p = archive_check(path)
        self.ensure_folder()
        sha = digest(p)
        href = storage_url(self.api("/upload", path=self.remote(p.name), overwrite="false")["href"])
        # Encrypted file stream; OAuth header is never sent to the storage host.
        with p.open("rb") as f, self.request(href, "PUT", f, authenticated=False) as response:
            if response.status not in (201, 202):
                raise BackupError("UPLOAD_STATUS_INVALID")
        # Read-back is required even if provider doesn't return a digest.
        with tempfile.TemporaryDirectory(prefix="clients-readback-") as work:
            self.download(p.name, Path(work) / p.name, sha)
        self.api(method="PATCH", path=self.remote(p.name),
                 payload={"custom_properties": {"client_backup_sha256": sha}})
        return sha

    def list_items(self):
        items, offset = [], 0
        directory_path = None
        while True:
            result = self.api(path=self.folder, limit=100, offset=offset,
                              fields='type,path,public_url,public_key,_embedded.items.name,_embedded.items.path,_embedded.items.type,_embedded.items.size,_embedded.items.public_url,_embedded.items.public_key,_embedded.items.custom_properties')
            if result.get('type') != 'dir' or result.get('public_url') or result.get('public_key'):
                raise BackupError('PRIVATE_DIRECTORY_LISTING_REQUIRED')
            # Disk returns canonical disk:/ paths for a requested app:/ folder.
            # Trust only this directory's own private API response, then require
            # an EXACT immediate-child path before normalizing to the alias.
            canonical = result.get('path', '')
            if (not isinstance(canonical, str) or '\\' in canonical
                    or '..' in canonical.split('/')
                    or not (canonical == self.folder or
                            canonical.startswith('disk:/') and canonical.endswith('/' + self.folder.split('/')[-1]))):
                raise BackupError('DIRECTORY_PATH_UNCONFIRMED')
            if directory_path is not None and canonical != directory_path:
                raise BackupError('DIRECTORY_IDENTITY_CHANGED')
            directory_path = canonical
            page = result.get("_embedded", {}).get("items")
            if not isinstance(page, list):
                raise BackupError("INVALID_DIRECTORY_LISTING")
            for item in page:
                if not isinstance(item, dict):
                    raise BackupError('INVALID_DIRECTORY_ITEM')
                name = item.get('name', '')
                normalized = dict(item)
                if (isinstance(name, str) and '/' not in name and '\\' not in name
                        and item.get('path') == canonical + '/' + name):
                    normalized['path'] = self.folder + '/' + name
                items.append(normalized)
            if len(page) < 100:
                break
            offset += 100
            if offset >= 10000:
                raise BackupError("DIRECTORY_TOO_LARGE")
        return items

    def retention_plan(self, now=None):
        now = now or dt.datetime.now(dt.timezone.utc)
        return retention_candidates(self.list_items(), self.folder, now)

    def check_freshness(self, now=None):
        now = now or dt.datetime.now(dt.timezone.utc)
        stamps = []
        for item in self.list_items():
            match = NAME.fullmatch(item.get("name", ""))
            sha = item.get("custom_properties", {}).get("client_backup_sha256", "")
            if (not match or item.get("type") != "file"
                    or item.get("path") != self.folder + "/" + item["name"]
                    or item.get('public_url') or item.get('public_key')
                    or not re.fullmatch(r"[a-f0-9]{64}", sha)):
                continue
            try:
                stamp = dt.datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
            except ValueError:
                continue
            stamps.append(stamp)
        if not stamps or not dt.timedelta(0) <= now - max(stamps) <= dt.timedelta(hours=36):
            raise BackupError("NO_RECENT_VERIFIED_BACKUP")


def retention_candidates(items, folder, now):
    """Plan only. Never DELETE: keep all recent files and latest verified file."""
    verified = []
    for item in items:
        match = NAME.fullmatch(item.get("name", ""))
        sha = item.get("custom_properties", {}).get("client_backup_sha256", "")
        if (not match or item.get("type") != "file"
                or item.get("path") != folder + "/" + item["name"]
                or not re.fullmatch(r"[a-f0-9]{64}", sha)):
            continue
        try:
            stamp = dt.datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        verified.append((stamp, item["name"]))
    verified.sort()
    cutoff = now - dt.timedelta(days=30)
    return [name for stamp, name in verified[:-1] if stamp < cutoff]


def main():
    os.umask(0o077)
    if os.environ.get("CLIENT_BACKUP_ENABLED") != "true":
        print("CLIENT_BACKUP_DISABLED")
        return
    if os.environ.get("CLIENT_BACKUP_REQUIRE_ENCRYPTION", "true") != "true":
        raise BackupError("ENCRYPTION_REQUIRED")
    disk = Disk(os.environ.get("YANDEX_DISK_TOKEN"),
                os.environ.get("CLIENT_BACKUP_YANDEX_PATH", "app:/clients-backups"))
    if len(sys.argv) == 3 and sys.argv[1] == "upload":
        sha = disk.upload(sys.argv[2])
        print("CLIENT_YANDEX_READBACK_OK sha256=" + sha)
    elif len(sys.argv) == 5 and sys.argv[1] == "download":
        disk.download(sys.argv[2], sys.argv[3], sys.argv[4])
        print("CLIENT_YANDEX_DOWNLOAD_OK")
    elif sys.argv[1:] == ["retention-plan"]:
        print("CLIENT_RETENTION_PLAN_ONLY candidates=" + str(len(disk.retention_plan())))
    else:
        raise BackupError("INVALID_COMMAND")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Provider error bodies/URLs may contain credentials. Never print exception text.
        print("CLIENT_YANDEX_OPERATION_FAILED", file=sys.stderr)
        sys.exit(1)
