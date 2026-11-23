import urllib.request
import os
import re

ASSET_ID = 'bfd7518b-95bf-49de-83a5-1a42796015bc'
BASE_CDN = f'https://img1.wsimg.com/isteam/ip/{ASSET_ID}'

# Create upload directory
UPLOAD_DIR = r'backend\uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def download(url, filename):
    path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(path):
        print(f"  SKIP (exists): {filename}")
        return path
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(path, 'wb') as f:
            f.write(data)
        print(f"  OK ({len(data)//1024}KB): {filename}")
        return path
    except Exception as e:
        print(f"  FAIL: {filename} -> {e}")
        return None

# 1. Logo - full resolution
print("=== Downloading LOGO ===")
logo_url = f'https://img1.wsimg.com/isteam/ip/{ASSET_ID}/logo.png'
download(logo_url, 'logo.png')

# 2. All unique hotel images (high-res originals)
images = [
    ('DJI_20240725161443_0022_D-d11f1e9.jpg', 'aerial_view.jpg'),
    ('R6M26609.jpg', 'hotel_photo_1.jpg'),
    ('R6M26686.jpg', 'hotel_photo_2.jpg'),
    ('R6M26715.jpg', 'hotel_photo_3.jpg'),
    ('R6M26718.jpg', 'hotel_photo_4.jpg'),
    ('R6M26849.jpg', 'hotel_photo_5.jpg'),
    ('R6M26944.jpg', 'hotel_photo_6.jpg'),
    ('WhatsApp%20Image%202025-11-21%20at%205.44.45%20AM.jpeg', 'room_photo_1.jpg'),
    ('WhatsApp%20Image%202025-11-21%20at%205.44.46%20AM.jpeg', 'room_photo_2.jpg'),
]

# Also try the (1) variant
wa_variant = 'WhatsApp%20Image%202025-11-21%20at%205.44.45%20AM%20(1).jpeg'

print("\n=== Downloading HOTEL IMAGES ===")
downloaded = {}
for orig, save_as in images:
    url = f'{BASE_CDN}/{orig}'
    result = download(url, save_as)
    if result:
        downloaded[save_as] = result

# Try WhatsApp variant
url = f'{BASE_CDN}/{wa_variant}'
download(url, 'room_photo_3.jpg')

# Also download favicon (for reference)
favicon_url = f'https://img1.wsimg.com/isteam/ip/{ASSET_ID}/favicon/4c249eae-ca21-4bb7-b33e-f7e41f8e5e9f.jpg'
download(favicon_url, 'favicon.jpg')

print(f"\nAll done! Files saved to: {os.path.abspath(UPLOAD_DIR)}")
print("Files downloaded:")
for f in os.listdir(UPLOAD_DIR):
    size = os.path.getsize(os.path.join(UPLOAD_DIR, f))
    print(f"  {f} ({size//1024}KB)")
