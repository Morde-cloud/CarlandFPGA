"""Pure-stdlib PNG decode + content verification for the five fixture images.

No third-party modules (PIL is not installed in this environment). Decodes the
PNGs written by the Godot harness (Python zlib + PNG unfilter) and checks:
dimensions, non-blank content (distinct colours, luminance stddev, near-black
fraction) and the orientation marker bars baked into every capture
(magenta strip at the top, cyan strip at the bottom).
"""

import hashlib
import json
import os
import struct
import sys
import zlib

WS = os.path.normpath(r"D:\pynq\CarlandFPGA\.local\deployment\node-b\evidence\director-app-recovery-20261016\assets-render-main-01")
PNG_NAMES = [
    "01_drill_actual_scale_oblique.png",
    "02_drill_head_detail_6blades_18studs.png",
    "03_obstacle_kind_gallery_5kinds.png",
    "04_world_overview_30obstacles_drill_frame.png",
    "05_world_alt_angle_hollow_edge_cube.png",
]
CHANNELS_BY_COLOR_TYPE = {0: 1, 2: 3, 4: 2, 6: 4}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def read_png(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: " + path)
    pos = 8
    width = height = bitdepth = colortype = None
    idat = bytearray()
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            width, height, bitdepth, colortype, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            if comp != 0 or filt != 0 or interlace != 0:
                raise ValueError("unsupported PNG (compression/filter/interlace) in " + path)
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    channels = CHANNELS_BY_COLOR_TYPE.get(colortype)
    if channels is None or bitdepth not in (8, 16):
        raise ValueError("unsupported colour type/bit depth %s/%s in %s" % (colortype, bitdepth, path))
    bytes_per_sample = bitdepth // 8
    bpp = channels * bytes_per_sample
    stride = width * bpp
    raw = zlib.decompress(bytes(idat))
    if len(raw) < (stride + 1) * height:
        raise ValueError("truncated image data in " + path)
    out = bytearray(height * stride)
    prev = bytearray(stride)
    src = 0
    for y in range(height):
        ftype = raw[src]
        src += 1
        line = bytearray(raw[src:src + stride])
        src += stride
        if ftype == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif ftype == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ftype == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif ftype == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                pa = abs(b - c)
                pb = abs(a - c)
                pc = abs(a + b - 2 * c)
                if pa <= pb and pa <= pc:
                    pr = a
                elif pb <= pc:
                    pr = b
                else:
                    pr = c
                line[x] = (line[x] + pr) & 0xFF
        elif ftype != 0:
            raise ValueError("bad PNG filter type %d at row %d in %s" % (ftype, y, path))
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return {"width": width, "height": height, "channels": channels, "bytes_per_sample": bytes_per_sample, "stride": stride, "pixels": bytes(out)}


def pixel_rgb(img, x, y):
    base = y * img["stride"] + x * img["channels"] * img["bytes_per_sample"]
    buf = img["pixels"]
    if img["bytes_per_sample"] == 1:
        vals = [buf[base + i] for i in range(img["channels"])]
    else:
        vals = [buf[base + 2 * i] for i in range(img["channels"])]
    if img["channels"] <= 2:
        return vals[0], vals[0], vals[0]
    return vals[0], vals[1], vals[2]


def analyse(path):
    img = read_png(path)
    w = img["width"]
    h = img["height"]
    step_x = max(1, w // 240)
    step_y = max(1, h // 135)
    count = 0
    lum_sum = 0.0
    lum_sq = 0.0
    near_black = 0
    distinct = set()
    y = 0
    while y < h:
        x = 0
        while x < w:
            r, g, b = pixel_rgb(img, x, y)
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
            lum_sum += lum
            lum_sq += lum * lum
            if lum < 0.02:
                near_black += 1
            distinct.add((r, g, b))
            count += 1
            x += step_x
        y += step_y
    mean = lum_sum / count
    var = max(lum_sq / count - mean * mean, 0.0)
    stddev = var ** 0.5
    near_black_fraction = near_black / float(count)

    def bar_fraction(row, predicate):
        hits = 0
        samples = 0
        x = w // 8
        while x < w - w // 8:
            r, g, b = pixel_rgb(img, x, row)
            if predicate(r, g, b):
                hits += 1
            samples += 1
            x += 8
        return hits / float(max(samples, 1))

    magenta_top = bar_fraction(3, lambda r, g, b: r > 128 and b > 128 and g < 96)
    cyan_bottom = bar_fraction(h - 4, lambda r, g, b: g > 128 and b > 128 and r < 96)
    content_nonblank = bool(len(distinct) >= 64 and stddev >= 0.02 and near_black_fraction < 0.98)
    orientation_ok = bool(magenta_top >= 0.9 and cyan_bottom >= 0.9)
    return {
        "path": path,
        "file_size": os.path.getsize(path),
        "sha256": sha256_file(path),
        "width": w,
        "height": h,
        "channels": img["channels"],
        "bit_depth_bytes": img["bytes_per_sample"],
        "expected_size_1280x720": bool(w == 1280 and h == 720),
        "samples": count,
        "distinct_colors_sample": len(distinct),
        "mean_luminance": round(mean, 6),
        "stddev_luminance": round(stddev, 6),
        "near_black_fraction": round(near_black_fraction, 6),
        "magenta_top_bar_fraction": round(magenta_top, 4),
        "cyan_bottom_bar_fraction": round(cyan_bottom, 4),
        "content_nonblank": content_nonblank,
        "orientation_ok": orientation_ok,
        "pass": bool(content_nonblank and orientation_ok),
    }


def main():
    results = os.path.join(WS, "results")
    png_dir = os.path.join(WS, "png")
    entries = []
    failures = []
    for name in PNG_NAMES:
        path = os.path.join(png_dir, name)
        if not os.path.exists(path):
            entries.append({"name": name, "path": path, "exists": False, "pass": False})
            failures.append(name + ":missing")
            continue
        try:
            info = analyse(path)
        except Exception as exc:  # noqa: BLE001 - evidence must record the failure
            entries.append({"name": name, "path": path, "exists": True, "pass": False, "error": repr(exc)})
            failures.append(name + ":decode_error")
            continue
        info["name"] = name
        info["exists"] = True
        entries.append(info)
        if not info["pass"]:
            failures.append(name + ":check_failed")
        print(name, "size=%dx%d" % (info["width"], info["height"]), "stddev=%.4f" % info["stddev_luminance"], "distinct=", info["distinct_colors_sample"], "nonblank=", info["content_nonblank"], "orientation=", info["orientation_ok"], "sha256=", info["sha256"])
    verdict = {
        "step": "png_verify",
        "decoder": "python-stdlib zlib + PNG unfilter (no PIL available)",
        "expected_images": PNG_NAMES,
        "images": entries,
        "failures": failures,
        "all_pass": not failures,
    }
    os.makedirs(results, exist_ok=True)
    with open(os.path.join(results, "png_verification.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(verdict, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print("png_verify all_pass=", verdict["all_pass"], "failures=", failures)
    return 0 if verdict["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())