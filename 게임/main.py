import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os

# --------------------
# 설정
# --------------------
BASE_WIDTH = 1024
BASE_HEIGHT = 768
BASE_PLAYER_SIZE = 64
MOVE_SPEED = 6
MAX_SPEED = 24
ACCEL = 1
TICK_MS = 50

# --------------------
# 맵 데이터
# --------------------
MAPS = {
    "village": {
        "bg": "village_bg.png",
        "npc": [(800, 400)],
        "shop": [(200, 150)],
        "walls": [
            (0, 0, 1024, 32),
            (0, 736, 1024, 768),
            (0, 0, 32, 768),
            (992, 0, 1024, 768)
        ],
        "player_start": (512, 384),
        "left_map_trigger": (0, 0, 32, 768),
        "right_map_trigger": (992, 0, 1024, 768),
        "left_map": None,
        "right_map": "forest"
    },
    "forest": {
        "bg": "forest_bg.png",
        "npc": [(500, 300)],
        "shop": [(100, 100)],
        "walls": [
            (0, 0, 1024, 32),
            (0, 736, 1024, 768)
        ],
        "player_start": (100, 650),
        "left_map_trigger": (0, 0, 32, 768),
        "right_map_trigger": (992, 0, 1024, 768),
        "left_map": "village",
        "right_map": None
    }
}

current_map = "village"

# --------------------
# 전역 상태
# --------------------
root = tk.Tk()
root.title("픽셀 RPG")
root.geometry(f"{BASE_WIDTH}x{BASE_HEIGHT}")

canvas = None

map_transitioning = False

SPRITES = {"down": [], "up": [], "left": [], "right": []}
SPRITE_PATHS = {
    "down": "player_down.png",
    "up": "player_up.png",
    "left": "player_left.png",
    "right": "player_right.png"
}

# 상점 스프라이트 시트 설정 (여기에 본인 PNG 파일명 넣기)
SHOP_SPRITE_PATH = "shop_spritesheet.png"
SHOP_SPRITES = []

bg_image = None
BG_PHOTO = None
bg_id = None

BASE_WALLS = []
walls = []

player_x = player_y = 0
player_dir = "down"
player_frame = 0
player_sprite = None
PLAYER_DISPLAY_SIZE = BASE_PLAYER_SIZE

npc = None
npc_x = npc_y = 0

shop = None
shop_x = shop_y = 0

# 상점 애니메이션 상태
shop_frame = 0
SHOP_ANIM_DELAY = 180  # 밀리초, 프레임 전환 속도
shop_anim_id = None

# 공격(attack) 애니메이션 상태 (Z 키)
ATTACK_SPRITE_PATH = "player_attack.png"
ATTACK_SPRITES = []
attack_frame = 0
ATTACK_ANIM_DELAY = 80
is_attacking = False
attack_anim_id = None

# 뒤집어 때리기
BACK_ATTACK_SPRITE_PATH = "player_back_attack.png"
BACK_ATTACK_SPRITES = []

# 현재 공격 재생 리스트
current_attack_sprites = None

# 원래 플레이어 상태 저장용
saved_player_dir = None
saved_player_frame = 0

# 전역: 뒤로 공격 스프라이트 및 상태
BACK_ATTACK_SPRITE_PATH = "player_back_attack.png"   # 뒤로 때리기 spritesheet 파일명으로 변경
BACK_ATTACK_SPRITES = []

last_horizontal = None           # 'a' 또는 'd' 중 마지막으로 눌린 수평키
current_attack_sprites = None    # 현재 재생 중인 공격 프레임 목록

# 중력/점프 변수 (forest에서만 활성)
GRAVITY = 1.6
JUMP_VELOCITY = -20
vertical_velocity = 0.0

# 착지 플래그 추가
on_ground = False

keys_pressed = set()
current_speed = MOVE_SPEED

gold = 100
inventory = []
quest_active = False
quest_completed = False

# --------------------
# helpers
# --------------------
def safe_open_pil(path):
    if path and os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except:
            pass
    return Image.new("RGBA", (BASE_PLAYER_SIZE, BASE_PLAYER_SIZE), (200, 200, 200, 255))

def load_spritesheet_frames(path, size):
    img = safe_open_pil(path)
    frame_w = 32
    num = max(1, img.width // frame_w)
    frames = []
    for i in range(num):
        left = i * frame_w
        frame = img.crop((left, 0, left + frame_w, img.height))
        frame = frame.resize((size, size), Image.NEAREST)
        frames.append(ImageTk.PhotoImage(frame))
    return frames

def get_scales():
    if canvas is None:
        return (1.0, 1.0, 1.0)
    w = canvas.winfo_width() or BASE_WIDTH
    h = canvas.winfo_height() or BASE_HEIGHT
    w_scale = w / BASE_WIDTH
    h_scale = h / BASE_HEIGHT
    uniform = min(w_scale, h_scale)
    return (w_scale, h_scale, uniform)

# --------------------
# rescale elements
# --------------------
def rescale_elements():
    global PLAYER_DISPLAY_SIZE, SPRITES, BG_PHOTO
    if canvas is None:
        return
    w_scale, h_scale, uniform = get_scales()
    PLAYER_DISPLAY_SIZE = max(4, int(BASE_PLAYER_SIZE * uniform))

    # reload player frames
    for d, p in SPRITE_PATHS.items():
        SPRITES[d] = load_spritesheet_frames(p, PLAYER_DISPLAY_SIZE)

    canvas.coords(player_sprite, player_x * w_scale, player_y * h_scale)
    frames = SPRITES.get(player_dir) or SPRITES["down"]
    if frames:
        canvas.itemconfig(player_sprite, image=frames[player_frame % len(frames)])
    canvas.tag_raise(player_sprite)

    if npc is not None:
        canvas.coords(npc, npc_x * w_scale, npc_y * h_scale, (npc_x + 32) * w_scale, (npc_y + 32) * h_scale)
        canvas.tag_raise(npc)

    # --- 변경: 상점 스프라이트를 캐릭터 크기로 다시 로드 및 적용 ---
    globals()["SHOP_SPRITES"] = load_spritesheet_frames(SHOP_SPRITE_PATH, PLAYER_DISPLAY_SIZE)
    # 공격 프레임도 동일 크기로 재생성
    globals()["ATTACK_SPRITES"] = load_spritesheet_frames(ATTACK_SPRITE_PATH, PLAYER_DISPLAY_SIZE)
    globals()["BACK_ATTACK_SPRITES"] = load_spritesheet_frames(BACK_ATTACK_SPRITE_PATH, PLAYER_DISPLAY_SIZE)
    if shop is not None:
        canvas.coords(shop, shop_x * w_scale, shop_y * h_scale)
        if SHOP_SPRITES:
            canvas.itemconfig(shop, image=SHOP_SPRITES[0])
        canvas.tag_raise(shop)

    for i, (mx1, my1, mx2, my2) in enumerate(BASE_WALLS):
        if i < len(walls):
            canvas.coords(walls[i], mx1 * w_scale, my1 * h_scale, mx2 * w_scale, my2 * h_scale)

    global bg_image
    if bg_image:
        w, h = canvas.winfo_width(), canvas.winfo_height()
        if w > 0 and h > 0:
            bg_resized = bg_image.resize((w, h), Image.NEAREST)
            bg_photo_new = ImageTk.PhotoImage(bg_resized)
            if globals().get("bg_id") is None:
                globals()["bg_id"] = canvas.create_image(0, 0, image=bg_photo_new, anchor="nw")
            else:
                canvas.itemconfig(globals()["bg_id"], image=bg_photo_new)
            globals()["BG_PHOTO"] = bg_photo_new

# --------------------
# load map
# --------------------
def load_map(map_name, start_pos=None):
    global current_map, BASE_WALLS, bg_image, player_x, player_y, player_sprite
    global npc, npc_x, npc_y, shop, shop_x, shop_y, walls

    current_map = map_name
    data = MAPS[map_name]
    BASE_WALLS = list(data["walls"])

    bg_path = data.get("bg")
    bg_image_local = safe_open_pil(bg_path) if bg_path else None
    globals()["bg_image"] = bg_image_local

    if start_pos is None:
        player_x, player_y = data["player_start"]
    else:
        player_x, player_y = start_pos

    _, _, uniform = get_scales()
    display_size = max(4, int(BASE_PLAYER_SIZE * uniform))
    for d, p in SPRITE_PATHS.items():
        SPRITES[d] = load_spritesheet_frames(p, display_size)

    if player_sprite is None:
        globals()["player_sprite"] = canvas.create_image(player_x * (canvas.winfo_width() / BASE_WIDTH),
                                                         player_y * (canvas.winfo_height() / BASE_HEIGHT),
                                                         image=SPRITES[player_dir][0], anchor="nw")
    else:
        canvas.coords(player_sprite, player_x * (canvas.winfo_width() / BASE_WIDTH),
                      player_y * (canvas.winfo_height() / BASE_HEIGHT))
        canvas.itemconfig(player_sprite, image=SPRITES[player_dir][0])
    canvas.tag_raise(player_sprite)

    npc_x_val, npc_y_val = data["npc"][0]
    globals()["npc_x"], globals()["npc_y"] = npc_x_val, npc_y_val
    if npc is None:
        globals()["npc"] = canvas.create_rectangle(npc_x_val, npc_y_val, npc_x_val + 32, npc_y_val + 32,
                                                  fill="orange", outline="black")
    else:
        canvas.coords(npc, npc_x_val, npc_y_val, npc_x_val + 32, npc_y_val + 32)

    shop_x_val, shop_y_val = data["shop"][0]
    globals()["shop_x"], globals()["shop_y"] = shop_x_val, shop_y_val

    # 상점: 이전에 사각형으로 만들던 부분을 스프라이트 이미지로 변경
    # SHOP_SPRITES에 프레임을 로드하고 캔버스에 이미지로 생성/업데이트
    globals()["SHOP_SPRITES"] = load_spritesheet_frames(SHOP_SPRITE_PATH, display_size)
    if shop is None:
        # anchor="nw"로 좌상단 기준 배치
        globals()["shop"] = canvas.create_image(shop_x_val, shop_y_val,
                                                image=SHOP_SPRITES[0] if SHOP_SPRITES else None,
                                                anchor="nw")
    else:
        canvas.coords(shop, shop_x_val, shop_y_val)
        if SHOP_SPRITES:
            canvas.itemconfig(shop, image=SHOP_SPRITES[0])

    for r in list(walls):
        try:
            canvas.delete(r)
        except:
            pass
    walls.clear()
    for (x1, y1, x2, y2) in BASE_WALLS:
        rect = canvas.create_rectangle(x1, y1, x2, y2, outline="", fill="", width=0)
        walls.append(rect)

    rescale_elements()

# --------------------
# collision
# --------------------
def check_collision(new_x, new_y):
    w_scale, h_scale, _ = get_scales()
    px1 = new_x * w_scale
    py1 = new_y * h_scale
    px2 = px1 + PLAYER_DISPLAY_SIZE
    py2 = py1 + PLAYER_DISPLAY_SIZE
    for rect in walls:
        x1, y1, x2, y2 = canvas.coords(rect)
        if px2 > x1 and px1 < x2 and py2 > y1 and py1 < y2:
            return True
    return False

# --------------------
# movement
# --------------------
def move_loop():
    global player_x, player_y, player_dir, player_frame, current_speed, map_transitioning, vertical_velocity, on_ground
    # 수평 입력 계산
    dx = dy = 0
    # --- 착지 판정 먼저 갱신 (간단한 아래 검사) ---
    try:
        on_ground = check_collision(player_x, player_y + 1) or (player_y >= BASE_HEIGHT - PLAYER_DISPLAY_SIZE - 1)
    except Exception:
        on_ground = (player_y >= BASE_HEIGHT - PLAYER_DISPLAY_SIZE - 1)
    # --- 기존 코드 유지: 수평/수직 입력 처리 ---
    if not is_attacking:
        # forest에서는 'w'를 위로 이동에 사용하지 않음(점프은 Space)
        if 'a' in keys_pressed:
            dx = -current_speed; player_dir = 'left'
        elif 'd' in keys_pressed:
            dx = current_speed; player_dir = 'right'
        else:
            if current_map != "forest":
                if 'w' in keys_pressed:
                    dy = -current_speed; player_dir = 'up'
                elif 's' in keys_pressed:
                    dy = current_speed; player_dir = 'down'
    else:
        dx = dy = 0

    # 수평/수직 이동 적용 (충돌 검사)
    if dx != 0 or dy != 0:
        new_x = player_x + dx
        new_y = player_y + dy
        if not check_collision(new_x, new_y):
            player_x = new_x
            player_y = new_y
        current_speed = min(current_speed + ACCEL, MAX_SPEED)
    else:
        current_speed = MOVE_SPEED

    # 중력/점프 처리 (forest에서만)
    if current_map == "forest":
        vertical_velocity += GRAVITY
        attempted_y = player_y + vertical_velocity

        # clamp 시드 (안전 범위)
        min_y = 0
        max_y = BASE_HEIGHT - PLAYER_DISPLAY_SIZE

        # 상승 충돌 처리
        if vertical_velocity < 0:
            tries = 0
            while check_collision(player_x, attempted_y) and tries < 8:
                attempted_y += 1
                vertical_velocity = 0
                tries += 1
            attempted_y = max(min_y, min(attempted_y, max_y))
        else:
            if check_collision(player_x, attempted_y):
                tries = 0
                while check_collision(player_x, attempted_y) and tries < 16 and attempted_y > min_y:
                    attempted_y -= 1
                    tries += 1
                vertical_velocity = 0
            attempted_y = max(min_y, min(attempted_y, max_y))
        player_y = attempted_y
        # 착지 판정 재설정 (수정: 수직속도가 거의 0이면 착지로 간주)
        if abs(vertical_velocity) < 1e-3 and (check_collision(player_x, player_y + 1) or player_y >= BASE_HEIGHT - PLAYER_DISPLAY_SIZE - 1):
            on_ground = True
        else:
            on_ground = False
    else:
        vertical_velocity = 0
        on_ground = True

    # 화면/맵 경계에서 X도 벗어나지 않게 강제
    min_x = 0
    max_x = BASE_WIDTH - PLAYER_DISPLAY_SIZE
    player_x = max(min_x, min(player_x, max_x))
    player_y = max(0, min(player_y, BASE_HEIGHT - PLAYER_DISPLAY_SIZE))

    # 스프라이트 위치 업데이트
    w_scale, h_scale, _ = get_scales()
    try:
        if player_sprite is not None:
            canvas.coords(player_sprite, player_x * w_scale, player_y * h_scale)
    except Exception:
        pass

    # 걷기 애니메이션 — 공격 중이면 건너뜀
    if not is_attacking:
        if dx != 0 or dy != 0:
            frames = SPRITES.get(player_dir) or SPRITES["down"]
            player_frame = (player_frame + 1) % max(1, len(frames))
            if frames and player_sprite is not None:
                canvas.itemconfig(player_sprite, image=frames[player_frame % len(frames)])
        else:
            frames = SPRITES.get(player_dir) or SPRITES["down"]
            if frames and player_sprite is not None:
                canvas.itemconfig(player_sprite, image=frames[0])

    # 힌트/포탈 표시 (트리거가 있을 때만 표시/진입 허용)
    canvas.delete("hint")
    canvas.delete("portal_hint")
    w_s, h_s, _ = get_scales()
    if abs(player_x - npc_x) < 50 and abs(player_y - npc_y) < 50:
        canvas.create_text(npc_x * w_s + 20, npc_y * h_s - 20, text="[E] 말하기", fill="black", tag="hint")
    elif abs(player_x - shop_x) < 60 and abs(player_y - shop_y) < 60:
        canvas.create_text(shop_x * w_s + 20, shop_y * h_s - 20, text="[E] 상점", fill="black", tag="hint")

    data = MAPS[current_map]
    left_t = data.get('left_map_trigger')
    right_t = data.get('right_map_trigger')

    if left_t and player_x <= left_t[2]:
        nxt = data.get('left_map')
        if nxt:
            canvas.create_text(player_x * w_s + 20, player_y * h_s - 40, text="[W] 입장", fill="blue", tag="portal_hint")
            if 'w' in keys_pressed and not map_transitioning:
                start_x = BASE_WIDTH - BASE_PLAYER_SIZE - 10
                clamped_y = int(min(max(player_y, 0), BASE_HEIGHT - BASE_PLAYER_SIZE))
                animate_map_transition(nxt, start_pos=(start_x, clamped_y))
    elif right_t and player_x + PLAYER_DISPLAY_SIZE >= right_t[0]:
        nxt = data.get('right_map')
        if nxt:
            canvas.create_text(player_x * w_s + 20, player_y * h_s - 40, text="[W] 입장", fill="blue", tag="portal_hint")
            if 'w' in keys_pressed and not map_transitioning:
                start_x = 10
                clamped_y = int(min(max(player_y, 0), BASE_HEIGHT - BASE_PLAYER_SIZE))
                animate_map_transition(nxt, start_pos=(start_x, clamped_y))

    root.after(TICK_MS, move_loop)

# ...existing code...
def start_jump():
    """Forest 맵에서만 작동하는 점프 시작 (on_ground 사용)."""
    global vertical_velocity, on_ground
    if current_map != "forest":
        return
    # 이미 공중이면 무시
    if not on_ground or abs(vertical_velocity) > 1e-3:
        return
    vertical_velocity = JUMP_VELOCITY
    on_ground = True
# ...existing code...

# --------------------
# input
# --------------------
def on_key_press(evt):
    global last_horizontal, player_x
    key = evt.keysym.lower()
    first_press = key not in keys_pressed
    keys_pressed.add(key)

    # 마지막 수평키 추적 (a 또는 d)
    if key in ('a', 'd'):
        last_horizontal = key

    # 동작은 최초 누름(first_press)에서만 실행하여 '씹힘' 방지
    if key == 'e' and first_press:
        handle_action()
    elif key == 'space' :
        # forest에서 Space로 점프
        if current_map == "forest":
                start_jump()
                return
    elif key == 'w' and first_press:
        # 기존 포탈/입장 키는 w로 유지
        try_enter_portal()
    elif key == 'z' and first_press:
        start_attack()

def on_key_release(evt):
    keys_pressed.discard(evt.keysym.lower())

# --------------------
# 포탈 진입 및 상점 애니메이션 (start_screen보다 위에 있어야 함)
# --------------------
def try_enter_portal():
    global player_x, player_y, map_transitioning
    if map_transitioning:
        return
    data = MAPS[current_map]
    left_t = data.get('left_map_trigger')
    right_t = data.get('right_map_trigger')

    if left_t and player_x <= left_t[2]:
        nxt = data.get('left_map')
        if nxt:
            start_x = BASE_WIDTH - BASE_PLAYER_SIZE - 10
            clamped_y = int(min(max(player_y, 0), BASE_HEIGHT - BASE_PLAYER_SIZE))
            animate_map_transition(nxt, start_pos=(start_x, clamped_y))
            return

    if right_t and player_x + PLAYER_DISPLAY_SIZE >= right_t[0]:
        nxt = data.get('right_map')
        if nxt:
            start_x = 10
            clamped_y = int(min(max(player_y, 0), BASE_HEIGHT - BASE_PLAYER_SIZE))
            animate_map_transition(nxt, start_pos=(start_x, clamped_y))

def animate_shop():
    global shop_frame, shop_anim_id
    try:
        if canvas is None:
            return
        if SHOP_SPRITES and shop is not None:
            shop_frame = (shop_frame + 1) % len(SHOP_SPRITES)
            canvas.itemconfig(shop, image=SHOP_SPRITES[shop_frame])
    except Exception:
        pass
    shop_anim_id = root.after(SHOP_ANIM_DELAY, animate_shop)

def start_attack():
    global is_attacking, attack_frame, attack_anim_id, current_attack_sprites
    global saved_player_dir, saved_player_frame, last_horizontal, map_transitioning
    # 이미 공격 중이거나 맵 전환 중이면 무시
    if is_attacking or map_transitioning:
        return

    # 공격 스프라이트 선택
    if last_horizontal == 'a' and BACK_ATTACK_SPRITES:
        sprites = BACK_ATTACK_SPRITES
    elif last_horizontal == 'd' and ATTACK_SPRITES:
        sprites = ATTACK_SPRITES
    else:
        sprites = ATTACK_SPRITES or BACK_ATTACK_SPRITES

    if not sprites:
        return

    # 현재 상태 저장
    saved_player_dir = player_dir
    saved_player_frame = player_frame

    current_attack_sprites = sprites
    is_attacking = True
    attack_frame = 0
    try:
        if player_sprite is not None:
            canvas.itemconfig(player_sprite, image=current_attack_sprites[0])
    except Exception:
        pass
    attack_anim_id = root.after(ATTACK_ANIM_DELAY, animate_attack)

def animate_attack():
    global attack_frame, is_attacking, attack_anim_id, current_attack_sprites
    global player_dir, player_frame, saved_player_dir, saved_player_frame
    try:
        if not current_attack_sprites or player_sprite is None:
            is_attacking = False
            current_attack_sprites = None
            return

        attack_frame += 1
        if attack_frame < len(current_attack_sprites):
            canvas.itemconfig(player_sprite, image=current_attack_sprites[attack_frame])
            attack_anim_id = root.after(ATTACK_ANIM_DELAY, animate_attack)
        else:
            # 애니 끝나면 저장해둔 상태로 복귀 (프레임은 대기 프레임 0)
            is_attacking = False
            current_attack_sprites = None
            if saved_player_dir is not None:
                player_dir = saved_player_dir
            player_frame = 0
            frames = SPRITES.get(player_dir) or SPRITES["down"]
            if frames and player_sprite is not None:
                canvas.itemconfig(player_sprite, image=frames[0])
            saved_player_dir = None
            saved_player_frame = 0
    except Exception:
        is_attacking = False
        current_attack_sprites = None
        saved_player_dir = None
        saved_player_frame = 0

def handle_action():
    global quest_active, quest_completed, gold
    if abs(player_x - npc_x) < 50 and abs(player_y - npc_y) < 50:
        if not quest_active and not quest_completed:
            start_quest()
        elif quest_active and not quest_completed:
            messagebox.showinfo("NPC", "아직 퀘스트를 완료하지 않았습니다.")
        elif quest_completed:
            messagebox.showinfo("NPC", "퀘스트 완료! 보상 50G")
            gold += 50
            quest_completed = False
    elif abs(player_x - shop_x) < 60 and abs(player_y - shop_y) < 60:
        open_shop()

def start_quest():
    global quest_active
    quest_active = True
    messagebox.showinfo("퀘스트", "괴물을 물리치고 돌아오세요!")

def complete_quest():
    global quest_active, quest_completed
    if quest_active:
        quest_active = False
        quest_completed = True
        messagebox.showinfo("퀘스트 완료", "NPC에게 돌아가세요!")

def open_shop():
    global gold
    shop_win = tk.Toplevel(root)
    shop_win.title("상점")
    tk.Label(shop_win, text=f"소지금: {gold} G").pack()
    def buy(item, price):
        global gold
        if gold >= price:
            gold -= price
            inventory.append(item)
            messagebox.showinfo("구매", f"{item} 구매 성공!")
        else:
            messagebox.showwarning("실패", "골드 부족!")
    tk.Button(shop_win, text="체력포션 (30G)", command=lambda: buy("체력포션", 30)).pack(fill="x")
    tk.Button(shop_win, text="마나포션 (20G)", command=lambda: buy("마나포션", 20)).pack(fill="x")
    tk.Button(shop_win, text="강화석 (50G)", command=lambda: buy("강화석", 50)).pack(fill="x")

# --------------------
# map slide animation
# --------------------
def animate_map_transition(target_map, start_pos=None):
    global map_transitioning
    if map_transitioning:
        return
    map_transitioning = True

    # 캔버스 크기와 스텝
    width = canvas.winfo_width() or BASE_WIDTH
    steps = 18
    dx = width / steps

    # 현재 맵 요소 수집 (존재하는 것만)
    current_items = []
    if globals().get("bg_id") is not None:
        current_items.append(globals()["bg_id"])
    if player_sprite is not None:
        current_items.append(player_sprite)
    if npc is not None:
        current_items.append(npc)
    if shop is not None:
        current_items.append(shop)
    current_items.extend(walls)

    # 1) 현재 화면을 왼쪽으로 슬라이드 아웃
    for _ in range(steps):
        for it in current_items:
            try:
                canvas.move(it, -dx, 0)
            except:
                pass
        root.update_idletasks()
        root.update()
        root.after(16)

    # 2) 현재 요소들을 캔버스에서 삭제하여 겹침 방지
    for it in current_items:
        try:
            canvas.delete(it)
        except:
            pass

    # 비어있는 요소 목록 갱신
    globals()["bg_id"] = None
    walls.clear()
    # player_sprite/npc/shop는 load_map에서 다시 생성 또는 재설정됨
    globals()["player_sprite"] = None
    globals()["npc"] = None
    globals()["shop"] = None

    # 3) 새 맵 로드 (start_pos 전달)
    load_map(target_map, start_pos=start_pos)

    # 4) 새 요소들을 화면 오른쪽 바깥(오프스크린)으로 이동시킨 뒤 슬라이드 인
    new_items = []
    if globals().get("bg_id") is not None:
        new_items.append(globals()["bg_id"])
    if player_sprite is not None:
        new_items.append(player_sprite)
    if npc is not None:
        new_items.append(npc)
    if shop is not None:
        new_items.append(shop)
    new_items.extend(walls)

    # 모두 오른쪽 바깥으로 배치
    for it in new_items:
        try:
            canvas.move(it, width, 0)
        except:
            pass

    # 새 요소들을 왼쪽으로 슬라이드 인
    for _ in range(steps):
        for it in new_items:
            try:
                canvas.move(it, -dx, 0)
            except:
                pass
        root.update_idletasks()
        root.update()
        root.after(16)

    rescale_elements()

    # 짧은 쿨다운 후 플래그 해제
    def _clear_flag():
        global map_transitioning
        map_transitioning = False
    root.after(300, _clear_flag)

# --------------------
# start screen
# --------------------
def start_screen():
    start_frame = tk.Frame(root, width=BASE_WIDTH, height=BASE_HEIGHT)
    start_frame.pack(fill="both", expand=True)
    tk.Label(start_frame, text="픽셀 RPG", font=("Arial", 36)).pack(pady=40)
    def start_game():
        start_frame.destroy()
        global canvas
        canvas = tk.Canvas(root, width=BASE_WIDTH, height=BASE_HEIGHT)
        canvas.pack(fill="both", expand=True)
        canvas.bind("<Configure>", lambda e: rescale_elements())
        # 키 바인딩을 전체(window)로 바꿔 포커스 상관없이 입력을 받게 함
        root.bind_all("<KeyPress>", on_key_press)
        root.bind_all("<KeyRelease>", on_key_release)
        load_map(current_map)
        # 상점 애니메이션 시작
        animate_shop()
        move_loop()
    tk.Button(start_frame, text="게임 시작", font=("Arial", 20), command=start_game).pack(pady=20)

start_screen()
root.mainloop()

