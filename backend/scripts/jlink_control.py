#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import time


FALLBACK_JTAG_SPEEDS_KHZ = (12000, 8000, 4000, 2000, 1000, 400, 100)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, write_through=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple J-Link target control action.")
    parser.add_argument("action", choices=["reset_run", "reset_halt", "resume"])
    parser.add_argument("--jlink-lib", default="", help="J-Link shared library path.")
    parser.add_argument("--jlink-serial", default="", help="J-Link probe serial number.")
    parser.add_argument("--jlink-device", default="RISC-V", help="J-Link target device name.")
    parser.add_argument("--interface", default="JTAG", help="J-Link target interface, for example JTAG or SWD.")
    parser.add_argument("--speed", type=int, default=4000, help="JTAG/SWD speed in kHz.")
    return parser.parse_args()


def candidate_jtag_speeds(preferred_speed: int) -> list[int]:
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


def connect_jlink(jlink, pylink_module, args: argparse.Namespace) -> int:
    interface_name = args.interface.upper()
    interface = getattr(pylink_module.enums.JLinkInterfaces, interface_name, None)
    if interface is None:
        raise ValueError(f"unsupported J-Link interface: {args.interface}")

    serial_no = int(args.jlink_serial) if args.jlink_serial else None
    last_error: Exception | None = None

    for speed in candidate_jtag_speeds(args.speed):
        try:
            try:
                jlink.close()
            except Exception:
                pass
            time.sleep(0.1)

            if serial_no is None:
                jlink.open()
            else:
                jlink.open(serial_no=serial_no)

            jlink.set_tif(interface)
            jlink.set_speed(speed)
            jlink.connect(args.jlink_device, verbose=False)

            if not jlink.target_connected():
                raise RuntimeError(
                    f"connected to probe but target did not respond over {interface_name} at {speed} kHz"
                )

            return speed
        except Exception as error:  # noqa: BLE001
            last_error = error

    assert last_error is not None
    raise last_error


def main() -> int:
    args = parse_args()

    try:
        import pylink
    except ImportError:
        print(
            "pylink-square is not installed. Install it with: python3 -m pip install --user pylink-square",
            file=sys.stderr,
        )
        return 1

    library = pylink.Library(dllpath=args.jlink_lib) if args.jlink_lib else None
    jlink = pylink.JLink(lib=library) if library else pylink.JLink()

    try:
        connected_speed = connect_jlink(jlink, pylink, args)

        if args.action == "reset_run":
            jlink.reset(halt=False)
            time.sleep(0.05)
            jlink.restart()
            print(f"J-Link reset and run completed at {connected_speed} kHz.")
        elif args.action == "reset_halt":
            jlink.reset(halt=True)
            print(f"J-Link reset and halt completed at {connected_speed} kHz.")
        else:
            jlink.restart()
            print(f"J-Link resume completed at {connected_speed} kHz.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"J-Link control failed: {exc}", file=sys.stderr)
        return 2
    finally:
        try:
            jlink.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
