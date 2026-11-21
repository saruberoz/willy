# Third-party notices

Willy (`willy.py`, `willy_rescue.py`, `willy_undo.py`, `start.sh`, `setup-usb.sh`) is
© 2026 Wilson Sumanang, released under the MIT License (see `LICENSE` in the repository).

A Willy USB stick also carries the following separate works, unmodified, under their own licences:

| On the stick | Component | Licence | Source |
|--------------|-----------|---------|--------|
| `willy/bin/willy-engine` | llamafile 0.10.6 (Mozilla.ai), which includes llama.cpp (MIT) and Cosmopolitan Libc (ISC) | Apache License 2.0 (`engine-LICENSE.txt`, `Apache-2.0.txt`) | https://github.com/mozilla-ai/llamafile |
| `willy/models/willy-large.gguf` | Ministral 3 8B Instruct 2512 by Mistral AI; GGUF Q4_K_M conversion by bartowski | Apache License 2.0 (`Apache-2.0.txt`) | https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512 |
| `willy/models/willy-small.gguf` | Ministral 3 3B Instruct 2512 by Mistral AI; GGUF Q4_K_M conversion by bartowski | Apache License 2.0 (`Apache-2.0.txt`) | https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512 |
| Boot menu (hidden VTOYEFI partition) | Ventoy 1.1.18 | GNU GPL v3 | https://github.com/ventoy/Ventoy |
| `ubuntu-26.04.1-desktop-amd64.iso` | Ubuntu 26.04.1 LTS, Canonical Ltd. | Various free software licences; redistributed unmodified | https://ubuntu.com/legal/intellectual-property-policy |

Ubuntu is a registered trademark of Canonical Ltd. Willy is not affiliated with or endorsed
by Canonical, Mozilla, Mistral AI or the Ventoy project.

All bundled components allow commercial redistribution under the terms above.
