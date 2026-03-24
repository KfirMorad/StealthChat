
import os, threading, asyncio, base64, tkinter as tk
from typing import Callable, Optional
from dotenv import load_dotenv
from PIL import Image, ImageGrab, ImageFile
import PIL.Image
import io
import requests
import time
import random
import re
import pathlib

import crypter
from chat import (
    bot, session_counts,
    start_auto_session_from_thread, join_session_from_thread,
    leave_session_from_thread, send_session_message_from_thread,
    register_receive_callback, unregister_receive_callback,
    sync_active_sessions,
)

load_dotenv()
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]; GUILD_ID = int(os.environ["GUILD_ID"])
threading.Thread(target=lambda: bot.run(BOT_TOKEN), daemon=True).start()

root = tk.Tk(); root.title("StealthChat GUI")
root.geometry("600x500"); root.configure(bg="#000"); root.resizable(False, False)
FONT = ("Consolas", 12); TX_BG, TX_FG = "#000", "#0f0"

current_session: Optional[str] = None
_my_receive_cb: Optional[Callable[[str], None]] = None
user_name: str

frame = tk.Frame(root, bg=TX_BG); frame.pack(fill="both", expand=True)

def clear_frame(): [c.destroy() for c in frame.winfo_children()]

# Allowed image extensions for path traversal mitigation
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

# Allowed image URL pattern for SSRF mitigation (only ibb.co URLs accepted for display)
ALLOWED_IMAGE_URL_PATTERN = re.compile(r'^https://i\.ibb\.co/[A-Za-z0-9/_\-]+\.(png|jpg|jpeg|gif|webp)$')

def sanitize_display_text(text: str) -> str:
    """Remove control characters and limit length to prevent injection in display."""
    # Remove non-printable characters except newline
    sanitized = re.sub(r'[^\x20-\x7E\n]', '', text)
    # Limit length
    return sanitized[:2000]

def safe_open_image_from_path(path: str) -> Optional[PIL.Image.Image]:
    """Open an image only if it has an allowed extension and is a real image file."""
    try:
        p = pathlib.Path(path).resolve()
        if p.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
            print(f"[safe_open_image_from_path] Rejected extension: {p.suffix}")
            return None
        img = Image.open(str(p))
        img.verify()  # verify it is actually an image
        # Re-open after verify (verify closes the file)
        img = Image.open(str(p))
        return img
    except Exception as e:
        print(f"[safe_open_image_from_path] error: {e}")
        return None

def on_close():
    if current_session and _my_receive_cb:
        pwd = crypter.session_passwords.get(current_session)
        if pwd:
            payload = f"System:{sanitize_display_text(user_name)} has left the session"
            enc     = crypter.encrypt_message(payload, pwd)
            send_session_message_from_thread(
                current_session, base64.urlsafe_b64encode(enc).decode())
        unregister_receive_callback(current_session, _my_receive_cb)
        leave_session_from_thread(current_session)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)


def upload_clipboard_image() -> Optional[str]:
    """Upload clipboard image to imgbb. Validates image type before upload."""
    try:
        raw = ImageGrab.grabclipboard()
        img: Optional[PIL.Image.Image] = None

        if isinstance(raw, PIL.Image.Image):
            img = raw

        # Case 2: file list - apply path traversal mitigation
        elif isinstance(raw, list) and len(raw) > 0:
            img = safe_open_image_from_path(str(raw[0]))
            if img is None:
                return None

        if img is None:
            return None

        # Validate image format
        img_format = img.format if img.format else "PNG"
        if img_format.upper() not in {"PNG", "JPEG", "JPG", "GIF", "BMP", "WEBP"}:
            print(f"[upload_clipboard_image] Rejected image format: {img_format}")
            return None

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()

        # SSRF mitigation: use a fixed, hardcoded URL (no user input in URL)
        upload_url = "https://api.imgbb.com/1/upload"
        resp = requests.post(upload_url, data={
            "key": IMGBB_API_KEY,
            "image": b64,
            "expiration": 600
        }, timeout=15)

        if resp.status_code == 200:
            result_url = resp.json().get("data", {}).get("url", "")
            # Validate returned URL matches expected pattern
            if not ALLOWED_IMAGE_URL_PATTERN.match(result_url):
                print(f"[upload_clipboard_image] Unexpected URL returned: {result_url}")
                return None
            return result_url
        return None

    except Exception as e:
        print(f"[upload_clipboard_image] error: {e}")
        return None


def show_connect_ui():
    clear_frame()
    canvas = tk.Canvas(frame, bg=TX_BG, highlightthickness=0)
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    canvas.lower("all")  
    char_w = 10
    canvas_w, canvas_h = 600, 500
    num_cols = canvas_w // char_w

    drops = []
    for i in range(num_cols):
        x = i * char_w
        if x < 180 or x > 420:
            drops.append({"x": x, "y": random.randint(-500, 0), "trail": []})

    matrix_chars = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def matrix_effect():
        if not canvas.winfo_exists():
            return

        canvas.delete("matrix")
        for drop in drops:
            x, y = drop["x"], drop["y"]
            char = random.choice(matrix_chars)
            drop["trail"].insert(0, (x, y, char))
            drop["trail"] = drop["trail"][:12]

            for i, (tx, ty, tch) in enumerate(drop["trail"]):
                if ty > canvas_h or ty < 0:
                    continue
                if i == 0:
                    color = "#0f0"  
                else:
                    fade = hex(max(0, 15 - i * 2))[2:].zfill(2)
                    color = f"#00{fade}00"  # fading tail
                canvas.create_text(tx, ty, text=tch, fill=color, font=("Consolas", 8), tags="matrix")

            drop["y"] += 15
            if drop["y"] > canvas_h + 50:
                drop["y"] = random.randint(-200, 0)
                drop["trail"].clear()

        frame.after(75, matrix_effect)

    matrix_effect()


    ascii_label = tk.Label(frame, fg=TX_FG, bg=TX_BG, font=("Consolas", 9), justify="left")
    ascii_label.pack(pady=(20, 10))

    def typewriter(text, delay=3):
        buf = [""]
        def tick(i=0):
            if i < len(text):
                c = text[i]
                buf[0] += c
                ascii_label.config(text=buf[0])
                frame.after(delay, tick, i + 1)
        tick()

    ascii_art = r"""
     __ _             _ _   _       ___ _           _
    / _\ |_ ___  __ _| | |_| |__   / __\ |__   __ _| |_
    \ \| __/ _ \/ _` | | __| '_ \ / /  | '_ \ / _` | __|
    _\ \ ||  __/ (_| | | |_| | | / /___| | | | (_| | |_
    \__/\__\___|\__,_|_|\__|_| |_\____/|_| |_|\__,_|\__|
    """
    typewriter(ascii_art.strip("\n"))

    root.bind("<Escape>", lambda _: on_close())


    name_v, room_v, pwd_v = tk.StringVar(), tk.StringVar(), tk.StringVar()

    def add_row(label, var, hide=False):
        tk.Label(frame, text=label, fg=TX_FG, bg=TX_BG, font=FONT).pack(pady=5)
        tk.Entry(frame, textvariable=var, show="*" if hide else "",
                 font=FONT, bg="#111", fg=TX_FG, insertbackground=TX_FG).pack(pady=5)

    add_row("Display name:", name_v)
    add_row("Session ID (blank = new):", room_v)
    add_row("Password:", pwd_v, hide=True)

    err_lbl = tk.Label(frame, text="", fg="#f00", bg=TX_BG, font=FONT); err_lbl.pack(pady=(0,10))

    def connect():
        global current_session, user_name, _my_receive_cb
        name, sid, pwd = name_v.get().strip(), room_v.get().strip(), pwd_v.get().strip()
        if not name: err_lbl.config(text="Enter display name"); return
        if not pwd:  err_lbl.config(text="Enter password");     return

        # Validate display name: alphanumeric + limited special chars, max 32 chars
        if not re.match(r'^[A-Za-z0-9_\-\.]{1,32}$', name):
            err_lbl.config(text="Display name: 1-32 alphanumeric/_/- chars only")
            return

        # Validate session ID if provided
        if sid and not re.match(r'^[A-Za-z0-9_\-]{1,64}$', sid):
            err_lbl.config(text="Invalid session ID format")
            return

        # Enforce minimum password strength
        if len(pwd) < 8:
            err_lbl.config(text="Password must be at least 8 characters")
            return

        try: asyncio.run_coroutine_threadsafe(sync_active_sessions(), bot.loop).result(5)
        except Exception: pass
        if sid and sid not in session_counts:
            err_lbl.config(text="Session ID not found"); return
        err_lbl.config(text="")

        if sid:
            join_session_from_thread(sid)
            crypter.init_session(sid, pwd)
        else:
            sid = start_auto_session_from_thread(GUILD_ID)
            crypter.init_session(sid, pwd)

        current_session = sid; user_name = name

        # Sanitize name before embedding in payload
        safe_name = sanitize_display_text(name)
        payload = f"System:{safe_name} has joined the session"
        # Retrieve password securely from session store
        session_pwd = crypter.session_passwords.get(sid)
        if not session_pwd:
            err_lbl.config(text="Session password not initialized")
            return
        enc = crypter.encrypt_message(payload, session_pwd)
        send_session_message_from_thread(sid, base64.urlsafe_b64encode(enc).decode())
        show_chat_ui()

    tk.Button(frame, text="Connect", command=connect,
              font=("Consolas", 14, "bold"),
              fg=TX_FG, bg="#221", bd=0, activebackground="#333").pack(pady=20)

def show_chat_ui():
    clear_frame()
    assert current_session
    sid = current_session

    chat_box = tk.Text(frame, bg=TX_BG, fg=TX_FG, font=FONT, state="disabled")
    chat_box.pack(fill="both", expand=True, padx=5, pady=5)

    def put(line: str, expire_after: int = 600):
        # Sanitize line before displaying to prevent injection
        safe_line = sanitize_display_text(line)
        chat_box.config(state="normal")
        tag = f"msg_{time.time()}"  # unique tag per line
        chat_box.insert("end", safe_line + "\n", tag)
        chat_box.config(state="disabled")
        chat_box.see("end")

        def clear():
            chat_box.config(state="normal")
            try:
                chat_box.delete(f"{tag}.first", f"{tag}.last +1l")
            except Exception:
                pass
            chat_box.config(state="disabled")

        chat_box.after(expire_after * 1000, clear)


    put(f"--- Session {sid} ---")

    def _recv(msg: str):
        if msg.startswith("System:"):
            safe_msg = sanitize_display_text(msg.split(':', 1)[1])
            put(f"*** {safe_msg} ***")

        elif msg.startswith("Client disconnected"):
            put(f"*** {sanitize_display_text(msg)} ***")
            entry.config(state="disabled")
            send_btn.config(state="disabled")

        elif ":" in msg:
            parts = msg.split(":", 1)
            sender = sanitize_display_text(parts[0])
            body = sanitize_display_text(parts[1])

            # Check if body looks like an allowed image URL
            body_stripped = body.strip()
            if ALLOWED_IMAGE_URL_PATTERN.match(body_stripped):
                put(f"< [Image] {sender}: {body_stripped}")

                try:
                    from PIL import Image, ImageTk
                    import urllib.request

                    # SSRF mitigation: only fetch URLs matching allowed pattern
                    req = urllib.request.Request(
                        body_stripped,
                        headers={"User-Agent": "StealthChat/1.0"}
                    )
                    resp = urllib.request.urlopen(req, timeout=10)
                    img_data = resp.read()
                    img = Image.open(io.BytesIO(img_data))

                    max_w = 300
                    max_h = 300
                    img.thumbnail((max_w, max_h))

                    photo = ImageTk.PhotoImage(img)

                    chat_box.config(state="normal")
                    chat_box.insert("end", "\n")                    
                    img_label = tk.Label(chat_box, image=photo, bg=TX_BG)
                    setattr(img_label, "image", photo)               
                    chat_box.window_create("end", window=img_label)
                    chat_box.insert("end", "\n\n")                   
                    chat_box.config(state="disabled")
                    chat_box.see("end")

                except Exception as e:
                    put(f"[Error displaying image: {sanitize_display_text(str(e))}]")

            else:
                if sender != user_name:
                    put(f"< [{sender}] {body}")

    register_receive_callback(sid, _recv)
    global _my_receive_cb
    _my_receive_cb = _recv

    bottom = tk.Frame(frame, bg=TX_BG)
    bottom.pack(fill="x", side="bottom", padx=5, pady=5)

    entry = tk.Entry(bottom, bg="#111", fg=TX_FG, font=FONT, insertbackground=TX_FG)
    entry.pack(side="left", fill="x", expand=True)

    send_btn = tk.Button(bottom, text="Send", fg=TX_FG, bg="#111", font=FONT)
    send_btn.pack(side="right", padx=(5, 0))

    def _send(_=None):
        txt = entry.get().strip()
        if not txt:
            return
        entry.delete(0, "end")
        # Sanitize text before display and transmission
        safe_txt = sanitize_display_text(txt)
        put(f"> {safe_txt}")
        # Sanitize user_name before embedding in payload
        safe_user = sanitize_display_text(user_name)
        # Use separator that won't conflict; colon is the delimiter
        # Ensure user_name doesn't contain colon to prevent spoofing
        safe_user_no_colon = safe_user.replace(':', '_')
        payload = f"{safe_user_no_colon}:{safe_txt}"
        # Retrieve password securely from session store
        session_pwd = crypter.session_passwords.get(sid)
        if not session_pwd:
            put("[Error: session password not found]")
            return
        enc = crypter.encrypt_message(payload, session_pwd)
        send_session_message_from_thread(
            sid, base64.urlsafe_b64encode(enc).decode()
        )

    def on_paste(_evt=None):
        url = upload_clipboard_image()
        if url:
            put("> [image pasted]")
            safe_user = sanitize_display_text(user_name).replace(':', '_')
            payload = f"{safe_user}:{url}"
            session_pwd = crypter.session_passwords.get(sid)
            if not session_pwd:
                put("[Error: session password not found]")
                return
            enc = crypter.encrypt_message(payload, session_pwd)
            send_session_message_from_thread(
                sid, base64.urlsafe_b64encode(enc).decode()
            )

    entry.bind("<Return>", _send)
    entry.bind("<Control-v>", on_paste)
    send_btn.config(command=_send)

    root.bind("<Escape>", lambda _: on_close())


show_connect_ui()
root.mainloop()
