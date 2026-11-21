"""Undo tests: planning what a command changes, and a real backup/restore round trip."""

import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import willy_undo as u  # noqa: E402


def read(path):
    with open(path) as fh:
        return fh.read()


def plan(cmd, existing=(), dirs=(), cwd="/home/u"):
    ex = set(existing) | set(dirs)
    return u.plan_command(cmd, cwd, exists=lambda p: p in ex, isdir=lambda p: p in dirs)


class TestPlan(unittest.TestCase):
    def test_sed_in_place(self):
        p = plan("sudo sed -i 's/a/b/' /etc/fstab", existing=["/etc/fstab"])
        self.assertEqual(p.files, ["/etc/fstab"])

    def test_sed_with_e(self):
        p = plan("sed -i -e 's/a/b/' -e 's/c/d/' a.conf", existing=["/home/u/a.conf"])
        self.assertEqual(p.files, ["/home/u/a.conf"])

    def test_redirect_overwrite_and_new(self):
        self.assertEqual(plan("echo x > /etc/hosts", existing=["/etc/hosts"]).files, ["/etc/hosts"])
        self.assertEqual(plan("echo x > new.txt").created, ["/home/u/new.txt"])

    def test_stderr_redirects_ignored(self):
        p = plan("rm old.log 2>/dev/null", existing=["/home/u/old.log"])
        self.assertEqual(p.files, ["/home/u/old.log"])
        self.assertEqual(p.created, [])

    def test_tee(self):
        p = plan("echo hi | sudo tee /etc/x", existing=["/etc/x"])
        self.assertEqual(p.files, ["/etc/x"])

    def test_cp_into_dir_and_over_file(self):
        p = plan("cp a.conf /etc/app/", existing=["/etc/app/a.conf"], dirs=["/etc/app"])
        self.assertEqual(p.files, ["/etc/app/a.conf"])
        p = plan("cp /etc/fstab /etc/fstab.bak")
        self.assertEqual(p.created, ["/etc/fstab.bak"])

    def test_mv_backs_up_source(self):
        p = plan("mv /etc/a.conf /etc/a.conf.off", existing=["/etc/a.conf"])
        self.assertEqual(p.files, ["/etc/a.conf"])
        self.assertEqual(p.created, ["/etc/a.conf.off"])

    def test_rm(self):
        p = plan("rm -rf /home/u/cache", existing=["/home/u/cache"])
        self.assertEqual(p.files, ["/home/u/cache"])

    def test_chmod_skips_mode(self):
        p = plan("chmod 600 /etc/secret", existing=["/etc/secret"])
        self.assertEqual(p.files, ["/etc/secret"])

    def test_chroot_paths(self):
        p = plan("sudo chroot /mnt/willy-target sed -i s/a/b/ /etc/fstab",
                 existing=["/mnt/willy-target/etc/fstab"])
        self.assertEqual(p.files, ["/mnt/willy-target/etc/fstab"])
        p = plan("sudo chroot /mnt/willy-target update-grub",
                 existing=["/mnt/willy-target/boot/grub/grub.cfg"])
        self.assertEqual(p.files, ["/mnt/willy-target/boot/grub/grub.cfg"])
        p = plan("sudo chroot /mnt/willy-target grub-install /dev/sda")
        self.assertIn("bootloader and initramfs changes", p.not_undoable)

    def test_systemctl_inverse(self):
        self.assertEqual(plan("sudo systemctl disable --now bluetooth").inverse,
                         ["sudo systemctl enable bluetooth"])
        self.assertEqual(plan("systemctl mask x.service").inverse, ["systemctl unmask x.service"])

    def test_not_undoable(self):
        p = plan("sudo apt-get install -y vim")
        self.assertFalse(p.undoable)
        self.assertTrue(any("NOT available" in line for line in p.describe()))
        self.assertIn("disk and partition changes", plan("sudo mkfs.ext4 /dev/sdb1").not_undoable)

    def test_mkdir_created(self):
        self.assertEqual(plan("mkdir -p /home/u/new").created, ["/home/u/new"])

    def test_chain(self):
        p = plan("cp /etc/a /etc/a.bak && sed -i s/x/y/ /etc/a", existing=["/etc/a"])
        self.assertEqual(p.files, ["/etc/a"])
        self.assertEqual(p.created, ["/etc/a.bak"])


class FakeUI(object):
    def __init__(self, approve=True):
        self.ok = approve
        self.said = []

    def approve(self, title, cmds):
        self.cmds = cmds
        return self.ok

    def run(self, cmd):
        import subprocess
        p = subprocess.run(["bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode()

    def say(self, text):
        self.said.append(text)


@unittest.skipUnless(hasattr(os, "getuid") and shutil.which("tar"), "needs Linux with tar")
class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.backups = os.path.join(self.tmp, "backups")
        self.conf = os.path.join(self.tmp, "app.conf")
        with open(self.conf, "w") as fh:
            fh.write("setting=original\n")
        os.chmod(self.conf, 0o640)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, cmd):
        import subprocess
        return subprocess.call(["bash", "-c", cmd], cwd=self.tmp)

    def test_edit_then_undo_restores_content_and_mode(self):
        ui = FakeUI()
        j = u.UndoJournal(self.backups, ui, session_id="t1")
        cmd = "sed -i s/original/broken/ %s && chmod 600 %s" % (self.conf, self.conf)
        entry, problem = j.prepare(cmd, u.plan_command(cmd, self.tmp))
        self.assertIsNone(problem)
        self._run(cmd)
        j.mark_ran(entry, 0)
        self.assertIn("broken", read(self.conf))
        note = j.undo_last()
        self.assertIn("reversed", note)
        self.assertEqual(read(self.conf), "setting=original\n")
        self.assertEqual(os.stat(self.conf).st_mode & 0o777, 0o640)
        self.assertTrue(os.path.exists(os.path.join(self.backups, "t1", "journal.json")))

    def test_created_file_removed_on_undo(self):
        ui = FakeUI()
        j = u.UndoJournal(self.backups, ui, session_id="t2")
        new = os.path.join(self.tmp, "new.txt")
        cmd = "echo hello > %s" % new
        entry, _ = j.prepare(cmd, u.plan_command(cmd, self.tmp))
        self._run(cmd)
        j.mark_ran(entry, 0)
        j.undo_last()
        self.assertFalse(os.path.exists(new))

    def test_deleted_folder_comes_back(self):
        folder = os.path.join(self.tmp, "keep")
        os.makedirs(os.path.join(folder, "sub"))
        with open(os.path.join(folder, "sub", "f.txt"), "w") as fh:
            fh.write("data")
        ui = FakeUI()
        j = u.UndoJournal(self.backups, ui, session_id="t3")
        cmd = "rm -rf %s" % folder
        entry, _ = j.prepare(cmd, u.plan_command(cmd, self.tmp))
        self._run(cmd)
        j.mark_ran(entry, 0)
        self.assertFalse(os.path.exists(folder))
        j.undo_last()
        self.assertEqual(read(os.path.join(folder, "sub", "f.txt")), "data")

    def test_declined_undo_keeps_entry(self):
        j = u.UndoJournal(self.backups, FakeUI(approve=False), session_id="t4")
        cmd = "sed -i s/a/b/ %s" % self.conf
        entry, _ = j.prepare(cmd, u.plan_command(cmd, self.tmp))
        j.mark_ran(entry, 0)
        self.assertIsNone(j.undo_last())
        self.assertEqual(len(j.pending()), 1)

    def test_nothing_to_undo(self):
        ui = FakeUI()
        j = u.UndoJournal(self.backups, ui, session_id="t5")
        with mock.patch("sys.stdout", io.StringIO()):
            self.assertIsNone(j.undo_last())
        self.assertIn("Nothing to undo", ui.said[-1])


if __name__ == "__main__":
    unittest.main()
