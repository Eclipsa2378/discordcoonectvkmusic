import time
import requests
from bs4 import BeautifulSoup
from pypresence import Presence
import re
import sys
import os
import threading
from PIL import Image, ImageDraw
import pystray
# --- Hide console window on Windows (for tray-only app) ---
if os.name == 'nt':
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception as e:
        pass  # If hiding fails, just continue
# For best results, run with pythonw.exe or package as windowed app

def add_to_autostart():
    try:
        import winshell
    except ImportError:
        print("[ERROR] Для автозапуска установите winshell: pip install winshell")
        return
    startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft\\Windows\\Start Menu\\Programs\\Startup")
    script_path = os.path.abspath(sys.argv[0])
    shortcut_path = os.path.join(startup_dir, "VKDiscordMusic.lnk")
    if not os.path.exists(shortcut_path):
        with winshell.shortcut(shortcut_path) as link:
            link.path = sys.executable
            link.arguments = f'"{script_path}"'
            link.description = "VK Discord Music Presence"
            link.icon_location = (sys.executable, 0)
        print("[DEBUG] Ярлык автозапуска создан.")
    else:
        print("[DEBUG] Ярлык автозапуска уже существует.")

def create_tray_icon(on_exit):
    # Генерируем простую иконку
    icon_size = 64
    image = Image.new('RGB', (icon_size, icon_size), color=(30, 144, 255))
    d = ImageDraw.Draw(image)
    d.ellipse((8, 8, 56, 56), fill=(255, 255, 255))
    d.text((20, 24), "VK", fill=(30, 144, 255))
    menu = pystray.Menu(pystray.MenuItem('Выход', on_exit))
    icon = pystray.Icon("VKDiscordMusic", image, "VK Discord Music", menu)
    return icon

VK_PROFILE_URL = "https://vk.com/******"  # Замените на нужный профиль
DISCORD_CLIENT_ID = "1392906865968418906"
def extract_status_audio(html):
    match = re.search(r'"status_audio":\s*\{([^}]+)\}', html)
    if not match:
        return None
    audio_block = match.group(1)
    artist_match = re.search(r'"artist":"([^"]+)"', audio_block)
    title_match = re.search(r'"title":"([^"]+)"', audio_block)
    if artist_match and title_match:
        artist = artist_match.group(1)
        title = title_match.group(1)
        return f"{artist} — {title}"
    return None

def get_current_track_from_vk(profile_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    print(f"[DEBUG] Запрашиваю страницу профиля ВК: {profile_url}")
    try:
        response = requests.get(profile_url, headers=headers)
        print(f"[DEBUG] Код ответа ВК: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Ошибка при запросе страницы ВК: {e}")
        return None
    if response.status_code != 200:
        print(f"[ERROR] Не удалось получить страницу ВК, код: {response.status_code}")
        return None

    # Выводим больше символов для быстрой проверки
    html_preview = response.text[:10000]
    print("[DEBUG] Превью HTML страницы (первые 10000 символов):\n", html_preview)

    # DEBUG: ищем трек через status_audio
    track = extract_status_audio(response.text)
    if track:
        print(f"[DEBUG] Найден трек через status_audio: {track}")
        return track

    # DEBUG: выводим все классы div на странице
    soup = BeautifulSoup(response.text, "html.parser")
    divs = soup.find_all("div")
    div_classes = set()
    for div in divs:
        if div.has_attr("class"):
            div_classes.update(div["class"])
    print("[DEBUG] Все классы div на странице:", div_classes)
    # Поиск блока с музыкой (может отличаться, проверьте структуру страницы)
    audio_block = soup.find("div", class_="audio_row__performer_title")
    if audio_block:
        artist = audio_block.find("a", class_="audio_row__performer")
        title = audio_block.find("span", class_="audio_row__title_inner")
        if artist and title:
            track = f"{artist.text.strip()} — {title.text.strip()}"
            print(f"[DEBUG] Найден трек: {track}")
            return track
    # Альтернативный способ: ищем по тексту
    audio_text = soup.find("div", class_="current_audio")
    if audio_text:
        track = audio_text.text.strip()
        print(f"[DEBUG] Найден трек (альтернативно): {track}")
        return track
    print("[DEBUG] Трек не найден на странице ВК.")
    return None

def main_loop(stop_event):
    print("[DEBUG] Запуск скрипта VK Discord Music Presence")
    rpc = None
    connected = False
    last_track = None
    while not stop_event.is_set():
        if not connected:
            try:
                rpc = Presence(DISCORD_CLIENT_ID)
                rpc.connect()
                connected = True
                print("[DEBUG] Успешно подключено к Discord Rich Presence!")
            except Exception as e:
                print(f"[ERROR] Не удалось подключиться к Discord: {e}")
                print("[DEBUG] Повторная попытка подключения к Discord через 10 секунд...")
                time.sleep(10)
                continue
        track = get_current_track_from_vk(VK_PROFILE_URL)
        print(f"[DEBUG] Текущий трек: {track}")
        try:
            if track and track != last_track:
                rpc.update(state=f"Играет: {track}", details="Слушает песенки")
                print(f"[DEBUG] Обновлен статус Discord: Играет: {track}")
                last_track = track
            elif not track and last_track != "none":
                rpc.update(state="Ничего не слушает", details="Тут пусто(")
                print("[DEBUG] Обновлен статус Discord: Ничего не слушает")
                last_track = "none"
        except Exception as e:
            print(f"[ERROR] Ошибка при обновлении Discord Presence: {e}")
            print("[DEBUG] Потеряно соединение с Discord. Будет предпринята повторная попытка.")
            connected = False
            rpc = None
        time.sleep(10)

def on_tray_exit(icon, stop_event):
    print("[DEBUG] Выход по клику из трея.")
    stop_event.set()
    icon.stop()
    sys.exit(0)

def main():
    # Проверка на аргумент автозапуска
    if "--autostart" in sys.argv:
        add_to_autostart()
        print("[DEBUG] Автозапуск добавлен. Скрипт завершает работу.")
        return
    stop_event = threading.Event()
    # Запуск основного цикла в отдельном потоке
    t = threading.Thread(target=main_loop, args=(stop_event,), daemon=True)
    t.start()
    # Запуск иконки в трее
    icon = create_tray_icon(lambda icon: on_tray_exit(icon, stop_event))
    print("[DEBUG] Запуск иконки в трее. Для выхода используйте меню трея.")
    icon.run()

if __name__ == "__main__":
    main() 