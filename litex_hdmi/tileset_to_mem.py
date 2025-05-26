from PIL import Image
import argparse

def tileset_to_mem(input_path, tile_width=16, tile_height=16, output_path="tiles.mem"):
    img = Image.open(input_path).convert("RGB")
    img_w, img_h = img.size

    tiles_x = img_w // tile_width
    tiles_y = img_h // tile_height
    total_tiles = tiles_x * tiles_y

    print(f"[✓] Tiles: {tiles_x} x {tiles_y} = {total_tiles} tiles")

    with open(output_path, "w") as f:
        for ty in range(tiles_y):
            for tx in range(tiles_x):
                for y in range(tile_height):
                    for x in range(tile_width):
                        px = img.getpixel((tx*tile_width + x, ty*tile_height + y))
                        rgb = (px[0] << 16) | (px[1] << 8) | px[2]
                        f.write(f"{rgb:06x}\n")
    print(f"[✓] Generado: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convierte tileset PNG a .mem")
    parser.add_argument("input", help="Archivo PNG del tileset")
    parser.add_argument("--tile_w", type=int, default=16, help="Ancho del tile")
    parser.add_argument("--tile_h", type=int, default=16, help="Alto del tile")
    parser.add_argument("--output", default="tiles.mem", help="Archivo de salida .mem")
    args = parser.parse_args()

    tileset_to_mem(args.input, args.tile_w, args.tile_h, args.output)
