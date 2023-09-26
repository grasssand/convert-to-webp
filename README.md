# Batch convert images to webp using `libwebp`

Convert all images in the input folder to webp. Support gif.

The output file maintains the original folder structure.

The result is saved in the `details.csv` of the output folder.

## Usage

```bash
usage: convert-to-webp [-h] -o OUT_DIR [-q QUALITY] [-l] in_dir

Convert images to webp

positional arguments:
  in_dir                input file or directory

options:
  -h, --help            show this help message and exit
  -o OUT_DIR, --out OUT_DIR
                        output directory
  -q QUALITY, --quality QUALITY
                        converted quality, default=80
  -l, --lossless        encode image losslessly, default=False
```
