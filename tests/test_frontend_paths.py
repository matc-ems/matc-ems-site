"""Frontend path checks — guard against trailing-slash-fragile relative URLs.

Vercel serves `instructors/index.html` at the URL `/instructors` with no
trailing slash and no redirect. A relative resource path in that page then
resolves against the site root (`/data.js`) instead of `/instructors/data.js`,
producing 404s. Local resource references must therefore be root-absolute.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def local_resource_refs(html: str) -> list[str]:
    """Return every <link href> / <script src> value pointing at a local file.

    External references (absolute http(s) URLs and protocol-relative `//`
    URLs) are excluded — only same-site resources are subject to the
    root-absolute requirement.
    """
    refs = re.findall(r'<(?:link|script)\b[^>]*?\b(?:href|src)="([^"]+)"', html)
    return [r for r in refs if not r.startswith(("http://", "https://", "//"))]


class TestInstructorHubPaths(unittest.TestCase):
    def test_local_resource_paths_are_root_absolute(self):
        html = (REPO_ROOT / "instructors" / "index.html").read_text(encoding="utf-8")
        local = local_resource_refs(html)
        self.assertTrue(local, "expected at least one local resource reference")
        not_absolute = [r for r in local if not r.startswith("/")]
        self.assertEqual(
            not_absolute,
            [],
            f"these local resource paths are not root-absolute and break when "
            f"/instructors is served without a trailing slash: {not_absolute}",
        )


if __name__ == "__main__":
    unittest.main()
