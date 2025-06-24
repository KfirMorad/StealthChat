# gui.py — StealthChat GUI for the user-count backend

import os, threading, asyncio, base64, tkinter as tk
from typing import Callable, Optional
from dotenv import load_dotenv
from PIL import Image, ImageGrab, ImageFile
import PIL.Image
import io
import requests
import time
import random

import crypter
from chat import (
    bot, session_counts,
    start_auto_session_from_thread, join_session_from_thread,
    leave_session_from_thread, send_session_message_from_thread,
    register_receive_callback, unregister_receive_callback,
    sync_active_sessions,
)

# ─── env / bot thread ───────────────────────────────────────────────────
load_dotenv()
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]
BOT_TOKEN = os.environ["BOT_TOKEN"]; GUILD_ID = int(os.environ["GUILD_ID"])
threading.Thread(target=lambda: bot.run(BOT_TOKEN), daemon=True).start()

# ─── Tk basics ──────────────────────────────────────────────────────────
root = tk.Tk(); root.title("StealthChat GUI")
root.geometry("600x500"); root.configure(bg="#000"); root.resizable(False, False)
FONT = ("Consolas", 12); TX_BG, TX_FG = "#000", "#0f0"

current_session: Optional[str] = None
_my_receive_cb: Optional[Callable[[str], None]] = None
user_name: str

frame = tk.Frame(root, bg=TX_BG); frame.pack(fill="both", expand=True)

def clear_frame(): [c.destroy() for c in frame.winfo_children()]

def on_close():
    if current_session and _my_receive_cb:
        pwd = crypter.session_passwords.get(current_session)
        if pwd:
            payload = f"System:{user_name} has left the session"
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
        img: Optional[PIL.Image.Image] = None  # Explicit type hint

        # Case 1: direct image object
        if isinstance(raw, PIL.Image.Image):
            img = raw

        # Case 2: file list
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

        resp = requests.post("https://api.imgbb.com/1/upload", data={
            "key": IMGBB_API_KEY,
            "image": b64,
            "expiration": 600
        })

        if resp.status_code == 200:
            return resp.json()["data"]["url"]
        return None

    except Exception as e:
        print(f"[upload_clipboard_image] error: {e}")
        return None
    try:
        raw = ImageGrab.grabclipboard()
        img = None

        # Case 1: direct image object
        if hasattr(raw, "save"):
            img = raw

        # Case 2: list of file paths
        elif isinstance(raw, list) and len(raw) > 0:
            from PIL import Image
            try:
                img = Image.open(raw[0])
            except Exception:
                pass  # fail silently

        if img is None:
            return None  # no image found

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()

        resp = requests.post("https://api.imgbb.com/1/upload", data={
            "key": IMGBB_API_KEY,
            "image": b64,
            "expiration": 600
        })

        if resp.status_code == 200:
            return resp.json()["data"]["url"]
        return None

    except Exception as e:
        print(f"[ERROR] upload_clipboard_image(): {e}")
        return None

    try:
        raw = ImageGrab.grabclipboard()

        # Case 1: it's a direct image object (from screenshot tools, etc.)
        if hasattr(raw, "save"):
            img = raw

        # Case 2: it's a file path list like ["C:/Users/Kfir/Desktop/pic.png"]
        elif isinstance(raw, list) and len(raw) > 0:
            try:
                from PIL import Image
                img = Image.open(raw[0])
            except Exception:
                return None
        else:
            return None

        # save to buffer
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode()

        # upload to imgbb
        resp = requests.post("https://api.imgbb.com/1/upload", data={
            "key": IMGBB_API_KEY,
            "image": b64,
            "expiration": 600  # delete after 10 minutes
        })

        if resp.status_code == 200:
            return resp.json()["data"]["url"]
        return None

    except Exception as e:
        print(f"[ERROR] upload_clipboard_image(): {e}")
        return None


# ───────────────────────── connect UI ───────────────────────────────────
def show_connect_ui():
    clear_frame()
    # Matrix effect behind everything
    # 1. Create and send canvas to the background
    canvas = tk.Canvas(frame, bg=TX_BG, highlightthickness=0)
    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    canvas.lower("all")  # ensure all widgets appear above

    # 2. Setup drops in left/right thirds
    char_w = 10
    canvas_w, canvas_h = 600, 500
    num_cols = canvas_w // char_w

    drops = []
    for i in range(num_cols):
        x = i * char_w
        if x < 180 or x > 420:
            drops.append({"x": x, "y": random.randint(-500, 0), "trail": []})

    matrix_chars = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    # 3. Enhanced movie-style effect
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
                    color = "#0f0"  # bright neon green head
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




    # ASCII logo appears ON TOP of matrix
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

    # Optional ESC exit
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

        payload = f"System:{name} has joined the session"
        enc = crypter.encrypt_message(payload, pwd)
        send_session_message_from_thread(sid, base64.urlsafe_b64encode(enc).decode())
        show_chat_ui()

    tk.Button(frame, text="Connect", command=connect,
              font=("Consolas", 14, "bold"),
              fg=TX_FG, bg="#222", bd=0, activebackground="#333").pack(pady=20)

# ───────────────────────── chat UI ───────────────────────────────────────
def show_chat_ui():
    clear_frame()
    assert current_session
    sid = current_session

    chat_box = tk.Text(frame, bg=TX_BG, fg=TX_FG, font=FONT, state="disabled")
    chat_box.pack(fill="both", expand=True, padx=5, pady=5)

    def put(line: str, expire_after: int = 600):
        chat_box.config(state="normal")
        tag = f"msg_{time.time()}"  # unique tag per line
        chat_box.insert("end", line + "\n", tag)
        chat_box.config(state="disabled")
        chat_box.see("end")

        def clear():
            chat_box.config(state="normal")
            chat_box.delete(f"{tag}.first", f"{tag}.last +1l")
            chat_box.config(state="disabled")

        chat_box.after(expire_after * 1000, clear)


    put(f"--- Session {sid} ---")

    def _recv(msg: str):
        if msg.startswith("System:"):
            put(f"*** {msg.split(':', 1)[1]} ***")

        elif msg.startswith("Client disconnected"):
            put(f"*** {msg} ***")
            entry.config(state="disabled")
            send_btn.config(state="disabled")

        # IMAGE branch
        elif "http" in msg and (msg.endswith(".png") or msg.endswith(".jpg") or ".ibb.co" in msg):
            sender, body = msg.split(":", 1)
            put(f"< [Image] {sender}: {body.strip()}")

            try:
                from PIL import Image, ImageTk
                import urllib.request

                # download
                resp = urllib.request.urlopen(body.strip())
                img_data = resp.read()
                img = Image.open(io.BytesIO(img_data))

                # cap size, preserve aspect ratio
                max_w = 300
                max_h = 300
                img.thumbnail((max_w, max_h))

                photo = ImageTk.PhotoImage(img)

                # inject blank line + image + blank line
                chat_box.config(state="normal")
                chat_box.insert("end", "\n")                      # ensure on new line
                img_label = tk.Label(chat_box, image=photo, bg=TX_BG)
                setattr(img_label, "image", photo)                # keep ref
                chat_box.window_create("end", window=img_label)
                chat_box.insert("end", "\n\n")                    # pad after
                chat_box.config(state="disabled")
                chat_box.see("end")

            except Exception as e:
                put(f"[Error displaying image: {e}]")


        else:
            sender, body = msg.split(":", 1)
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
        put(f"> {txt}")
        payload = f"{user_name}:{txt}"
        pwd = crypter.session_passwords[sid]
        enc = crypter.encrypt_message(payload, pwd)
        send_session_message_from_thread(
            sid, base64.urlsafe_b64encode(enc).decode()
        )

    def on_paste(_evt=None):
        url = upload_clipboard_image()
        if url:
            put("> [Image pasted]")
            payload = f"{user_name}:{url}"
            pwd     = crypter.session_passwords[sid]
            enc     = crypter.encrypt_message(payload, pwd)
            send_session_message_from_thread(
                sid, base64.urlsafe_b64encode(enc).decode()
            )


    send_btn.config(command=_send)
    entry.bind("<Return>", _send)
    root.bind("<Control-v>", on_paste)
    entry.focus_set()


# ───────────────────────── start app ────────────────────────────────────
show_connect_ui(); root.mainloop()
