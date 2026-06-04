"""
sudoku_com.py  –  Basys3 FPGA Sudoku Solver host script
========================================================

Terminal display
  • Thick ┃ borders separate the 3×3 boxes; thin │ separate cells within a box
  • Heavy ━ lines for box-row separators; thin ─ for within-box row dividers
  • given digits   →  bold red       (both puzzle and solution views)
  • empty cells    →  dim  _         (puzzle view only)
  • solved digits  →  bold green     (solution view)

PNG image  ( sudoku_YYYYMMDD_HHMMSS.png )
  • side-by-side PUZZLE → SOLUTION on dark navy background
  • given  = warm red    solved = mint green    empty = dim _
  • FPGA solve time + timestamp embedded in footer

TIMING ACCURACY NOTES
======================
The FPGA solves in hardware (microsecond or sub-microsecond range).
Python's time.perf_counter_ns() gives nanosecond-resolution timestamps,
but the dominant source of error is the serial port UART latency:

  - Each byte sent at 115200 baud takes ~86.8 µs to transmit.
  - Python's serial.write() returns BEFORE the byte has finished
    leaving the USB-UART chip, adding ~1-5 ms of OS/driver jitter.
  - The last byte of the puzzle arrives at the FPGA roughly
    CLKS_PER_BIT * 10 / 50e6 = 173.6 µs after Python's write() call.

Strategy used here:
  1. Send ALL 81 bytes in ONE serial.write() call (no per-byte sleep).
     This minimises Python loop overhead and OS scheduling jitter.
  2. Record t_send_end immediately after write() returns.
  3. Record t_first_byte_ns when the FIRST response byte is seen.
  4. solve_ns  = t_first_byte_ns - t_send_end_ns
     This is the best-effort Python-side estimate.  It includes:
       • Time for the last byte to finish transmitting  (~87 µs)
       • FPGA solve time                                (actual target)
       • UART TX serialisation of first reply byte      (~87 µs)
     So the true solve time ≈ solve_ns - 2 × 87 µs.
  5. We display BOTH the raw measured value and the corrected estimate.

For a definitive on-chip measurement, a cycle counter inside the
Verilog and a separate status read-back would be needed.
"""

import serial
import time
import os
import datetime
import sys

# ── CONFIG ────────────────────────────────────────────────────────────────────
COM_PORT   = 'COM18'
BAUD       = 115200
OUTPUT_DIR = '.'          # folder where the PNG is saved

# At 115200 baud, one 10-bit UART frame = 1/115200 * 10 ≈ 86.8 µs
UART_BYTE_NS = int(1e9 / BAUD * 10)   # ≈ 86 805 ns per byte
# ─────────────────────────────────────────────────────────────────────────────

puzzle = [
    8,0,0, 0,0,0, 0,0,0,
    0,0,3, 6,0,0, 0,0,0,
    0,7,0, 0,9,0, 2,0,0,

    0,5,0, 0,0,7, 0,0,0,
    0,0,0, 0,4,5, 7,0,0,
    0,0,0, 1,0,0, 0,3,0,

    0,0,1, 0,0,0, 0,6,8,
    0,0,8, 5,0,0, 0,1,0,
    0,9,0, 0,0,0, 4,0,0,
]

# ─────────────────────────────────────────────────────────────────────────────
#  ANSI helpers
# ─────────────────────────────────────────────────────────────────────────────
RESET = "\033[0m"

def _c(codes, s): return f"\033[{codes}m{s}{RESET}"
def red(s):       return _c("1;91", s)
def green(s):     return _c("1;92", s)
def yellow(s):    return _c("1;93", s)
def cyan(s):      return _c("1;96", s)
def white(s):     return _c("1;97", s)
def bold(s):      return _c("1",    s)
def dim(s):       return _c("2",    s)


# ─────────────────────────────────────────────────────────────────────────────
#  Timing formatter  –  auto-selects µs / ms / s based on magnitude
# ─────────────────────────────────────────────────────────────────────────────
def fmt_ns(ns):
    """Return a human-readable string for a nanosecond count."""
    if ns < 0:
        return f"{ns} ns  (negative – see note above)"
    if ns < 1_000:
        return f"{ns} ns"
    if ns < 1_000_000:
        return f"{ns / 1e3:.3f} µs  ({ns} ns)"
    if ns < 1_000_000_000:
        return f"{ns / 1e6:.3f} ms  ({ns} ns)"
    return f"{ns / 1e9:.6f} s  ({ns} ns)"


# ─────────────────────────────────────────────────────────────────────────────
#  Terminal grid printer
# ─────────────────────────────────────────────────────────────────────────────
def print_grid_terminal(grid, is_solution=False, puzzle_ref=None):
    S = "━" * 17
    s = "─" * 17

    top = white("┏" + S + "┯" + S + "┯" + S + "┓")
    mid = dim(  "┠" + s + "┼" + s + "┼" + s + "┨")
    box = white("┣" + S + "╪" + S + "╪" + S + "┫")
    bot = white("┗" + S + "┷" + S + "┷" + S + "┛")

    print(top)
    for r in range(9):
        parts = []
        for c in range(9):
            parts.append(bold("┃") if c % 3 == 0 else dim("│"))
            val = grid[r * 9 + c]
            if is_solution and puzzle_ref is not None:
                given = (puzzle_ref[r * 9 + c] != 0)
                digit = red(str(val)) if given else green(str(val))
            else:
                digit = red(str(val)) if val != 0 else dim("_")
            parts.append(f"  {digit}  ")
        parts.append(bold("┃"))
        print("".join(parts))
        if r < 8:
            print(box if (r + 1) % 3 == 0 else mid)
    print(bot)


# ─────────────────────────────────────────────────────────────────────────────
#  PNG generator
# ─────────────────────────────────────────────────────────────────────────────
def save_image(puzzle, solution, solve_ns, corrected_ns, output_dir='.'):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print(yellow("  [Image] Pillow not installed – skipping PNG.  "
                     "Run:  pip install pillow"))
        return None

    def load(path, size):
        for p in [path,
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"]:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def load_reg(path, size):
        for p in [path,
                  "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()

    MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
    SANS_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    SANS_R = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

    f_title = load(SANS_B, 36)
    f_label = load(SANS_B, 24)
    f_digit = load(MONO_B, 38)
    f_empty = load(MONO_B, 32)
    f_stat  = load(SANS_B, 20)
    f_stamp = load_reg(SANS_R, 17)
    f_arrow = load(SANS_B, 56)
    f_leg   = load_reg(SANS_R, 16)

    BG          = ( 13,  14,  26)
    PANEL_BG    = ( 20,  23,  42)
    PANEL_BORD  = ( 55,  62, 100)
    BOX_TINT    = ( 27,  31,  54)
    LINE_THICK  = (100, 112, 168)
    LINE_THIN   = ( 45,  52,  82)
    GIVEN_FG    = (232,  74,  74)
    SOLVED_FG   = ( 68, 212, 152)
    EMPTY_FG    = ( 82,  88, 124)
    TITLE_FG    = (228, 234, 255)
    LABEL_FG    = (148, 164, 218)
    STAT_FG     = (255, 208,  60)
    STAT2_FG    = (130, 200, 255)
    STAMP_FG    = ( 80,  88, 126)
    ARROW_FG    = ( 88, 118, 205)
    SEP_LINE    = ( 50,  56,  92)

    CELL      = 68
    INNER_PAD = 44
    GAP       = 84
    OUTER     = 44
    TOP_H     = 100
    BOT_H     = 110          # taller footer for two timing lines
    LABEL_H   = 36

    grid_px = 9 * CELL
    panel_w = grid_px + 2 * INNER_PAD
    panel_h = grid_px + 2 * INNER_PAD + LABEL_H
    total_w = 2 * panel_w + GAP + 2 * OUTER
    total_h = TOP_H + panel_h + BOT_H + 2 * OUTER

    img  = Image.new("RGB", (total_w, total_h), BG)
    draw = ImageDraw.Draw(img)

    def centred(text, cx, cy, font, fill):
        bb = draw.textbbox((0, 0), text, font=font)
        w, h = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((cx - w // 2, cy - h // 2), text, font=font, fill=fill)

    centred("FPGA Sudoku Solver",
            total_w // 2, OUTER + TOP_H // 2, f_title, TITLE_FG)

    arrow_cx = OUTER + panel_w + GAP // 2
    arrow_cy = OUTER + TOP_H + LABEL_H + INNER_PAD + grid_px // 2
    centred("\u2192", arrow_cx, arrow_cy, f_arrow, ARROW_FG)

    def draw_grid(ox, oy, grid, is_solved):
        card_x0 = ox - INNER_PAD
        card_y0 = oy - INNER_PAD - LABEL_H
        card_x1 = ox + grid_px + INNER_PAD
        card_y1 = oy + grid_px + INNER_PAD
        draw.rounded_rectangle(
            [card_x0, card_y0, card_x1, card_y1],
            radius=20, fill=PANEL_BG, outline=PANEL_BORD, width=2)
        for br in range(3):
            for bc in range(3):
                if (br + bc) % 2 == 0:
                    bx0 = ox + bc * 3 * CELL + 2
                    by0 = oy + br * 3 * CELL + 2
                    draw.rectangle(
                        [bx0, by0, bx0 + 3 * CELL - 3, by0 + 3 * CELL - 3],
                        fill=BOX_TINT)
        for k in range(10):
            thick = (k % 3 == 0)
            col = LINE_THICK if thick else LINE_THIN
            lw  = 3 if thick else 1
            draw.line([(ox + k * CELL, oy), (ox + k * CELL, oy + grid_px)],
                      fill=col, width=lw)
            draw.line([(ox, oy + k * CELL), (ox + grid_px, oy + k * CELL)],
                      fill=col, width=lw)
        for idx, val in enumerate(grid):
            r, c = divmod(idx, 9)
            cx = ox + c * CELL + CELL // 2
            cy = oy + r * CELL + CELL // 2
            given = (puzzle[idx] != 0)
            if is_solved:
                colour = GIVEN_FG if given else SOLVED_FG
                centred(str(val), cx, cy, f_digit, colour)
            else:
                if val != 0:
                    centred(str(val), cx, cy, f_digit, GIVEN_FG)
                else:
                    centred("_", cx, cy, f_empty, EMPTY_FG)

    def panel_label(ox, oy, text):
        centred(text, ox + grid_px // 2, oy - LABEL_H // 2, f_label, LABEL_FG)

    grid_y = OUTER + TOP_H + LABEL_H + INNER_PAD
    lx     = OUTER + INNER_PAD
    rx     = OUTER + panel_w + GAP + INNER_PAD

    draw_grid(lx, grid_y, puzzle,   is_solved=False)
    draw_grid(rx, grid_y, solution, is_solved=True)
    panel_label(lx, grid_y, "PUZZLE")
    panel_label(rx, grid_y, "SOLUTION")

    leg_y = grid_y + grid_px + 18
    dot_r = 7
    items = [
        (GIVEN_FG,  "Given digit",       lx),
        (SOLVED_FG, "Solved digit",      lx + 170),
        (EMPTY_FG,  "Empty cell  ( _ )", lx + 345),
    ]
    for colour, label, bx in items:
        draw.ellipse(
            [(bx, leg_y - dot_r), (bx + 2 * dot_r, leg_y + dot_r)],
            fill=colour)
        draw.text((bx + 2 * dot_r + 8, leg_y - 9), label,
                  font=f_leg, fill=colour)

    # ── footer  (two timing lines) ────────────────────────────────────────────
    footer_y = total_h - BOT_H - OUTER // 2
    draw.line([(OUTER, footer_y), (total_w - OUTER, footer_y)],
              fill=SEP_LINE, width=1)

    # Line 1: raw measured time
    raw_str = fmt_ns(solve_ns)
    centred(f"\u23f1  FPGA solve time (measured):  {raw_str}",
            total_w // 2, footer_y + 24, f_stat, STAT_FG)

    # Line 2: UART-latency-corrected estimate
    cor_str = fmt_ns(corrected_ns)
    centred(f"\u2699  FPGA solve time (corrected): {cor_str}",
            total_w // 2, footer_y + 56, f_stat, STAT2_FG)

    ts = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    centred(f"Generated: {ts}",
            total_w // 2, footer_y + 88, f_stamp, STAMP_FG)

    fname = "sudoku_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
    fpath = os.path.join(output_dir, fname)
    os.makedirs(output_dir, exist_ok=True)
    img.save(fpath, dpi=(150, 150))
    return fpath


# ─────────────────────────────────────────────────────────────────────────────
#  Terminal helpers
# ─────────────────────────────────────────────────────────────────────────────
def sep(char="─", width=62):
    print(dim(char * width))

def header(text):
    sep("═")
    print(f"  {cyan(text)}")
    sep("═")

def info(label, value):
    print(f"  {dim(label + ':')}  {white(value)}")


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    assert len(puzzle) == 81,                "Puzzle must have exactly 81 cells"
    assert all(0 <= v <= 9 for v in puzzle), "All values must be 0-9"

    header("FPGA Sudoku Solver")
    print()
    print(f"  {yellow('INPUT PUZZLE')}  "
          f"{dim('( red = given digit  |  _ = empty cell )')}")
    print()
    print_grid_terminal(puzzle, is_solution=False)
    print()

    # ── connect ───────────────────────────────────────────────────────────────
    sep()
    print(f"  Connecting to Basys3 on {white(COM_PORT)} "
          f"@ {white(str(BAUD))} baud ...")
    sep()

    try:
        ser = serial.Serial(COM_PORT, BAUD, timeout=10)
    except serial.SerialException as e:
        print(f"\n  {red('ERROR')} - Cannot open serial port: {e}\n")
        sys.exit(1)

    time.sleep(3)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    print(f"  {green('Connected.')}  Sending 81 bytes ...\n")

    # ── send puzzle ───────────────────────────────────────────────────────────
    # Send ALL 81 bytes in ONE call.
    # Reasons:
    #   1. Eliminates per-byte Python loop overhead (~10 ms × 81 = ~810 ms wasted).
    #   2. Reduces OS scheduling jitter between bytes.
    #   3. Makes t_send_end a sharper reference point.
    #
    # The FPGA's top_basys3 state machine accepts bytes one at a time as
    # they arrive over UART, so sending them back-to-back is fine as long
    # as each byte arrives within the UART frame gap (which it will at
    # 115200 baud with USB-CDC).

    payload = bytes(puzzle)

    t_send_start_ns = time.perf_counter_ns()
    ser.write(payload)
    # ser.flush() ensures the OS has handed bytes to the USB driver.
    # On Windows this also waits for the TX buffer to drain.
    ser.flush()
    t_send_end_ns = time.perf_counter_ns()

    send_ns  = t_send_end_ns - t_send_start_ns
    send_ms  = send_ns / 1e6

    print(f"  {dim('Puzzle sent')}  "
          f"({dim(fmt_ns(send_ns))})")
    print(f"  {yellow('Waiting for FPGA ...')}\n")

    # ── receive first byte  (start of solution) ───────────────────────────────
    # t_first_byte_ns is stamped as soon as read(1) returns, which is as
    # close as Python can get to the moment the byte arrived.
    t_first_byte_ns = time.perf_counter_ns()
    first = ser.read(1)
    t_first_byte_ns = time.perf_counter_ns()   # re-stamp AFTER blocking read

    if len(first) == 0:
        ser.close()
        print(f"  {red('TIMEOUT')} - No response from FPGA.\n")
        sys.exit(1)

    if first[0] == 0xFF:
        ser.close()
        elapsed_ns = t_first_byte_ns - t_send_end_ns
        print(f"  {red('NO SOLUTION')} - FPGA reports this puzzle is unsolvable.")
        info("Response time", fmt_ns(elapsed_ns))
        print()
        sys.exit(0)

    # ── receive remaining 80 bytes ────────────────────────────────────────────
    rest  = ser.read(80)
    t_end_ns = time.perf_counter_ns()
    ser.close()

    if len(rest) < 80:
        print(f"  {red('ERROR')} - Received only {1 + len(rest)}/81 bytes.\n")
        sys.exit(1)

    raw = list(first + rest)
    if any(b < 0x30 or b > 0x39 for b in raw):
        print(f"  {red('ERROR')} - Out-of-range bytes received: {raw}\n")
        sys.exit(1)

    solution = [b - 0x30 for b in raw]

    # ── timing calculations ───────────────────────────────────────────────────
    #
    # solve_ns (raw, measured by Python)
    # ====================================
    # = time from write() returning  →  first reply byte arriving
    # This is the most honest Python-side measurement.
    # It still contains UART serialisation latency on both ends.
    #
    # corrected_ns (best-effort true solve estimate)
    # ================================================
    # Subtract:
    #   • 1 UART byte time for the last puzzle byte to finish transmitting
    #     (write() returns before the USB-UART chip has clocked it out)
    #   • 1 UART byte time for the first reply byte to finish transmitting
    #     before Python's read() can see it
    # These two corrections together = 2 × UART_BYTE_NS ≈ 174 µs
    #
    # total_ns = full Python-visible round trip
    #
    solve_ns     = t_first_byte_ns - t_send_end_ns
    corrected_ns = solve_ns - 2 * UART_BYTE_NS
    total_ns     = t_end_ns - t_send_start_ns

    # ── print solution ────────────────────────────────────────────────────────
    print(f"  {green('SOLVED!')}  "
          f"{dim('( red = given digit  |  green = solved digit )')}\n")
    print_grid_terminal(solution, is_solution=True, puzzle_ref=puzzle)
    print()

    # ── timing summary ────────────────────────────────────────────────────────
    sep()
    print(f"  {yellow('TIMING SUMMARY')}")
    sep()
    info("Send time (write+flush)  ", fmt_ns(send_ns))
    print()
    info("FPGA solve  [RAW]        ", fmt_ns(solve_ns))
    print(f"  {dim('  Raw = time between Python write() returning and first reply byte')}")
    print(f"  {dim('  Includes ~87 µs last-TX-byte delay + ~87 µs first-RX-byte delay')}")
    print()
    info("FPGA solve  [CORRECTED]  ", fmt_ns(corrected_ns))
    print(f"  {dim('  Corrected = Raw − 2 × one UART byte time (~174 µs total)')}")
    print(f"  {dim('  Best-effort estimate of true hardware solve time')}")
    print()
    info("Total round-trip         ", fmt_ns(total_ns))
    sep()
    print()

    # ── generate PNG ──────────────────────────────────────────────────────────
    print(f"  {cyan('Generating image ...')}")
    fpath = save_image(puzzle, solution, solve_ns, corrected_ns,
                       output_dir=OUTPUT_DIR)
    if fpath:
        print(f"  {green('Image saved  ->')}  {white(fpath)}\n")
    else:
        print(f"  {yellow('Image skipped (install Pillow:  pip install pillow).')}\n")


if __name__ == "__main__":
    main()