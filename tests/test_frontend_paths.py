"""Frontend path checks — guard against trailing-slash-fragile relative URLs.

Vercel serves a sub-directory page (e.g. `instructors/index.html` at the URL
`/instructors`) with no trailing slash and no redirect. A relative resource
path in such a page resolves against the site root (`/data.js`) instead of the
page's own directory, producing 404s. Local resource references in these pages
must therefore be root-absolute.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pages served at a non-root URL path. The root index.html is exempt — `/`
# always carries a trailing slash, so relative paths resolve correctly there.
SUBDIRECTORY_PAGES = [
    "instructors/index.html",
    "sim-lab/index.html",
]


def local_resource_refs(html: str) -> list[str]:
    """Return every <link href> / <script src> value pointing at a local file.

    External references (absolute http(s) URLs and protocol-relative `//`
    URLs) are excluded — only same-site resources must be root-absolute.
    """
    refs = re.findall(r'<(?:link|script)\b[^>]*?\b(?:href|src)="([^"]+)"', html)
    return [r for r in refs if not r.startswith(("http://", "https://", "//"))]


class TestSubdirectoryPagePaths(unittest.TestCase):
    def test_local_resource_paths_are_root_absolute(self):
        for page in SUBDIRECTORY_PAGES:
            with self.subTest(page=page):
                html = (REPO_ROOT / page).read_text(encoding="utf-8")
                local = local_resource_refs(html)
                self.assertTrue(
                    local, f"{page}: expected at least one local resource reference"
                )
                not_absolute = [r for r in local if not r.startswith("/")]
                self.assertEqual(
                    not_absolute,
                    [],
                    f"{page}: these local resource paths are not root-absolute and "
                    f"break when the page is served without a trailing slash: "
                    f"{not_absolute}",
                )


if __name__ == "__main__":
    unittest.main()
