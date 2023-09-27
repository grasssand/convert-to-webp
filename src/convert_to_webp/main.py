import csv
import logging
import math
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Generator

QUALITY = 80
LOSSLESS = False
IMAGE_EXT = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]


logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    level=logging.DEBUG,
)
re_output_file_size = re.compile(r"[o|O]utput.+?(\d+)\sbytes")


class Converter:
    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        quality: int = QUALITY,
        lossless: bool = LOSSLESS,
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.quality = quality
        self.lossless = lossless

        self.missing = []

    def check_libwebp(self) -> bool:
        return bool(shutil.which("cwebp") and shutil.which("gif2webp"))

    def is_image(self, file: Path) -> bool:
        return file.is_file() and (file.suffix.lower() in IMAGE_EXT)

    def get_output_path(self, input_path: Path) -> Path:
        output_path = (
            self.output_dir
            / input_path.relative_to(self.input_dir).parent
            / f"{input_path.stem}.webp"
        )
        if not output_path.parent.is_dir():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        return output_path

    def parse_stdout(
        self, input_file: Path, stdout: str
    ) -> tuple[str, str, int, int | None, float | None]:
        file_dir, file_name = str(input_file.parent), input_file.name
        original_size = math.ceil(
            input_file.stat().st_size / 1024
        )  # bytes to KB, min is 1KB
        webp_size, changed_rate = None, None
        matched = re_output_file_size.search(stdout)
        if original_size and matched:
            webp_size = math.ceil(int(matched.group(1)) / 1024)
            changed_rate = round((webp_size - original_size) / original_size, 2)

        return file_dir, file_name, original_size, webp_size, changed_rate

    def get_all_images(self, input_path: Path) -> Generator[Path, None, None]:
        if input_path.is_file() and self.is_image(input_path):
            yield input_path
        elif input_path.is_dir():
            for i in self.input_dir.glob("**/*"):
                if self.is_image(i):
                    yield i
                elif i.is_file():
                    self.missing.append(str(i))

    def convert(
        self, input_file: Path
    ) -> tuple[str, str, int, int | None, float | None]:
        output_file = self.get_output_path(input_file)

        cli = "gif2webp" if input_file.suffix.lower() == ".gif" else "cwebp"
        command = [cli, "-q", str(self.quality)]
        if self.lossless and cli == "cwebp":
            command.append("-lossless")
        if not self.lossless and cli == "gif2webp":
            command.append("-lossy")
        command += ["-o", output_file, "--", input_file]

        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        return self.parse_stdout(input_file, result.stdout.decode())

    def main(self) -> None:
        if not self.check_libwebp():
            sys.exit("Please install `libwebp` first!")

        started_at = time.monotonic()
        count = 0

        images = self.get_all_images(self.input_dir)
        failed, bigger = [], []

        headers = ["dir", "file", "original(KB)", "webp(KB)", "changed"]
        converted_details = self.output_dir / "details.csv"
        missing_files = self.output_dir / "missing.csv"
        if not self.output_dir.is_dir():
            self.output_dir.mkdir(parents=True)

        with (
            ProcessPoolExecutor() as executor,
            open(converted_details, "w", encoding="utf8", newline="") as f,
            open(missing_files, "w", encoding="utf8") as m,
        ):
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            for result in executor.map(self.convert, images):
                writer.writerow(dict(zip(headers, result)))
                count += 1

                file_dir, file_name, original_size, webp_size, changed_rate = result
                logging.info(
                    f"{file_dir}/{file_name}"
                    f"| {original_size:>5} KB"
                    + (
                        f"| {webp_size:>5} KB| {changed_rate:>5.0%}"
                        if webp_size
                        else "|"
                    )
                )

                if changed_rate is None:
                    failed.append(f"{file_dir}/{file_name}")
                    count -= 1
                elif changed_rate > 1:
                    bigger.append(f"{file_dir}/{file_name}")

            # write not converted files
            for i in self.missing:
                m.write(i)

        if bigger or failed:
            print(f"{'=' * 20} WARNING {'=' * 20}")
            for i in bigger:
                logging.warning(f"Converted {i} is BIGGER")
            for i in failed:
                logging.error(f"Converted {i} FAILED")

        print(f"{'=' * 20} Result {'=' * 20}")
        logging.info(f"Converted: {count}, Cost: {time.monotonic() - started_at:.2f}s")
        logging.info(f"View all details in {converted_details.resolve()}")
        logging.info(f"View not converted files in {missing_files.resolve()}")


def cli():
    import argparse

    parser = argparse.ArgumentParser(
        prog="convert-to-webp", description="Convert images to webp"
    )
    parser.add_argument("in_dir", type=Path, help="input file or directory")
    parser.add_argument(
        "-o",
        "--out",
        dest="out_dir",
        type=Path,
        required=True,
        help="output directory",
    )
    parser.add_argument(
        "-q", "--quality", type=int, default=80, help="converted quality, default=80"
    )
    parser.add_argument(
        "-l",
        "--lossless",
        action="store_true",
        help="encode image losslessly, default=False",
    )
    args = parser.parse_args()

    converter = Converter(
        input_dir=args.in_dir,
        output_dir=args.out_dir,
        quality=args.quality,
        lossless=args.lossless,
    )
    converter.main()


if __name__ == "__main__":
    cli()
