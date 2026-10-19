import unittest

from scripts.sync import wrap_viewer


class WrapViewerTests(unittest.TestCase):
    def test_wrap_viewer_preserves_title_and_adds_home_link_for_metadata_head(self):
        viewer = (
            '<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Cloth-Feed Gripper Review</title>\n'
            '<div id="rail"><div class="rail-top"><a class="brand">Gripper</a></div></div>\n'
            '<script>window.viewerReady = true;</script>'
        ).encode("utf-8")

        wrapped = wrap_viewer(viewer, "https://example.test")

        self.assertTrue(wrapped.startswith(b"<!doctype html>"))
        self.assertEqual(wrapped.count(b'<meta charset="utf-8">'), 1)
        self.assertEqual(wrapped.count(b'<meta name="viewport"'), 1)
        self.assertIn(b"<title>Cloth-Feed Gripper Review</title>", wrapped)
        self.assertIn(b'<div id="rail"><div class="rail-top">', wrapped)
        self.assertIn(b'a.href = "/";', wrapped)
        self.assertIn(b'a.textContent = "Home";', wrapped)
        self.assertIn(b'a.setAttribute("aria-label", "Project home page");', wrapped)
        self.assertTrue(wrapped.endswith(b"</script>\n</html>\n"))

    def test_wrap_viewer_rejects_an_unknown_start_structure_loudly(self):
        with self.assertRaisesRegex(SystemExit, "structure"):
            wrap_viewer(b"<main>unknown viewer layout</main>", "https://example.test")


if __name__ == "__main__":
    unittest.main()
