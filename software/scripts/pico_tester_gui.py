#!/usr/bin/env python3
"""
RP2040 Distribution Board Test Suite - Flet GUI Console
Modern Python Desktop Application for RP2040 Serial Terminal & Diagnostics
"""

import sys
import time
import json
import queue
import pathlib
import threading
from datetime import datetime
import flet as ft
import serial
import serial.tools.list_ports

CONFIG_PATH = pathlib.Path.home() / ".pico_tester_gui.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


class PicoTestApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "RP2040 Distribution Board - Test Suite & Console"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 10
        self.page.spacing = 10
        self.page.window.width = 1240
        self.page.window.height = 840
        self.page.window.min_width = 900
        self.page.window.min_height = 650

        # Saved configuration
        self.config = load_config()

        # Serial Connection & Queue State
        self.ser: serial.Serial | None = None
        self.running = True
        self.monitoring_active = False
        self.line_queue = queue.Queue()

        # Command History
        self.cmd_history: list[str] = []

        # --- Header Components ---
        self.port_dropdown = ft.Dropdown(
            label="Port Série COM",
            width=220,
            dense=True,
            options=[]
        )
        self.baud_dropdown = ft.Dropdown(
            label="Baudrate",
            width=120,
            dense=True,
            value=self.config.get("last_baud", "115200"),
            options=[
                ft.dropdown.Option("9600"),
                ft.dropdown.Option("57600"),
                ft.dropdown.Option("115200"),
                ft.dropdown.Option("230400"),
                ft.dropdown.Option("460800"),
            ]
        )
        # Highly visible connect button
        self.connect_btn = ft.Button(
            "Connexion",
            icon=ft.Icons.POWER_SETTINGS_NEW,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN_700,
                elevation=3,
                padding=ft.Padding(16, 12, 16, 12)
            ),
            on_click=self.toggle_connection
        )
        self.status_badge = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.CIRCLE, size=12, color=ft.Colors.RED_400),
                    ft.Text("Déconnecté", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400)
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER
            ),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            padding=ft.Padding(12, 6, 12, 6),
            border_radius=16,
        )

        # --- Stepper Control Inputs ---
        self.stepper_ch = ft.Dropdown(
            label="Canal",
            width=90,
            dense=True,
            value="0",
            options=[
                ft.dropdown.Option("0"),
                ft.dropdown.Option("1"),
                ft.dropdown.Option("2"),
                ft.dropdown.Option("3"),
                ft.dropdown.Option("4"),
                ft.dropdown.Option("all"),
            ]
        )
        self.stepper_steps = ft.TextField(label="Steps", value="400", width=100, dense=True)
        self.stepper_speed = ft.TextField(label="Vitesse (sps)", value="3000", width=110, dense=True)
        self.stepper_current = ft.TextField(label="Courant (mA)", value="600", width=110, dense=True)
        self.stepper_usteps = ft.Dropdown(
            label="Micropas",
            width=100,
            dense=True,
            value="16",
            options=[
                ft.dropdown.Option("1"),
                ft.dropdown.Option("2"),
                ft.dropdown.Option("4"),
                ft.dropdown.Option("8"),
                ft.dropdown.Option("16"),
                ft.dropdown.Option("32"),
                ft.dropdown.Option("64"),
                ft.dropdown.Option("128"),
                ft.dropdown.Option("256"),
            ]
        )

        # --- PWM / MOSFET Control Inputs ---
        self.pwm_ch = ft.Dropdown(
            label="Canal PWM",
            width=100,
            dense=True,
            value="0",
            options=[
                ft.dropdown.Option("0"),
                ft.dropdown.Option("1"),
                ft.dropdown.Option("2"),
                ft.dropdown.Option("3"),
            ]
        )
        self.pwm_duty = ft.TextField(label="Puissance (%)", value="50", width=120, dense=True)

        # --- Servo / PCA9685 Control Inputs ---
        self.servo_ch = ft.Dropdown(
            label="Canal Servo",
            width=100,
            dense=True,
            value="0",
            options=[ft.dropdown.Option(str(i)) for i in range(16)]
        )
        self.servo_angle = ft.TextField(label="Angle (° 0-180)", value="90", width=120, dense=True)

        # --- Terminal Log View ---
        self.terminal_list = ft.ListView(
            expand=True,
            spacing=2,
            padding=8,
            auto_scroll=True
        )
        self.command_input = ft.TextField(
            hint_text="Tapez une commande (ex: status, stepper move 0 400 3000, help)...",
            expand=True,
            dense=True,
            autofocus=True,
            on_submit=self.on_send_command
        )
        self.send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            icon_color=ft.Colors.CYAN_400,
            tooltip="Envoyer la commande",
            on_click=self.on_send_command
        )
        self.auto_scroll_chk = ft.Checkbox(label="Auto-scroll", value=True)

        self.setup_ui()
        self.refresh_ports()

        # Launch Flet-managed background UI queue pump for instant rendering
        self.page.run_thread(self.ui_pump_loop)

    def setup_ui(self):
        # Header Toolbar
        header_card = ft.Card(
            content=ft.Container(
                content=ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.MEMORY, color=ft.Colors.CYAN_400, size=28),
                                ft.Column(
                                    [
                                        ft.Text("RP2040 Test Suite", size=16, weight=ft.FontWeight.BOLD),
                                        ft.Text("Distribution Board v1.3", size=11, color=ft.Colors.GREY_400)
                                    ],
                                    spacing=0
                                )
                            ],
                            spacing=10
                        ),
                        ft.Row(
                            [
                                self.port_dropdown,
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH,
                                    tooltip="Actualiser les ports COM",
                                    on_click=lambda _: self.refresh_ports()
                                ),
                                self.baud_dropdown,
                                self.connect_btn,
                                self.status_badge
                            ],
                            spacing=8
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                padding=10
            )
        )

        # Left Panel - Full Controls matching 'help' menu
        left_panel = ft.Container(
            width=360,
            content=ft.Column(
                [
                    # --- Card 1: System Commands ---
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.SETTINGS, color=ft.Colors.CYAN_400, size=18),
                                            ft.Text("SYSTÈME & GENERAL", size=13, weight=ft.FontWeight.BOLD)
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Status", icon=ft.Icons.INFO_OUTLINE, on_click=lambda _: self.send_cmd("status"), expand=True),
                                            ft.OutlinedButton("Help / ?", icon=ft.Icons.HELP_OUTLINE, on_click=lambda _: self.send_cmd("help"), expand=True),
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Reboot", icon=ft.Icons.RESTART_ALT, on_click=lambda _: self.send_cmd("reboot"), expand=True),
                                            ft.OutlinedButton("Bootloader", icon=ft.Icons.USB, on_click=lambda _: self.send_cmd("reboot bootloader"), expand=True),
                                        ],
                                        spacing=6
                                    ),
                                    ft.OutlinedButton(
                                        "Lancer Auto-Test Complet",
                                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                        style=ft.ButtonStyle(color=ft.Colors.AMBER_400),
                                        on_click=lambda _: self.send_cmd("test all"),
                                        width=330
                                    )
                                ],
                                spacing=8
                            ),
                            padding=10
                        )
                    ),

                    # --- Card 2: Steppers ---
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.SETTINGS_INPUT_COMPONENT, color=ft.Colors.GREEN_400, size=18),
                                            ft.Text("MOTEURS PAS-À-PAS (TMC2209)", size=13, weight=ft.FontWeight.BOLD)
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row([self.stepper_ch, self.stepper_steps, self.stepper_speed], spacing=6),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Move Relatif", icon=ft.Icons.MOVE_DOWN, on_click=self.on_stepper_move, expand=True),
                                            ft.OutlinedButton("Run Continu", icon=ft.Icons.PLAY_ARROW, on_click=self.on_stepper_run, expand=True),
                                            ft.OutlinedButton("Stop", icon=ft.Icons.STOP, style=ft.ButtonStyle(color=ft.Colors.RED_400), on_click=self.on_stepper_stop, expand=True),
                                        ],
                                        spacing=4
                                    ),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Enable", on_click=self.on_stepper_enable, expand=True),
                                            ft.OutlinedButton("Disable", on_click=self.on_stepper_disable, expand=True),
                                            ft.OutlinedButton("Diag / Stall", on_click=lambda _: self.send_cmd("stepper diag"), expand=True),
                                        ],
                                        spacing=4
                                    ),
                                    ft.Divider(height=1),
                                    ft.Row(
                                        [
                                            self.stepper_current,
                                            ft.OutlinedButton("Fixer mA", on_click=self.on_stepper_current, expand=True),
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row(
                                        [
                                            self.stepper_usteps,
                                            ft.OutlinedButton("Fixer Micropas", on_click=self.on_stepper_usteps, expand=True),
                                        ],
                                        spacing=6
                                    ),
                                ],
                                spacing=8
                            ),
                            padding=10
                        )
                    ),

                    # --- Card 3: PWM / Power Outputs ---
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE, color=ft.Colors.AMBER_400, size=18),
                                            ft.Text("SORTIES POWER & PWM", size=13, weight=ft.FontWeight.BOLD)
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row([self.pwm_ch, self.pwm_duty], spacing=6),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Appliquer PWM", icon=ft.Icons.TUNE, on_click=self.on_pwm_set, expand=True),
                                            ft.OutlinedButton("Toutes Off", icon=ft.Icons.POWER_OFF, style=ft.ButtonStyle(color=ft.Colors.RED_400), on_click=lambda _: self.send_cmd("pwm off"), expand=True),
                                        ],
                                        spacing=6
                                    )
                                ],
                                spacing=8
                            ),
                            padding=10
                        )
                    ),

                    # --- Card 4: PCA9685 & Servos ---
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.TUNE, color=ft.Colors.PURPLE_300, size=18),
                                            ft.Text("PCA9685 / SERVOS & HORLOGE", size=13, weight=ft.FontWeight.BOLD)
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Osc Ext Y1 25MHz", on_click=lambda _: self.send_cmd("servo clock external"), expand=True),
                                            ft.OutlinedButton("Osc Interne", on_click=lambda _: self.send_cmd("servo clock internal"), expand=True),
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row([self.servo_ch, self.servo_angle], spacing=6),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Fixer Angle", icon=ft.Icons.ROTATE_RIGHT, on_click=self.on_servo_set, expand=True),
                                            ft.OutlinedButton("Sweep 0-180-0", icon=ft.Icons.SWIPE_ROUNDED, on_click=self.on_servo_sweep, expand=True),
                                        ],
                                        spacing=6
                                    ),
                                    ft.OutlinedButton("Scan Bus I2C", icon=ft.Icons.SEARCH, on_click=lambda _: self.send_cmd("servo scan"), width=330)
                                ],
                                spacing=8
                            ),
                            padding=10
                        )
                    ),

                    # --- Card 5: Inputs & Monitor ---
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.SENSORS, color=ft.Colors.CYAN_300, size=18),
                                            ft.Text("ENTRÉES & SURVEILLANCE", size=13, weight=ft.FontWeight.BOLD)
                                        ],
                                        spacing=6
                                    ),
                                    ft.Row(
                                        [
                                            ft.OutlinedButton("Lire Entrées", icon=ft.Icons.CHECK_BOX, on_click=lambda _: self.send_cmd("inputs"), expand=True),
                                            ft.OutlinedButton("Mode Monitor Live", icon=ft.Icons.MONITOR_HEART, on_click=self.toggle_monitor, expand=True),
                                        ],
                                        spacing=6
                                    )
                                ],
                                spacing=8
                            ),
                            padding=10
                        )
                    ),
                ],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                spacing=8
            )
        )

        # Right Panel - Serial Console Terminal
        right_panel = ft.Container(
            expand=True,
            content=ft.Card(
                content=ft.Container(
                    content=ft.Column(
                        [
                            # Top Bar of Console
                            ft.Row(
                                [
                                    ft.Row(
                                        [
                                            ft.Icon(ft.Icons.TERMINAL, color=ft.Colors.CYAN_400, size=20),
                                            ft.Text("Console Série RP2040", size=15, weight=ft.FontWeight.BOLD),
                                        ],
                                        spacing=8
                                    ),
                                    ft.Row(
                                        [
                                            self.auto_scroll_chk,
                                            ft.TextButton(
                                                "Effacer Console",
                                                icon=ft.Icons.DELETE_SWEEP,
                                                on_click=lambda _: self.clear_terminal()
                                            )
                                        ],
                                        spacing=10
                                    )
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                            ),

                            # Main Console Terminal Window (Large Top Area)
                            ft.Container(
                                expand=True,
                                content=self.terminal_list,
                                bgcolor=ft.Colors.BLACK,
                                border=ft.Border.all(width=1, color=ft.Colors.GREY_800),
                                border_radius=8,
                                padding=4
                            ),

                            # Bottom Command Input Line
                            ft.Row(
                                [
                                    self.command_input,
                                    self.send_btn
                                ],
                                spacing=8,
                                alignment=ft.MainAxisAlignment.CENTER
                            )
                        ],
                        spacing=8
                    ),
                    padding=10
                )
            )
        )

        # Main Layout
        self.page.add(
            header_card,
            ft.Row([left_panel, right_panel], expand=True, spacing=10)
        )

        # Append Welcome Log
        self.append_terminal_line("=== RP2040 Distribution Board Flet GUI Ready ===", color=ft.Colors.CYAN_400)
        if self.port_dropdown.value:
            self.append_terminal_line(f"Port mémorisé: {self.port_dropdown.value}. Cliquez sur 'Connexion'.", color=ft.Colors.GREY_400)
        else:
            self.append_terminal_line("Sélectionnez un port COM et cliquez sur 'Connexion'.", color=ft.Colors.GREY_400)

    # --- Stepper Action Handlers ---
    def on_stepper_move(self, e=None):
        ch = self.stepper_ch.value or "0"
        steps = self.stepper_steps.value or "400"
        speed = self.stepper_speed.value or "3000"
        self.send_cmd(f"stepper move {ch} {steps} {speed}")

    def on_stepper_run(self, e=None):
        ch = self.stepper_ch.value or "0"
        speed = self.stepper_speed.value or "3000"
        self.send_cmd(f"stepper run {ch} {speed}")

    def on_stepper_stop(self, e=None):
        ch = self.stepper_ch.value or "0"
        self.send_cmd(f"stepper stop {ch}")

    def on_stepper_enable(self, e=None):
        ch = self.stepper_ch.value or "0"
        self.send_cmd(f"stepper enable {ch}")

    def on_stepper_disable(self, e=None):
        ch = self.stepper_ch.value or "0"
        self.send_cmd(f"stepper disable {ch}")

    def on_stepper_current(self, e=None):
        ch = self.stepper_ch.value or "0"
        mA = self.stepper_current.value or "600"
        self.send_cmd(f"stepper current {ch} {mA}")

    def on_stepper_usteps(self, e=None):
        ch = self.stepper_ch.value or "0"
        u = self.stepper_usteps.value or "16"
        self.send_cmd(f"stepper usteps {ch} {u}")

    # --- PWM Action Handlers ---
    def on_pwm_set(self, e=None):
        ch = self.pwm_ch.value or "0"
        duty = self.pwm_duty.value or "50"
        self.send_cmd(f"pwm set {ch} {duty}")

    # --- Servo Action Handlers ---
    def on_servo_set(self, e=None):
        ch = self.servo_ch.value or "0"
        angle = self.servo_angle.value or "90"
        self.send_cmd(f"servo set {ch} {angle}")

    def on_servo_sweep(self, e=None):
        ch = self.servo_ch.value or "0"
        self.send_cmd(f"servo sweep {ch}")

    # --- Monitor Mode Toggle ---
    def toggle_monitor(self, e=None):
        if not self.monitoring_active:
            self.send_cmd("monitor")
            self.monitoring_active = True
        else:
            # Sending newline stops monitor mode
            self.send_cmd("")
            self.monitoring_active = False

    # --- Connection & Port Management ---
    def refresh_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_dropdown.options = [
            ft.dropdown.Option(p.device, text=f"{p.device} ({p.description})") for p in ports
        ]
        
        last_port = self.config.get("last_port")
        if last_port and any(p.device == last_port for p in ports):
            self.port_dropdown.value = last_port
        elif ports:
            self.port_dropdown.value = ports[0].device
        else:
            self.port_dropdown.value = None

        self.page.update()

    def toggle_connection(self, e=None):
        if self.ser and self.ser.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self):
        port = self.port_dropdown.value
        baud = int(self.baud_dropdown.value or "115200")

        if not port:
            self.append_terminal_line("Erreur: Aucun port COM sélectionné !", color=ft.Colors.RED_400)
            return

        try:
            self.ser = serial.Serial(port, baud, timeout=0.01)

            # Save connected port to config for future app launches
            self.config["last_port"] = port
            self.config["last_baud"] = str(baud)
            save_config(self.config)

            # Start serial reader background task via Flet thread runner
            self.page.run_thread(self.serial_read_loop)

            # High-visibility Connected state
            self.connect_btn.text = "Déconnexion"
            self.connect_btn.icon = ft.Icons.POWER_OFF
            self.connect_btn.style = ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.RED_700,
                elevation=3,
                padding=ft.Padding(16, 12, 16, 12)
            )
            self.status_badge.content.controls[0].color = ft.Colors.GREEN_400
            self.status_badge.content.controls[1].text = f"Connecté ({port})"
            self.status_badge.content.controls[1].color = ft.Colors.GREEN_400

            self.append_terminal_line(f"--> Connecté au port {port} à {baud} baud.", color=ft.Colors.GREEN_400)
            self.page.update()

        except Exception as ex:
            self.append_terminal_line(f"Impossible d'ouvrir le port {port}: {ex}", color=ft.Colors.RED_400)
            self.page.update()

    def disconnect_serial(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

        self.connect_btn.text = "Connexion"
        self.connect_btn.icon = ft.Icons.POWER_SETTINGS_NEW
        self.connect_btn.style = ft.ButtonStyle(
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.GREEN_700,
            elevation=3,
            padding=ft.Padding(16, 12, 16, 12)
        )
        self.status_badge.content.controls[0].color = ft.Colors.RED_400
        self.status_badge.content.controls[1].text = "Déconnecté"
        self.status_badge.content.controls[1].color = ft.Colors.RED_400

        self.append_terminal_line("<-- Port série déconnecté.", color=ft.Colors.AMBER_400)
        self.page.update()

    def serial_read_loop(self):
        buf = ""
        while self.running and self.ser and self.ser.is_open:
            try:
                waiting = self.ser.in_waiting
                if waiting > 0:
                    chunk = self.ser.read(waiting).decode("utf-8", errors="replace")
                    buf += chunk
                    if "\n" in buf:
                        lines = buf.split("\n")
                        buf = lines.pop()  # Keep last unfinished fragment
                        
                        for l in lines:
                            clean_text = l.rstrip("\r")
                            if clean_text:
                                self.append_terminal_line(clean_text, color=ft.Colors.GREEN_200)
                else:
                    time.sleep(0.005)
            except Exception as ex:
                if self.running and self.ser and self.ser.is_open:
                    self.append_terminal_line(f"Erreur lecture série: {ex}", color=ft.Colors.RED_400)
                break

    # --- Thread-Safe UI Queue Pump ---
    def ui_pump_loop(self):
        """Runs under page.run_thread to drain the queue and trigger immediate UI repaints."""
        while self.running:
            batch = []
            while not self.line_queue.empty():
                try:
                    batch.append(self.line_queue.get_nowait())
                except Exception:
                    break

            if batch:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                new_controls = []
                for text, color, is_cmd in batch:
                    prefix = f"[{timestamp}] "
                    weight = ft.FontWeight.BOLD if is_cmd else ft.FontWeight.NORMAL
                    new_controls.append(
                        ft.Text(
                            f"{prefix}{text}",
                            font_family="Consolas",
                            size=13,
                            color=color,
                            weight=weight,
                            selectable=True
                        )
                    )

                self.terminal_list.controls.extend(new_controls)
                if len(self.terminal_list.controls) > 1000:
                    self.terminal_list.controls = self.terminal_list.controls[-1000:]
                self.terminal_list.auto_scroll = bool(self.auto_scroll_chk.value)
                self.page.update()

            time.sleep(0.01)

    def send_cmd(self, cmd_str: str):
        if not self.ser or not self.ser.is_open:
            self.append_terminal_line("Attention: Non connecté au port série !", color=ft.Colors.AMBER_400)
            return

        try:
            full_cmd = cmd_str.strip() + "\r\n"
            self.ser.write(full_cmd.encode("utf-8"))
            self.append_terminal_line(f"> {cmd_str.strip()}", color=ft.Colors.CYAN_300, is_cmd=True)
        except Exception as ex:
            self.append_terminal_line(f"Erreur d'envoi: {ex}", color=ft.Colors.RED_400)

    def on_send_command(self, e=None):
        cmd = self.command_input.value
        if cmd and cmd.strip():
            self.send_cmd(cmd)
            self.cmd_history.append(cmd)
            self.command_input.value = ""
            self.page.update()

    def append_terminal_line(self, text: str, color=ft.Colors.GREEN_200, is_cmd=False):
        self.line_queue.put((text, color, is_cmd))

    def clear_terminal(self):
        self.terminal_list.controls.clear()
        self.page.update()


def main(page: ft.Page):
    PicoTestApp(page)


if __name__ == "__main__":
    ft.run(main)
