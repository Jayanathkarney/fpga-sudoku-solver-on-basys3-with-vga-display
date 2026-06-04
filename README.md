# FPGA Sudoku Solver

**Hardware Sudoku Solver with AC-3 Constraint Propagation, MRV-Guided Backtracking, and VGA Display**

Implemented in Verilog HDL on the **Digilent Basys3 (Artix-7 XC7A35T)** FPGA.
Course project for **E3-231: Digital Systems Design with FPGAs**, IISc Bengaluru (Jan–Apr 2026).

---

## What This Project Does

This system solves any valid 9×9 Sudoku puzzle entirely in hardware — no CPU, no software solver.
You send the puzzle over UART from a PC, and the FPGA solves it and displays the result on a VGA monitor in real time.

### Key Features

- **AC-3 Constraint Propagation Engine** — All 81 cells processed in parallel each pass; converges in O(P) clock cycles
- **MRV-Guided Backtracking** — Minimum Remaining Values heuristic orders cells smartly, reducing wasted search
- **LIFO Stack MRV Trick** — Achieves correct MRV ordering with zero sorting hardware (just a shift-register)
- **VGA Display (640×480 @ 60 Hz)** — Four navigable tabs: FPGA Solve, User Mode, Statistics, Reset
- **Real-Time Conflict Detection** — Highlights conflicting cells live in User Mode (pink background, red digit)
- **UART Interface (115200 baud)** — Send puzzle from PC Python script; receive solution + performance stats
- **Cycle-Accurate Performance Monitor** — Tracks 6 metrics: total cycles, AC-3 cycles, pass count, cells solved by AC-3, backtrack count, peak stack depth
- **Verified on Arto Inkala puzzle** — One of the hardest known 9×9 Sudoku instances

---

## Hardware Required

| Component | Details |
|-----------|---------|
| FPGA Board | Digilent Basys3 (Artix-7 XC7A35T) |
| Display | VGA monitor (640×480 @ 60Hz) |
| PC | For UART communication (Python script) |
| USB Cable | Micro-USB for programming + UART |

---

## Repository Structure

```
fpga-sudoku-solver/
│
├── rtl/                    # All Verilog source files (.v)
│   ├── top_basys3.v        # Top-level module — wires everything together
│   ├── ac3_controller.v    # Parallel AC-3 arc-consistency engine
│   ├── candidate_store.v   # 81×9-bit candidate mask register array
│   ├── handoff_fsm.v       # AC-3 → Backtracker bridge; MRV ordering
│   ├── sudoku_solver.v     # Wrapper for control + updater + checker
│   ├── control.v           # Backtracking control FSM (7 states)
│   ├── updater.v           # Shift-register stack FSM; manages cell ordering
│   ├── checker.v           # Combinational conflict detector (row/col/box)
│   ├── uart_rx.v           # UART receiver (115200 baud, 8N1)
│   ├── uart_tx.v           # UART transmitter
│   ├── vga_sync.v          # VGA sync signal generator (640×480@60Hz)
│   ├── vga_renderer.v      # Two-stage pipelined VGA renderer
│   ├── conflict_detect.v   # Real-time 30-stage pipelined conflict scanner
│   ├── perf_counters.v     # 6-counter performance monitor
│   └── seven_seg.v         # 7-segment display driver (1kHz multiplex)
│
├── constraints/
│   └── basys3.xdc          # Timing + pin assignment constraints (100MHz clock, LVCMOS33)
│
├── python_host/
│   └── sudoku_host.py      # PC-side script: sends puzzle over UART, receives solution + stats
│
├── vivado/
│   └── (Vivado project files — .xpr, .bit, etc.)
│
├── docs/
│   └── project_report.pdf  # Full design report (IISc E3-231)
│
└── README.md               # You are here
```

---

## How It Works — Architecture Overview

```
[PC Python Script]
       |
   UART (115200 baud) — 81 bytes (puzzle)
       |
       ▼
[UART RX] ──► [Display RAM] ──► [Candidate Store]
                                      |
                                 [AC-3 Engine]          ← processes all 81 cells in parallel
                                      |
                                 [Handoff FSM]          ← extracts solved cells, sorts rest by MRV
                                      |
                              [Backtracking Solver]     ← control + updater + checker FSMs
                                      |
                               [Solution RAM]
                                      |
                    ┌─────────────────┴──────────────────┐
                    ▼                                     ▼
             [VGA Renderer]                        [UART TX]
          (display on monitor)             (81 solution bytes + 11 perf bytes → PC)
```

### The Three-Layer Solver Pipeline

1. **AC-3 Engine** — Eliminates impossible digit candidates from each cell by enforcing arc consistency across all rows, columns, and 3×3 boxes. Runs until no more eliminations are possible (fixed point).

2. **Handoff FSM** — After AC-3, cells with only one candidate are directly written as solved. Remaining unsolved cells are pushed onto a stack in MRV order (most-constrained cell first) using a clever LIFO prepend trick — no sorting hardware needed.

3. **Backtracking Solver** — Pops cells from the MRV-ordered stack, tries digit values 1–9, checks for conflicts combinationally, advances on success, backtracks on failure. Operates at 100 MHz with single-cycle conflict check latency.

---

## Performance (Observed on Hardware)

| Puzzle Type | Solve Time | Notes |
|-------------|-----------|-------|
| Easy (AC-3 alone) | < 50 µs | No backtracking needed |
| Hard (with backtracking) | 1 – 10 ms | e.g. Arto Inkala puzzle |

Solve time = from UART puzzle received to solution ready. All at **100 MHz** system clock.

---

## Resource Utilisation (Basys3 / Artix-7)

| Resource | Used | Available | % |
|----------|------|-----------|---|
| Slice LUTs | 17,094 | 20,800 | ~82% |
| Slice Registers | 5,229 | 41,600 | ~13% |
| Bonded IOB | 44 | 106 | ~42% |

Largest consumer: `candidate_store` (10,149 LUTs for the 729-bit mask array).

---

## How to Use

### 1. Program the FPGA
- Open the project in **Vivado 2023.x**
- Run Synthesis → Implementation → Generate Bitstream
- Program the Basys3 via USB

### 2. Connect Hardware
- Plug in a VGA monitor
- Connect USB cable (used for both programming and UART)

### 3. Send a Puzzle from PC
```bash
cd python_host
python sudoku_host.py
```
The script sends 81 bytes (one per cell, `0` for empty, `1–9` for givens) and prints the solution + performance stats.

### 4. Use the Board Directly (User Mode)
- Use **SW[3:0]** to select digit (0 = erase, 1–9 = value)
- Use **BTNU/BTND/BTNL/BTNR** to move the cursor
- Flip **SW[14]** to place the digit
- Switch to **FPGA Solve tab** to let the hardware solve it

### VGA Tabs
| Tab | What it shows |
|-----|--------------|
| FPGA Solve | Hardware solving mode; blue = given, green = solved |
| User Mode | Manual entry with real-time conflict highlighting |
| Statistics | Bar chart of all 6 performance counters |
| Reset | Clears the board |

---

## UART Protocol

| Direction | Bytes | Format |
|-----------|-------|--------|
| PC → FPGA | 81 bytes | BCD digit per cell (lower nibble); `0x00` = empty |
| FPGA → PC | 93 bytes | 81 solution bytes + 11 performance bytes + `0xFE` sentinel |

Performance bytes (bytes 82–92, big-endian):
`total_cycles (32-bit)` · `ac3_cycles (16-bit)` · `ac3_passes (8-bit)` · `cells_solved_ac3 (7-bit)` · `backtrack_count (8-bit)` · `max_bt_depth (7-bit)`

---

## Timing & Constraints Summary

- **Single clock domain**: 100 MHz (pin W5)
- **VGA pixel clock**: 25 MHz derived via divide-by-4 counter (no second clock domain)
- **Multicycle path constraints** (2-setup / 1-hold) applied to:
  - Candidate store → AC-3 engine (729-bit bus)
  - Candidate store → Handoff FSM
  - Display RAM → VGA pipeline Stage-1
- **Timing closure**: Achieved — 0 failing endpoints, WNS = +0.026 ns

---

## Key Design Insights

- **No sorting hardware for MRV**: Cells emitted high-to-low candidate count into a LIFO stack → most-constrained cell naturally ends up at top. Zero comparators needed.
- **No integer division in conflict detection**: Row/column/box peer indices precomputed in lookup tables → 27-comparison scan fits in 30-cycle pipeline at 100 MHz.
- **No external memory**: Everything (candidate store, display RAM, backtrack stack) lives in FPGA distributed RAM / flip-flops.

---

## Author

**Karney Jayanath** (Sr. No. 26831)
Department of Electronic Systems Engineering, IISc Bengaluru
Course: E3-231 — Digital Systems Design with FPGAs (Jan–Apr 2026)

---

## References

- A. K. Mackworth, "Consistency in Networks of Relations," *Artificial Intelligence*, 1977
- P. Norvig, ["Solving Every Sudoku Puzzle"](https://norvig.com/sudoku.html), 2006
- Xilinx Vivado Design Suite UG892
- Digilent Basys3 Reference Manual
