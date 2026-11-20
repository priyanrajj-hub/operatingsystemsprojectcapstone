import urllib.request, re

with open('vercel_out.txt', 'rb') as f:
    text = f.read().decode('utf-16le', errors='ignore')

url_match = re.search(r'https://[^\s]+\.vercel\.app', text)
if url_match:
    url = url_match.group(0)
    print("Found exact deployment URL:", url)
    with open('verified_url.txt', 'w') as out:
        out.write(url)
else:
    print("No URL found in vercel_out.txt")
