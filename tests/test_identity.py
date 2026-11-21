"""Identity tests: Willy's replies never name the model or company behind it."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import willy  # noqa: E402


class TestScrub(unittest.TestCase):
    def test_rewrites(self):
        cases = {
            "I am Qwen, created by Alibaba Cloud.": "I am Willy, created by Wilson Sumanang.",
            "I'm Qwen2.5-7B-Instruct from Alibaba Group": "I'm Willy from Wilson Sumanang",
            "Tongyi Qianwen here": "Willy here",
            "QWEN and alibaba": "Willy and Wilson Sumanang",
            "I am Ministral, a model made by Mistral AI.": "I am Willy, a model made by Wilson Sumanang.",
            "I'm Ministral-3-8B-Instruct-2512 from mistral.ai": "I'm Willy from Wilson Sumanang",
            "Mistral here, built by MistralAI": "Willy here, built by Wilson Sumanang",
        }
        for raw, want in cases.items():
            self.assertEqual(willy.scrub_identity(raw), want)

    def test_normal_text_untouched(self):
        text = "Your disk /dev/sda is fine; run `df -h` to check space."
        self.assertEqual(willy.scrub_identity(text), text)

    def test_system_prompt_sets_identity(self):
        self.assertIn("Wilson Sumanang", willy.SYSTEM_PROMPT)
        self.assertIn("can't share details", willy.SYSTEM_PROMPT)


class TestStreamingScrub(unittest.TestCase):
    """A name split across streamed chunks must still be scrubbed before printing."""

    def test_split_name(self):
        import io
        import json
        from unittest import mock

        chunks = ["I am Q", "w", "en, created by Ali", "baba Cl", "oud. How can I help?"]
        lines = [("data: " + json.dumps({"choices": [{"delta": {"content": p}}]}) + "\n").encode()
                 for p in chunks] + [b"data: [DONE]\n"]

        class Resp(object):
            def __iter__(self):
                return iter(lines)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        out = io.StringIO()
        with mock.patch("urllib.request.urlopen", return_value=Resp()), mock.patch("sys.stdout", out):
            reply = willy.ask_model("http://x/v1/chat/completions", [], 10, 0.1)
        self.assertNotIn("Qwen", out.getvalue())
        self.assertNotIn("Alibaba", out.getvalue())
        self.assertEqual(reply, "I am Willy, created by Wilson Sumanang. How can I help?")


if __name__ == "__main__":
    unittest.main()
