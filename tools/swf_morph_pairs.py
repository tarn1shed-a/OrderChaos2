"""Read paired solid DefineMorphShape geometry for original UI masks.

Adobe SWF19 pp145-146 (PDF146-147):
https://open-flash.github.io/mirrors/swf-spec-19.pdf
EndEdges keep geometry/MoveTo; StartEdges supply both shapes' style indices.
SVG projection is a browser adaptation, not an observation of Flash rasterization.
"""
import struct
from ui_assets import Bits
from swf_ui_graphics import paths


def edge_stream(raw, fills, lines, end=False):
    bits = Bits(raw)
    nf, nl = bits.u(4), bits.u(4)
    if end and (nf or nl):
        raise ValueError('EndEdges carry unexpected style bit widths')
    x = y = f0 = f1 = line = 0
    result = []
    for _ in range(100000):
        if bits.u(1):
            straight, size = bits.u(1), bits.u(4) + 2
            start = (x, y)
            if straight:
                if bits.u(1):
                    dx, dy = bits.s(size), bits.s(size)
                elif bits.u(1):
                    dx, dy = 0, bits.s(size)
                else:
                    dx, dy = bits.s(size), 0
                x += dx
                y += dy
                control = None
            else:
                control = (x + bits.s(size), y + bits.s(size))
                x, y = control[0] + bits.s(size), control[1] + bits.s(size)
            result.append(((start, control, (x, y)), (f0, f1, line)))
        else:
            flags = bits.u(5)
            if not flags:
                bits.align()
                if bits.pos() != len(raw):
                    raise ValueError('Trailing original morph edge bytes')
                return result
            if flags & 1:
                size = bits.u(5)
                x, y = bits.s(size), bits.s(size)
            if flags & 2:
                f0 = bits.u(nf)
            if flags & 4:
                f1 = bits.u(nf)
            if flags & 8:
                line = bits.u(nl)
            if flags & 16 or f0 > fills or f1 > fills or line > lines:
                raise ValueError('Uncovered original morph style change')
    raise ValueError('Morph edge record bound')


def morph_shape(kind, raw, *, ratio):
    if kind != 46 or type(ratio) is not int or not 0 <= ratio <= 65535:
        raise ValueError('Explicit original DefineMorphShape ratio required')
    try:
        bits = Bits(raw, 2)
        start_bounds, end_bounds = bits.rect(), bits.rect()
        offset_at = bits.pos()
        at = offset_at + 4
        end_at = at + struct.unpack_from('<I', raw, offset_at)[0]
        if not at < end_at < len(raw):
            raise ValueError('Original EndEdges outside source')
        def take(n):
            nonlocal at
            if at + n > end_at:
                raise ValueError('Truncated original morph styles')
            value = raw[at:at+n]
            at += n
            return value
        def count():
            n = take(1)[0]
            if n > 16:
                raise ValueError('Unsupported source morph style count')
            return n
        fills = []
        for _ in range(count()):
            if take(1) != b'\0':
                raise ValueError('Only solid original morph styles supported')
            fills.append((list(take(4)), list(take(4))))
        lines = []
        for _ in range(count()):
            widths = struct.unpack('<HH', take(4))
            lines.append((widths, list(take(4)), list(take(4))))
        a = edge_stream(raw[at:end_at], len(fills), len(lines))
        b = edge_stream(raw[end_at:], len(fills), len(lines), end=True)
    except (IndexError, struct.error) as error:
        raise ValueError('Truncated original morph record') from error
    if len(a) != len(b) or not a:
        raise ValueError('Original start/end edge counts differ')
    t = ratio / 65535
    mix = lambda x, y: x + (y-x) * t
    point = lambda x, y: tuple(mix(u, v) for u, v in zip(x, y))
    fill_edges, line_edges = [[] for _ in fills], [[] for _ in lines]
    for (left, styles), (right, _) in zip(a, b):
        ca, cb = left[1], right[1]
        if (ca is None) != (cb is None):
            ca = ca or tuple((u+v)/2 for u, v in zip(left[0], left[2]))
            cb = cb or tuple((u+v)/2 for u, v in zip(right[0], right[2]))
        edge = (point(left[0], right[0]), point(ca, cb) if ca is not None else None, point(left[2], right[2]))
        f0, f1, line = styles
        if f0:
            fill_edges[f0-1].append((edge[2], edge[1], edge[0]))
        if f1:
            fill_edges[f1-1].append(edge)
        if line:
            line_edges[line-1].append(edge)
    return {'boundsTwips': [mix(x, y) for x, y in zip(start_bounds, end_bounds)],
            'fillRule': 'evenodd',
            'fills': [{'paint': {'kind': 'solid', 'color': [mix(x, y) for x, y in zip(*colors)]},
                       'path': paths(edges, True)} for colors, edges in zip(fills, fill_edges) if edges],
            'lines': [{'paint': {'kind': 'solid', 'color': [mix(x, y) for x, y in zip(c0, c1)]},
                       'width': mix(*widths), 'cap': 0, 'join': 0,
                       'path': paths(edges, False)} for (widths, c0, c1), edges in zip(lines, line_edges) if edges],
            'sourceMorph': {'kind': kind, 'ratio': ratio, 'edgeCount': len(a),
                            'startEdgesSpan': [at, end_at], 'endEdgesSpan': [end_at, len(raw)],
                            'sourceRasterizationObserved': False}}
