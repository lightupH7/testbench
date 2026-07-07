#!/usr/bin/env python3

import argparse
import struct
import sys
import time
from contextlib import contextmanager


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, write_through=True)

pylink = None


FLASH_BASE = 0x20000000
SRAM_BASE = 0x10000000
FC_BASE = 0x41000000

FC_DIS = FC_BASE + 0x010
FC_INIT = FC_BASE + 0x018
FC_CTRL_REGWEN = FC_BASE + 0x01C
FC_CONTROL = FC_BASE + 0x020
FC_ADDR = FC_BASE + 0x024
FC_PROG_TYPE_EN = FC_BASE + 0x028
FC_DEFAULT_REGION = FC_BASE + 0x090
FC_OP_STATUS = FC_BASE + 0x170
FC_STATUS = FC_BASE + 0x174
FC_ERR_CODE = FC_BASE + 0x17C
FC_STD_FAULT = FC_BASE + 0x180
FC_FAULT_STATUS = FC_BASE + 0x184
FC_ERR_ADDR = FC_BASE + 0x188
FC_PROG_FIFO = FC_BASE + 0x1B0

PAGE_SIZE_BYTES = 2048
FLASH_BUS_WORD_BYTES = 4

# Earlgrey's common data flash program resolution is 64 bytes.
# If your generated register constants disagree, pass --program-window-bytes.
DEFAULT_PROGRAM_WINDOW_BYTES = 64
DEFAULT_JTAG_SPEED_KHZ = 12000
DEFAULT_ROM_INIT_DELAY = 0.1
FALLBACK_JTAG_SPEEDS_KHZ = (12000, 8000, 4000, 2000, 1000, 400, 100)

CONTROL_START = 1 << 0
CONTROL_OP_PROG = 0x1 << 4
CONTROL_OP_ERASE = 0x2 << 4
CONTROL_NUM_SHIFT = 16
CONTROL_NUM_MASK = 0xFFF

STATUS_PROG_FULL = 1 << 2
STATUS_PROG_EMPTY = 1 << 3
STATUS_INIT_WIP = 1 << 4
STATUS_INITIALIZED = 1 << 5

OP_STATUS_DONE = 1 << 0
OP_STATUS_ERR = 1 << 1

ERR_CODE_ALL_RECOVERABLE = 0xFF

DEFAULT_REGION_VAL = (
    (0x9 << 20) |  # he_en = false
    (0x9 << 16) |  # ecc_en = false
    (0x9 << 12) |  # scramble_en = false
    (0x6 << 8) |   # erase_en = true
    (0x6 << 4) |   # prog_en = true
    (0x6 << 0)     # rd_en = true
)


def parse_int(value):
    return int(value, 0)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Program OpenTitan Zephyr ELF through J-Link and flash_ctrl."
    )
    parser.add_argument("--elf", required=True, help="Path to zephyr.elf")
    parser.add_argument("--jlink-lib", required=True, help="Path to libjlinkarm.so")
    parser.add_argument(
        "--jtag-speed",
        type=parse_int,
        default=DEFAULT_JTAG_SPEED_KHZ,
        help=f"JTAG speed in kHz. Default: {DEFAULT_JTAG_SPEED_KHZ}",
    )
    parser.add_argument("--device", default="RISC-V", help="J-Link target device name")
    parser.add_argument("--expected-entry", type=parse_int, default=0x20000400)
    parser.add_argument("--flash-base", type=parse_int, default=FLASH_BASE)
    parser.add_argument(
        "--rom-init-delay",
        type=float,
        default=DEFAULT_ROM_INIT_DELAY,
        help=f"Delay after ROM restart in seconds. Default: {DEFAULT_ROM_INIT_DELAY}",
    )
    parser.add_argument(
        "--program-window-bytes",
        type=parse_int,
        default=DEFAULT_PROGRAM_WINDOW_BYTES,
        help=(
            "Flash program resolution window in bytes. "
            "Use FLASH_CTRL_PARAM_REG_BUS_PGM_RES_BYTES from the generated "
            "flash_ctrl register header if this default is wrong. Default: 64"
        ),
    )
    parser.add_argument(
        "--progress-words",
        type=parse_int,
        default=4096,
        help="Print flash programming progress every N 32-bit words. Default: 4096",
    )
    return parser.parse_args()


def parse_elf(path):
    with open(path, "rb") as elf:
        raw = elf.read()

    if raw[:4] != b"\x7fELF":
        raise SystemExit(f"not an ELF file: {path}")
    if raw[4] != 1:
        raise SystemExit("only ELF32 files are supported")

    endian = "<" if raw[5] == 1 else ">"
    entry = struct.unpack_from(endian + "I", raw, 24)[0]
    phoff = struct.unpack_from(endian + "I", raw, 28)[0]
    phentsize = struct.unpack_from(endian + "H", raw, 42)[0]
    phnum = struct.unpack_from(endian + "H", raw, 44)[0]

    segments = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        p_type = struct.unpack_from(endian + "I", raw, offset + 0)[0]
        p_offset = struct.unpack_from(endian + "I", raw, offset + 4)[0]
        p_paddr = struct.unpack_from(endian + "I", raw, offset + 12)[0]
        p_filesz = struct.unpack_from(endian + "I", raw, offset + 16)[0]
        if p_type == 1 and p_filesz > 0:
            segments.append((p_paddr, bytearray(raw[p_offset:p_offset + p_filesz])))

    return segments, entry


def merge_adjacent_segments(segments):
    if not segments:
        return []

    merged = []
    for addr, data in sorted(segments, key=lambda item: item[0]):
        payload = bytearray(data)
        if not merged:
            merged.append((addr, payload))
            continue

        prev_addr, prev_data = merged[-1]
        prev_end = prev_addr + len(prev_data)
        if prev_end == addr:
            prev_data.extend(payload)
            merged[-1] = (prev_addr, prev_data)
            continue

        merged.append((addr, payload))

    return merged


def w32(jlink, addr, value):
    jlink.memory_write32(addr, [value])


def r32(jlink, addr):
    return jlink.memory_read32(addr, 1)[0]


def wait_init(jlink, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = r32(jlink, FC_STATUS)
        if not (status & STATUS_INIT_WIP) and (status & STATUS_INITIALIZED):
            return True
        time.sleep(0.01)
    return False


def dump_fc_status(jlink):
    print("--- Flash controller register dump ---")
    print("    DIS          = 0x{:08X}  (9=OK, 6=DISABLED)".format(r32(jlink, FC_DIS)))
    print("    CTRL_REGWEN  = 0x{:08X}".format(r32(jlink, FC_CTRL_REGWEN)))
    print("    CONTROL      = 0x{:08X}".format(r32(jlink, FC_CONTROL)))
    print("    ADDR         = 0x{:08X}".format(r32(jlink, FC_ADDR)))
    print("    OP_STATUS    = 0x{:08X}".format(r32(jlink, FC_OP_STATUS)))
    print("    STATUS       = 0x{:08X}".format(r32(jlink, FC_STATUS)))
    print("    ERR_CODE     = 0x{:08X}".format(r32(jlink, FC_ERR_CODE)))
    print("    ERR_ADDR     = 0x{:08X}".format(r32(jlink, FC_ERR_ADDR)))
    print("    STD_FAULT    = 0x{:08X}".format(r32(jlink, FC_STD_FAULT)))
    print("    FAULT_STATUS = 0x{:08X}".format(r32(jlink, FC_FAULT_STATUS)))
    print("    DEFAULT_RGN  = 0x{:08X}".format(r32(jlink, FC_DEFAULT_REGION)))
    print("    PROG_TYPE_EN = 0x{:08X}".format(r32(jlink, FC_PROG_TYPE_EN)))


def candidate_jtag_speeds(preferred_speed):
    speeds = [preferred_speed]
    for speed in FALLBACK_JTAG_SPEEDS_KHZ:
        if speed <= preferred_speed and speed not in speeds:
            speeds.append(speed)
    halved = preferred_speed
    while halved > 100:
        halved = max(100, halved // 2)
        if halved not in speeds:
            speeds.append(halved)
        if halved == 100:
            break
    return speeds


def connect_jlink(jlink, args, *, halt_after_connect):
    last_error = None
    for speed in candidate_jtag_speeds(args.jtag_speed):
        try:
            try:
                jlink.close()
            except Exception:
                pass
            time.sleep(0.1)
            jlink.open()
            jlink.set_tif(pylink.enums.JLinkInterfaces.JTAG)
            jlink.set_speed(speed)
            jlink.connect(args.device, verbose=False)
            if halt_after_connect:
                jlink.halt()
            args.current_jtag_speed = speed
            return speed
        except Exception as error:  # noqa: BLE001
            last_error = error
    raise last_error


def reconnect(jlink, args):
    time.sleep(0.5)
    previous_speed = getattr(args, "current_jtag_speed", args.jtag_speed)
    speed = connect_jlink(jlink, args, halt_after_connect=True)
    if speed != previous_speed:
        print(
            "    [RETRY] Reconnected to target at {} kHz "
            "(requested {} kHz)".format(speed, args.jtag_speed)
        )
    else:
        print("    [RETRY] Reconnected to target at {} kHz".format(speed))


def halt_with_reconnect(jlink, args, retries=2, settle_delay=0.05):
    last_error = None
    for attempt in range(retries + 1):
        try:
            jlink.halt()
            return
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt >= retries:
                break
            time.sleep(settle_delay)
            reconnect(jlink, args)
    raise last_error


def clear_operation_status(jlink):
    # OP_STATUS is cleared by writing 0 in this target flow.
    # ERR_CODE is rw1c, so write all implemented recoverable bits to clear stale errors.
    w32(jlink, FC_OP_STATUS, 0x0)
    w32(jlink, FC_ERR_CODE, ERR_CODE_ALL_RECOVERABLE)


def wait_done(jlink, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        op_status = r32(jlink, FC_OP_STATUS)
        if op_status & OP_STATUS_DONE:
            if op_status & OP_STATUS_ERR:
                w32(jlink, FC_OP_STATUS, 0x0)
                dump_fc_status(jlink)
                raise RuntimeError("Flash op error! OP_STATUS=0x{:08X}".format(op_status))
            w32(jlink, FC_OP_STATUS, 0x0)
            return
        time.sleep(0.001)
    raise TimeoutError("Flash op timed out")


def wait_ctrl_ready(jlink, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if r32(jlink, FC_CTRL_REGWEN) & 1:
            return
        time.sleep(0.0001)
    raise TimeoutError("CTRL_REGWEN did not become ready")


def wait_prog_fifo_not_full(jlink, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not (r32(jlink, FC_STATUS) & STATUS_PROG_FULL):
            return
        time.sleep(0.0001)
    raise TimeoutError("PROG_FIFO stayed full")


def flash_offset(args, flash_addr):
    if flash_addr < args.flash_base:
        raise ValueError(
            "flash address 0x{:08X} is below flash base 0x{:08X}".format(
                flash_addr, args.flash_base
            )
        )
    return flash_addr - args.flash_base


def erase_page(jlink, args, flash_addr):
    clear_operation_status(jlink)
    wait_ctrl_ready(jlink)

    control = CONTROL_OP_ERASE  # ERASE_SEL=0, data partition, page erase.
    w32(jlink, FC_ADDR, flash_offset(args, flash_addr))
    w32(jlink, FC_CONTROL, control | CONTROL_START)
    wait_done(jlink, timeout=15.0)


def program_chunk_once(jlink, args, flash_addr, words):
    if not words:
        return
    if len(words) > CONTROL_NUM_MASK + 1:
        raise ValueError("chunk too large: {} words".format(len(words)))

    clear_operation_status(jlink)
    wait_ctrl_ready(jlink)

    control = CONTROL_OP_PROG | ((len(words) - 1) << CONTROL_NUM_SHIFT)

    # ADDR is a byte address relative to flash, not the CPU-visible flash address.
    w32(jlink, FC_ADDR, flash_offset(args, flash_addr))

    # Start one multi-word program transaction.
    w32(jlink, FC_CONTROL, control | CONTROL_START)

    # prog_fifo is a fixed-address FIFO. Do not use memory_write32(FC_PROG_FIFO, words),
    # because that would write FC_PROG_FIFO, FC_PROG_FIFO+4, ...
    for word in words:
        wait_prog_fifo_not_full(jlink)
        w32(jlink, FC_PROG_FIFO, word)

    wait_done(jlink, timeout=15.0)


def program_chunk(jlink, args, flash_addr, words, max_retries=3):
    for attempt in range(max_retries):
        try:
            program_chunk_once(jlink, args, flash_addr, words)
            return
        except Exception as error:
            if attempt < max_retries - 1:
                print(
                    "    [RETRY] chunk at 0x{:08X}, {} words, attempt {}/{}: {}".format(
                        flash_addr, len(words), attempt + 1, max_retries, error
                    )
                )
                reconnect(jlink, args)
            else:
                raise


def validate_program_options(args):
    if args.program_window_bytes <= 0:
        raise ValueError("--program-window-bytes must be positive")
    if args.program_window_bytes % FLASH_BUS_WORD_BYTES != 0:
        raise ValueError("--program-window-bytes must be a multiple of 4")
    if args.program_window_bytes // FLASH_BUS_WORD_BYTES > CONTROL_NUM_MASK + 1:
        raise ValueError("--program-window-bytes is too large for CONTROL.NUM")
    if args.progress_words <= 0:
        raise ValueError("--progress-words must be positive")


def program_segment(jlink, args, flash_addr, data):
    if flash_addr % FLASH_BUS_WORD_BYTES != 0:
        raise ValueError("flash segment address is not word aligned: 0x{:08X}".format(flash_addr))

    while len(data) % FLASH_BUS_WORD_BYTES:
        data += b"\xff"

    words = list(
        struct.unpack_from(
            "<{}I".format(len(data) // FLASH_BUS_WORD_BYTES), bytes(data)
        )
    )
    total = len(words)
    done = 0
    last_print = 0

    while done < total:
        curr_addr = flash_addr + done * FLASH_BUS_WORD_BYTES
        curr_offset = flash_offset(args, curr_addr)

        # Program operations must not cross the flash program resolution window.
        window_pos = curr_offset % args.program_window_bytes
        bytes_until_window_end = args.program_window_bytes - window_pos
        words_until_window_end = bytes_until_window_end // FLASH_BUS_WORD_BYTES
        if words_until_window_end <= 0:
            raise ValueError("invalid program window split at 0x{:08X}".format(curr_addr))

        chunk_words = min(total - done, words_until_window_end)
        chunk = words[done:done + chunk_words]

        program_chunk(jlink, args, curr_addr, chunk)
        done += chunk_words

        if done - last_print >= args.progress_words or done == total:
            print("    {:5d}/{} words".format(done, total))
            last_print = done


def write_sram_segment(jlink, addr, data):
    padded = bytearray(data)
    while len(padded) % FLASH_BUS_WORD_BYTES:
        padded += b"\x00"
    words = list(
        struct.unpack_from(
            "<{}I".format(len(padded) // FLASH_BUS_WORD_BYTES), bytes(padded)
        )
    )
    if words:
        jlink.memory_write32(addr, words)


@contextmanager
def timed_step(label):
    start = time.monotonic()
    print(label)
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        print("    [TIME] {:.3f}s".format(elapsed))


def main():
    global pylink

    args = parse_args()
    validate_program_options(args)

    try:
        import pylink as pylink_module
    except ImportError:
        print(
            "pylink-square is not installed. Install it with: "
            "python3 -m pip install --user pylink-square",
            file=sys.stderr,
        )
        sys.exit(1)
    pylink = pylink_module

    print("=== OpenTitan Zephyr Flash Programmer (J-Link/pylink) ===\n")
    print(f"[1] Parsing ELF: {args.elf}")
    segments, entry = parse_elf(args.elf)
    print("    Entry: 0x{:08X}".format(entry))
    if entry != args.expected_entry:
        print("    WARNING: expected entry 0x{:08X}".format(args.expected_entry))

    flash_segments = [(addr, data) for addr, data in segments if addr >= args.flash_base]
    sram_segments = [(addr, data) for addr, data in segments if SRAM_BASE <= addr < args.flash_base]
    flash_segments = merge_adjacent_segments(flash_segments)
    sram_segments = merge_adjacent_segments(sram_segments)
    if not flash_segments:
        raise SystemExit("no flash LOAD segments found")

    for addr, data in flash_segments:
        print("    Flash segment: 0x{:08X}  {} bytes".format(addr, len(data)))
    for addr, data in sram_segments:
        print("    SRAM  segment: 0x{:08X}  {} bytes".format(addr, len(data)))
    print("    Program window: {} bytes".format(args.program_window_bytes))

    print("\n[2] Connecting J-Link (JTAG, {}) ...".format(args.device))
    library = pylink.Library(dllpath=args.jlink_lib)
    jlink = pylink.JLink(lib=library)
    try:
        speed = connect_jlink(jlink, args, halt_after_connect=False)
        if speed != args.jtag_speed:
            print(
                "    Connected at {} kHz (requested {} kHz)".format(
                    speed, args.jtag_speed
                )
            )
        else:
            print("    Connected at {} kHz".format(speed))

        with timed_step("\n[3] Reset + ROM init ..."):
            halt_with_reconnect(jlink, args)
            jlink.reset()
            jlink.restart()
            time.sleep(args.rom_init_delay)
            halt_with_reconnect(jlink, args)
            print("    CPU halted after ROM init")

        with timed_step("\n[4] Initialising Flash Controller ..."):
            if r32(jlink, FC_DIS) != 0x9:
                w32(jlink, FC_DIS, 0x9)
                time.sleep(0.01)
            w32(jlink, FC_INIT, 1)
            if wait_init(jlink, timeout=10.0):
                print("    Flash ready")
            else:
                print("    WARNING: init timeout, continuing anyway ...")
            wait_ctrl_ready(jlink, timeout=1.0)
            w32(jlink, FC_PROG_TYPE_EN, 0x1)
            w32(jlink, FC_DEFAULT_REGION, DEFAULT_REGION_VAL)

        with timed_step("\n[5] Erasing pages ..."):
            pages_needed = set()
            for addr, data in flash_segments:
                first_page = (addr - args.flash_base) // PAGE_SIZE_BYTES
                last_page = (addr + len(data) - 1 - args.flash_base) // PAGE_SIZE_BYTES
                pages_needed.update(range(first_page, last_page + 1))
            for page in sorted(pages_needed):
                page_addr = args.flash_base + page * PAGE_SIZE_BYTES
                print("    Page {:2d}  0x{:08X}".format(page, page_addr))
                erase_page(jlink, args, page_addr)

        with timed_step("\n[6] Programming flash ..."):
            for addr, data in flash_segments:
                print("    0x{:08X}  {} bytes".format(addr, len(data)))
                program_segment(jlink, args, addr, bytearray(data))
                print("    done")

        if sram_segments:
            with timed_step("\n[7] Writing SRAM segments ..."):
                for addr, data in sram_segments:
                    print("    0x{:08X}  {} bytes".format(addr, len(data)))
                    write_sram_segment(jlink, addr, data)
                print("    done")

        with timed_step("\n[8] Resetting and starting ..."):
            jlink.reset()
            jlink.restart()
        print("\n=== Done! Entry: 0x{:08X} ===".format(entry))
    finally:
        try:
            jlink.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
