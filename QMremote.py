import os
import time
import threading
import datetime
import requests
from urllib.parse import quote

import tkinter as tk
from tkinter import messagebox

# ==========================
# Firebase 기본 설정
# ==========================
FIREBASE_ROOT = "https://test-mode-49b3b-default-rtdb.firebaseio.com"

# 서버 목록 (한글 그대로 사용, 2x2 배치 순서)
SERVER_LIST = [
    "큐엠메인서버1",
    "큐엠메인서버2",
    "큐엠메인서버3",
    "큐엠메인서버5",
]

# 이 PC의 ID = 윈도우 컴퓨터 이름
PC_ID = os.environ.get("COMPUTERNAME", "UNKNOWN_PC")

# 현재 PC 표시 이름 (Firebase config에서 불러오거나, 설정창에서 입력)
current_user_name = ""  # 비어 있으면 PC_ID를 대신 사용

# 서버 상태 캐시
# 각 서버: {"status": "OFF" / "ON", "user": str, "timestamp": str}
server_states = {
    name: {"status": "OFF", "user": "", "timestamp": ""}
    for name in SERVER_LIST
}

# 서버별 비고 캐시 (Firebase /notes 에 저장)
firebase_notes = {
    name: ""
    for name in SERVER_LIST
}

# UI 위젯 캐시
# {server_name: {"status_label": label, "note_label": label, "start_btn": btn, "end_btn": btn, "note_btn": btn}}
server_widgets = {}

# ==========================
# Firebase 헬퍼 함수
# ==========================

def fb_url(path: str) -> str:
    """
    Firebase Realtime DB 경로를 .json까지 포함해서 만들어주는 함수
    path 예시: "/servers" 또는 "/servers/큐엠메인서버1"
    """
    if not path.startswith("/"):
        path = "/" + path
    return f"{FIREBASE_ROOT}{path}.json"


def get_servers_state():
    """Firebase에서 전체 /servers 상태를 가져옴."""
    try:
        res = requests.get(fb_url("/servers"), timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data is None:
                return {}
            return data
    except Exception:
        pass
    return {}


def put_server_state(server_name: str, state: dict):
    """특정 서버 상태를 Firebase에 저장."""
    try:
        # 한글 서버명 URL 인코딩
        encoded_name = quote(server_name, safe="")
        url = fb_url(f"/servers/{encoded_name}")
        requests.put(url, json=state, timeout=3)
    except Exception as e:
        print("[ERROR] put_server_state:", e)


def get_pc_config():
    """이 PC의 config (/config/PC_ID)를 Firebase에서 읽기."""
    try:
        url = fb_url(f"/config/{PC_ID}")
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def put_pc_config(name: str):
    """이 PC의 config (/config/PC_ID)에 name 저장."""
    try:
        url = fb_url(f"/config/{PC_ID}")
        data = {"name": name}
        requests.put(url, json=data, timeout=3)
    except Exception as e:
        print("[ERROR] put_pc_config:", e)


def save_note_to_firebase(server_name: str, note: str):
    """서버별 비고를 /notes/<server_name> 에 저장."""
    try:
        encoded_name = quote(server_name, safe="")
        url = fb_url(f"/notes/{encoded_name}")
        requests.put(url, json=note, timeout=3)
    except Exception as e:
        print("[ERROR] save_note_to_firebase:", e)


def load_notes_from_firebase():
    """프로그램 시작 시 /notes 를 읽어서 firebase_notes 채움."""
    global firebase_notes
    try:
        url = fb_url("/notes")
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, dict):
                for name in SERVER_LIST:
                    val = data.get(name, "")
                    if isinstance(val, str):
                        firebase_notes[name] = val
    except Exception:
        pass


# ==========================
# 공통 유틸
# ==========================

def get_effective_username() -> str:
    """표시 이름이 있으면 그걸 쓰고, 없으면 PC_ID 사용."""
    global current_user_name
    return current_user_name.strip() if current_user_name.strip() else PC_ID


def is_this_pc_in_use() -> bool:
    """현재 이 PC 이름이 '사용 중(ON)'인 서버의 user와 같으면 True."""
    my_name = get_effective_username()

    for name, state in server_states.items():
        if state.get("status") == "ON" and state.get("user") == my_name:
            return True
    return False


# ==========================
# 버튼 동작
# ==========================

def on_start(server_name: str):
    """서버에 사용 시작 요청."""
    state = server_states.get(server_name, {"status": "OFF", "user": "", "timestamp": ""})

    if state["status"] == "ON":
        messagebox.showwarning("사용 중", f"{server_name}은(는) 현재 {state['user']} 님이 사용 중입니다.")
        return

    new_state = {
        "status": "ON",
        "user": get_effective_username(),
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    put_server_state(server_name, new_state)
    server_states[server_name] = new_state

    # 비고는 자동 입력 없음 (사용자가 직접 입력하는 구조 유지)
    update_single_server_ui(server_name)


def on_stop(server_name: str):
    """서버 사용 종료 요청."""
    state = server_states.get(server_name, {"status": "OFF", "user": "", "timestamp": ""})

    if state["status"] != "ON":
        messagebox.showinfo("정보", f"{server_name}은(는) 이미 사용 중이 아닙니다.")
        return

    if state["user"] != get_effective_username():
        messagebox.showwarning(
            "오류",
            f"{server_name}은(는) 현재 {state['user']} 님이 사용 중입니다.\n본인만 종료할 수 있습니다."
        )
        return

    # 서버 상태 OFF
    new_state = {
        "status": "OFF",
        "user": "",
        "timestamp": "",
    }
    put_server_state(server_name, new_state)
    server_states[server_name] = new_state

    # ⭐ 비고 삭제
    firebase_notes[server_name] = ""
    save_note_to_firebase(server_name, "")

    update_single_server_ui(server_name)

# ==========================
# 설정(이 PC 이름) 관련
# ==========================

def open_settings_window():
    # 본인이 사용 중일 때는 이름 변경 금지
    if is_this_pc_in_use():
        messagebox.showwarning(
            "이름 변경 불가",
            "현재 이 PC는 서버 사용 중입니다.\n사용 종료 후 이름을 변경하세요."
        )
        return

    settings_win = tk.Toplevel(root)
    settings_win.title("설정")
    settings_win.configure(bg="#FFFFFF")

    pc_id_label = tk.Label(
        settings_win,
        text=f"PC ID (컴퓨터 이름): {PC_ID}",
        font=("맑은 고딕", 10),
        bg="#FFFFFF",
        fg="#333333",
    )
    pc_id_label.pack(padx=10, pady=(10, 5), anchor="w")

    name_frame = tk.Frame(settings_win, bg="#FFFFFF")
    name_frame.pack(padx=10, pady=5, fill="x")

    tk.Label(
        name_frame,
        text="이 PC 표시 이름:",
        font=("맑은 고딕", 10),
        bg="#FFFFFF",
        fg="#333333",
    ).pack(side="left")

    name_var = tk.StringVar()
    name_var.set(current_user_name)
    name_entry = tk.Entry(name_frame, textvariable=name_var, width=30)
    name_entry.pack(side="left", padx=(5, 0))

    def save_name():
        global current_user_name
        new_name = name_var.get().strip()
        current_user_name = new_name
        put_pc_config(new_name)
        messagebox.showinfo("저장 완료", "PC 표시 이름이 저장되었습니다.")
        root.title(f"큐엠 원격 모니터링 - {get_effective_username()}")
        settings_win.destroy()

    save_btn = tk.Button(
        settings_win,
        text="저장",
        command=save_name,
        bg="#4A90E2",
        fg="white",
        activebackground="#357ABD",
        activeforeground="white",
        bd=0,
        padx=15,
        pady=6,
        font=("맑은 고딕", 10, "bold"),
        cursor="hand2",
    )
    save_btn.pack(pady=(5, 10))

    settings_win.grab_set()


def load_initial_pc_name():
    """프로그램 시작 시 Firebase에서 이 PC의 이름을 불러옴."""
    global current_user_name
    cfg = get_pc_config()
    name = cfg.get("name", "").strip() if isinstance(cfg, dict) else ""
    current_user_name = name
    root.title(f"큐엠 원격 모니터링 - {get_effective_username()}")


# ==========================
# UI 업데이트
# ==========================

def update_single_server_ui(server_name: str):
    """특정 서버의 UI만 업데이트."""
    state = server_states.get(server_name, {"status": "OFF", "user": "", "timestamp": ""})
    widgets = server_widgets.get(server_name)
    if not widgets:
        return

    status_label = widgets["status_label"]
    note_label = widgets["note_label"]

    # 비고 표시
    base_note = firebase_notes.get(server_name, "").strip()
    if not base_note:
        base_note = "(없음)"

    if state["status"] == "ON":
        user = state.get("user", "")
        ts = state.get("timestamp", "")

        # 경과 시간 계산
        time_str = ""
        if ts:
            try:
                start_dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                diff = datetime.datetime.now() - start_dt
                minutes = diff.seconds // 60
                time_str = f"{minutes}분 경과"
            except:
                pass

        # 상태 표시
        if time_str:
            status_label.config(
                text=f"🟢 사용 중 ({user}) - {time_str}",
                bg="#E1F8E8",
                fg="#006622",
            )
        else:
            status_label.config(
                text=f"🟢 사용 중 ({user})",
                bg="#E1F8E8",
                fg="#006622",
            )

        # 사용 중일 때도 비고 그대로 표시
        note_label.config(text=base_note)

    else:
        # 사용 가능 상태
        status_label.config(
            text="⚪ 사용 가능",
            bg="#F0F0F0",
            fg="#333333",
        )
        note_label.config(text=base_note)

def update_all_servers_ui():
    """모든 서버 UI 업데이트 + 설정 버튼 잠금/해제."""
    for name in SERVER_LIST:
        update_single_server_ui(name)

    # 내가 사용 중일 때만 설정 버튼 잠금
    if is_this_pc_in_use():
        settings_btn.config(state="disabled")
    else:
        settings_btn.config(state="normal")


# ==========================
# Polling Thread
# ==========================

def polling_thread():
    """1초마다 /servers 상태를 읽어서 server_states 갱신."""
    global server_states

    while True:
        data = get_servers_state()
        if isinstance(data, dict):
            changed = False
            for name in SERVER_LIST:
                new_state = data.get(name)
                if not isinstance(new_state, dict):
                    new_state = {"status": "OFF", "user": "", "timestamp": ""}

                old_state = server_states.get(name)
                if old_state != new_state:
                    server_states[name] = new_state
                    changed = True

            if changed:
                root.after(0, update_all_servers_ui)

        # ⭐ 자동 종료(1시간 초과)
        for name, state in server_states.items():
            if state.get("status") == "ON" and state.get("timestamp"):
                try:
                    start_dt = datetime.datetime.strptime(state["timestamp"], "%Y-%m-%d %H:%M:%S")
                    diff = datetime.datetime.now() - start_dt
                    if diff.total_seconds() >= 3600:  # 1시간
                        print(f"[AUTO STOP] {name} 1시간 초과 → 자동 종료")
                        root.after(0, lambda n=name: on_stop(n))
                except:
                    pass

        time.sleep(1)
# ==========================
# Tkinter UI 구성 (Apple Dashboard 스타일, 2x2 레이아웃)
# ==========================

root = tk.Tk()
root.title("큐엠 원격 모니터링")
root.configure(bg="#F2F2F7")

# 상단 헤더
header_frame = tk.Frame(root, bg="#F2F2F7")
header_frame.pack(fill="x", pady=(10, 5))

header_label = tk.Label(
    header_frame,
    text="큐엠 원격 모니터링",
    bg="#F2F2F7",
    fg="#222222",
    font=("맑은 고딕", 16, "bold")
)
header_label.pack(pady=(0, 5))

# 메인 카드 영역
main_frame = tk.Frame(root, bg="#F2F2F7")
main_frame.pack(padx=15, pady=(10, 10), fill="both", expand=True)

def create_card(parent, server_name, row, col):
    # 카드 프레임 (Apple Dashboard 느낌)
    card = tk.Frame(
        parent,
        bg="#FFFFFF",
        bd=1,
        relief="solid",
        highlightthickness=0,
    )
    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

    # grid 가로/세로 늘어나도록
    parent.grid_rowconfigure(row, weight=1)
    parent.grid_columnconfigure(col, weight=1)

    # 서버 이름
    title = tk.Label(
        card,
        text=server_name,
        bg="#FFFFFF",
        fg="#333333",
        font=("맑은 고딕", 12, "bold"),
        anchor="w",
    )
    title.pack(fill="x", padx=15, pady=(12, 4))

    # 상단 구분선
    sep = tk.Frame(card, bg="#E0E0E0", height=1)
    sep.pack(fill="x", padx=15, pady=(0, 8))

    # 상태 뱃지
    status_label = tk.Label(
        card,
        text="⚪ 사용 가능",
        font=("맑은 고딕", 10, "bold"),
        bg="#F0F0F0",
        fg="#333333",
        padx=10,
        pady=4,
        anchor="w",
    )
    status_label.pack(fill="x", padx=15, pady=(0, 8))

    # 비고 박스
    note_box = tk.Frame(card, bg="#F7F7F7", bd=1, relief="solid")
    note_box.pack(fill="both", padx=15, pady=(0, 10), expand=True)

    note_title = tk.Label(
        note_box,
        text="비고",
        bg="#F7F7F7",
        fg="#444444",
        font=("맑은 고딕", 10, "bold"),
        anchor="w",
    )
    note_title.pack(fill="x", padx=10, pady=(8, 2))

    note_label = tk.Label(
        note_box,
        text="(없음)",
        bg="#F7F7F7",
        fg="#555555",
        justify="left",
        font=("맑은 고딕", 10),
        anchor="w",
    )
    note_label.pack(fill="both", padx=10, pady=(0, 8))

    # 버튼 공통 스타일
    def create_button(master, text, color, command):
        return tk.Button(
            master,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground="#333333",
            activeforeground="white",
            font=("맑은 고딕", 10, "bold"),
            bd=0,
            padx=12,
            pady=5,
            relief="flat",
            cursor="hand2",
        )

    btn_row = tk.Frame(card, bg="#FFFFFF")
    btn_row.pack(anchor="w", padx=15, pady=(0, 12))

    start_btn = create_button(
        btn_row,
        "사용 시작",
        "#4A90E2",
        lambda n=server_name: on_start(n),
    )
    start_btn.pack(side="left", padx=(0, 7))

    end_btn = create_button(
        btn_row,
        "사용 종료",
        "#D0021B",
        lambda n=server_name: on_stop(n),
    )
    end_btn.pack(side="left", padx=(0, 7))

    def make_edit_note_func(name: str):
        def edit_note():
            edit = tk.Toplevel(root)
            edit.title(f"{name} 비고 수정")
            edit.configure(bg="#FFFFFF")

            tk.Label(
                edit,
                text="비고 입력:",
                font=("맑은 고딕", 10),
                bg="#FFFFFF",
                fg="#333333",
            ).pack(padx=10, pady=5, anchor="w")

            text_var = tk.StringVar()
            text_var.set(firebase_notes.get(name, ""))

            entry = tk.Entry(edit, textvariable=text_var, width=40)
            entry.pack(padx=10, pady=5)

            def save_note():
                firebase_notes[name] = text_var.get().strip()
                save_note_to_firebase(name, firebase_notes[name])
                edit.destroy()
                update_single_server_ui(name)

            tk.Button(
                edit,
                text="저장",
                command=save_note,
                bg="#4A90E2",
                fg="white",
                activebackground="#357ABD",
                activeforeground="white",
                bd=0,
                padx=15,
                pady=6,
                font=("맑은 고딕", 10, "bold"),
                cursor="hand2",
            ).pack(pady=10)

            edit.grab_set()
        return edit_note

    note_btn = create_button(
        btn_row,
        "비고 편집",
        "#7B8D93",
        make_edit_note_func(server_name),
    )
    note_btn.pack(side="left", padx=(0, 7))

    server_widgets[server_name] = {
        "status_label": status_label,
        "note_label": note_label,
        "start_btn": start_btn,
        "end_btn": end_btn,
        "note_btn": note_btn,
    }


# 2x2 카드 생성 (1,2 / 3,5)
for idx, name in enumerate(SERVER_LIST):
    row = idx // 2  # 0,0,1,1
    col = idx % 2   # 0,1,0,1
    create_card(main_frame, name, row, col)

# 하단 설정 버튼 영역
bottom_frame = tk.Frame(root, bg="#F2F2F7")
bottom_frame.pack(fill="x", padx=15, pady=(0, 10))

settings_btn = tk.Button(
    bottom_frame,
    text="설정 (PC 이름)",
    command=open_settings_window,
    bg="#FFFFFF",
    fg="#333333",
    activebackground="#E0E0E0",
    activeforeground="#111111",
    bd=1,
    relief="solid",
    padx=12,
    pady=4,
    font=("맑은 고딕", 10, "bold"),
    cursor="hand2",
)
settings_btn.pack(side="right")

# 초기 PC 이름 / 비고 불러오기
load_initial_pc_name()
load_notes_from_firebase()
# 초기 UI 한번 갱신
update_all_servers_ui()

# Polling 스레드 시작
t = threading.Thread(target=polling_thread, daemon=True)
t.start()

root.mainloop()
