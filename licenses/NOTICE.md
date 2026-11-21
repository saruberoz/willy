# Third-party notices

Willy (`willy.py`, `willy_rescue.py`, `willy_undo.py`, `start.sh`, `setup-usb.sh`) is
© 2026 Wilson Sumanang, released under the MIT License (see `LICENSE` in the repository).

A Willy USB stick also carries the following separate works, unmodified, under their own licences:

| On the stick | Component | Licence | Source |
|--------------|-----------|---------|--------|
| `willy/bin/willy-engine` | llamafile 0.9.3 (Mozilla Ocho), which includes llama.cpp (MIT) and Cosmopolitan Libc (ISC) | Apache License 2.0 (`engine-LICENSE.txt`, `Apache-2.0.txt`) | https://github.com/Mozilla-Ocho/llamafile |
| `willy/models/willy-large.gguf` | Qwen2.5-7B-Instruct by the Qwen team, Alibaba Cloud; GGUF Q4_K_M conversion by bartowski | Apache License 2.0 (`large-brain-LICENSE.txt`) | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct |
| `willy/models/willy-small.gguf` | Qwen2.5-3B-Instruct by the Qwen team, Alibaba Cloud; GGUF Q4_K_M conversion by bartowski | Qwen Research License, **non-commercial use only** (`small-brain-LICENSE.txt`) | https://huggingface.co/Qwen/Qwen2.5-3B-Instruct |
| Boot menu (hidden VTOYEFI partition) | Ventoy 1.1.18 | GNU GPL v3 | https://github.com/ventoy/Ventoy |
| `ubuntu-26.04.1-desktop-amd64.iso` | Ubuntu 26.04.1 LTS, Canonical Ltd. | Various free software licences; redistributed unmodified | https://ubuntu.com/legal/intellectual-property-policy |

Ubuntu is a registered trademark of Canonical Ltd. Willy is not affiliated with or endorsed
by Canonical, Mozilla, Alibaba Cloud or the Ventoy project.

**Note for anyone selling sticks:** the small brain's licence does not allow commercial use.
Build sale sticks with `setup-usb.sh ... large`, which leaves the small brain out.
