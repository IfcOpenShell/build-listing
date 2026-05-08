"""
Usage: `python to_md.py s3data.json > output.md`

To generate 's3data.json', use the following AWS CLI command (no credentials required):
    aws s3api list-objects --output json --bucket ifcopenshell-builds --no-sign-request > s3data.json

"""

import itertools
import json
import operator
import re
import sys
from collections import defaultdict
from typing import NamedTuple
from urllib.parse import quote_plus

import humanize
import natsort
from packaging.utils import parse_wheel_filename

PREFIX = "https://s3.amazonaws.com/ifcopenshell-builds/"


class Asset(NamedTuple):
    version: str
    commit: str
    last_modified: str
    product: str
    os: str
    size: int
    key: str


def is_valid_product(product):
    if product in {"IfcConvert", "IfcGeomServer", "svgfill", "IfcViewerFull", "IfcViewerMinimal"}:
        return True
    elif re.match(r"^ifcopenshell-python-\d{2,3}u?$", product):
        return True
    return False


def get_bucket_data():
    bucket = json.load(open(sys.argv[1]))
    for zip_data in bucket["Contents"]:
        key: str = zip_data["Key"]
        if key.endswith(".zip"):
            parts = key.removesuffix(".zip").rsplit("-", 3)
            if len(parts) == 4:
                product, version, commit, os = parts

                if is_valid_product(product):
                    pass
                elif product.count("-") and is_valid_product(product.rsplit("-", 1)[0]) and os == "arm64":
                    parts = key.removesuffix(".zip").rsplit("-", 4)
                    product, version, commit, os, arm64 = parts
                    os = f"{os}-{arm64}"
                else:
                    continue

                if len(commit) != 7:
                    continue

                # E.g. searching for 'v0.8.5'.
                if not re.match(r"^v\d\.\d\.\d+$", version):
                    continue

                if os in {
                    "macosm164",
                    "macos64",
                    "linux64",
                    "linuxarm64",
                    "win32",
                    "win64",
                    "linux32",
                    "win-arm64",
                }:
                    pass
                else:
                    continue

                yield Asset(
                    version,
                    commit,
                    zip_data["LastModified"],
                    product,
                    os,
                    zip_data["Size"],
                    key,
                )
        elif key.endswith(".whl"):
            fixed = key.replace("ifcopenshell-python", "ifcopenshell_python")
            fixed = re.sub(r"(v\d\.\d\.\d)(\-|\+)(\w{7})", "v0.8.1+\\3", fixed)
            try:
                module_name, version, _, tags = parse_wheel_filename(fixed)
            except:
                continue

            if module_name == "ifcopenshell":
                module_name += "-python"

            if len(tags) != 1:
                continue

            tag = next(iter(tags))

            if "wasm" not in tag.platform:
                continue

            abi = re.sub("c|p|y", "", tag.abi)

            assert version.local is not None
            yield Asset(
                f"v{version.public}",
                version.local,
                zip_data["LastModified"],
                f"{module_name}-{abi}",
                "WASM",
                zip_data["Size"],
                key,
            )


if len(sys.argv) != 2:
    print(__doc__)
    exit(1)

print("# IfcOpenShell Builds")
print("Source code - [IfcOpenShell/build-listing](https://github.com/IfcOpenShell/build-listing)")
print()

commit_dates: defaultdict[str, list[str]] = defaultdict(list)
for asset in get_bucket_data():
    commit_dates[asset.commit].append(asset.last_modified)
hash_to_date = {commit: min(dates) for commit, dates in commit_dates.items()}

data = natsort.natsorted(get_bucket_data(), reverse=True)

for section, subsections in itertools.groupby(data, key=operator.attrgetter("version")):
    print("##", section)

    for commit, rows in itertools.groupby(
        sorted(subsections, key=lambda t: hash_to_date[t.commit], reverse=True),
        key=operator.attrgetter("commit"),
    ):
        print(f"### {commit} ({hash_to_date[commit]})")
        rows = list(rows)

        def unique_sorted(vs: list[str]) -> list[str]:
            return natsort.natsorted(set(vs))

        product = unique_sorted([r.product for r in rows])
        os = unique_sorted([r.os for r in rows])

        def format_os(os: str) -> str:
            os = os.replace("m1", " M1")
            os = os.replace("arm", " ARM")
            os = os.replace("os", "OS")
            os = os.replace("win-", "win")
            os = re.sub(r"(32|64)", r" \1bit", os)
            os = f"{os[0].upper()}{os[1:]}"
            return os

        # Header.
        osh = list(map(format_os, os))
        existing_products = {(r.product, r.os): (humanize.naturalsize(r.size), quote_plus(r.key)) for r in rows}
        print()
        print("item|", "|".join(osh))
        print("|".join(["---"] + [":---:"] * len(osh)))

        # Rows.
        for product_ in product:
            links: list[str] = []
            for os_ in os:
                size, filename = existing_products.get((product_, os_), ("-", ""))
                if filename:
                    url = f"{PREFIX}{filename}"
                    link = f"[{size}]({url})"
                else:
                    link = "-"
                links.append(link)

            print(product_, "|", "|".join(links))
        print()
