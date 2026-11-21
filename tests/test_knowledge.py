"""Fix-guide tests: the right guide is found, guides are safe, and they're well formed."""

import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
import willy  # noqa: E402
import willy_knowledge as wk  # noqa: E402

KB = wk.Knowledge(os.path.join(ROOT, "knowledge"))

EXPECT = {
    "My wifi stopped working after an update": "wifi",
    "my disk is full and I don't know why": "disk-full",
    "the PC is really slow": "slow-pc-memory",
    "nginx won't start": "service-fails",
    "there's no sound": "no-sound",
    "I can't install updates, apt shows errors": "apt-dpkg-errors",
    "is my disk healthy?": "disk-errors-readonly",
    "booting takes ages": "slow-boot",
    "wifi connected but no website loads": "no-internet-dns",
    "screen resolution is wrong": "display-graphics",
    "my usb drive isn't detected": "usb-drive",
    "I get Read-only file system errors": "disk-errors-readonly",
    "bluetooth headphones won't connect": "bluetooth",
    "printer stopped printing": "printer",
    "my installed linux won't boot, it drops to emergency mode": "emergency-mode-fstab",
    "grub rescue> error after windows update": "grub-repair",
    "kernel panic after update": "kernel-panic-after-update",
    "I log in and it sends me back to the login screen": "login-loop",
    "certificate errors everywhere and the clock is wrong": "time-certificates",
    "user is not in the sudoers file": "sudo-broken",
    "E: dpkg was interrupted, you must manually run 'sudo dpkg --configure -a'": "apt-dpkg-errors",
    "nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)": "service-fails",
    "EXT4-fs (nvme0n1p2): Remounting filesystem read-only": "disk-errors-readonly",
    "VFS: Unable to mount root fs on unknown-block(0,0)": "kernel-panic-after-update",
    "/boot is 100% full and the kernel update fails": "boot-partition-full",
    # Guides added on 21 Nov 2026
    "my CPU is at 100% and the fan is loud": "high-cpu",
    "programs keep getting killed, out of memory": "memory-oom-swap",
    "high iowait, the disk is the bottleneck": "disk-io-slow",
    "I deleted files but df still shows the disk full": "deleted-files-logrotate",
    "connection refused when I connect to my server on port 8080": "service-unreachable-ports",
    "how do I open port 443 in the firewall with ufw": "firewall",
    "how do I set a static IP address": "network-config",
    "I want to capture network traffic with tcpdump": "packet-capture",
    "Too many open files error in my app": "processes-limits",
    "umount says target is busy": "storage-mount-fsck",
    "how do I extend my LVM root volume": "lvm",
    "Permission denied when I save a file in my folder": "permissions",
    "SELinux is blocking my web server": "selinux",
    "where are the log files and how do I read them": "logs",
    "dnf update fails on fedora": "packages-dnf-rpm",
    "where do I start troubleshooting, I'm stuck": "debugging-method",
    "the server is slow, give me a quick performance triage checklist": "performance-triage",
    "connections time out, SYN packets get no answer": "network-deep-debugging",
    "which iptables rule is dropping my packets": "firewall-tracing",
    "the program crashed with a segmentation fault (core dumped)": "crashes-coredumps",
    "the program hangs, what is it doing? strace": "tracing-strace-bpf",
    "AppArmor DENIED messages, the app can't open files": "sandbox-apparmor-firejail",
    "the ipsec vpn tunnel is up but no traffic passes": "vpn-ipsec-wireguard",
    "modprobe: Key was rejected by service": "kernel-modules",
    "my website shows 502 Bad Gateway": "web-502-php-fpm",
}


class TestRetrieval(unittest.TestCase):
    def test_guides_loaded(self):
        self.assertGreaterEqual(len(KB), 45)

    def test_right_guide_first(self):
        for question, want in EXPECT.items():
            with self.subTest(question=question):
                hits = KB.search(question)
                self.assertTrue(hits, "no guide for %r" % question)
                self.assertEqual(hits[0][1].id, want)

    def test_small_talk_gets_no_guide(self):
        for q in ("hello how are you", "thanks, that worked!", "what can you do?", "who made you?", "ok", ""):
            self.assertEqual(KB.search(q), [], q)

    def test_augment_attaches_once(self):
        seen = set()
        text, titles = KB.augment("nginx won't start", seen)
        self.assertIn("[Willy fix guides", text)
        self.assertIn("--- Guide:", text)
        self.assertTrue(titles)
        again, titles2 = KB.augment("nginx still won't start", seen)
        self.assertEqual((again, titles2), ("", []))

    def test_guides_are_capped(self):
        text, _ = KB.augment("my disk is full", set())
        self.assertLess(len(text), 2 * (KB.max_chars + 300))

    def test_missing_folder_is_harmless(self):
        empty = wk.Knowledge("/nonexistent/willy/knowledge")
        self.assertEqual(len(empty), 0)
        self.assertEqual(empty.augment("wifi broken", set()), ("", []))


class TestGuideCommands(unittest.TestCase):
    def test_list_and_read(self):
        listing = willy.guides_list(KB)
        self.assertIn("offline fix guides", listing)
        self.assertIn("1.", listing)
        self.assertIn("Disk full", willy.guide_text(KB, "disk full"))
        self.assertIn("## Undo notes", willy.guide_text(KB, "1"))
        self.assertIn("No guide matches", willy.guide_text(KB, "zzzz qqqq"))
        self.assertIn("missing", willy.guides_list(wk.Knowledge("/nonexistent")))


class TestGuideContent(unittest.TestCase):
    def test_well_formed(self):
        for g in KB.guides:
            with self.subTest(guide=g.id):
                self.assertTrue(g.title and not g.title.startswith("#"))
                self.assertTrue(g.keywords.strip(), "no Keywords line")
                self.assertIn("## Undo notes", g.body)

    def test_no_guide_suggests_a_blocked_command(self):
        for g in KB.guides:
            for cmd in re.findall(r"`([^`\n]+)`", g.body):
                with self.subTest(guide=g.id, cmd=cmd):
                    self.assertNotEqual(willy.classify(cmd)[0], "blocked")

    def test_no_brand_names_in_guides(self):
        brands = re.compile(r"qwen|alibaba|mistral|ministral|llamafile|llama\.cpp|bartowski", re.I)
        for g in KB.guides:
            self.assertIsNone(brands.search(g.title + g.keywords + g.body), g.id)


if __name__ == "__main__":
    unittest.main()
