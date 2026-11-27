from html import unescape
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
SITE_URL = "https://newleadershotelandeventcentre.com/"
ASSET_ID = "bfd7518b-95bf-49de-83a5-1a42796015bc"
BASE_URL = f"https://img1.wsimg.com/isteam/ip/{ASSET_ID}"
OUTPUT = ROOT / "scratch_images.json"
IMAGE_PATH = re.compile(
    rf"img1\.wsimg\.com/isteam/ip/{ASSET_ID}/"
    r"(?P<path>(?:[^/:\"'<>\s]+/)*[^/:\"'<>\s]+\.(?:jpe?g|png|webp))",
    re.IGNORECASE,
)


def main() -> None:
    request = Request(SITE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=20) as response:
        html = response.read().decode("utf-8", errors="replace")
    paths = sorted({match.group("path") for match in IMAGE_PATH.finditer(html)})

    images = [
        {
            "filename": path.rsplit("/", 1)[-1],
            "source_url": f"{BASE_URL}/{quote(path, safe='/()%')}",
            "category": (
                "logo" if path.lower().endswith("logo.png")
                else "other" if "/favicon/" in path.lower()
                else "gallery"
            ),
        }
        for path in paths
    ]
    poster = re.search(
        r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if poster:
        source_url = unescape(poster.group(1))
        images.append(
            {
                "filename": "official-video-poster",
                "source_url": source_url,
                "category": "banner",
            }
        )
    result = {
        "source_url": SITE_URL,
        "asset_id": ASSET_ID,
        "images": images,
    }
    OUTPUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(f"Found {len(images)} hotel image assets; manifest saved to {OUTPUT.name}.")


if __name__ == "__main__":
    main()
