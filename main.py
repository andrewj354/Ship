import customtkinter as ctk
import tkintermapview
import requests
import random
import threading
import datetime
import os
import math  # НОВЕ: для розрахунку дистанції між точками
from collections import deque
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# --- НАЛАШТУВАННЯ ---
DRONE_IP = "http://192.168.4.1"
UPDATE_INTERVAL = 1000
LOG_FILE = "drone_data_log.txt"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# --- КЛАС РОБОТИ З ДРОНОМ ---
class HybridDrone:
    def __init__(self):
        self.history_len = 30
        self.ph_history = deque([0] * self.history_len, maxlen=self.history_len)
        self.temp_history = deque([0] * self.history_len, maxlen=self.history_len)
        self.turb_history = deque([0] * self.history_len, maxlen=self.history_len)

        # НОВЕ: Динамічні координати замість статичних
        self.current_lat = 49.8356
        self.current_lon = 24.0146

        # НОВЕ: Налаштування автопілота
        self.home_coords = (49.8356, 24.0146)  # Початкова точка Home
        self.waypoints = []  # Список точок маршруту
        self.current_wp_index = 0
        self.mode = "MANUAL"  # MANUAL, MISSION, RTH

        self.current_data = {
            "temp": 0.0,
            "ph": 0.0,
            "turb": 0.0,
            "lat": self.current_lat,
            "lon": self.current_lon,
            "connected": False
        }

    def simulate_movement(self):
        """НОВЕ: Симулює рух кораблика до точок на карті для тестування інтерфейсу"""
        if self.mode in ["MISSION", "RTH"]:
            target = None
            if self.mode == "MISSION" and self.waypoints:
                if self.current_wp_index < len(self.waypoints):
                    target = self.waypoints[self.current_wp_index]
                else:
                    self.mode = "MANUAL"  # Місію завершено
                    print("✅ Місію завершено!")
            elif self.mode == "RTH":
                target = self.home_coords

            if target:
                # Векторна математика для симуляції руху
                dy = target[0] - self.current_lat
                dx = target[1] - self.current_lon
                dist = math.hypot(dx, dy)

                if dist < 0.00005:  # Якщо досягли точки (приблизно 5 метрів)
                    if self.mode == "MISSION":
                        print(f"📍 Точку {self.current_wp_index + 1} досягнуто!")
                        self.current_wp_index += 1
                    elif self.mode == "RTH":
                        print("🏠 Кораблик повернувся додому!")
                        self.mode = "MANUAL"
                else:
                    # Швидкість симуляції (градуси за тік)
                    speed = 0.00005
                    self.current_lat += (dy / dist) * speed
                    self.current_lon += (dx / dist) * speed

    def fetch_data(self):
        self.simulate_movement()  # Оновлюємо координати

        try:
            response = requests.get(DRONE_IP, timeout=2)
            if response.status_code == 200:
                self.current_data["connected"] = True
                self.current_data["temp"] = round(random.uniform(18.0, 20.0), 1)
                self.current_data["ph"] = round(random.uniform(6.8, 7.2), 2)
                self.current_data["turb"] = round(random.uniform(0.1, 0.5), 2)

                # Оновлюємо дані координат з симулятора
                self.current_data["lat"] = self.current_lat
                self.current_data["lon"] = self.current_lon

                self.temp_history.append(self.current_data["temp"])
                self.ph_history.append(self.current_data["ph"])
                self.turb_history.append(self.current_data["turb"])
                self.save_to_log()
            else:
                self.current_data["connected"] = False
        except requests.exceptions.RequestException:
            self.current_data["connected"] = False
            # Для тестування інтерфейсу без реального кораблика, залишаємо генерацію координат
            self.current_data["lat"] = self.current_lat
            self.current_data["lon"] = self.current_lon

    def save_to_log(self):
        try:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = (f"[{now}] Темп: {self.current_data['temp']} °C | "
                        f"pH: {self.current_data['ph']} | "
                        f"Мутність: {self.current_data['turb']} V | "
                        f"GPS: {self.current_data['lat']:.5f}, {self.current_data['lon']:.5f}\n")
            with open(LOG_FILE, "a", encoding="utf-8") as file:
                file.write(log_line)
        except Exception as e:
            pass

    def send_command(self, command):
        def thread_task():
            try:
                url = f"{DRONE_IP}{command}"
                requests.get(url, timeout=3, headers={'Connection': 'close'})
                print(f"✅ Команда {command} відправлена!")
            except Exception:
                print(f"⚠️ Симуляція команди: {command} (Реальний дрон не підключено)")

        threading.Thread(target=thread_task).start()


# --- ГОЛОВНЕ ВІКНО ---
class DroneDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🇺🇦 Water Drone Control Station (Waypoints & RTH)")
        self.geometry("1400x900")

        self.drone = HybridDrone()
        self.drone_marker = None

        # НОВЕ: Змінні для відображення маршруту на карті
        self.waypoint_markers = []
        self.path_line = None
        self.home_marker = None

        self.setup_ui()
        self.setup_map_interactions()  # НОВЕ
        self.update_loop()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === ЛІВА ПАНЕЛЬ ===
        left_panel = ctk.CTkFrame(self, width=320, corner_radius=15)
        left_panel.grid(row=0, column=0, rowspan=2, padx=20, pady=20, sticky="nsew")

        ctk.CTkLabel(left_panel, text="СЕНСОРИ", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 5))

        self.lbl_status = ctk.CTkLabel(left_panel, text="OFFLINE", font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color="#c0392b", text_color="white", corner_radius=5, width=200, height=30)
        self.lbl_status.pack(pady=5)

        self.lbl_ph = self.create_sensor_card(left_panel, "pH Води", "--", "#2ecc71")
        self.lbl_temp = self.create_sensor_card(left_panel, "Температура (°C)", "--", "#e67e22")

        # --- НОВЕ: ПАНЕЛЬ АВТОПІЛОТА ---
        ctk.CTkLabel(left_panel, text="АВТОПІЛОТ ТА МІСІЇ", font=ctk.CTkFont(size=16, weight="bold")).pack(
            pady=(20, 10))

        self.lbl_mode = ctk.CTkLabel(left_panel, text="Режим: MANUAL", text_color="#f1c40f",
                                     font=ctk.CTkFont(weight="bold"))
        self.lbl_mode.pack(pady=5)

        btn_auto_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_auto_frame.pack(pady=5)

        ctk.CTkButton(btn_auto_frame, text="▶️ СТАРТ", width=90, fg_color="#2980b9",
                      command=self.start_mission).grid(row=0, column=0, padx=5)
        ctk.CTkButton(btn_auto_frame, text="⏹️ СТОП", width=90, fg_color="#e74c3c",
                      command=self.stop_mission).grid(row=0, column=1, padx=5)

        ctk.CTkButton(left_panel, text="🏠 ПОВЕРНЕННЯ НА БАЗУ (RTH)", fg_color="#8e44ad", hover_color="#9b59b6",
                      command=self.start_rth).pack(pady=10)

        ctk.CTkButton(left_panel, text="🗑️ ОЧИСТИТИ ТОЧКИ", fg_color="#7f8c8d", hover_color="#95a5a6",
                      command=self.clear_waypoints).pack(pady=5)

        # --- РУЧНЕ КЕРУВАННЯ ---
        ctk.CTkLabel(left_panel, text="РУЧНЕ КЕРУВАННЯ", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        btn_nav_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_nav_frame.pack(pady=5)

        ctk.CTkButton(btn_nav_frame, text="⬅️", width=50, command=lambda: self.drone.send_command("/left")).grid(row=0,
                                                                                                                 column=0,
                                                                                                                 padx=5)
        ctk.CTkButton(btn_nav_frame, text="⬆️", width=50, command=lambda: self.drone.send_command("/forward")).grid(
            row=0, column=1, padx=5)
        ctk.CTkButton(btn_nav_frame, text="➡️", width=50, command=lambda: self.drone.send_command("/right")).grid(row=0,
                                                                                                                  column=2,
                                                                                                                  padx=5)

        # === ПРАВА ПАНЕЛЬ (КАРТА + ГРАФІКИ) ===
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=2)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        # -- КАРТА --
        map_frame = ctk.CTkFrame(right_panel, corner_radius=15)
        map_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        self.map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=15)
        self.map_widget.pack(fill="both", expand=True, padx=10, pady=10)
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

        self.map_widget.set_position(49.8356, 24.0146)
        self.map_widget.set_zoom(18)

        # Малюємо початкову точку Home
        self.home_marker = self.map_widget.set_marker(self.drone.home_coords[0], self.drone.home_coords[1],
                                                      text="🏠 HOME", marker_color_circle="#8e44ad")

        # -- ГРАФІКИ --
        graphs_frame = ctk.CTkFrame(right_panel, corner_radius=15)
        graphs_frame.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        plt.style.use('dark_background')
        self.fig = Figure(figsize=(10, 3.5), dpi=100, facecolor='#2b2b2b')
        self.ax1 = self.fig.add_subplot(131)
        self.ax2 = self.fig.add_subplot(132)
        self.ax3 = self.fig.add_subplot(133)

        self.canvas = FigureCanvasTkAgg(self.fig, master=graphs_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)

    def create_sensor_card(self, parent, title, value, color):
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=2, border_color=color)
        card.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12)).pack(pady=(5, 0))
        lbl = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        lbl.pack(pady=(0, 5))
        return lbl

    # --- НОВЕ: ФУНКЦІЇ АВТОПІЛОТА ТА КАРТИ ---
    def setup_map_interactions(self):
        """Додає контекстне меню по кліку правою кнопкою миші на карту"""
        self.map_widget.add_right_click_menu_command(label="📍 Додати точку (Waypoint)", command=self.add_waypoint_event,
                                                     pass_coords=True)
        self.map_widget.add_right_click_menu_command(label="🏠 Встановити HOME тут", command=self.set_home_event,
                                                     pass_coords=True)

    def add_waypoint_event(self, coords):
        """Обробник кліку для додавання точки"""
        self.drone.waypoints.append(coords)
        wp_number = len(self.drone.waypoints)
        marker = self.map_widget.set_marker(coords[0], coords[1], text=f"WP {wp_number}", marker_color_circle="#3498db")
        self.waypoint_markers.append(marker)
        self.draw_path()

    def set_home_event(self, coords):
        """Змінює точку повернення додому"""
        self.drone.home_coords = coords
        if self.home_marker:
            self.home_marker.set_position(coords[0], coords[1])
        print(f"🏠 Нова точка Home: {coords}")

    def draw_path(self):
        """Малює лінію між точками маршруту"""
        if self.path_line:
            self.path_line.delete()

        if len(self.drone.waypoints) > 0:
            # Малюємо лінію від поточного положення дрона до першої точки, і далі по точках
            path_coords = [(self.drone.current_lat, self.drone.current_lon)] + self.drone.waypoints
            self.path_line = self.map_widget.set_path(path_coords, color="#e74c3c", width=2)

    def clear_waypoints(self):
        """Очищує всі точки з карти та пам'яті"""
        self.drone.waypoints = []
        self.drone.current_wp_index = 0
        for marker in self.waypoint_markers:
            marker.delete()
        self.waypoint_markers.clear()
        if self.path_line:
            self.path_line.delete()
            self.path_line = None
        self.stop_mission()

    def start_mission(self):
        if not self.drone.waypoints:
            print("⚠️ Немає точок для місії!")
            return
        self.drone.mode = "MISSION"
        self.drone.current_wp_index = 0
        self.lbl_mode.configure(text="Режим: AUTO (MISSION)", text_color="#3498db")
        self.drone.send_command("/start_auto")  # Відправляємо команду на ESP

    def stop_mission(self):
        self.drone.mode = "MANUAL"
        self.lbl_mode.configure(text="Режим: MANUAL", text_color="#f1c40f")
        self.drone.send_command("/stop")

    def start_rth(self):
        self.drone.mode = "RTH"
        self.lbl_mode.configure(text="Режим: RTH (HOME)", text_color="#9b59b6")
        self.drone.send_command("/rth")

    # --- ОНОВЛЕННЯ ДАНИХ ---
    def update_loop(self):
        threading.Thread(target=self.drone.fetch_data, daemon=True).start()

        # Оновлення інтерфейсу навіть якщо немає підключення до реального заліза (для симуляції)
        if self.drone.current_data["connected"]:
            self.lbl_status.configure(text="ONLINE", fg_color="#27ae60")
            self.lbl_temp.configure(text=f"{self.drone.current_data['temp']} °C")
            self.lbl_ph.configure(text=f"{self.drone.current_data['ph']:.2f}")
        else:
            self.lbl_status.configure(text="SIMULATION MODE", fg_color="#f39c12")

        # Оновлення маркера дрона
        lat = self.drone.current_data['lat']
        lon = self.drone.current_data['lon']

        if self.drone_marker is None:
            self.drone_marker = self.map_widget.set_marker(lat, lon, text="Дрон", marker_color_outside="#e74c3c")
        else:
            self.drone_marker.set_position(lat, lon)

        # Оновлюємо лінію маршруту, якщо дрон рухається в місії
        if self.drone.mode == "MISSION" and self.drone.waypoints:
            self.draw_path()

        self.update_graphs()

        # Оновлення статусу режиму на випадок автоматичного завершення місії
        if self.drone.mode == "MANUAL" and self.lbl_mode.cget("text") != "Режим: MANUAL":
            self.lbl_mode.configure(text="Режим: MANUAL", text_color="#f1c40f")

        self.after(UPDATE_INTERVAL, self.update_loop)

    def update_graphs(self):
        x_axis = list(range(-30, 0))

        self.ax1.clear()
        self.ax1.plot(x_axis, self.drone.temp_history, color='#e67e22', linewidth=2)
        self.ax1.set_title("Температура (°C)", fontsize=10, color='white')
        self.ax1.set_facecolor('#2b2b2b')
        self.ax1.tick_params(colors='white')

        self.ax2.clear()
        self.ax2.plot(x_axis, self.drone.ph_history, color='#2ecc71', linewidth=2)
        self.ax2.set_title("pH", fontsize=10, color='white')
        self.ax2.set_facecolor('#2b2b2b')
        self.ax2.tick_params(colors='white')

        self.ax3.clear()
        self.ax3.plot(x_axis, self.drone.turb_history, color='#3498db', linewidth=2)
        self.ax3.set_title("Мутність", fontsize=10, color='white')
        self.ax3.set_facecolor('#2b2b2b')
        self.ax3.tick_params(colors='white')

        self.fig.tight_layout(pad=1.0)
        self.canvas.draw()


if __name__ == "__main__":
    app = DroneDashboard()
    app.mainloop()