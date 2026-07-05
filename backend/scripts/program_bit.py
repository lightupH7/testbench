#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path


TCL_TEMPLATE = r"""
set bitfile __BITFILE__
set hw_target_pattern __HW_TARGET__
set device_pattern __DEVICE__

proc fail_and_exit {message code} {
    puts "ERROR: $message"
    catch {close_hw_target}
    catch {disconnect_hw_server}
    catch {close_hw_manager}
    exit $code
}

if {$bitfile eq ""} {
    fail_and_exit "bit file path is required" 2
}

if {![file exists $bitfile]} {
    fail_and_exit "bit file does not exist: $bitfile" 3
}

open_hw_manager
connect_hw_server

set all_targets [get_hw_targets]
if {[llength $all_targets] == 0} {
    fail_and_exit "no hardware targets found" 4
}

puts "INFO: available hw_targets: $all_targets"

if {$hw_target_pattern ne ""} {
    set matched_targets [get_hw_targets $hw_target_pattern]
    if {[llength $matched_targets] == 0} {
        fail_and_exit "hardware target not found: $hw_target_pattern" 5
    }
    set selected_target [lindex $matched_targets 0]
} else {
    set selected_target [lindex $all_targets 0]
}

puts "INFO: selected hw_target: $selected_target"
current_hw_target $selected_target
open_hw_target

set all_devices [get_hw_devices]
if {[llength $all_devices] == 0} {
    fail_and_exit "no hardware devices found" 6
}

puts "INFO: available hw_devices: $all_devices"

if {$device_pattern ne ""} {
    set matched_devices [get_hw_devices $device_pattern]
    if {[llength $matched_devices] == 0} {
        set matched_devices [list]
        foreach dev $all_devices {
            if {[string match "*$device_pattern*" $dev]} {
                lappend matched_devices $dev
            }
        }
    }
    if {[llength $matched_devices] == 0} {
        fail_and_exit "hardware device not found: $device_pattern" 7
    }
    set device [lindex $matched_devices 0]
} elseif {[llength $all_devices] == 1} {
    set device [lindex $all_devices 0]
} else {
    set device [lindex $all_devices 0]
}

puts "INFO: selected hw_device: $device"
current_hw_device $device
refresh_hw_device $device
set_property PROGRAM.FILE $bitfile $device
program_hw_devices $device
refresh_hw_device $device

puts "INFO: programmed bit file $bitfile to $device"

close_hw_target
disconnect_hw_server
close_hw_manager
exit 0
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a temporary Vivado TCL script and program a bitstream."
    )
    parser.add_argument("--bit", required=True, help="Path to bitstream file")
    parser.add_argument("--vivado-bin", default="", help="Path to vivado executable")
    parser.add_argument("--hw-target", default="", help="Vivado hw_target pattern")
    parser.add_argument("--device", default="", help="Vivado hw_device name or pattern")
    parser.add_argument("--keep-tcl", action="store_true", help="Keep generated TCL file for debugging")
    parser.add_argument("--dry-run", action="store_true", help="Print command without executing Vivado")
    return parser.parse_args()


def tcl_quote(value: str) -> str:
    return "{" + value.replace("\\", "/").replace("}", r"\}") + "}"


def resolve_vivado_bin(configured: str) -> Path:
    if configured:
        path = Path(configured).expanduser().resolve()
        if not path.exists():
            raise SystemExit(f"vivado executable not found: {path}")
        return path

    found = shutil.which("vivado")
    if found is None:
        raise SystemExit("vivado executable not found on PATH")
    return Path(found).resolve()


def build_tcl(bit_path: Path, hw_target: str, device: str) -> str:
    return (
        TCL_TEMPLATE
        .replace("__BITFILE__", tcl_quote(str(bit_path)))
        .replace("__HW_TARGET__", tcl_quote(hw_target))
        .replace("__DEVICE__", tcl_quote(device))
    )


def main() -> None:
    args = parse_args()
    bit_path = Path(args.bit).expanduser().resolve()
    if not bit_path.exists():
        raise SystemExit(f"bit file not found: {bit_path}")

    vivado_bin = resolve_vivado_bin(args.vivado_bin)
    tcl_content = build_tcl(
        bit_path=bit_path,
        hw_target=args.hw_target,
        device=args.device,
    )

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".tcl",
            prefix="program_bit_",
            delete=False,
        ) as temp_file:
            temp_file.write(tcl_content)
            temp_path = Path(temp_file.name)

        command = [
            str(vivado_bin),
            "-mode",
            "batch",
            "-source",
            str(temp_path),
            "-nolog",
            "-nojournal",
            "-notrace",
        ]

        if args.dry_run:
            print(" ".join(command))
            return

        completed = subprocess.run(command, check=False)
        raise SystemExit(completed.returncode)
    finally:
        if temp_path is not None and temp_path.exists() and not args.keep_tcl:
            temp_path.unlink()


if __name__ == "__main__":
    main()
