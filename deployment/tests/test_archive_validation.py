#!/usr/bin/python3
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "deploy_voting.py"
SPEC = importlib.util.spec_from_file_location("deploy_voting", MODULE_PATH)
deploy_voting = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(deploy_voting)


SHA = "a" * 40
ROOT = f"example-voting-app-{SHA}"


class ArchiveValidationTests(unittest.TestCase):
    def make_archive(self, path, entries):
        with tarfile.open(path, "w:gz") as archive:
            for name, kind, content in entries:
                member = tarfile.TarInfo(name)
                if kind == "file":
                    payload = content.encode()
                    member.size = len(payload)
                    archive.addfile(member, io.BytesIO(payload))
                elif kind == "symlink":
                    member.type = tarfile.SYMTYPE
                    member.linkname = content
                    archive.addfile(member)

    def required_entries(self):
        return [
            (f"{ROOT}/helm/voting-app/Chart.yaml", "file", "apiVersion: v2\nname: voting-app\nversion: 1.0.0\n"),
            (f"{ROOT}/helm/voting-app/values.yaml", "file", "vote: {}\n"),
            (f"{ROOT}/result/tests/tests.py", "file", "print('ok')\n"),
            (f"{ROOT}/README.md", "file", "not selected\n"),
        ]

    def extract(self, entries):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        archive = base / "source.tar.gz"
        destination = base / "source"
        destination.mkdir()
        self.make_archive(archive, entries)
        return destination, deploy_voting.safe_extract_selected(archive, destination, SHA)

    def test_extracts_only_chart_and_e2e_test(self):
        destination, (chart, test) = self.extract(self.required_entries())
        self.assertTrue((chart / "Chart.yaml").is_file())
        self.assertTrue(test.is_file())
        self.assertFalse((destination / "README.md").exists())

    def test_rejects_traversal_even_outside_selected_paths(self):
        entries = self.required_entries() + [(f"{ROOT}/../escape", "file", "bad")]
        with self.assertRaises(deploy_voting.DeploymentError):
            self.extract(entries)

    def test_rejects_selected_symlink(self):
        entries = self.required_entries()
        entries[0] = (f"{ROOT}/helm/voting-app/Chart.yaml", "symlink", "/etc/passwd")
        with self.assertRaises(deploy_voting.DeploymentError):
            self.extract(entries)

    def test_rejects_duplicate_selected_path(self):
        entries = self.required_entries()
        entries.append(entries[0])
        with self.assertRaises(deploy_voting.DeploymentError):
            self.extract(entries)

    def test_rejects_member_size_over_limit(self):
        original_limit = deploy_voting.MAX_MEMBER_BYTES
        deploy_voting.MAX_MEMBER_BYTES = 1
        self.addCleanup(setattr, deploy_voting, "MAX_MEMBER_BYTES", original_limit)
        with self.assertRaises(deploy_voting.DeploymentError):
            self.extract(self.required_entries())

    def test_rejects_excessive_members_while_streaming(self):
        original_limit = deploy_voting.MAX_MEMBERS
        deploy_voting.MAX_MEMBERS = 3
        self.addCleanup(setattr, deploy_voting, "MAX_MEMBERS", original_limit)
        with self.assertRaises(deploy_voting.DeploymentError):
            self.extract(self.required_entries())


class MainGuardAndArgumentTests(unittest.TestCase):
    def github_main_response(self, sha):
        response = io.BytesIO(("{\"sha\": \"" + sha + "\"}").encode())
        response.status = 200
        response.headers = {}
        response.geturl = lambda: "https://api.github.com/repos/ecstasywonder/example-voting-app/commits/main"
        return response

    def test_rejects_stale_main_before_any_download(self):
        with patch.object(
            deploy_voting,
            "open_fixed_https",
            return_value=self.github_main_response("b" * 40),
        ):
            with self.assertRaises(deploy_voting.DeploymentError):
                deploy_voting.require_current_main(SHA)

    def test_accepts_current_main(self):
        with patch.object(
            deploy_voting,
            "open_fixed_https",
            return_value=self.github_main_response(SHA),
        ):
            deploy_voting.require_current_main(SHA)

    def test_main_rejects_malformed_interface(self):
        with patch.object(deploy_voting.sys, "argv", [
            "deploy-voting", "A" * 40, "sha256:" + "a" * 64,
            "sha256:" + "a" * 64, "sha256:" + "a" * 64,
        ]):
            self.assertEqual(deploy_voting.main(), 64)


if __name__ == "__main__":
    unittest.main()
