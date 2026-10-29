"""K 線型態教練的共用函式：字型、配色、型態圖庫、K 棒產生與繪圖。

座標慣例：型態用「型態單位」描述，x 為 0–100（時間由左到右），y 為 0–100（價格由低到高）。
繪圖時再用 Mapper 換算成 K 棒索引與實際價格，所以單張示意圖與一覽表共用同一份型態定義。
"""
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patheffects as pe  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "..", "assets", "fonts")

# ---------------------------------------------------------------- fonts & colors

_fonts_ready = False


def setup_fonts():
    """註冊內建的 Noto Sans TC，讓中文標籤不會變成方塊。"""
    global _fonts_ready
    if _fonts_ready:
        return
    for fn in ("NotoSansTC-Regular.otf", "NotoSansTC-Bold.otf"):
        p = os.path.join(FONT_DIR, fn)
        if os.path.exists(p):
            font_manager.fontManager.addfont(p)
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Noto Sans TC", "Noto Sans CJK TC", "Microsoft JhengHei", "PingFang TC",
        "Heiti TC", "WenQuanYi Zen Hei", "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    _fonts_ready = True


INK = "#1d2a33"
MUTED = "#6b7a85"
GRID = "#e8edf1"
BG = "#ffffff"
STRUCT = "#2563eb"   # 型態結構線（藍）
NECK = "#e08a00"     # 頸線、關鍵壓力支撐（琥珀）
TARGET = "#7c3aed"   # 目標價（紫）

CONVENTIONS = {
    "tw": {"up": "#d93a3a", "down": "#14965a", "label": "台股配色：紅漲綠跌"},
    "us": {"up": "#14965a", "down": "#d93a3a", "label": "國際配色：綠漲紅跌"},
}


def colors(convention="tw"):
    c = CONVENTIONS.get(convention, CONVENTIONS["tw"])
    return {
        "up": c["up"], "down": c["down"], "bull": c["up"], "bear": c["down"],
        "struct": STRUCT, "neck": NECK, "target": TARGET, "neutral": MUTED,
        "ink": INK, "label": c["label"],
    }


def halo(color="#ffffff", width=4):
    return [pe.withStroke(linewidth=width, foreground=color)]


# ---------------------------------------------------------------- pattern library


def line(p1, p2):
    (x1, y1), (x2, y2) = p1, p2
    k = (y2 - y1) / (x2 - x1)
    return lambda x: y1 + k * (x - x1)


def _flip_pattern(p, **over):
    """把頂部型態上下翻轉成底部型態（或多頭翻空頭）。"""
    f = lambda y: 100 - y  # noqa: E731
    q = dict(p)
    q["path"] = [(x, f(y)) for x, y in p["path"]]
    q["points"] = [(x, f(y), t, "below" if pos == "above" else "above") for x, y, t, pos in p.get("points", [])]
    q["lines"] = [((a[0], f(a[1])), (b[0], f(b[1])), t, s) for a, b, t, s in p.get("lines", [])]
    if p.get("break"):
        x, y, t = p["break"]
        q["break"] = (x, f(y), t)
    if p.get("target"):
        t = dict(p["target"])
        t["from"], t["to"] = f(t["from"]), f(t["to"])
        q["target"] = t
    q["bias"] = {"bull": "bear", "bear": "bull"}.get(p["bias"], p["bias"])
    q.update(over)
    return q


def _hs_top():
    nk = line((20, 48), (42, 49))
    head, brk = 80, nk(62)
    return {
        "key": "head_shoulders_top", "name": "頭肩頂", "en": "Head and Shoulders Top",
        "type": "頂部反轉", "bias": "bear",
        "path": [(0, 26), (12, 60), (20, 48), (32, head), (42, 49), (54, 62), (62, brk), (66, 43),
                 (72, nk(72) - 2.5), (80, 33), (92, 24)],
        "points": [(12, 60, "左肩", "above"), (32, head, "頭", "above"), (54, 62, "右肩", "above")],
        "lines": [((12, nk(12)), (82, nk(82)), "頸線", "neck")],
        "break": (62, brk, "跌破頸線"),
        "target": {"x": 88, "from": brk, "to": brk - (head - nk(32)), "label": "目標價\n（頭到頸線的距離）"},
        "vol": [(0, 1.0), (12, 1.45), (20, 0.9), (32, 1.1), (42, 0.8), (54, 0.65), (62, 1.9), (70, 1.2), (92, 1.0)],
        "notes": {
            "辨識": "上漲末段出現三個高點，中間的「頭」最高，兩側肩部高度接近；兩個回檔低點連成頸線。",
            "確認": "收盤價跌破頸線，最好伴隨量增；跌破後常回測頸線但站不回去。",
            "失效": "跌破後又收回頸線之上，或股價直接突破右肩高點。",
            "目標": "量出「頭部到頸線」的垂直距離，從跌破點往下扣。",
        },
        "stage_cut": 60,
    }


def _hs_bottom():
    p = _flip_pattern(_hs_top(), key="head_shoulders_bottom", name="頭肩底", en="Head and Shoulders Bottom",
                      type="底部反轉")
    p["break"] = (p["break"][0], p["break"][1], "突破頸線")
    p["target"]["label"] = "目標價\n（頭到頸線的距離）"
    p["notes"] = {
        "辨識": "下跌末段出現三個低點，中間的「頭」最低，兩側肩部高度接近；兩個反彈高點連成頸線。",
        "確認": "收盤價帶量突破頸線；突破後常回測頸線並守住。",
        "失效": "突破後又跌回頸線之下，或股價跌破右肩低點。",
        "目標": "量出「頭部到頸線」的垂直距離，從突破點往上加。",
    }
    return p


def _double_top():
    nk = 52
    return {
        "key": "double_top", "name": "M 頭（雙重頂）", "en": "Double Top", "type": "頂部反轉", "bias": "bear",
        "path": [(0, 28), (18, 72), (32, nk), (46, 71), (56, nk), (60, 46), (66, nk - 1), (74, 40), (88, 30)],
        "points": [(18, 72, "第一頂", "above"), (46, 71, "第二頂", "above"), (32, nk, "頸線低點", "below")],
        "lines": [((10, nk), (80, nk), "頸線", "neck"), ((14, 72), (50, 72), "", "struct")],
        "break": (56, nk, "跌破頸線"),
        "target": {"x": 84, "from": nk, "to": nk - (72 - nk), "label": "目標價\n（頂部到頸線的距離）"},
        "vol": [(0, 1.0), (18, 1.5), (32, 0.9), (46, 1.0), (56, 1.8), (64, 1.1), (88, 1.0)],
        "notes": {
            "辨識": "上漲後兩次攻到相近高點都過不去，中間的回檔低點就是頸線；第二頂量能通常比第一頂小。",
            "確認": "收盤跌破頸線（中間低點），最好量增。",
            "失效": "跌破後收回頸線，或價格突破兩個頂部的高點。",
            "目標": "頂部到頸線的距離，從跌破點往下扣。",
        },
        "stage_cut": 54,
    }


def _double_bottom():
    p = _flip_pattern(_double_top(), key="double_bottom", name="W 底（雙重底）", en="Double Bottom", type="底部反轉")
    p["points"] = [(18, 28, "第一底", "below"), (46, 29, "第二底", "below"), (32, 48, "頸線高點", "above")]
    p["break"] = (p["break"][0], p["break"][1], "突破頸線")
    p["target"]["label"] = "目標價\n（底部到頸線的距離）"
    p["notes"] = {
        "辨識": "下跌後兩次探到相近低點都守住，中間的反彈高點就是頸線；第二底常出現量縮。",
        "確認": "收盤帶量突破頸線（中間高點）。",
        "失效": "突破後跌回頸線之下，或價格跌破兩個底部的低點。",
        "目標": "底部到頸線的距離，從突破點往上加。",
    }
    return p


def _asc_triangle():
    res, sup = 75, line((28, 58), (61, 70))
    return {
        "key": "ascending_triangle", "name": "上升三角形", "en": "Ascending Triangle", "type": "多頭中繼",
        "bias": "bull",
        "path": [(0, 32), (10, 52), (20, res), (28, 58), (38, res), (46, sup(46)), (55, res), (61, sup(61)),
                 (67, res), (71, 82), (76, 79), (88, 94)],
        "points": [],
        "lines": [((16, res), (74, res), "水平壓力", "neck"), ((24, sup(24)), (68, sup(68)), "低點墊高", "struct")],
        "break": (67.5, res, "帶量突破"),
        "target": {"x": 84, "from": res, "to": res + (res - 58), "label": "目標價\n（三角形高度）"},
        "vol": [(0, 1.1), (10, 1.2), (20, 1.0), (40, 0.8), (62, 0.55), (68, 1.9), (76, 1.2), (88, 1.0)],
        "notes": {
            "辨識": "上方是幾乎水平的壓力，下方低點一次比一次高，形成收斂的直角三角形；整理時量縮。",
            "確認": "收盤帶量突破水平壓力。",
            "失效": "突破後跌回三角形內，或跌破墊高的低點連線。",
            "目標": "三角形最寬處的高度，從突破點往上加。",
        },
        "stage_cut": 64,
    }


def _desc_triangle():
    p = _flip_pattern(_asc_triangle(), key="descending_triangle", name="下降三角形", en="Descending Triangle",
                      type="空頭中繼")
    p["lines"] = [(a, b, {"水平壓力": "水平支撐", "低點墊高": "高點下移"}[t], s) for a, b, t, s in p["lines"]]
    p["break"] = (p["break"][0], p["break"][1], "跌破支撐")
    p["target"]["label"] = "目標價\n（三角形高度）"
    p["notes"] = {
        "辨識": "下方是幾乎水平的支撐，上方高點一次比一次低，形成收斂的直角三角形。",
        "確認": "收盤跌破水平支撐，量增更可靠。",
        "失效": "跌破後收回三角形內，或突破下降的高點連線。",
        "目標": "三角形最寬處的高度，從跌破點往下扣。",
    }
    return p


def _sym_triangle():
    up, lo = line((16, 82), (38, 75)), line((26, 46), (48, 54))
    brk_x = 66
    return {
        "key": "symmetrical_triangle", "name": "對稱三角形（三角收斂）", "en": "Symmetrical Triangle",
        "type": "中繼整理", "bias": "neutral",
        "path": [(0, 30), (10, 60), (16, up(16)), (26, lo(26)), (38, up(38)), (48, lo(48)), (56, up(56)),
                 (62, lo(62)), (brk_x, up(brk_x)), (70, 73), (76, 70), (90, 90)],
        "points": [],
        "lines": [((14, up(14)), (74, up(74)), "高點下移", "struct"), ((22, lo(22)), (74, lo(74)), "低點墊高", "struct")],
        "break": (brk_x, up(brk_x), "突破收斂"),
        "target": {"x": 84, "from": up(brk_x), "to": up(brk_x) + (82 - lo(16)), "label": "目標價\n（開口高度）"},
        "vol": [(0, 1.1), (10, 1.3), (20, 1.0), (40, 0.75), (62, 0.5), (66, 1.8), (76, 1.2), (90, 1.0)],
        "notes": {
            "辨識": "高點越來越低、低點越來越高，兩條線往右收斂；多空力道暫時平衡，量能逐步萎縮。",
            "確認": "收盤帶量突破任一邊才算數，順著原本趨勢的機率較高（此圖為向上）。",
            "失效": "突破後很快跌回三角形內；越接近尖端才突破，力道通常越弱。",
            "目標": "三角形開口（最寬處）的高度，從突破點量起。",
        },
        "stage_cut": 63,
    }


def _rising_wedge():
    up, lo = line((14, 60), (50, 78)), line((20, 44), (50, 70))
    brk = (61, lo(61))
    return {
        "key": "rising_wedge", "name": "上升楔形", "en": "Rising Wedge", "type": "偏空（多頭力竭）", "bias": "bear",
        "path": [(0, 36), (8, 50), (14, up(14)), (20, lo(20)), (30, up(30)), (36, lo(36)), (45, up(45)),
                 (50, lo(50)), (56, up(56)), brk, (65, 72), (69, 75), (78, 60), (90, 46)],
        "points": [],
        "lines": [((12, up(12)), (64, up(64)), "上緣", "struct"), ((18, lo(18)), (64, lo(64)), "下緣（較陡）", "struct")],
        "break": (brk[0], brk[1], "跌破下緣"),
        "target": {"x": 84, "from": brk[1], "to": 44, "label": "目標價\n（回到楔形起點）"},
        "vol": [(0, 1.2), (14, 1.1), (30, 0.9), (50, 0.65), (61, 1.8), (70, 1.2), (90, 1.0)],
        "notes": {
            "辨識": "價格沿著兩條「都往上」但逐漸收斂的線上漲，下緣比上緣陡，漲勢越來越吃力，量能遞減。",
            "確認": "收盤跌破楔形下緣。",
            "失效": "跌破後迅速站回楔形內，或放量突破上緣。",
            "目標": "常見目標是楔形的起漲點附近。",
        },
        "stage_cut": 59,
    }


def _falling_wedge():
    p = _flip_pattern(_rising_wedge(), key="falling_wedge", name="下降楔形", en="Falling Wedge",
                      type="偏多（空頭力竭）")
    p["lines"] = [(a, b, {"上緣": "下緣", "下緣（較陡）": "上緣（較陡）"}[t], s) for a, b, t, s in p["lines"]]
    p["break"] = (p["break"][0], p["break"][1], "突破上緣")
    p["target"]["label"] = "目標價\n（回到楔形起點）"
    p["notes"] = {
        "辨識": "價格沿著兩條「都往下」但逐漸收斂的線下跌，上緣比下緣陡，跌勢越來越弱，量能遞減。",
        "確認": "收盤帶量突破楔形上緣。",
        "失效": "突破後跌回楔形內，或跌破下緣創新低。",
        "目標": "常見目標是楔形的起跌點附近。",
    }
    return p


def _bull_flag():
    up = line((24, 76), (48, 66))
    lo = lambda x: up(x) - 11  # noqa: E731
    brk_x = 57
    return {
        "key": "bull_flag", "name": "多頭旗形", "en": "Bull Flag", "type": "多頭中繼", "bias": "bull",
        "path": [(0, 30), (8, 34), (24, 76), (30, lo(30)), (37, up(37)), (43, lo(43)), (49, up(49)),
                 (53, lo(53) + 1), (brk_x, up(brk_x)), (61, 74), (66, 71), (82, 99)],
        "points": [],
        "lines": [((8, 34), (24, 76), "旗桿", "pole"), ((24, up(24)), (60, up(60)), "旗面上緣", "struct"),
                  ((26, lo(26)), (60, lo(60)), "旗面下緣", "struct")],
        "break": (brk_x, up(brk_x), "突破旗面"),
        "target": {"x": 76, "from": up(brk_x), "to": up(brk_x) + (76 - 34), "label": "目標價\n（旗桿長度）"},
        "vol": [(0, 1.0), (8, 1.2), (20, 2.0), (26, 1.3), (40, 0.7), (54, 0.55), (57, 1.8), (66, 1.2), (82, 1.1)],
        "notes": {
            "辨識": "急漲形成「旗桿」後，出現小幅向下傾斜、上下緣平行的整理通道，整理期間量縮。",
            "確認": "收盤帶量突破旗面上緣。",
            "失效": "跌破旗面下緣，或回檔超過旗桿的一半。",
            "目標": "旗桿長度，從突破點往上加。",
        },
        "stage_cut": 55,
    }


def _bear_flag():
    p = _flip_pattern(_bull_flag(), key="bear_flag", name="空頭旗形", en="Bear Flag", type="空頭中繼")
    p["lines"] = [(a, b, {"旗桿": "旗桿", "旗面上緣": "旗面下緣", "旗面下緣": "旗面上緣"}[t], s) for a, b, t, s in p["lines"]]
    p["break"] = (p["break"][0], p["break"][1], "跌破旗面")
    p["target"]["label"] = "目標價\n（旗桿長度）"
    p["notes"] = {
        "辨識": "急跌形成「旗桿」後，出現小幅向上傾斜、上下緣平行的反彈通道，反彈量縮。",
        "確認": "收盤跌破旗面下緣。",
        "失效": "突破旗面上緣，或反彈超過旗桿的一半。",
        "目標": "旗桿長度，從跌破點往下扣。",
    }
    return p


def _rectangle():
    top, bot = 70, 55
    return {
        "key": "rectangle", "name": "矩形整理（箱型）", "en": "Rectangle", "type": "中繼整理", "bias": "bull",
        "path": [(0, 32), (12, top), (20, bot), (30, top), (40, bot), (50, top), (58, bot + 1), (66, top),
                 (69, 77), (73, 73), (86, 88)],
        "points": [],
        "lines": [((10, top), (72, top), "箱頂壓力", "neck"), ((10, bot), (72, bot), "箱底支撐", "neck")],
        "break": (66, top, "突破箱頂"),
        "target": {"x": 82, "from": top, "to": top + (top - bot), "label": "目標價\n（箱子高度）"},
        "vol": [(0, 1.1), (12, 1.2), (30, 0.9), (58, 0.7), (66, 1.8), (73, 1.2), (86, 1.0)],
        "notes": {
            "辨識": "價格在水平的上下界之間來回震盪，高點相近、低點相近，像一個箱子。",
            "確認": "收盤帶量突破箱頂（或跌破箱底），方向以突破為準。",
            "失效": "突破後又回到箱子裡，常是假突破。",
            "目標": "箱子的高度，從突破點量起。",
        },
        "stage_cut": 63,
    }


def _cup_handle():
    rim = 80
    cup = [(x, rim - 30 * math.sin(math.pi * (x - 10) / 48)) for x in range(12, 58, 3)]
    return {
        "key": "cup_handle", "name": "杯柄型態", "en": "Cup and Handle", "type": "多頭延續", "bias": "bull",
        "path": [(0, 58), (10, rim)] + cup + [(58, rim), (62, 73), (66, 76), (69, 72.5), (73, rim), (76, 86), (88, 98)],
        "points": [(10, rim, "左杯緣", "above"), (34, 50, "杯底", "below"), (58, rim, "右杯緣", "above"),
                   (66, 71, "柄", "below")],
        "lines": [((8, rim), (78, rim), "杯緣（頸線）", "neck")],
        "break": (73, rim, "突破杯緣"),
        "target": {"x": 84, "from": rim, "to": rim + 30, "label": "目標價\n（杯深）"},
        "vol": [(0, 1.2), (10, 1.1), (34, 0.6), (58, 1.0), (66, 0.6), (73, 1.9), (80, 1.2), (88, 1.0)],
        "notes": {
            "辨識": "圓弧狀的「杯子」打底（不是 V 字急殺急拉），回到杯緣後小幅回檔形成「柄」，柄的深度較淺。",
            "確認": "收盤帶量突破杯緣（頸線）。",
            "失效": "柄回檔太深（超過杯深一半），或突破後跌回杯內。",
            "目標": "杯子深度，從突破點往上加。",
        },
        "stage_cut": 71,
    }


def _rounding_bottom():
    nk = 64
    curve = [(x, nk - 22 * math.sin(math.pi * (x - 12) / 58)) for x in range(14, 70, 3)]
    return {
        "key": "rounding_bottom", "name": "圓弧底", "en": "Rounding Bottom", "type": "底部反轉", "bias": "bull",
        "path": [(0, 84), (12, nk)] + curve + [(70, nk), (74, 70), (78, 68), (90, 82)],
        "points": [(41, nk - 22, "弧形低點", "below")],
        "lines": [((8, nk), (84, nk), "頸線", "neck")],
        "break": (71, nk + 1, "突破頸線"),
        "target": {"x": 86, "from": nk, "to": nk + 22, "label": "目標價\n（弧底深度）"},
        "vol": [(0, 1.3), (12, 1.1), (41, 0.5), (60, 0.9), (71, 1.8), (80, 1.3), (90, 1.1)],
        "notes": {
            "辨識": "跌勢慢慢趨緩、轉平再慢慢回升，整體呈碗狀；量能常同步呈現「兩頭大、中間小」。",
            "確認": "收盤帶量突破弧形起跌處的頸線。",
            "失效": "突破後跌回頸線下，或再度破底。",
            "目標": "弧底深度，從突破點往上加。",
        },
        "stage_cut": 67,
    }


# --- K 線組合 (o, h, l, c)


def _trend(start, end, n):
    """產生一段方向一致、帶一點節奏變化的前置趨勢 K 棒。"""
    out, prev = [], start
    step = (end - start) / n
    for i in range(n):
        c = start + step * (i + 1) + (0.6 if i % 2 else -0.4) * abs(step) * 0.5
        o = prev + (-0.3 if step > 0 else 0.3) * abs(step) * 0.4
        h, lo = max(o, c) + abs(step) * 0.35, min(o, c) - abs(step) * 0.35
        out.append((o, h, lo, c))
        prev = c
    return out


def _candle(key, name, en, ctype, bias, prior, pattern, after, label, notes):
    candles = prior + pattern + after
    return {"key": key, "name": name, "en": en, "type": ctype, "bias": bias, "kind": "candle",
            "candles": candles, "highlight": (len(prior), len(prior) + len(pattern) - 1), "label": label,
            "notes": notes}


def _candles():
    down = _trend(84, 60, 6)
    up = _trend(52, 78, 6)
    return [
        _candle("hammer", "錘子線", "Hammer", "底部反轉訊號", "bull", down,
                [(58.6, 60.8, 47.0, 60.3)], [(60.6, 68.0, 60.0, 67.4)],
                "下影線 ≥ 實體 2 倍\n實體在上端",
                {"辨識": "出現在下跌之後；實體小、位於K棒上端，下影線至少是實體的兩倍，幾乎沒有上影線。",
                 "確認": "隔天收紅、收盤高於錘子線實體，確認買盤接手。",
                 "失效": "後續收盤跌破錘子線的最低點。",
                 "目標": "單根K線不測量目標，搭配前波壓力或均線判斷。"}),
        _candle("shooting_star", "流星線", "Shooting Star", "頂部反轉訊號", "bear", up,
                [(80.2, 92.0, 79.0, 79.5)], [(79.0, 79.6, 71.0, 71.8)],
                "上影線 ≥ 實體 2 倍\n實體在下端",
                {"辨識": "出現在上漲之後；實體小、位於K棒下端，上影線至少是實體的兩倍，代表高檔賣壓湧現。",
                 "確認": "隔天收黑、收盤低於流星線實體。",
                 "失效": "後續收盤突破流星線的最高點。",
                 "目標": "單根K線不測量目標，搭配前波支撐判斷。"}),
        _candle("doji", "十字線", "Doji", "轉折警訊", "neutral", up,
                [(80.0, 85.5, 74.5, 80.15)], [(79.6, 80.2, 72.0, 72.8)],
                "開盤 ≈ 收盤\n多空拉鋸",
                {"辨識": "開盤價與收盤價幾乎相同，上下影線長短不一；出現在明顯趨勢後代表力道減弱。",
                 "確認": "要看隔天方向：在高檔後接黑K、在低檔後接紅K，轉折機率才提高。",
                 "失效": "隔天順著原趨勢延續並創新高（或新低）。",
                 "目標": "十字線本身只是警訊，不單獨作為進出依據。"}),
        _candle("bullish_engulfing", "多頭吞噬", "Bullish Engulfing", "底部反轉訊號", "bull", _trend(82, 63, 5),
                [(62.0, 63.0, 58.6, 59.4), (58.6, 68.0, 58.0, 67.4)], [(67.0, 71.0, 66.0, 70.2)],
                "紅K 實體完全包住\n前一根黑K 實體",
                {"辨識": "下跌中先出現一根黑K，隔天紅K的實體從更低開出、收得更高，把前一根實體完全包住。",
                 "確認": "吞噬當天量增，隔天續強不跌破紅K的一半。",
                 "失效": "後續收盤跌破吞噬紅K的最低點。",
                 "目標": "以前波壓力或區間高點作為參考。"}),
        _candle("bearish_engulfing", "空頭吞噬", "Bearish Engulfing", "頂部反轉訊號", "bear", _trend(54, 72, 5),
                [(72.0, 75.6, 71.6, 74.6), (75.4, 76.0, 66.0, 66.6)], [(67.0, 68.0, 62.0, 62.8)],
                "黑K 實體完全包住\n前一根紅K 實體",
                {"辨識": "上漲中先出現一根紅K，隔天黑K的實體從更高開出、收得更低，把前一根實體完全包住。",
                 "確認": "吞噬當天量增，隔天無法收復黑K的一半。",
                 "失效": "後續收盤突破吞噬黑K的最高點。",
                 "目標": "以前波支撐或區間低點作為參考。"}),
        _candle("morning_star", "晨星", "Morning Star", "底部反轉訊號", "bull", _trend(84, 71, 4),
                [(70.0, 70.6, 58.6, 59.0), (56.2, 57.6, 54.0, 55.6), (57.0, 68.6, 56.6, 68.0)], [(68.0, 71.0, 67.0, 70.4)],
                "長黑 → 小星 → 長紅\n收盤過長黑一半",
                {"辨識": "三根K線：先一根長黑，再一根跳空的小實體（星），第三根長紅收進第一根長黑實體的一半以上。",
                 "確認": "第三根長紅量增，之後不跌破星線低點。",
                 "失效": "後續收盤跌破星線的最低點。",
                 "目標": "以前波壓力作為參考。"}),
        _candle("evening_star", "夜星", "Evening Star", "頂部反轉訊號", "bear", _trend(50, 62, 4),
                [(62.0, 73.6, 61.4, 73.0), (75.4, 77.0, 74.4, 76.0), (74.0, 74.6, 62.4, 63.0)], [(63.0, 64.0, 59.0, 59.6)],
                "長紅 → 小星 → 長黑\n收盤破長紅一半",
                {"辨識": "三根K線：先一根長紅，再一根跳空的小實體（星），第三根長黑收進第一根長紅實體的一半以下。",
                 "確認": "第三根長黑量增，之後無法站回星線高點。",
                 "失效": "後續收盤突破星線的最高點。",
                 "目標": "以前波支撐作為參考。"}),
        _candle("three_white_soldiers", "紅三兵", "Three White Soldiers", "底部轉強訊號", "bull", _trend(64, 52, 5),
                [(52.0, 58.6, 51.6, 58.0), (56.4, 64.6, 55.8, 64.0), (62.4, 70.6, 61.8, 70.0)], [],
                "連續三根長紅\n每根收盤創新高",
                {"辨識": "低檔或整理後連續三根實體飽滿的紅K，每根都在前一根實體內開盤、收在更高位置，上影線短。",
                 "確認": "量能溫和放大，之後回檔不跌破第一根紅K的低點。",
                 "失效": "第三根上影線很長或爆量收小，常代表追價力道不足。",
                 "目標": "以前波壓力作為參考。"}),
        _candle("three_black_crows", "黑三鴉", "Three Black Crows", "頂部轉弱訊號", "bear", _trend(66, 78, 5),
                [(78.0, 78.6, 71.4, 72.0), (73.6, 74.2, 65.4, 66.0), (67.6, 68.2, 59.4, 60.0)], [],
                "連續三根長黑\n每根收盤創新低",
                {"辨識": "高檔後連續三根實體飽滿的黑K，每根都在前一根實體內開盤、收在更低位置，下影線短。",
                 "確認": "之後反彈無法站回第一根黑K的高點。",
                 "失效": "很快出現長紅收復第一根黑K的高點。",
                 "目標": "以前波支撐作為參考。"}),
    ]


def _build_library():
    chart = [_hs_top(), _hs_bottom(), _double_top(), _double_bottom(), _asc_triangle(), _desc_triangle(),
             _sym_triangle(), _rising_wedge(), _falling_wedge(), _bull_flag(), _bear_flag(), _rectangle(),
             _cup_handle(), _rounding_bottom()]
    for p in chart:
        p["kind"] = "chart"
    return {p["key"]: p for p in chart + _candles()}


PATTERNS = _build_library()

_DOWN_NOTES = {
    "rectangle": {"確認": "收盤跌破箱底，量增更可靠；跌破後箱底轉為壓力。", "失效": "跌破後又站回箱子裡，常是假跌破。",
                  "目標": "箱子的高度，從跌破點往下扣。"},
    "symmetrical_triangle": {"確認": "收盤跌破下方的低點連線，量增更可靠。", "失效": "跌破後很快回到三角形內。",
                             "目標": "三角形開口（最寬處）的高度，從跌破點往下扣。"},
}


def breakdown_variant(p):
    """方向未定的型態（箱型、對稱三角形）改畫成向下跌破的版本。"""
    if p["key"] not in _DOWN_NOTES:
        raise SystemExit("只有箱型（rectangle）與對稱三角形（symmetrical_triangle）有向下跌破的版本。")
    q = _flip_pattern(p, bias="bear", name=p["name"] + "－向下跌破")
    swap = {"箱頂壓力": "箱底支撐", "箱底支撐": "箱頂壓力", "高點下移": "低點墊高", "低點墊高": "高點下移"}
    q["lines"] = [(a, b, swap.get(t, t), s) for a, b, t, s in q["lines"]]
    x, y, t = q["break"]
    q["break"] = (x, y, {"突破箱頂": "跌破箱底", "突破收斂": "跌破收斂"}.get(t, t))
    q["notes"] = {**p["notes"], **_DOWN_NOTES[p["key"]]}
    return q

BIAS_LABEL = {"bull": "看漲", "bear": "看空", "neutral": "方向待確認"}


def list_patterns():
    return [(k, p["name"], p["en"], p["kind"], p["type"]) for k, p in PATTERNS.items()]


def find_pattern(key):
    key = (key or "").strip()
    if key in PATTERNS:
        return PATTERNS[key]
    for p in PATTERNS.values():  # 也接受中文名稱或英文名稱
        if key in (p["name"], p["en"]) or key in p["name"]:
            return p
    raise SystemExit(f"找不到型態「{key}」。可用代碼：\n" + "\n".join(f"  {k}  {n}" for k, n, *_ in list_patterns()))


# ---------------------------------------------------------------- candle generation


class Mapper:
    """型態單位 → 圖上座標（K 棒索引、價格）。"""

    def __init__(self, n, offset=0, base=None, amp=None):
        self.n, self.offset, self.base, self.amp = n, offset, base, amp

    def x(self, u):
        return self.offset + u * (self.n - 1) / 100.0

    def y(self, v):
        if self.base is None:
            return v
        return self.base * (1 + (v - 50) / 100.0 * self.amp)


def sample_path(path, n, cut=None):
    """把轉折點路徑取樣成 n 根 K 棒的收盤參考值；轉折點會對齊到最近的 K 棒，確保頭部、底部清楚。"""
    path = list(path)
    if path[-1][0] < 100:  # 延伸尾段，避免最後幾根 K 棒變成一條平線
        (xa, ya), (xb, yb) = path[-2], path[-1]
        path.append((100, yb + (yb - ya) / (xb - xa) * (100 - xb) * 0.5))
    xs = np.array([p[0] for p in path], float)
    ys = np.array([p[1] for p in path], float)
    t = np.linspace(0, 100, n)
    mid = np.interp(t, xs, ys)
    for x, y in path:
        i = int(round(x * (n - 1) / 100.0))
        if 0 <= i < n:
            mid[i] = y
    if cut is not None:
        keep = t <= cut
        t, mid = t[keep], mid[keep]
    return t, mid


def ohlc_from_mid(mid, rng, noise):
    closes = mid + rng.normal(0, noise * 0.45, len(mid))
    out, prev = [], closes[0] - (closes[1] - closes[0] if len(closes) > 1 else 0)
    for c in closes:
        o = prev + rng.normal(0, noise * 0.3)
        h = max(o, c) + abs(rng.normal(0, noise * 0.7))
        lo = min(o, c) - abs(rng.normal(0, noise * 0.7))
        out.append((o, h, lo, c))
        prev = c
    return out


def volume_from_profile(profile, t, rng, base=1.0):
    xs = [p[0] for p in profile]
    vs = [p[1] for p in profile]
    v = np.interp(t, xs, vs)
    return base * v * rng.lognormal(0, 0.18, len(t))


# ---------------------------------------------------------------- drawing


def draw_candles(ax, ohlc, xs, col, width=0.62):
    for x, (o, h, lo, c) in zip(xs, ohlc):
        color = col["up"] if c >= o else col["down"]
        ax.plot([x, x], [lo, h], color=color, lw=1.1, solid_capstyle="butt", zorder=2)
        bottom, height = min(o, c), max(abs(c - o), (h - lo) * 0.012 + 1e-9)
        ax.add_patch(Rectangle((x - width / 2, bottom), width, height, facecolor=color, edgecolor=color, lw=0.8,
                               zorder=3))


def draw_volume(ax, vol, ohlc, xs, col, width=0.62):
    for x, v, (o, _h, _l, c) in zip(xs, vol, ohlc):
        ax.bar(x, v, width=width, color=col["up"] if c >= o else col["down"], alpha=0.45, lw=0)
    ax.set_yticks([])
    ax.set_ylim(0, max(vol) * 1.25)
    ax.text(0.005, 0.92, "成交量", transform=ax.transAxes, fontsize=9, color=MUTED, va="top")


def style_axes(ax, right_price=True):
    ax.set_facecolor(BG)
    for s in ("top", "left"):
        ax.spines[s].set_visible(False)
    for s in ("right", "bottom"):
        ax.spines[s].set_color("#c9d3da")
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    if right_price:
        ax.yaxis.tick_right()
    ax.tick_params(colors=MUTED, labelsize=9, length=0)


def draw_overlays(ax, p, m, col, show_break=True, show_target=True, fs=12, label_break=True):
    """畫型態結構：頸線、趨勢線、關鍵點、突破點與目標價。"""
    for a, b, text, style in p.get("lines", []):
        x1, y1, x2, y2 = m.x(a[0]), m.y(a[1]), m.x(b[0]), m.y(b[1])
        if style == "pole":
            ax.plot([x1, x2], [y1, y2], color=col["struct"], lw=9, alpha=0.18, solid_capstyle="round", zorder=4)
            ax.text((x1 + x2) / 2 - 1.2, (y1 + y2) / 2, text, color=col["struct"], fontsize=fs, fontweight="bold",
                    ha="right", va="center", path_effects=halo(), zorder=8)
            continue
        c = col["neck"] if style == "neck" else col["struct"]
        ax.plot([x1, x2], [y1, y2], color=c, lw=2.2, ls=(0, (6, 4)), zorder=5)
        if text:
            ax.text(x2 + 0.6, y2, text, color=c, fontsize=fs - 1, fontweight="bold", va="center", ha="left",
                    path_effects=halo(), zorder=8)
    yr = ax.get_ylim()
    dy = (yr[1] - yr[0]) * 0.045
    for x, y, text, pos in p.get("points", []):
        X, Y = m.x(x), m.y(y)
        ax.plot(X, Y, "o", ms=9, mfc="white", mec=col["struct"], mew=2.4, zorder=7)
        ax.text(X, Y + (dy if pos == "above" else -dy), text, color=col["struct"], fontsize=fs, fontweight="bold",
                ha="center", va="bottom" if pos == "above" else "top", path_effects=halo(), zorder=8)
    if show_break and p.get("break"):
        x, y, text = p["break"]
        bc = col["bull"] if p["bias"] == "bull" or "突破" in text else col["bear"]
        X, Y = m.x(x), m.y(y)
        ax.plot(X, Y, "o", ms=13 * fs / 12, mfc="none", mec=bc, mew=2.6, zorder=7)
        if not label_break:
            text = ""
        down = "跌破" in p["break"][2]
        ax.annotate(text, (X, Y), xytext=(X - 5.5, Y + (-3.2 if down else 3.2) * dy), color=bc, fontsize=fs,
                    fontweight="bold", ha="center", va="center", path_effects=halo(), zorder=9,
                    arrowprops=dict(arrowstyle="-|>", color=bc, lw=1.8, shrinkA=4, shrinkB=8))
    if show_target and p.get("target"):
        t = p["target"]
        X, y0, y1 = m.x(t["x"]), m.y(t["from"]), m.y(t["to"])
        bx = m.x(p["break"][0]) if p.get("break") else X - 8
        ax.plot([bx, X + 1.5], [y1, y1], color=col["target"], lw=1.6, ls=(0, (2, 3)), zorder=5)
        ax.annotate("", (X, y1), xytext=(X, y0),
                    arrowprops=dict(arrowstyle="<|-|>", color=col["target"], lw=2, shrinkA=0, shrinkB=0), zorder=6)
        ax.text(X + 1.2, (y0 + y1) / 2, t["label"], color=col["target"], fontsize=fs - 1, fontweight="bold",
                va="center", ha="left", path_effects=halo(), zorder=8, linespacing=1.3)


def overlay_limits(p, m, ys):
    vals = list(ys)
    for a, b, *_ in p.get("lines", []):
        vals += [m.y(a[1]), m.y(b[1])]
    if p.get("target"):
        vals += [m.y(p["target"]["from"]), m.y(p["target"]["to"])]
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.1
    return lo - pad, hi + pad


def draw_notes(ax, notes, col):
    ax.axis("off")
    rows = [k for k in ("辨識", "確認", "失效", "目標") if k in notes]
    for i, k in enumerate(rows):
        y = 0.92 - i * 0.25
        ax.text(0.0, y, k, fontsize=11.5, fontweight="bold", color="white", va="top", ha="left",
                bbox=dict(boxstyle="round,pad=0.28", fc={"辨識": STRUCT, "確認": col["bull"], "失效": col["bear"],
                                                          "目標": TARGET}[k], ec="none"))
        ax.text(0.045, y, notes[k], fontsize=11.5, color=INK, va="top", ha="left", wrap=True)


def chip(fig, x, y, text, color):
    fig.text(x, y, text, fontsize=11, color="white", fontweight="bold", va="center", ha="left",
             bbox=dict(boxstyle="round,pad=0.35", fc=color, ec="none"))


def highlight_box(ax, x0, x1, ylo, yhi, color, label, above=True):
    pad_x, pad_y = 0.55, (yhi - ylo) * 0.08 + 0.4
    ax.add_patch(FancyBboxPatch((x0 - pad_x, ylo - pad_y), (x1 - x0) + 2 * pad_x, (yhi - ylo) + 2 * pad_y,
                                boxstyle="round,pad=0.02,rounding_size=0.6", fill=False, ec=color, lw=2.2,
                                ls=(0, (5, 3)), zorder=6))
    ty = yhi + pad_y * 1.6 if above else ylo - pad_y * 1.6
    ax.text((x0 + x1) / 2, ty, label, color=color, fontsize=12, fontweight="bold", ha="center",
            va="bottom" if above else "top", path_effects=halo(), zorder=8, linespacing=1.35)
