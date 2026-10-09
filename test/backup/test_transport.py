import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

spec = importlib.util.spec_from_file_location("backup_yandex", Path(__file__).parents[2] / "backup/yandex.py")
y = importlib.util.module_from_spec(spec)
spec.loader.exec_module(y)
NAME = "clients-20261009T000000Z.dump.age"
DATA = b"age-encryption.org/v1\n" + b"synthetic encrypted stand-in"
HASH = hashlib.sha256(DATA).hexdigest()


class Response(io.BytesIO):
    status = 201


class FakeDisk(y.Disk):
    def __init__(self):
        super().__init__("not-a-real-token", "app:/clients-backups-test")
        self.data = DATA
        self.calls = []
        self.corrupt = False

    def api(self, suffix="", method="GET", payload=None, **query):
        self.calls.append((suffix, method, payload, query))
        if suffix in ("/upload", "/download"):
            return {"href": "https://uploader.disk.yandex.net/test"}
        if query.get("path") == self.folder:
            return {"type": "dir"}
        return {"type": "file", "size": len(self.data)}

    def request(self, url, method="GET", data=None, authenticated=True):
        if authenticated:
            raise AssertionError("OAuth must not go to the storage URL")
        y.storage_url(url)
        if method == "PUT":
            self.data = data.read()
            return Response()
        return Response(b"wrong" if self.corrupt else self.data)


class TransferTests(unittest.TestCase):
    def test_storage_hosts(self):
        for url in ("https://uploader1.disk.yandex.net/upload", "https://a.storage.yandex.net/x",
                    "https://downloader.disk.yandex.ru/disk/test"):
            self.assertEqual(y.storage_url(url), url)

    def test_reject_unsafe_hosts(self):
        for url in ("http://a.disk.yandex.net/x", "https://a.disk.yandex.net.evil/x",
                    "https://evil/x", "https://user@a.disk.yandex.net/x",
                    "https://a.disk.yandex.net:8443/x", "https://a.disk.yandex.net/x#secret",
                    "https://downloader.disk.yandex.ru.evil/x", "https://evil.disk.yandex.ru/x"):
            with self.subTest(url=url), self.assertRaises(y.BackupError):
                y.storage_url(url)

    def test_folder_allowlist(self):
        for folder in ("disk:/", "app:/existing-backups", "app:/clients-backups/../other"):
            with self.assertRaises(y.BackupError):
                y.Disk("fake", folder)

    def test_token_newline(self):
        with self.assertRaises(y.BackupError):
            y.Disk("fake\nheader", "app:/clients-backups")

    def test_plaintext_and_symlink_refused(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / NAME
            p.write_bytes(b"PGDMP plaintext")
            with self.assertRaises(y.BackupError):
                y.archive_check(p)
            p.write_bytes(DATA)
            link = Path(work) / "clients-20261008T000000Z.dump.age"
            link.symlink_to(p)
            with self.assertRaises(y.BackupError):
                y.archive_check(link)

    def test_upload_readback_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / NAME
            p.write_bytes(DATA)
            disk = FakeDisk()
            self.assertEqual(disk.upload(p), HASH)
            self.assertEqual(disk.calls[1][3]["overwrite"], "false")
            self.assertEqual(disk.calls[-1][1], "PATCH")
            self.assertEqual(disk.calls[-1][2]["custom_properties"]["client_backup_sha256"], HASH)

    def test_corruption_no_verified_marker_no_partial(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / NAME
            p.write_bytes(DATA)
            disk = FakeDisk()
            disk.corrupt = True
            with self.assertRaises(y.BackupError):
                disk.upload(p)
            self.assertFalse(any(c[1] == "PATCH" for c in disk.calls))
            destination = Path(work) / "download.age"
            with self.assertRaises(y.BackupError):
                disk.download(NAME, destination, HASH)
            self.assertFalse(destination.exists())
            self.assertFalse(list(Path(work).glob(".clients-download-*")))

    def test_download_exact_bytes_and_permissions(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / NAME
            FakeDisk().download(NAME, p, HASH)
            self.assertEqual(p.read_bytes(), DATA)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(y.BackupError):
                FakeDisk().download(NAME, p, HASH)

    def test_wrong_hash_refused(self):
        with tempfile.TemporaryDirectory() as work:
            with self.assertRaises(y.BackupError):
                FakeDisk().download(NAME, Path(work) / NAME, "0" * 64)

    def test_auth_only_api_and_storage_content_length(self):
        disk = y.Disk("fake", "app:/clients-backups")
        with patch.object(disk.opener, "open", return_value=Response()) as opened:
            disk.request(y.API + "?path=test")
            self.assertEqual(opened.call_args[0][0].headers["Authorization"], "OAuth fake")
            with tempfile.TemporaryFile() as f:
                f.write(DATA)
                f.seek(0)
                disk.request("https://a.disk.yandex.net/x", "PUT", f, False)
            headers = opened.call_args[0][0].headers
            self.assertNotIn("Authorization", headers)
            self.assertEqual(headers["Content-length"], str(len(DATA)))
        with self.assertRaises(y.BackupError):
            disk.request("https://evil.invalid")

    def test_redirect_blocked(self):
        with self.assertRaises(y.BackupError):
            y.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://evil")

    def test_download_redirect_only_validated_get_without_headers(self):
        req = y.urllib.request.Request("https://downloader.disk.yandex.ru/disk/test", method="GET")
        handler = y.DownloadRedirect()
        result = handler.redirect_request(req, None, 302, "redirect", {}, "https://s1.storage.yandex.net/test")
        self.assertEqual(result.headers, {})
        self.assertEqual(result._client_redirect_count, 1)
        for destination in ("http://s1.storage.yandex.net/test", "https://evil.invalid/test",
                            "https://s1.storage.yandex.net.evil/test"):
            with self.assertRaises(y.BackupError):
                handler.redirect_request(req, None, 302, "redirect", {}, destination)
        req.add_header("Authorization", "never-forward")
        with self.assertRaises(y.BackupError):
            handler.redirect_request(req, None, 302, "redirect", {}, "https://s1.storage.yandex.net/test")

    def test_download_redirect_hop_limit_and_upload_refused(self):
        handler = y.DownloadRedirect()
        req = y.urllib.request.Request("https://s1.storage.yandex.net/test", method="GET")
        req._client_redirect_count = 3
        with self.assertRaises(y.BackupError):
            handler.redirect_request(req, None, 302, "redirect", {}, "https://s1.storage.yandex.net/test")
        req = y.urllib.request.Request("https://s1.storage.yandex.net/test", method="PUT")
        with self.assertRaises(y.BackupError):
            handler.redirect_request(req, None, 302, "redirect", {}, "https://s1.storage.yandex.net/test")

    def test_public_folder_refused(self):
        disk = FakeDisk()
        with patch.object(disk, "api", return_value={"type": "dir", "public_url": "public"}):
            with self.assertRaises(y.BackupError):
                disk.ensure_folder()

    def test_retention_exact_boundary_latest_and_unknown_preserved(self):
        folder = "app:/clients-backups"
        def item(stamp, verified=True):
            name = "clients-" + stamp + ".dump.age"
            return {"name": name, "path": folder + "/" + name, "type": "file",
                    "custom_properties": {"client_backup_sha256": HASH} if verified else {}}
        now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
        items = [item("20260908T000000Z"), item("20260909T000000Z"),
                 item("20261009T000000Z"), item("20260101T000000Z", False)]
        self.assertEqual(y.retention_candidates(items, folder, now), [items[0]["name"]])
        self.assertEqual(y.retention_candidates(items[:1], folder, now), [])

    def test_folder_missing_is_created(self):
        disk = FakeDisk()
        missing = urllib.error.HTTPError(y.API, 404, "missing", {}, None)
        with patch.object(disk, "api", side_effect=[missing, {}, {"type": "dir"}]) as api:
            disk.ensure_folder()
            self.assertEqual(api.call_args_list[1].kwargs["method"], "PUT")

    def test_folder_permission_failure_not_ignored(self):
        disk = FakeDisk()
        forbidden = urllib.error.HTTPError(y.API, 403, "forbidden", {}, None)
        with patch.object(disk, "api", side_effect=forbidden), self.assertRaises(urllib.error.HTTPError):
            disk.ensure_folder()

    def test_freshness_missing_stale_future_and_valid(self):
        disk = FakeDisk()
        now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
        def item(stamp):
            name = "clients-" + stamp + ".dump.age"
            return {"name": name, "type": "file", "path": disk.folder + "/" + name,
                    "custom_properties": {"client_backup_sha256": HASH}}
        for items in ([], [item("20261007T000000Z")], [item("20261010T000000Z")]):
            with patch.object(disk, "list_items", return_value=items), self.assertRaises(y.BackupError):
                disk.check_freshness(now)
        with patch.object(disk, "list_items", return_value=[item("20261008T000000Z")]):
            disk.check_freshness(now)

    def test_exact_36_hour_boundary_unverified_and_public_ignored(self):
        disk = FakeDisk()
        now = dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc)
        name = 'clients-20261008T000000Z.dump.age'
        item = {'name': name, 'type': 'file', 'path': disk.folder + '/' + name,
                'custom_properties': {'client_backup_sha256': HASH}}
        with patch.object(disk, 'list_items', return_value=[item]):
            disk.check_freshness(now)
            with self.assertRaises(y.BackupError):
                disk.check_freshness(now + dt.timedelta(seconds=1))
        for bad in (dict(item, custom_properties={}), dict(item, public_url='https://public.invalid')):
            with patch.object(disk, 'list_items', return_value=[bad]), self.assertRaises(y.BackupError):
                disk.check_freshness(now)

    def test_monitor_directory_must_be_private(self):
        disk = FakeDisk()
        with patch.object(disk, 'api', return_value={'type': 'dir', 'public_key': 'public', '_embedded': {'items': []}}), self.assertRaises(y.BackupError):
            disk.list_items()

    def test_canonical_app_directory_normalized_only_for_exact_children(self):
        disk = FakeDisk()
        root = 'disk:/Applications/TestApp/clients-backups-test'
        good = {'name': NAME, 'path': root+'/'+NAME, 'type': 'file', 'custom_properties': {'client_backup_sha256': HASH}}
        unrelated = dict(good, path='disk:/other/'+NAME)
        with patch.object(disk, 'api', return_value={'type': 'dir', 'path': root, '_embedded': {'items': [good, unrelated]}}):
            items = disk.list_items()
            self.assertEqual(items[0]['path'], disk.folder+'/'+NAME)
            self.assertEqual(items[1]['path'], unrelated['path'])
            disk.check_freshness(dt.datetime(2026,10,9,tzinfo=dt.timezone.utc))
        for bad in ('disk:/other-folder', 'disk:/Applications/../clients-backups-test', ''):
            with patch.object(disk, 'api', return_value={'type': 'dir', 'path': bad, '_embedded': {'items': []}}), self.assertRaises(y.BackupError):
                disk.list_items()


if __name__ == "__main__":
    unittest.main()
