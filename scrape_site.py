import urllib.request
import re
import json

BASE = 'https://newleadershotelandeventcentre.com'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    try:
        return urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
    except Exception as e:
        return f'ERROR: {e}'

# Fetch homepage
print("Fetching homepage...")
home = fetch(BASE + '/')
with open('scratch_homepage.html', 'w', encoding='utf-8') as f:
    f.write(home)
print(f"Homepage fetched: {len(home)} chars")

# Extract images - all src attributes
imgs = re.findall(r'src=["\']([^"\']+\.(jpg|jpeg|png|gif|webp|svg))["\']', home, re.IGNORECASE)
img_urls = []
for src, ext in imgs:
    if src.startswith('http'):
        img_urls.append(src)
    elif src.startswith('/'):
        img_urls.append(BASE + src)

# Extract background images from inline styles
bg_imgs = re.findall(r'url\(["\']?([^"\')\s]+\.(jpg|jpeg|png|gif|webp))["\']?\)', home, re.IGNORECASE)
for src, ext in bg_imgs:
    if src.startswith('http'):
        img_urls.append(src)
    elif src.startswith('/'):
        img_urls.append(BASE + src)

# Extract all internal links
links = re.findall(r'href=["\'](' + BASE + r'/[^"\'#?]*)["\']', home)
links += re.findall(r'href=["\'](/[^"\'#?][^"\']*)["\']', home)
links = list(set(links))

# Extract text content blocks
title = re.search(r'<title>(.*?)</title>', home, re.IGNORECASE)
meta_desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', home, re.IGNORECASE)
phones = re.findall(r'[\+0][\d\s\-\(\)]{9,20}', home)
emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', home)

# Strip HTML tags to get text
clean = re.sub(r'<script[^>]*>.*?</script>', '', home, flags=re.DOTALL)
clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL)
clean = re.sub(r'<[^>]+>', ' ', clean)
clean = re.sub(r'\s+', ' ', clean).strip()

print("\n=== PAGE TITLE ===")
if title: print(title.group(1))

print("\n=== META DESCRIPTION ===")
if meta_desc: print(meta_desc.group(1))

print("\n=== IMAGES FOUND ===")
img_urls = list(set(img_urls))
for u in img_urls:
    print(u)

print("\n=== INTERNAL LINKS ===")
for l in sorted(set(links))[:30]:
    print(l)

print("\n=== PHONE NUMBERS ===")
for p in list(set(phones))[:10]:
    print(p.strip())

print("\n=== EMAILS ===")
for e in list(set(emails))[:10]:
    print(e)

print("\n=== PAGE TEXT (first 3000 chars) ===")
print(clean[:3000])

# Save results
result = {
    'title': title.group(1) if title else '',
    'meta_desc': meta_desc.group(1) if meta_desc else '',
    'images': img_urls,
    'links': sorted(set(links)),
    'phones': list(set(phones)),
    'emails': list(set(emails)),
}
with open('scratch_scrape_result.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2)
print("\nSaved to scratch_scrape_result.json")
