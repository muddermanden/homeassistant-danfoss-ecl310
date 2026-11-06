"""Circuit 1 as the author's house has it: direct heating with a mixing loop (mixing loop), no heat exchanger.

Water path, circuit 1:
  supply in -> T1 (bypass joins) -> S3 -> P2 (Grundfos) -> radiators -> return
  -> T2 (bypass branches off, vertical bypass up to T1 with a valve symbol, black on top = return -> supply)
  -> M2 -> T with the DHW return -> out to level 2. (The only check valve is the one in the bypass.)
Circuit 2 (DHW) keeps its heat exchanger and is unchanged.
"""
import re

BYPASS_X = 540          # where heat exchanger 1 used to be
S3_SHIFT = 0            # S3 stays where Danfoss draws it: after T1, before P2 (confirmed on site)
BLUE = "#1f61a3"


def _pipe(d, colour=BLUE):
    return (f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="5" '
            f'stroke-miterlimit="10" pointer-events="stroke"/>')


def _valve_symbol(cx, cy, vertical):
    """Danfoss black/white bow-tie; the black triangle sits on the downstream side."""
    if vertical:  # black on top
        black = f"M {cx - 15} {cy - 25} L {cx} {cy} L {cx + 15} {cy - 25} Z"
        white = f"M {cx - 15} {cy + 25} L {cx} {cy} L {cx + 15} {cy + 25} Z"
    else:         # black on the left (flow goes left)
        black = f"M {cx - 25} {cy - 15} L {cx} {cy} L {cx - 25} {cy + 15} Z"
        white = f"M {cx + 25} {cy - 15} L {cx} {cy} L {cx + 25} {cy + 15} Z"
    return (f'<path d="{black}" fill="#000000" stroke="rgb(0, 0, 0)"/>'
            f'<path d="{white}" fill="#ffffff" stroke="rgb(0, 0, 0)"/>')


def _drop_cell(svg, marker):
    """Remove the drawio cell group that contains `marker`."""
    i = svg.index(marker)
    start = svg.rindex('<g id="cell-', 0, i)
    nxt = svg.find('<g id="cell-', i)
    # a cell is a flat <g>...</g>; cut up to the last </g> before the next cell
    end = svg.rindex("</g>", i, nxt if nxt != -1 else len(svg)) + 4
    return svg[:start] + svg[end:]


def transform(svg):
    svg = _drop_cell(svg, '<rect x="480" y="140"')          # heat exchanger 1
    svg = _drop_cell(svg, 'data-title="S5"')                # no circuit-1 return sensor in a direct system
    # supply straight through to T1, and from T1 on to P2
    svg = svg.replace('d="M 30 160 L 480 160"', f'd="M 30 160 L {BYPASS_X} 160"', 1)
    svg = svg.replace('d="M 780 160 L 580 160"', f'd="M 780 160 L {BYPASS_X} 160"', 1)
    # radiator return to T2, and T2 on to M2
    svg = svg.replace('d="M 1200 320 L 915 320.5 L 580 320"', f'd="M 1200 320 L 915 320.5 L {BYPASS_X} 320"', 1)
    svg = svg.replace('d="M 325 320 L 480 320"', f'd="M 325 320 L {BYPASS_X} 320"', 1)
    if S3_SHIFT:
        svg = _shift_s3(svg)
    # bypass with its check valve (black on top: return -> supply)
    extra = (_pipe(f"M {BYPASS_X} 320 L {BYPASS_X} 265 M {BYPASS_X} 215 L {BYPASS_X} 160")
             + _valve_symbol(BYPASS_X, 240, vertical=True))
    k = svg.rindex("</svg>")
    return svg[:k] + extra + svg[k:]


def _shift_s3(svg):
    i = svg.index('data-title="S3"')
    g = svg.rindex('<g id="cell-', 0, i)
    gt = svg.index(">", g) + 1
    svg = svg[:gt] + f'<g transform="translate({S3_SHIFT},0)">' + svg[gt:]
    end = svg.index("</g></g>", gt) + len("</g></g>")
    return svg[:end] + "</g>" + svg[end:]


# overlay geometry for the direct layout (replaces live_symbols.PIPES / FLOWS entries)
PIPES = {
    "district_supply": ("sensor.heat_meter_flow_temperature",
                        f"M 40 160 L {BYPASS_X} 160 M 240 160 L 240 310 M 240 330 L 240 480 L 480 480"),
    "heating_supply": ("sensor.s3_flow_temperature_sensor_circuit_1",
                       f"M {BYPASS_X} 160 L 780 160 M 820 160 L 1200 160"),  # mixed water, from T1 on
}
FLOWS_DISTRICT = (f"M 40 160 L {BYPASS_X} 160 M 240 160 L 240 310 M 240 330 L 240 480 L 480 480 "
                  f"M {BYPASS_X} 320 L 325 320 M 275 320 L 40 320 "
                  "M 480 640 L 325 640 M 275 640 L 80 640 L 80 320")
FLOWS_HEATING = (f"M {BYPASS_X} 160 L 780 160 M 820 160 L 1200 160 M 1200 320 L {BYPASS_X} 320 "
                 f"L {BYPASS_X} 265 M {BYPASS_X} 215 L {BYPASS_X} 160")

# radiator inlet riser (T-off from the supply down to the radiator valve) follows the mixed-water colour too
PIPES["heating_supply"] = (PIPES["heating_supply"][0],
                           PIPES["heating_supply"][1] + " M 920 160 L 920.5 207 L 950 207")

# Bypass: no sensor in it. Bottom (T2) is coloured by the heat meter return (closest available; it also contains
# the DHW return), top (T1) by S3, with a vertical gradient between. Same temperature scale as the supply pipes, so
# the colour always means the same temperature; warm return water in the bypass therefore reads orange, not blue.
BYPASS_D = f"M {BYPASS_X} 320 L {BYPASS_X} 265 M {BYPASS_X} 215 L {BYPASS_X} 160"
BYPASS_BOTTOM = "sensor.heat_meter_return_temperature"
BYPASS_TOP = "sensor.s3_flow_temperature_sensor_circuit_1"


def bypass_overlays(svg, bands, overlay, uri, root):
    out = []
    for blo, bhi, bcol in bands:          # bottom (return) band
        for tlo, thi, tcol in bands:      # top (S3) band
            conds = []
            for entity, lo, hi in ((BYPASS_BOTTOM, blo, bhi), (BYPASS_TOP, tlo, thi)):
                c = {"condition": "numeric_state", "entity": entity}
                if lo is not None: c["above"] = lo
                if hi is not None: c["below"] = hi
                conds.append(c)
            grad = (f'<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="320" x2="0" y2="160">'
                    f'<stop offset="0" stop-color="{bcol}"/><stop offset="1" stop-color="{tcol}"/></linearGradient></defs>'
                    f'<path d="{BYPASS_D}" fill="none" stroke="url(#g)" stroke-width="5"/>')
            out.append(overlay(uri(root, grad), conds))
    grey = f'<path d="{BYPASS_D}" fill="none" stroke="#9e9e9e" stroke-width="5"/>'
    out.append(overlay(uri(root, grey), [{"condition": "or", "conditions": [
        {"condition": "state", "entity": e, "state": ["unavailable", "unknown"]} for e in (BYPASS_BOTTOM, BYPASS_TOP)]}]))
    return out


# --- One-pipe (single-string) radiator loop: the author's house has 8 radiators on one loop ---
# The radiator's inlet and outlet both tee into the same loop pipe; after the last radiator the loop turns
# down at the right edge and comes back along the bottom to T2 (bypass) and M2. No separate return header.
LOOP_OUTLET_X = 1160     # radiator outlet tee on the loop, downstream of the inlet tee (x 920)
LOOP_RIGHT_X = 1200
LOOP_DASH_END_X = 965   # dashed (unshown) part of the loop: back to about below the radiator's left edge, like the DHW loop
LOOP_DASH = "15 15"     # same dash as the DHW circulation line in circuit 2
MARKER_SHIFT_Y = 140     # the circled 1 moves below the loop so the pipes don't run through it
ONE_PIPE_MARKER = (1180, 240 + MARKER_SHIFT_Y)


def one_pipe(svg):
    # radiator outlet: up into the loop instead of down into a return header
    old = ('d="M 1130 275.71 L 1160.5 275.7 L 1160 320" fill="none" stroke="#1f61a3"')
    assert old in svg
    svg = svg.replace(old, f'd="M 1130 275.71 L {LOOP_OUTLET_X}.5 275.7 L {LOOP_OUTLET_X} 160" fill="none" stroke="#e2000f"', 1)
    # move the circled 1 down, below the loop
    i = svg.index('data-title="1"')
    gt = svg.index(">", i) + 1
    svg = svg[:gt] + f'<g transform="translate(0,{MARKER_SHIFT_Y})">' + svg[gt:]
    end = svg.index("</g></g>", gt) + len("</g></g>")
    svg = svg[:end] + "</g>" + svg[end:]
    # the loop after the radiator outlet stands for the radiators not drawn: dashed, like the DHW circulation line
    svg = svg.replace('d="M 820 160 L 1020 160 L 1200 160"', f'd="M 820 160 L {LOOP_OUTLET_X} 160"', 1)
    svg = svg.replace(f'd="M 1200 320 L 915 320.5 L {BYPASS_X} 320"',
                      f'd="M {LOOP_DASH_END_X} 320 L 915 320.5 L {BYPASS_X} 320"', 1)
    dashed = (f'<path d="{LOOP_DASHED_D}" fill="none" stroke="#e2000f" stroke-width="5" '
              f'stroke-miterlimit="10" stroke-dasharray="{LOOP_DASH}" pointer-events="stroke"/>')
    k = svg.rindex("</svg>")
    return svg[:k] + dashed + svg[k:]


# Loop colour: from T1 to the right edge (incl. the radiator stubs and the turn down) the S3 colour; the bottom run
# back to T2 cools along its length, a horizontal gradient from the S3 colour (right) to the return colour (left,
# heat meter return, same source as the bypass bottom).
LOOP_DASHED_D = f"M {LOOP_OUTLET_X} 160 L {LOOP_RIGHT_X} 160 L {LOOP_RIGHT_X} 320 L {LOOP_DASH_END_X} 320"
ONE_PIPE_SUPPLY = (f"M {BYPASS_X} 160 L 780 160 M 820 160 L {LOOP_OUTLET_X} 160 "
                   f"M 920 160 L 920.5 207 L 950 207 M 1130 275.71 L {LOOP_OUTLET_X}.5 275.7 L {LOOP_OUTLET_X} 160")
LOOP_RETURN_D = f"M {LOOP_DASH_END_X} 320 L 915 320.5 L {BYPASS_X} 320"
# flow dashes only on the solid pipes: the dashed (unshown) loop part would look dash-dotted
FLOWS_HEATING_ONE_PIPE = (f"M {BYPASS_X} 160 L 780 160 M 820 160 L {LOOP_OUTLET_X} 160 "
                          f"M {LOOP_DASH_END_X} 320 L {BYPASS_X} 320 L {BYPASS_X} 265 M {BYPASS_X} 215 L {BYPASS_X} 160")


def loop_return_overlays(svg, bands, overlay, uri, root):
    out = []
    for slo, shi, scol in bands:          # S3 band (right end)
        for rlo, rhi, rcol in bands:      # return band (left end)
            conds = []
            for entity, lo, hi in ((BYPASS_TOP, slo, shi), (BYPASS_BOTTOM, rlo, rhi)):
                c = {"condition": "numeric_state", "entity": entity}
                if lo is not None: c["above"] = lo
                if hi is not None: c["below"] = hi
                conds.append(c)
            grad = (f'<defs><linearGradient id="r" gradientUnits="userSpaceOnUse" x1="{LOOP_DASH_END_X}" y1="0" '
                    f'x2="{BYPASS_X}" y2="0"><stop offset="0" stop-color="{scol}"/>'
                    f'<stop offset="1" stop-color="{rcol}"/></linearGradient></defs>'
                    f'<path d="{LOOP_RETURN_D}" fill="none" stroke="url(#r)" stroke-width="5"/>')
            out.append(overlay(uri(root, grad), conds))
    return out


# Pipes that the colour overlays paint: neutral light grey in the base drawing, so no original red/blue shows
# at anti-aliased edges, corners or dash gaps (red specks showed at the loop corner).
UNDERLAY = "#d6d6d6"
OVERLAID = ["M 30 160 L 540 160", "M 240 160 L 240 310", "M 480 480 L 240 480 L 240 330",
            "M 780 160 L 540 160", "M 820 160 L 1160 160", "M 950 207 L 920.5 207 L 920 160",
            "M 1130 275.71 L 1160.5 275.7 L 1160 160", "M 965 320 L 915 320.5 L 540 320", "M 325 320 L 540 320",
            "M 40 320 L 275 320"]


def neutral_underlay(svg):
    for d in OVERLAID + [LOOP_DASHED_D, BYPASS_D]:
        svg, n = re.subn(r'(d="' + re.escape(d) + r'"[^>]*?stroke=")#[0-9a-fA-F]{6}(")', r"\g<1>" + UNDERLAY + r"\2", svg)
    return svg
