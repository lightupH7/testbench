#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Sequence


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, write_through=True)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ELF = REPO_ROOT / "zephyr_elf" / "zephyr.elf"
DEFAULT_BIN = REPO_ROOT / "zephyr_elf" / "zephyr.flash.bin"
DEFAULT_TARGET_CFG = REPO_ROOT / "scripts" / "openocd" / "target" / "lowrisc-earlgrey.cfg"
DEFAULT_PROGRAMMER = REPO_ROOT / "scripts" / "program-cw310-zephyr-elf-pylink.py"
DEFAULT_BITSTREAM_PROGRAMMER = REPO_ROOT / "scripts" / "program-cw310-vivado.sh"
DEFAULT_OPENTITAN_ENV_PYTHON = Path("/home/cmt/work/opentitan/.pixi/envs/default/bin/python")


def parse_int(value: str) -> int:
    return int(value, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Zephyr ELF into an OpenTitan flash image and load it onto a CW310."
    )
    parser.add_argument("--elf", default=str(DEFAULT_ELF), help=f"ELF to load. Default: {DEFAULT_ELF}")
    parser.add_argument("--bin", dest="bin_path", default=str(DEFAULT_BIN), help=f"Raw flash image to generate. Default: {DEFAULT_BIN}")
    parser.add_argument("--flash-base", default="0x20000000", help="Flash base used when extracting ELF segments.")
    parser.add_argument("--expected-entry", "--entry", default="0x20000400", help="Warn if the ELF entry differs from this address.")
    parser.add_argument("--interface", default=os.environ.get("OPENTITAN_INTERFACE", "cw310"), help="opentitantool interface.")
    parser.add_argument("--opentitantool", default=os.environ.get("OPENTITANTOOL", "opentitantool"), help="opentitantool executable.")
    parser.add_argument("--set-pll", action="store_true", help="Run 'opentitantool fpga set-pll' before bootstrap.")
    parser.add_argument("--program-bitstream", action="store_true", help="Program bitstream before loading firmware.")
    parser.add_argument("--method", choices=["pylink", "openocd", "bootstrap"], default="pylink", help="Programming method.")
    parser.add_argument("--jlink", action="store_true", help="Equivalent to --method pylink.")
    parser.add_argument("--jlink-lib", default=os.environ.get("JLINK_LIB", ""), help="J-Link shared library for pylink-square.")
    parser.add_argument("--jlink-device", default=os.environ.get("JLINK_DEVICE", "RISC-V"), help="J-Link target device name.")
    parser.add_argument("--jtag-speed", "--adapter-speed", dest="adapter_speed", default=os.environ.get("JTAG_SPEED_KHZ", os.environ.get("OPENOCD_ADAPTER_SPEED", "12000")), help="JTAG speed for pylink/OpenOCD.")
    parser.add_argument("--rom-init-delay", default=os.environ.get("ROM_INIT_DELAY", "0.1"), help="Delay after ROM restart for pylink flow.")
    parser.add_argument("--program-window-bytes", default=os.environ.get("FLASH_PROGRAM_WINDOW_BYTES", "64"), help="Flash program resolution window in bytes for pylink.")
    parser.add_argument("--progress-words", default=os.environ.get("FLASH_PROGRESS_WORDS", "4096"), help="Print pylink programming progress every N words.")
    parser.add_argument("--openocd", default=os.environ.get("OPENOCD", "openocd"), help="OpenOCD executable.")
    parser.add_argument("--adapter-cfg", default=os.environ.get("OPENOCD_ADAPTER_CFG", "interface/jlink.cfg"), help="OpenOCD adapter cfg.")
    parser.add_argument("--target-cfg", default=os.environ.get("OPENOCD_TARGET_CFG", str(DEFAULT_TARGET_CFG)), help="OpenOCD target cfg.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without programming the board.")
    parser.add_argument("--no-keep-bin", action="store_true", help="Remove the generated raw flash image on exit.")
    return parser.parse_args()


def normalize_path(path: str) -> Path:
    return Path(path).expanduser().resolve()


def quote_cmd(args: Sequence[str]) -> str:
    return " ".join(shlex_quote(arg) for arg in args)


def shlex_quote(value: str) -> str:
    return subprocess.list2cmdline([value]) if os.name == "nt" else __import__("shlex").quote(value)


def run_or_print(args: Sequence[str], dry_run: bool) -> None:
    if dry_run:
        print(quote_cmd(list(args)))
        return
    subprocess.run(list(args), check=True)


def extract_flash_image(elf_path: Path, bin_path: Path, flash_base: int, expected_entry: int) -> None:
    with elf_path.open("rb") as elf:
        ident = elf.read(16)
        if ident[:4] != b"\x7fELF":
            raise SystemExit(f"not an ELF file: {elf_path}")
        if ident[4] != 1:
            raise SystemExit("only ELF32 files are supported")
        endian = "<" if ident[5] == 1 else ">"

        elf.seek(24)
        entry = struct.unpack(endian + "I", elf.read(4))[0]
        elf.seek(28)
        phoff = struct.unpack(endian + "I", elf.read(4))[0]
        elf.seek(42)
        phentsize, phnum = struct.unpack(endian + "HH", elf.read(4))

        image = bytearray()
        loaded: list[tuple[int, int, int, int, int]] = []

        for index in range(phnum):
            elf.seek(phoff + index * phentsize)
            phdr = elf.read(phentsize)
            if len(phdr) < 32:
                continue
            p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, _, _ = struct.unpack(
                endian + "IIIIIIII",
                phdr[:32],
            )
            if p_type != 1 or p_filesz == 0:
                continue
            if p_paddr < flash_base:
                raise SystemExit(
                    f"LOAD segment at paddr=0x{p_paddr:08x} is below flash base "
                    f"0x{flash_base:08x}; this does not look like an OpenTitan flash image"
                )

            offset = p_paddr - flash_base
            end = offset + p_filesz
            if len(image) < end:
                image.extend(b"\x00" * (end - len(image)))

            elf.seek(p_offset)
            image[offset:end] = elf.read(p_filesz)
            loaded.append((p_offset, p_vaddr, p_paddr, p_filesz, p_memsz))

    if not loaded:
        raise SystemExit("no file-backed LOAD segments found")

    bin_path.parent.mkdir(parents=True, exist_ok=True)
    with bin_path.open("wb") as out:
        out.write(image)

    print(f"ELF entry: 0x{entry:08x}")
    if entry != expected_entry:
        print(
            f"warning: ELF entry is 0x{entry:08x}, expected 0x{expected_entry:08x}",
            file=sys.stderr,
        )
    print(f"Flash base: 0x{flash_base:08x}")
    for p_offset, p_vaddr, p_paddr, p_filesz, p_memsz in loaded:
        print(
            "LOAD "
            f"file=0x{p_offset:x} vaddr=0x{p_vaddr:08x} "
            f"paddr=0x{p_paddr:08x} filesz=0x{p_filesz:x} memsz=0x{p_memsz:x}"
        )
    print(f"Wrote flash image: {bin_path} ({bin_path.stat().st_size} bytes)")


def detect_jlink_lib(preferred: str) -> Path | None:
    if preferred:
        candidate = normalize_path(preferred)
        if candidate.is_file():
            return candidate
        raise SystemExit(f"J-Link library not found: {candidate}")

    candidates = [
        Path("/opt/SEGGER/JLink/libjlinkarm.so"),
        Path("/usr/lib/libjlinkarm.so"),
        Path("/usr/local/lib/libjlinkarm.so"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def python_has_pylink(command: Sequence[str]) -> bool:
    try:
        subprocess.run(
            [*command, "-c", "import pylink"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


def select_pylink_python() -> list[str] | None:
    candidates = [
        ["python3", "-u"],
        ["pixi", "run", "python", "-u"],
    ]
    if DEFAULT_OPENTITAN_ENV_PYTHON.is_file():
        candidates.append([str(DEFAULT_OPENTITAN_ENV_PYTHON), "-u"])

    for candidate in candidates:
        if python_has_pylink(candidate):
            return candidate
    return None


def ensure_command_exists(command: str, label: str) -> None:
    if shutil.which(command) is None:
        raise SystemExit(f"{label} not found: {command}")


def run_program_bitstream(dry_run: bool) -> None:
    run_or_print([str(DEFAULT_BITSTREAM_PROGRAMMER)], dry_run=dry_run)


def run_bootstrap(args: argparse.Namespace, bin_path: Path) -> None:
    if args.set_pll:
        run_or_print(
            [args.opentitantool, f"--interface={args.interface}", "fpga", "set-pll"],
            dry_run=args.dry_run,
        )
    run_or_print(
        [args.opentitantool, f"--interface={args.interface}", "bootstrap", str(bin_path)],
        dry_run=args.dry_run,
    )


def run_pylink(args: argparse.Namespace, elf_path: Path) -> None:
    jlink_lib = detect_jlink_lib(args.jlink_lib)
    if jlink_lib is None:
        raise SystemExit(
            "Unable to find libjlinkarm.so.\n"
            "Install SEGGER J-Link Software, or pass --jlink-lib /path/to/libjlinkarm.so."
        )

    python_cmd = select_pylink_python()
    if python_cmd is None:
        raise SystemExit(
            "pylink-square is not installed in any usable Python environment.\n"
            "Install it with one of:\n\n"
            "  python3 -m pip install --user pylink-square\n"
            "  pixi add --pypi pylink-square"
        )

    command = [
        *python_cmd,
        str(DEFAULT_PROGRAMMER),
        "--elf",
        str(elf_path),
        "--jlink-lib",
        str(jlink_lib),
        "--jtag-speed",
        str(args.adapter_speed),
        "--device",
        args.jlink_device,
        "--expected-entry",
        str(args.expected_entry),
        "--flash-base",
        str(args.flash_base),
        "--rom-init-delay",
        str(args.rom_init_delay),
        "--program-window-bytes",
        str(args.program_window_bytes),
        "--progress-words",
        str(args.progress_words),
    ]
    run_or_print(command, dry_run=args.dry_run)


def run_openocd(args: argparse.Namespace, elf_path: Path, target_cfg: Path) -> None:
    if not target_cfg.is_file():
        raise SystemExit(f"OpenOCD target cfg not found: {target_cfg}")
    ensure_command_exists(args.openocd, "OpenOCD")

    command = [
        args.openocd,
        "-f",
        args.adapter_cfg,
        "-c",
        f"adapter speed {args.adapter_speed}; transport select jtag; reset_config trst_only",
        "-f",
        str(target_cfg),
        "-c",
        f"init; halt; load_image {{{elf_path}}}; resume {args.expected_entry}; shutdown",
    ]
    try:
        run_or_print(command, dry_run=args.dry_run)
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            "OpenOCD connected through J-Link, but failed to write the ELF into 0x20000000.\n"
            "This ELF is linked for the OpenTitan flash address space, and generic JTAG memory\n"
            "writes cannot program that flash region on this target. To load this exact ELF\n"
            "into flash, use the OpenTitan bootstrap flow:\n\n"
            f"  {Path(__file__).name} --method bootstrap --opentitantool /path/to/opentitantool\n\n"
            "J-Link/OpenOCD is still useful for halt/resume/register/debug access, or for\n"
            "loading a program that is linked to executable SRAM."
        ) from error


def main() -> None:
    args = parse_args()
    if args.jlink:
        args.method = "pylink"

    elf_path = normalize_path(args.elf)
    bin_path = normalize_path(args.bin_path)
    target_cfg = normalize_path(args.target_cfg)
    args.flash_base = parse_int(str(args.flash_base))
    args.expected_entry = parse_int(str(args.expected_entry))
    args.adapter_speed = parse_int(str(args.adapter_speed))
    args.rom_init_delay = float(args.rom_init_delay)
    args.program_window_bytes = parse_int(str(args.program_window_bytes))
    args.progress_words = parse_int(str(args.progress_words))

    if not elf_path.is_file():
        raise SystemExit(f"ELF not found: {elf_path}")

    extract_flash_image(
        elf_path=elf_path,
        bin_path=bin_path,
        flash_base=args.flash_base,
        expected_entry=args.expected_entry,
    )

    try:
        if args.program_bitstream:
            run_program_bitstream(dry_run=args.dry_run)

        if args.method == "bootstrap":
            ensure_command_exists(args.opentitantool, "opentitantool")
            run_bootstrap(args, bin_path)
        elif args.method == "pylink":
            run_pylink(args, elf_path)
        else:
            run_openocd(args, elf_path, target_cfg)
    finally:
        if args.no_keep_bin:
            bin_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
