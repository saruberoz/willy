# What is a program doing? strace, ltrace, bpftrace and BCC tools
Keywords: strace ltrace trace system calls syscalls which file does it open hangs stuck what is it doing bpftrace ebpf bcc execsnoop opensnoop tcpconnect biolatency kprobe tracepoint ptrace permission denied which config file

## strace: system calls of one program (adds overhead, so keep it short)
- Run a program under strace, following children, saving to a file: `strace -f -o /tmp/trace.txt <command>`
- Only file activity ("which config file does it read?"): `strace -f -e trace=%file <command> 2>&1 | grep -v ENOENT | tail -n 40`
- Only network: `strace -f -e trace=%network <command>`
- A running process for 10 seconds: `sudo timeout 10 strace -f -p <PID>`; a summary instead of every call: `sudo timeout 10 strace -c -f -p <PID>`
- **Hanging program:** `sudo timeout 5 strace -p <PID>` shows the call it's stuck in (for example `read` on a socket = waiting for the network, `futex` = waiting for another thread, `wait4` = waiting for a child).
- Reading results: `= -1 ENOENT` = file not found, `EACCES` = permission denied, `ECONNREFUSED` = nothing listening.
- `ltrace <command>` does the same for library calls (often less useful; may show nothing on modern builds).

## eBPF tools: system-wide, low overhead (need root and a recent kernel)
BCC tools (Ubuntu package `bpfcc-tools`, commands end in `-bpfcc`; Fedora `bcc-tools` in `/usr/share/bcc/tools/`):
- `sudo timeout 10 execsnoop-bpfcc`: every program started (great for "something keeps spawning")
- `sudo timeout 10 opensnoop-bpfcc -p <PID>`: files opened
- `sudo timeout 10 tcpconnect-bpfcc`: outgoing TCP connections with process names
- `sudo timeout 10 biolatency-bpfcc`: disk latency histogram

bpftrace one-liners (package `bpftrace`):
- List probes: `sudo bpftrace -l 'tracepoint:syscalls:*open*'`
- Files opened, by program: `sudo timeout 10 bpftrace -e 'tracepoint:syscalls:sys_enter_openat { printf("%s %s\n", comm, str(args.filename)); }'`
- Count system calls per program: `sudo timeout 10 bpftrace -e 'tracepoint:raw_syscalls:sys_enter { @[comm] = count(); }'`

Always wrap these in `timeout` (or stop them with Ctrl+C yourself); otherwise they run forever.

## Privacy
Traces can show file contents, network data and passwords passed to programs. Delete trace files afterwards.

## Undo notes
Tracing changes nothing on disk. strace briefly slows the traced program while attached.
