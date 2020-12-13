import glob
import os
from collections import namedtuple

import dhash
from wand.image import Image

paths = sorted(glob.glob("./test-data/*.jpg"))

ImageInfo = namedtuple("ImageInfo", ["path", "dhash", "file_size_in_mb", "dims"])


def get_image_info(path):
    with Image(filename=path) as image:
        bits = dhash.dhash_int(image)
        file_size_in_mb = os.path.getsize(path) / (1024 * 1024)
        dims = (image.width, image.height)
        image_info = ImageInfo(
            path=path, dhash=bits, file_size_in_mb=file_size_in_mb, dims=dims
        )
    return image_info


def get_image_infos(paths):
    image_infos = []
    for path in paths:
        with Image(filename=path) as image:
            bits = dhash.dhash_int(image)
            file_size_in_mb = os.path.getsize(path) / (1024 * 1024)
            dims = (image.width, image.height)
            image_infos.append(
                ImageInfo(
                    path=path, dhash=bits, file_size_in_mb=file_size_in_mb, dims=dims
                )
            )
    return image_infos


def find_duplicates(image_info, image_infos):
    duplicates = []
    for i, match_image_info in enumerate(image_infos):
        if dhash.get_num_bits_different(image_info.dhash, match_image_info.dhash) <= 2:
            duplicates.append(i)
    return duplicates


# for image_info in image_infos:
#     print(f"finding dupes of {image_info.path}...")
#     for match_image_info in image_infos:
#         if image_info.path == match_image_info.path:
#             continue
#         if dhash.get_num_bits_different(image_info.dhash, match_image_info.dhash) <= 2:
#             print(f"\tdupe detected: {match_image_info.path}")
