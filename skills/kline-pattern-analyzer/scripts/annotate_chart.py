#!/usr/bin/env python3
"""在使用者上傳的 K 線截圖上疊加型態標註（頸線、關鍵點、突破箭頭、說明）。

座標一律用「比例座標」：x、y 都是 0–1，原點在圖片左上角（x 往右、y 往下），
例如 {"x": 0.42, "y": 0.18} 代表從左邊 42%、從上面 18% 的位置。

用法：
  python annotate_chart.py --image chart.png --info                    # 看尺寸與明暗
  python annotate_chart.py --image chart.png --grid -o grid.png        # 畫 10% 格線，輔助定位
  python annotate_chart.py --image chart.png --spec spec.json -o out.png

spec.json 範例：
{
  "title": "頭肩底（形成中）",
  "subtitle": "判讀信心：中｜日K｜台股配色",
  "convention": "tw",
  "bias": "bull",
  "verdict": "看漲（中）",
  "polyline": [[0.18,0.55],[0.27,0.40],[0.36,0.72],[0.47,0.41],[0.58,0.57]],
  "points": [{"x":0.18,"y":0.55,"label":"左肩","pos":"below"}],
  "lines":  [{"from":[0.22,0.40],"to":[0.80,0.38],"label":"頸線","kind":"neck"},
             {"from":[0.60,0.38],"to":[0.90,0.38],"label":"站上 410 看漲成立","kind":"bull"},
             {"from":[0.60,0.57],"to":[0.90,0.57],"label":"跌破 375 轉看空","kind":"bear"}],
  "zones":  [{"x0":0.15,"y0":0.30,"x1":0.62,"y1":0.78,"label":"型態區間"}],
  "arrows": [{"from":[0.62,0.45],"to":[0.70,0.25],"label":"突破後目標","kind":"bull"}],
  "notes":  ["三個低點中間最低，左右肩高度接近。", "尚未收盤突破頸線，屬形成中。"]
}
kind 可用：struct（藍，型態結構）、neck（橘，頸線／關鍵價）、support、resistance、target（紫）、
bull（看漲色，多方門檻）、bear（看空色，空方門檻）。
bias 決定右上角標籤顏色（bull / bear / neutral），verdict 是標籤文字，例如「看漲（強）」「看空（中）」「中性（等突破）」。
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kline_lib as K  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

LIGHT = {"struct": "#2563eb", "neck": "#e08a00", "support": "#0f9fb0", "resistance": "#e08a00",
         "target": "#7c3aed", "text": "#1d2a33", "muted": "#5b6b76", "halo": "#ffffff", "band": "#ffffff"}
DARK = {"struct": "#6ea8ff", "neck": "#ffb020", "support": "#3fd0e0", "resistance": "#ffb020",
        "target": "#b48cff", "text": "#e8eef2", "muted": "#9fb0bb", "halo": "#0b1015", "band": "#11171d"}


def load_image(path):
    img = plt.imread(path)
    if img.dtype != np.float32 and img.dtype != np.float64:
        img = img.astype(np.float32) / 255.0
    if img.ndim == 2:
        img = np.stack([img] * 3, axis=-1)
    return img


def luminance(img):
    rgb = img[..., :3]
    return float((0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]).mean())


NO_LINE_START = "，。、；：！？）」』》%％,.;:!?)"


def wrap(text, width):
    """中英混排的簡易斷行：中文字算 1 格、英數算 0.55 格。"""
    lines, cur, w = [], "", 0.0
    for ch in text:
        cw = 0.55 if ord(ch) < 0x2E80 else 1.0
        if w + cw > width and cur and ch not in NO_LINE_START:
            lines.append(cur)
            cur, w = "", 0.0
        cur += ch
        w += cw
    if cur:
        lines.append(cur)
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", required=True)
    ap.add_argument("--spec")
    ap.add_argument("-o", "--out", default="annotated.png")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--grid", action="store_true", help="疊上 10% 座標格線（定位輔助）")
    a = ap.parse_args()
    K.setup_fonts()
    img = load_image(a.image)
    H, W = img.shape[:2]
    lum = luminance(img)
    dark = lum < 0.45
    if a.info:
        print(json.dumps({"width": W, "height": H, "luminance": round(lum, 3), "theme": "dark" if dark else "light"}))
        return
    spec = {}
    if a.spec:
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
    pal = DARK if dark else LIGHT
    conv = K.colors(spec.get("convention", "tw"))
    pal = dict(pal, bull=conv["bull"], bear=conv["bear"])

    disp_w = max(W, 1100)
    scale = disp_w / W
    img_h_in, fig_w_in = H * scale / 100, disp_w / 100
    fs = 13 * (fig_w_in / 11) ** 0.5
    notes = spec.get("notes", [])
    chars = (disp_w - 90) / (fs * 100 / 72)
    note_lines = [wrap("‧ " + n, chars) for n in notes]
    n_lines = sum(len(x) for x in note_lines)
    header_in = 0.95 if spec.get("title") else 0
    notes_in = (0.32 + n_lines * fs * 1.75 / 72) if notes else 0
    foot_in = 0.32
    fig_h = header_in + img_h_in + notes_in + foot_in
    fig = plt.figure(figsize=(fig_w_in, fig_h), dpi=100, facecolor=pal["band"])
    img_bottom = (notes_in + foot_in) / fig_h
    ax = fig.add_axes([0, img_bottom, 1, img_h_in / fig_h])
    ax.imshow(img, extent=[0, 1, 1, 0], aspect="auto", interpolation="lanczos")
    ax.set_xlim(0, 1)
    ax.set_ylim(1, 0)
    ax.axis("off")
    h = K.halo(pal["halo"], 4.5)

    if a.grid:
        for v in np.arange(0.1, 1.0, 0.1):
            ax.axvline(v, color="#ff2d55", lw=0.8, alpha=0.55)
            ax.axhline(v, color="#ff2d55", lw=0.8, alpha=0.55)
            ax.text(v, 0.012, f"{v:.1f}", color="#ff2d55", fontsize=fs * 0.75, ha="center", va="top", path_effects=h)
            ax.text(0.006, v, f"{v:.1f}", color="#ff2d55", fontsize=fs * 0.75, ha="left", va="center", path_effects=h)

    def c(kind, default="struct"):
        return pal.get(kind or default, pal["struct"])

    for z in spec.get("zones", []):
        x0, x1 = sorted([z["x0"], z["x1"]])
        y0, y1 = sorted([z["y0"], z["y1"]])
        col = c(z.get("kind"))
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=col, alpha=0.1, ec="none", zorder=2))
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=col, lw=1.6, ls=(0, (5, 4)), zorder=3))
        if z.get("label"):
            ax.text(x0 + 0.005, y0 + 0.008, z["label"], color=col, fontsize=fs * 0.9, fontweight="bold", va="top",
                    path_effects=h, zorder=9)
    if spec.get("polyline"):
        pts = np.array(spec["polyline"], float)
        ax.plot(pts[:, 0], pts[:, 1], color=c(spec.get("polyline_kind")), lw=3, alpha=0.85, solid_joinstyle="round",
                path_effects=K.halo(pal["halo"], 6), zorder=4)
    for ln in spec.get("lines", []):
        (x1, y1), (x2, y2) = ln["from"], ln["to"]
        col = c(ln.get("kind"), "neck")
        ax.plot([x1, x2], [y1, y2], color=col, lw=2.6, ls=(0, (7, 4)), path_effects=K.halo(pal["halo"], 5), zorder=5)
        if ln.get("label"):
            right = x2 < 0.86
            ax.text(x2 + (0.008 if right else -0.008), y2, ln["label"], color=col, fontsize=fs, fontweight="bold",
                    ha="left" if right else "right", va="center" if right else "bottom", path_effects=h, zorder=9)
    for ar in spec.get("arrows", []):
        col = c(ar.get("kind"), "target")
        ax.annotate("", tuple(ar["to"]), xytext=tuple(ar["from"]), zorder=8,
                    arrowprops=dict(arrowstyle="-|>,head_width=0.45,head_length=0.8", color=col, lw=3,
                                    path_effects=K.halo(pal["halo"], 6)))
        if ar.get("label"):
            tx, ty = ar["to"]
            ax.text(tx + 0.008, ty, ar["label"], color=col, fontsize=fs, fontweight="bold", ha="left", va="center",
                    path_effects=h, zorder=9)
    off = {"above": (0, -0.045), "below": (0, 0.045), "left": (-0.02, 0), "right": (0.02, 0)}
    align = {"above": ("center", "bottom"), "below": ("center", "top"), "left": ("right", "center"),
             "right": ("left", "center")}
    for p in spec.get("points", []):
        col = c(p.get("kind"))
        pos = p.get("pos", "above")
        ax.plot(p["x"], p["y"], "o", ms=12, mfc="none", mec=col, mew=3, path_effects=K.halo(pal["halo"], 6), zorder=7)
        if p.get("label"):
            dx, dy = off.get(pos, off["above"])
            ha, va = align.get(pos, align["above"])
            ax.text(p["x"] + dx, p["y"] + dy, p["label"], color=col, fontsize=fs * 1.05, fontweight="bold", ha=ha,
                    va=va, path_effects=h, zorder=9)

    if spec.get("title"):
        top = 1 - (header_in * 0.42) / fig_h
        fig.text(0.02, top, spec["title"], fontsize=fs * 1.6, fontweight="bold", color=pal["text"], va="center")
        if spec.get("subtitle"):
            fig.text(0.02, 1 - (header_in * 0.8) / fig_h, spec["subtitle"], fontsize=fs * 0.9, color=pal["muted"],
                     va="center")
        bias = spec.get("bias")
        label = spec.get("verdict") or K.BIAS_LABEL.get(bias)
        if label:
            bc = {"bull": pal["bull"], "bear": pal["bear"]}.get(bias, "#6b7a85")
            fig.text(0.98, top, label, fontsize=fs, color="white", fontweight="bold", ha="right",
                     va="center", bbox=dict(boxstyle="round,pad=0.35", fc=bc, ec="none"))
    if notes:
        y = (notes_in + foot_in - 0.18) / fig_h
        step = fs * 1.75 / 72 / fig_h
        for block in note_lines:
            for i, ln in enumerate(block):
                fig.text(0.02 + (0 if i == 0 else 0.016), y, ln, fontsize=fs, color=pal["text"], va="top")
                y -= step
    fig.text(0.02, 0.12 / fig_h, "AI 輔助判讀‧僅供學習參考，非投資建議；標註位置為估計，請以原圖價格為準",
             fontsize=fs * 0.72, color=pal["muted"], va="bottom")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    fig.savefig(a.out, facecolor=pal["band"])
    plt.close(fig)
    print(a.out)


if __name__ == "__main__":
    main()
