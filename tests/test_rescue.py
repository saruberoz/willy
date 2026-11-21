"""Rescue helper tests: live-session detection, disk discovery and mount options."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import willy_rescue as r  # noqa: E402

LSBLK = {
    "blockdevices": [
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 512110190592, "fstype": None,
         "mountpoint": None, "type": "disk", "label": None, "uuid": None, "tran": "nvme", "rm": False,
         "children": [
             {"name": "nvme0n1p1", "path": "/dev/nvme0n1p1", "size": 536870912, "fstype": "vfat",
              "mountpoint": None, "type": "part", "label": None, "uuid": "AAAA-1111", "tran": None, "rm": False},
             {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "size": 400000000000, "fstype": "ext4",
              "mountpoint": None, "type": "part", "label": None, "uuid": "u-root", "tran": None, "rm": False},
             {"name": "nvme0n1p3", "path": "/dev/nvme0n1p3", "size": 100000000000, "fstype": "crypto_LUKS",
              "mountpoint": None, "type": "part", "label": None, "uuid": "u-luks", "tran": None, "rm": False},
         ]},
        {"name": "sda", "path": "/dev/sda", "size": 256000000000, "fstype": None, "mountpoint": None,
         "type": "disk", "label": None, "uuid": None, "tran": "usb", "rm": True,
         "children": [
             {"name": "sda1", "path": "/dev/sda1", "size": 255000000000, "fstype": "exfat",
              "mountpoint": "/media/ubuntu/Ventoy", "type": "part", "label": "Ventoy", "uuid": "v",
              "tran": None, "rm": True},
             {"name": "sda2", "path": "/dev/sda2", "size": 33554432, "fstype": "vfat", "mountpoint": None,
              "type": "part", "label": "VTOYEFI", "uuid": "e", "tran": None, "rm": True},
         ]},
        {"name": "loop0", "path": "/dev/loop0", "size": 3000000000, "fstype": "squashfs",
         "mountpoint": "/rofs", "type": "loop", "label": None, "uuid": None, "tran": None, "rm": False},
        {"name": "sdb", "path": "/dev/sdb", "size": 1000000000000, "fstype": None, "mountpoint": None,
         "type": "disk", "label": None, "uuid": None, "tran": "sata", "rm": False,
         "children": [
             {"name": "sdb1", "path": "/dev/sdb1", "size": 1000000000000, "fstype": "LVM2_member",
              "mountpoint": None, "type": "part", "label": None, "uuid": "lvm", "tran": None, "rm": False},
         ]},
    ]
}


class TestDetect(unittest.TestCase):
    def test_live_cmdlines(self):
        no = lambda p: False  # noqa: E731
        self.assertTrue(r.is_live_session("BOOT_IMAGE=/casper/vmlinuz boot=casper quiet", no))
        self.assertTrue(r.is_live_session("boot=live components", no))
        self.assertTrue(r.is_live_session("root=live:CDLABEL=Fedora rd.live.image", no))
        self.assertFalse(r.is_live_session("BOOT_IMAGE=/vmlinuz root=UUID=x ro quiet", no))
        self.assertTrue(r.is_live_session("root=UUID=x", lambda p: p == "/rofs"))


class TestDisks(unittest.TestCase):
    def setUp(self):
        self.devices = r.parse_lsblk(json.dumps(LSBLK))

    def test_flatten_and_disk_links(self):
        paths = [d["path"] for d in self.devices]
        self.assertIn("/dev/nvme0n1p2", paths)
        p2 = next(d for d in self.devices if d["path"] == "/dev/nvme0n1p2")
        self.assertEqual(p2["disk"], "/dev/nvme0n1")
        self.assertEqual(p2["tran"], "nvme")

    def test_candidates_skip_stick_and_live_root(self):
        linux, locked, lvm = r.find_candidates(self.devices)
        self.assertEqual([d["path"] for d in linux], ["/dev/nvme0n1p2"])
        self.assertEqual([d["path"] for d in locked], ["/dev/nvme0n1p3"])
        self.assertEqual([d["path"] for d in lvm], ["/dev/sdb1"])

    def test_ventoy_disk_flagged(self):
        sda1 = next(d for d in self.devices if d["path"] == "/dev/sda1")
        self.assertTrue(sda1["ventoy_disk"])

    def test_unlocked_luks_not_listed_as_locked(self):
        data = json.loads(json.dumps(LSBLK))
        data["blockdevices"][0]["children"][2]["children"] = [
            {"name": "willy-crypt", "path": "/dev/mapper/willy-crypt", "size": 1, "fstype": "ext4",
             "mountpoint": None, "type": "crypt", "label": None, "uuid": "c", "tran": None, "rm": False}]
        linux, locked, _ = r.find_candidates(r.parse_lsblk(json.dumps(data)))
        self.assertEqual(locked, [])
        self.assertIn("/dev/mapper/willy-crypt", [d["path"] for d in linux])


class TestBlkidFallback(unittest.TestCase):
    def test_fills_missing_fstype(self):
        data = {"blockdevices": [{"name": "loop0", "path": "/dev/loop0", "size": 1, "fstype": None,
                                  "mountpoint": None, "type": "loop", "label": None, "uuid": None,
                                  "tran": None, "rm": False}]}
        devices = r.parse_lsblk(json.dumps(data))
        self.assertEqual(r.find_candidates(devices)[0], [])
        blkid = r.parse_blkid_export("DEVNAME=/dev/loop0\nUUID=abc\nTYPE=ext4\n\nDEVNAME=/dev/sda1\n"
                                     "LABEL=Ventoy\nTYPE=exfat\n")
        r.fill_from_blkid(devices, blkid)
        self.assertEqual([d["path"] for d in r.find_candidates(devices)[0]], ["/dev/loop0"])


class TestHelpers(unittest.TestCase):
    def test_read_only_options_never_replay_journals(self):
        self.assertEqual(r.ro_mount_options("ext4"), "ro,noload")
        self.assertEqual(r.ro_mount_options("xfs"), "ro,norecovery")
        self.assertEqual(r.ro_mount_options("btrfs", "@"), "ro,rescue=nologreplay,subvol=@")
        self.assertTrue(r.ro_mount_options("f2fs").startswith("ro"))

    def test_os_release(self):
        info = r.parse_os_release('NAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04.1 LTS"\nID=ubuntu\n')
        self.assertEqual(info["PRETTY_NAME"], "Ubuntu 24.04.1 LTS")

    def test_fstab_boot_mounts(self):
        fstab = ("# comment\nUUID=root / ext4 defaults 0 1\nUUID=AAAA-1111 /boot/efi vfat umask=0077 0 1\n"
                 "UUID=boot /boot ext4 defaults 0 2\n/swapfile none swap sw 0 0\n")
        self.assertEqual(r.fstab_extra_mounts(fstab),
                         [("UUID=boot", "/boot"), ("UUID=AAAA-1111", "/boot/efi")])

    def test_human_size(self):
        self.assertEqual(r.human_size(512110190592), "476.9 GB")


if __name__ == "__main__":
    unittest.main()
