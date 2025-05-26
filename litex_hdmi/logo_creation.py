from PIL import Image

def convert_logo_to_mem(input_path, output_path, bg_color=(0, 0, 0)):
    img = Image.open(input_path).convert("RGB")
    w, h = img.size

    with open(output_path, "w") as f:
        for y in range(h):
            for x in range(w):
                r, g, b = img.getpixel((x, y))
                if (r, g, b) == bg_color:
                    val = 0x000000  # transparente (negro)
                else:
                    val = (r << 16) | (g << 8) | b
                f.write(f"{val:06x}\n")

    print(f"[✓] Logo convertido a: {output_path} ({w}x{h})")

# Uso manual:
convert_logo_to_mem("rect1.png", "logo.mem", bg_color=(0, 0, 0))
