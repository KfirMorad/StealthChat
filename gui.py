
import os, threading, asyncio, base64, tkinter as tk
from typing import Callable, Optional
from dotenv import load_dotenv
from PIL import Image, ImageGrab, ImageFile
import PIL.Image
import io
import requests
import time
import random
import urllib.parse

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

# Allowed image host for SSRF prevention
ALLOWED_IMAGE_HOST = "i.ibb.co"


def sanitize_display(text: str) -> str:
    """Strip control characters and limit length for safe display."""
    sanitized = "".join(c for c in text if c.isprintable() or c in (" ", "\t"))
    return sanitized[:2000]


def is_safe_image_url(url: str) -> bool:
    """Validate that an image URL points to the expected trusted host."""
    try:
        parsed = urllib.parse.urlparse(url)
        return (
            parsed.scheme in ("https",)
            and parsed.netloc == ALLOWED_IMAGE_HOST
        )
    except Exception:
        return False


def build_payload(name: str, text: str) -> str:
    """Build a message payload, escaping colons in the username."""
    safe_name = name.replace(":", "\\:")
    return f"{safe_name}:{text}"


def split_payload(payload: str):
    """Split a payload into (sender, body), respecting escaped colons in sender."""
    parts = payload.split(":", 1)
    if len(parts) == 2:
        sender = parts[0].replace("\\:", ":")
        body = parts[1]
        return sender, body
    return payload, ""


def on_close():
    if current_session and _my_receive_cb:
        pwd = crypter.session_passwords.get(current_session)
        if pwd:
            payload = build_payload("System", f"{user_name} has left the session")
            enc     = crypter.encrypt_message(payload, pwd)
            send_session_message_from_thread(
                current_session, base64.urlsafe_b64encode(enc).decode())
        unregister_receive_callback(current_session, _my_receive_cb)
        leave_session_from_thread(current_session)
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)


def upload_clipboard_image() -> Optional[str]:
    try:
        raw = ImageGrab.grabclipboard()
        img: Optional[PIL.Image.Image] = None

        if isinstance(raw, PIL.Image.Image):
            img = raw
        elif isinstance(raw, list) and len(raw) > 0:
            try:
                img = Image.open(raw[0])
            except Exception:
                return None

        if img is None:
            return None

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()

        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={
                "key": IMGBB_API_KEY,
                "image": b64,
                "expiration": 600
            },
            timeout=15
        )

        if resp.status_code == 200:
            url = resp.json()["data"]["url"]
            # Validate the returned URL before using it
            if is_safe_image_url(url):
                return url
            else:
                print(f"[upload_clipboard_image] Untrusted URL returned: {url}")
                return None
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
                    color = f"#00{fade}00"
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
        # Validate name does not contain structural characters that break parsing
        if len(name) > 64:
            err_lbl.config(text="Display name too long (max 64 chars)"); return
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

        payload = build_payload("System", f"{name} has joined the session")
        enc = crypter.encrypt_message(payload, pwd)
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
        safe_line = sanitize_display(line)
        chat_box.config(state="normal")
        tag = f"msg_{time.time()}_{random.randint(0, 999999)}"
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
        # Only treat as System message if it was decrypted with the correct key
        # and the sender field is literally "System" (enforced by split_payload)
        if msg.startswith("System:"):
            _, body = split_payload(msg)
            put(f"*** {sanitize_display(body)} ***")

        elif msg.startswith("Client disconnected"):
            put(f"*** {sanitize_display(msg)} ***")
            entry.config(state="disabled")
            send_btn.config(state="disabled")

        else:
            sender, body = split_payload(msg)
            sender = sanitize_display(sender)
            body = sanitize_display(body)
            body_stripped = body.strip()

            # Check if body is a safe image URL (case-sensitive, validated host)
            if is_safe_image_url(body_stripped):
                put(f"< [Image] {sender}: {body_stripped}")

                try:
                    from PIL import ImageTk
                    import urllib.request

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
                    put(f"[Error displaying image: {sanitize_display(str(e))}]")

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
        put(f"> {sanitize_display(txt)}")
        payload = build_payload(user_name, txt)
        pwd = crypter.session_passwords[sid]
        enc = crypter.encrypt_message(payload, pwd)
        send_session_message_from_thread(
            sid, base64.urlsafe_b64encode(enc).decode()
        )

    def on_paste(_evt=None):
        url = upload_clipboard_image()
        if url:
            put("> [image pasted]")
            payload = build_payload(user_name, url)
            pwd = crypter.session_passwords.get(sid)
            if pwd:
                enc = crypter.encrypt_message(payload, pwd)
                send_session_message_from_thread(
                    sid, base64.urlsafe_b64encode(enc).decode()
                )

    entry.bind("<Return>", _send)
    entry.bind("<Control-v>", on_paste)
    send_btn.config(command=_send)


show_connect_ui()
root.mainloop()
