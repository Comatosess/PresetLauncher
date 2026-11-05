from PIL import Image, ImageDraw, ImageFilter

S = 256


def grad(c1, c2, w, h):
    g = Image.new("RGBA", (w, h))
    px = g.load()
    for x in range(w):
        t = x / (w - 1)
        col = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)) + (255,)
        for y in range(h):
            px[x, y] = col
    return g


base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(base).rounded_rectangle(
    (6, 6, S - 6, S - 6), radius=60, fill=(14, 14, 19, 255), outline=(42, 42, 54, 255), width=3
)

tri = [(98, 72), (98, 184), (190, 128)]

glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(glow).polygon(tri, fill=(124, 92, 255, 170))
glow = glow.filter(ImageFilter.GaussianBlur(14))
base = Image.alpha_composite(base, glow)

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).polygon(tri, fill=255)
base.paste(grad((124, 92, 255), (255, 92, 190), S, S), (0, 0), mask)

base.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print("icon.ico готов")
