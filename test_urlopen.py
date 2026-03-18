
import urllib.request
import os

def test(url):
    print(f"Testing: {url}")
    try:
        resp = urllib.request.urlopen(url)
        print(f"Success! Read {len(resp.read())} bytes")
    except Exception as e:
        print(f"Failed: {e}")

target = os.path.abspath(".env.example").replace("\\", "/")
# Basic file URL
test(f"file:///{target}")

# Try satisfy: "http" in msg and msg.endswith(".png")
# Windows might be picky about ? and # in file:// URLs
test(f"file:///{target}#http.png")
test(f"file:///{target}?http.png")

# What if we use a relative path?
test("file:README.md?http.png")

# SSRF to a non-existent local port
test("http://127.0.0.1:9999/test.png")
