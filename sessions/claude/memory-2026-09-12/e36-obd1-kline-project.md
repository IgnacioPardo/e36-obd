---
name: e36-obd1-kline-project
description: "Ignacio's E36 OBD1 project — car/hardware specifics and the decision to write a native macOS KWP71 client instead of using INPA"
metadata: 
  node_type: memory
  type: project
  originSessionId: 520df9c4-5564-4e32-b377-60307bb80ef3
  modified: 2026-08-09T19:35:32.465Z
---

Ignacio owns a 1994 BMW E36 sedan, M43B16 engine, Bosch Motronic M1.7.2 DME — an OBD1 car, so generic OBD2 scan tools cannot talk to it at all. Hardware: FTDI FT232R-based "INPA compatible" K+DCAN USB cable plus a 16-pin OBD2 → BMW 20-pin round adapter. The 20-pin round port is in the engine bay, not under the dash.

Started 2026-08-09. Project lives at ~/Desktop/E36_OBD.

**Why:** Ignacio is on an Apple Silicon Mac. INPA/EDIABAS is 32-bit x86 Windows software needing a VM, so he chose (out of four offered options) to write a native Python KWP71 client instead. Goals: read/clear fault codes, live data logging to CSV, and learning the protocol.

**How to apply:** The 5-baud slow init is bit-banged via the UART BREAK signal (`TIOCSBRK`), NOT FTDI bitbang mode — libftdi can't claim the USB device because Apple's built-in AppleUSBFTDI driver owns it. BREAK control was verified working on macOS 26.3 / arm64. The cable's K-line transceiver is powered from OBD2 pin 16 (car battery), so it cannot echo anything when unplugged from the car — silence on a loopback probe is only a fault if the car is connected with ignition on.

Ignacio prefers parallel subagent work over serial execution, and declined a mock-ECU test harness for this project.
