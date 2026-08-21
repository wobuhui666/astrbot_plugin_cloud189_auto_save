from __future__ import annotations

import unittest

from core.templates import fmt_speed, pt_status_card


class TemplatesTest(unittest.TestCase):
    def test_format_speed(self):
        self.assertEqual(fmt_speed(0), "0.0 B/s")
        self.assertEqual(fmt_speed(1024), "1.0 KB/s")
        self.assertEqual(fmt_speed(3 * 1024 * 1024), "3.0 MB/s")

    def test_pt_status_contains_global_speeds_and_active_release(self):
        text = pt_status_card(
            {
                "transferStats": {
                    "downloadSpeed": 2 * 1024 * 1024,
                    "cloudUploadSpeed": 512 * 1024,
                },
                "releases": [
                    {
                        "id": 9,
                        "title": "Example S01E01",
                        "status": "downloading",
                        "downloader": {"progress": 42, "downloadSpeed": 1024},
                    }
                ],
            }
        )

        self.assertIn("PT 总下载速度:2.0 MB/s", text)
        self.assertIn("天翼总上传速度:512.0 KB/s", text)
        self.assertIn("#9 [downloading 42%]", text)


if __name__ == "__main__":
    unittest.main()
