#!/usr/bin/env python3
"""產生標準的 K 線型態示意圖（含標註、成交量與判讀重點）。

用法：
  python draw_pattern.py --list                              # 列出所有型態代碼
  python draw_pattern.py head_shoulders_bottom -o out.png    # 單一型態示意圖
  python draw_pattern.py "W 底" -o out.png --convention us   # 也可用中文名稱；us = 綠漲紅跌
  python draw_pattern.py --all -o outdir/                    # 每個型態各一張
  python draw_pattern.py --sheet -o sheet.png                # 全部型態一覽表（講義用）
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kline_lib as K  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


def _header(fig, p, col, y=0.962):
    fig.text(0.03, y, p["name"], fontsize=22, fontweight="bold", color=K.INK, va="center")
    fig.text(0.03, y - 0.04, f'{p["en"]}　·　{p["type"]}', fontsize=11.5, color=K.MUTED, va="center")
    bias_color = {"bull": col["bull"], "bear": col["bear"]}.get(p["bias"], K.MUTED)
    K.chip(fig, 0.86, y, K.BIAS_LABEL[p["bias"]], bias_color)


def render_chart_pattern(p, col, out, seed=7):
    n = 64
    m = K.Mapper(n)
    rng = np.random.default_rng(seed)
    t, mid = K.sample_path(p["path"], n)
    ohlc = K.ohlc_from_mid(mid, rng, noise=1.0)
    xs = [m.x(u) for u in t]
    vol = K.volume_from_profile(p["vol"], t, rng)

    fig = plt.figure(figsize=(12, 7.8), dpi=150, facecolor=K.BG)
    gs = fig.add_gridspec(3, 1, height_ratios=[3.3, 0.7, 1.35], hspace=0.08, left=0.03, right=0.94, top=0.89,
                          bottom=0.05)
    ax, axv, axn = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
    K.style_axes(ax)
    K.draw_candles(ax, ohlc, xs, col)
    lo, hi = K.overlay_limits(p, m, [c[1] for c in ohlc] + [c[2] for c in ohlc])
    ax.set_ylim(lo, hi)
    ax.set_xlim(-1.5, n + 9)
    ax.set_xticks([])
    ax.set_yticklabels([])
    K.draw_overlays(ax, p, m, col)
    K.style_axes(axv)
    axv.set_xlim(ax.get_xlim())
    axv.set_xticks([])
    K.draw_volume(axv, vol, ohlc, xs, col)
    K.draw_notes(axn, p["notes"], col)
    _header(fig, p, col)
    fig.text(0.03, 0.012, f'示意圖‧教學用途，非投資建議　|　{col["label"]}　|　藍線＝型態結構　橘線＝頸線／關鍵價　紫色＝目標價',
             fontsize=9, color=K.MUTED)
    fig.savefig(out, facecolor=K.BG)
    plt.close(fig)


def render_candle_pattern(p, col, out):
    candles = p["candles"]
    xs = list(range(len(candles)))
    fig = plt.figure(figsize=(12, 7.8), dpi=150, facecolor=K.BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[3.6, 1.35], hspace=0.1, left=0.03, right=0.94, top=0.89, bottom=0.05)
    ax, axn = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    K.style_axes(ax)
    K.draw_candles(ax, candles, xs, col, width=0.58)
    lows, highs = [c[2] for c in candles], [c[1] for c in candles]
    span = max(highs) - min(lows)
    ax.set_ylim(min(lows) - span * 0.18, max(highs) + span * 0.32)
    ax.set_xlim(-0.8, len(candles) - 0.2)
    ax.set_xticks([])
    ax.set_yticklabels([])
    a, b = p["highlight"]
    seg = candles[a:b + 1]
    above = p["bias"] != "bull"
    K.highlight_box(ax, a, b, min(c[2] for c in seg), max(c[1] for c in seg), K.STRUCT, p["label"], above=True)
    trend = "前段下跌" if candles[0][3] > candles[a - 1][3] else "前段上漲"
    ax.annotate("", (a - 1.2, candles[a - 1][3]), xytext=(0, candles[0][3]),
                arrowprops=dict(arrowstyle="-|>", color=K.MUTED, lw=1.4, ls=(0, (4, 3)), alpha=0.8))
    ax.text(0.2, candles[0][3] + span * (0.06 if trend == "前段上漲" else -0.06), trend, color=K.MUTED, fontsize=11,
            va="bottom" if trend == "前段上漲" else "top")
    del above
    K.draw_notes(axn, p["notes"], col)
    _header(fig, p, col)
    fig.text(0.03, 0.012, f'示意圖‧教學用途，非投資建議　|　{col["label"]}', fontsize=9, color=K.MUTED)
    fig.savefig(out, facecolor=K.BG)
    plt.close(fig)


def render(p, col, out):
    if p["kind"] == "candle":
        render_candle_pattern(p, col, out)
    else:
        render_chart_pattern(p, col, out)


def render_sheet(col, out):
    pats = list(K.PATTERNS.values())
    cols = 4
    rows = (len(pats) + cols - 1) // cols
    fig = plt.figure(figsize=(16, 3.3 * rows + 1.2), dpi=130, facecolor=K.BG)
    top = 1 - 1.0 / (3.3 * rows + 1.2)
    gs = fig.add_gridspec(rows, cols, left=0.02, right=0.98, top=top, bottom=0.02, hspace=0.42, wspace=0.08)
    fig.text(0.02, 1 - 0.45 / (3.3 * rows + 1.2), "K 線型態一覽表", fontsize=24, fontweight="bold", color=K.INK,
             va="center")
    fig.text(0.98, 1 - 0.45 / (3.3 * rows + 1.2), f'{col["label"]}　·　示意圖，教學用途', fontsize=12, color=K.MUTED,
             va="center", ha="right")
    for i, p in enumerate(pats):
        ax = fig.add_subplot(gs[i // cols, i % cols])
        K.style_axes(ax, right_price=False)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color("#dbe3e8")
        bias_color = {"bull": col["bull"], "bear": col["bear"]}.get(p["bias"], K.MUTED)
        ax.set_title(f'{p["name"]}', loc="left", fontsize=13.5, fontweight="bold", color=K.INK, pad=6)
        ax.text(1.0, 1.035, K.BIAS_LABEL[p["bias"]], transform=ax.transAxes, ha="right", va="bottom", fontsize=10.5,
                color="white", fontweight="bold", bbox=dict(boxstyle="round,pad=0.25", fc=bias_color, ec="none"))
        if p["kind"] == "candle":
            c = p["candles"]
            K.draw_candles(ax, c, range(len(c)), col, width=0.58)
            a, b = p["highlight"]
            seg = c[a:b + 1]
            span = max(x[1] for x in c) - min(x[2] for x in c)
            K.highlight_box(ax, a, b, min(x[2] for x in seg), max(x[1] for x in seg), K.STRUCT, "", above=True)
            ax.set_ylim(min(x[2] for x in c) - span * 0.1, max(x[1] for x in c) + span * 0.15)
            ax.set_xlim(-0.8, len(c) - 0.2)
        else:
            n = 46
            m = K.Mapper(n)
            t, mid = K.sample_path(p["path"], n)
            ohlc = K.ohlc_from_mid(mid, np.random.default_rng(3), noise=0.8)
            K.draw_candles(ax, ohlc, [m.x(u) for u in t], col, width=0.6)
            lo, hi = K.overlay_limits(p, m, [x[1] for x in ohlc] + [x[2] for x in ohlc])
            ax.set_ylim(lo, hi)
            ax.set_xlim(-1, n + 1)
            q = dict(p)
            q["lines"] = [(a, b, "", s) for a, b, _t, s in p["lines"]]
            q["points"] = [(x, y, t, pos) for x, y, t, pos in p["points"] if len(t) <= 2]
            K.draw_overlays(ax, q, m, col, show_target=False, fs=9.5, label_break=False)
    fig.savefig(out, facecolor=K.BG)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", nargs="?", help="型態代碼或中文名稱")
    ap.add_argument("-o", "--out", default="pattern.png", help="輸出檔名（--all 時為資料夾）")
    ap.add_argument("--convention", choices=["tw", "us"], default="tw", help="tw=紅漲綠跌（預設），us=綠漲紅跌")
    ap.add_argument("--list", action="store_true", help="列出所有型態")
    ap.add_argument("--all", action="store_true", help="輸出所有型態各一張")
    ap.add_argument("--sheet", action="store_true", help="輸出全部型態一覽表")
    ap.add_argument("--down", action="store_true", help="箱型、對稱三角形改畫向下跌破的版本")
    a = ap.parse_args()
    K.setup_fonts()
    col = K.colors(a.convention)
    if a.list:
        for k, name, en, kind, typ in K.list_patterns():
            print(f"{k:24s} {name}｜{en}｜{'K線組合' if kind == 'candle' else '圖表型態'}｜{typ}")
        return
    if a.sheet:
        render_sheet(col, a.out)
        print(a.out)
        return
    if a.all:
        os.makedirs(a.out, exist_ok=True)
        for i, p in enumerate(K.PATTERNS.values(), 1):
            path = os.path.join(a.out, f"{i:02d}_{p['key']}.png")
            render(p, col, path)
            print(path)
        return
    if not a.pattern:
        ap.error("請指定型態，或用 --list 查看可用型態")
    p = K.find_pattern(a.pattern)
    if a.down:
        p = K.breakdown_variant(p)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    render(p, col, a.out)
    print(a.out)


if __name__ == "__main__":
    main()
