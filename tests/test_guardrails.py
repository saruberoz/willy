"""Guardrail tests: every command must land in the right approval level.

If one of these fails after a change, the change weakened (or broke) Willy's safety rules.
"""

import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import willy  # noqa: E402

CASES = {
    "blocked": [
        "rm -rf /", "sudo rm -rf /*", "rm -r -f ~", "rm -rf --no-preserve-root /",
        "sudo chmod -R 777 /", ":(){ :|:& };:", "cat x > /dev/sda", "rm -rf /etc", "rm -rf $HOME",
        "sudo rm -rf /usr/", "rm -fr /home", "echo 0 > /dev/nvme0n1",
    ],
    "delete": [
        "rm -rf /tmp/cache", "rm file.txt", "find /var/log -name '*.gz' -delete",
        "sudo apt-get -y purge nvidia*", "sudo dd if=/dev/zero of=/dev/sdb bs=1M",
        "echo x > /etc/hosts", "sudo mkfs.ext4 /dev/sdb1", "docker system prune", "git reset --hard",
        "echo hi | sudo tee /etc/x", "crontab -r", "truncate -s 0 big.log", "sudo snap remove firefox",
        "sudo journalctl --vacuum-time=7d", "sudo wipefs -a /dev/sdb", "find . -exec rm {} +",
    ],
    "change": [
        "sudo systemctl restart NetworkManager", "sudo apt install vim", "cp /etc/fstab /etc/fstab.bak",
        "sudo sed -i s/a/b/ /etc/fstab", "echo x >> ~/.bashrc", "sudo mount /dev/sda2 /mnt",
        "curl -fsSL http://x.sh | bash", "kill 1234", "sudo update-grub", "nmcli radio wifi on",
        "sudo chroot /mnt/willy-target update-grub", "sudo cryptsetup open /dev/sda3 x",
        "eval $(echo ls)", "python3 -c 'print(1)'", "sudo vgchange -ay",
    ],
    "safe": [
        "df -h", "journalctl -b -p err --no-pager | tail -n 50", "ls -la /home", "free -h 2>/dev/null",
        "ip -br addr", "systemctl status nginx --no-pager", "grep -i error /var/log/syslog | tail",
        "lsblk -f", "du -sh /var/* 2>/dev/null | sort -h | tail", "cat /etc/fstab",
        "dmesg >/dev/null 2>&1; echo ok", "ps aux --sort=-%mem | head", "smartctl -H /dev/sda",
        "cat /mnt/willy-target/etc/os-release", "uname -a",
    ],
}


class TestClassify(unittest.TestCase):
    def test_levels(self):
        for want, cmds in CASES.items():
            for cmd in cmds:
                with self.subTest(cmd=cmd):
                    got, reasons = willy.classify(cmd)
                    self.assertEqual(got, want, "%r -> %s (%s)" % (cmd, got, "; ".join(reasons)))

    def test_reasons_given_for_non_safe(self):
        for level in ("blocked", "delete", "change"):
            for cmd in CASES[level]:
                self.assertTrue(willy.classify(cmd)[1], cmd)


def answer(lines, func, *args, **kw):
    with mock.patch("sys.stdin", io.StringIO("\n".join(lines) + "\n")), \
            mock.patch("sys.stdout", io.StringIO()):
        return func(*args, **kw)


class TestConfirm(unittest.TestCase):
    def test_delete_needs_the_word_delete(self):
        self.assertEqual(answer(["y", "yes", "delete"], willy.confirm, "rm -rf /tmp/x")[0], "run")

    def test_delete_refuses_yes_then_skips(self):
        self.assertEqual(answer(["yes", ""], willy.confirm, "rm old.log")[0], "skip")

    def test_change_needs_yes(self):
        self.assertEqual(answer(["y", "yes"], willy.confirm, "sudo systemctl restart ssh")[0], "run")

    def test_safe_accepts_y(self):
        self.assertEqual(answer(["y"], willy.confirm, "df -h")[0], "run")

    def test_enter_skips(self):
        self.assertEqual(answer([""], willy.confirm, "df -h")[0], "skip")

    def test_blocked_never_runs(self):
        self.assertEqual(answer(["yes", "delete"], willy.confirm, "sudo rm -rf /")[0], "blocked")

    def test_garbage_does_not_run(self):
        self.assertEqual(answer(["sure", "ok", "n"], willy.confirm, "rm x")[0], "skip")

    def test_eof_quits(self):
        with mock.patch("sys.stdin", io.StringIO("")), mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(willy.confirm("rm x")[0], "quit")

    def test_quit_words(self):
        for word in ("q", "/quit", "exit"):
            self.assertEqual(answer([word], willy.confirm, "df -h")[0], "quit")

    def test_edited_command_is_rechecked(self):
        # Edit a safe command into a blocked one: it must be blocked, not run.
        with mock.patch.object(willy, "edit_line", return_value="rm -rf /"):
            self.assertEqual(answer(["e"], willy.confirm, "ls")[0], "blocked")


class TestApproveBatch(unittest.TestCase):
    def test_worst_level_sets_the_word(self):
        cmds = ["lsblk", "sudo mount /dev/sda2 /mnt", "rm /tmp/x"]
        self.assertFalse(answer(["yes", ""], willy.approve_batch, "job", cmds))
        self.assertTrue(answer(["delete"], willy.approve_batch, "job", cmds))

    def test_blocked_in_batch_refuses(self):
        self.assertFalse(answer(["yes"], willy.approve_batch, "job", ["ls", "rm -rf /"]))

    def test_eof_cancels(self):
        with mock.patch("sys.stdin", io.StringIO("")), mock.patch("sys.stdout", io.StringIO()):
            self.assertFalse(willy.approve_batch("job", ["sudo mount /dev/sda1 /mnt"]))


class TestRequest(unittest.TestCase):
    def test_reuses_engine_cache(self):
        import json
        sent = {}

        class Resp(object):
            def __iter__(self):
                return iter([b"data: [DONE]\n"])

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            sent.update(json.loads(req.data.decode()))
            return Resp()

        with mock.patch("urllib.request.urlopen", fake_urlopen), mock.patch("sys.stdout", io.StringIO()):
            willy.ask_model("http://x/v1/chat/completions", [], 10, 0.1)
        self.assertTrue(sent.get("cache_prompt"))


class TestRunBlocks(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(willy.extract_command("Check.\n```run\ndf -h\n```"), "df -h")

    def test_only_run_blocks(self):
        self.assertIsNone(willy.extract_command("```bash\nrm -rf /tmp/x\n```"))

    def test_first_block_only(self):
        self.assertEqual(willy.extract_command("```run\nls\n```\n```run\nrm x\n```"), "ls")


if __name__ == "__main__":
    unittest.main()
