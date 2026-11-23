import urllib.request
import re
import json
import os

BASE = 'https://newleadershotelandeventcentre.com'
IMG_CDN = 'https://img1.wsimg.com'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    try:
        return urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return ''

def extract_images(html_content, page_base=BASE):
    imgs = set()
    # Protocol-relative //img1.wsimg.com
    for m in re.finditer(r'(?:src|href)=["\']?(//img1\.wsimg\.com/[^"\'>\s]+)["\']?', html_content):
        imgs.add('https:' + m.group(1))
    # Absolute https
    for m in re.finditer(r'(?:src|href)=["\']?(https://img1\.wsimg\.com/[^"\'>\s]+)["\']?', html_content):
        imgs.add(m.group(1))
    # Background images in style
    for m in re.finditer(r'url\(["\']?(//img1\.wsimg\.com/[^"\')\s]+)["\']?\)', html_content):
        imgs.add('https:' + m.group(1))
    for m in re.finditer(r'url\(["\']?(https://img1\.wsimg\.com/[^"\')\s]+)["\']?\)', html_content):
        imgs.add(m.group(1))
    return imgs

# Read saved homepage
with open('scratch_homepage.html', 'r', encoding='utf-8') as f:
    home = f.read()

all_images = extract_images(home)

print(f"Found {len(all_images)} images on homepage")
for img in sorted(all_images):
    print(f"  {img}")

# Classify images
logo_imgs = [i for i in all_images if 'logo' in i.lower()]
favicon_imgs = [i for i in all_images if 'favicon' in i.lower()]
other_imgs = [i for i in all_images if 'logo' not in i.lower() and 'favicon' not in i.lower()]

print(f"\n=== LOGO URLS ===")
for i in logo_imgs: print(i)

print(f"\n=== OTHER CONTENT IMAGES ===")
for i in other_imgs: print(i)

# Extract the base asset ID
asset_id = 'bfd7518b-95bf-49de-83a5-1a42796015bc'
logo_base = f'https://img1.wsimg.com/isteam/ip/{asset_id}/logo.png'
logo_hires = logo_base + '/:/rs=w:400,h:400,m'

print(f"\n=== HIGH-RES LOGO URL ===")
print(logo_hires)

# Try to get image list from the GoDaddy isteam API
isteam_base = f'https://img1.wsimg.com/isteam/ip/{asset_id}/'

# Extract all unique image paths from the HTML
all_isteam = set()
for m in re.finditer(r'img1\.wsimg\.com/isteam/ip/' + asset_id + r'/([^/"\'>\s:,\)]+)', home):
    path = m.group(1)
    if not path.startswith('favicon') and 'logo.png' not in path:
        full = isteam_base + path
        all_isteam.add(full)

print(f"\n=== ALL ISTEAM IMAGE PATHS ===")
for i in sorted(all_isteam):
    print(i)

# Save final
result = {
    'asset_id': asset_id,
    'logo_hires': logo_hires,
    'logo_urls': logo_imgs,
    'content_images': sorted(all_isteam),
    'all_images': sorted(all_images),
}
with open('scratch_images.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2)
print("\nSaved to scratch_images.json")
