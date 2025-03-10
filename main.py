import sys
import serial
import subprocess
import configparser
import re
import matplotlib
matplotlib.use("QtAgg")
# PyQt6 用のバックエンド
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QTabWidget, QTextEdit, QComboBox, QHBoxLayout, QSizePolicy, QFileDialog, QSpinBox, QFormLayout, QGroupBox, QLineEdit
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPixmap

CONFIG_FILE = "config.ini"

class FlashThread(QThread):
    log_signal = pyqtSignal(str)

    def __init__(self, port, file_path):
        super().__init__()
        self.port = port
        self.file_path = file_path

    def run(self):
        cmd = [
            "STM32_Programmer_CLI",
            "-c", f"port={self.port}",
            "-d", self.file_path
        ]
        self.log_signal.emit(f"[{self.timestamp()}] フラッシュ開始: {self.file_path}")

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            startupinfo=startupinfo
        )

        for line in iter(process.stdout.readline, ''):
            self.log_signal.emit(f"[{self.timestamp()}] {line.strip()}")

        process.stdout.close()
        process.wait()
        self.log_signal.emit(f"[{self.timestamp()}] フラッシュ完了")

    def timestamp(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]

class SerialReaderThread(QThread):
    data_received = pyqtSignal(str)
    graph_data_received = pyqtSignal(dict)
    device_info_received = pyqtSignal(str, str)  # 機体情報を受信するシグナルを追加

    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self.running = True

    def run(self):
        pattern = re.compile(r"^\[adc\]@((?:[A-Za-z0-9_]+:[-\d.]+,?\s*)+)$")  # 可変長データ対応
        info_pattern = re.compile(r"^\[info\]@([A-Za-z0-9_]+)\s*:\s*(.+)$")  # 機体情報を識別する正規表現を追加

        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        self.data_received.emit(f"[{self.timestamp()}] {data}")
                        match_adc = pattern.match(data)
                        if match_adc:
                            values_str = match_adc.group(1)
                            values = {}
                            for pair in values_str.split(','):
                                pair = pair.strip()
                                if ':' in pair:
                                    label, val = pair.split(':')
                                    values[label.strip()] = float(val)
                            self.graph_data_received.emit(values)

                        match_info = info_pattern.match(data)
                        if match_info:
                            key, value = match_info.groups()
                            self.device_info_received.emit(key, value)  # 機体情報のシグナルを発火

                except Exception as e:
                    self.data_received.emit(f"[{self.timestamp()}] Error: {e}")

    def stop(self):
        self.running = False
        self.wait()

    def timestamp(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]

class DeviceInfoWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window  # 親ウィンドウ（STM32Flasher）を保持

        self.info_fields = {}  # 受信パラメータを保持
        self.info_box = QGroupBox("機体情報")
        self.box_layout = QFormLayout()
        self.info_box.setLayout(self.box_layout)

        # 機体への接続ボタン
        self.debug_button = QPushButton("OrbitalXに接続")
        self.debug_button.clicked.connect(self.start_debug_mode)

        # パラメータ送信ボタン
        self.send_button = QPushButton("パラメータを送信")
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_parameters)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.info_box)
        main_layout.addWidget(self.debug_button, alignment=Qt.AlignmentFlag.AlignRight)
        main_layout.addWidget(self.send_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.setLayout(main_layout)

    def start_debug_mode(self):
        """ 機体をデバッグモードにする """
        if self.main_window.ser:  # `self.parent()` の代わりに `self.main_window` を使う
            self.main_window.ser.write(b"[debug]@\n")

    def send_parameters(self):
        """ ツール上で編集したパラメータを機体へ送信 """
        if self.main_window.ser:
            param_str = ",".join([f"{key}:{field.text()}" for key, field in self.info_fields.items()])
            command = f"[param]@{param_str}\\n"
            self.main_window.ser.write(command.encode())

class GraphWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.data = {}  # データ数を可変にするため空リストに
        self.times = []
        self.max_points = 500  # 最大保持データ数

        self.y_min = 0
        self.y_max = 5000

        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)

        # Y軸調整スピンボックス（間隔を統一）
        self.y_min_spinbox = QSpinBox()
        self.y_min_spinbox.setRange(-99999, 99999)
        self.y_min_spinbox.setValue(self.y_min)
        self.y_min_spinbox.setFixedWidth(80)
        self.y_min_spinbox.valueChanged.connect(self.update_y_limits)

        self.y_max_spinbox = QSpinBox()
        self.y_max_spinbox.setRange(-99999, 99999)
        self.y_max_spinbox.setValue(self.y_max)
        self.y_max_spinbox.setFixedWidth(80)
        self.y_max_spinbox.valueChanged.connect(self.update_y_limits)

        control_layout = QFormLayout()
        control_layout.addRow("Y min:", self.y_min_spinbox)
        control_layout.addRow("Y max:", self.y_max_spinbox)

        layout = QVBoxLayout()
        layout.addLayout(control_layout)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)

    def update_y_limits(self):
        """ Y 軸の最小・最大をスピンボックスの値に合わせて更新 """
        self.y_min = self.y_min_spinbox.value()
        self.y_max = self.y_max_spinbox.value()
        self.update_plot()

    def add_data(self, values):
        """ 可変長データを受け取り、グラフに追加 """
        for key in values.keys():
            if key not in self.data:
                self.data[key] = []  # 新しいラベルが追加された場合に初期化

        self.times.append(datetime.now().strftime("%H:%M:%S"))
        for key, val in values.items():
            if key not in self.data:
                self.data[key] = []
            self.data[key].append(val)

        # 移動窓方式：データが max_points を超えたら古いデータを削除
        if len(self.times) > self.max_points:
            self.times.pop(0)
            for key in self.data.keys():
                self.data[key].pop(0)

    def update_plot(self):
        """ グラフの描画を更新 """
        if not self.times or not self.data:
            return

        x_data = list(range(len(self.times)))

        self.ax.clear()
        self.ax.grid(True, linestyle="--", linewidth=0.5)

        if len(self.times) <= self.max_points:
            self.ax.set_xlim(0, self.max_points)
        else:
            self.ax.set_xlim(len(self.times) - self.max_points, len(self.times))

        tick_step = max(1, len(self.times) // 10)
        self.ax.set_xticks(x_data[::tick_step])
        self.ax.set_xticklabels(self.times[::tick_step], rotation=45, ha="right")

        colors = ["red", "blue", "green", "purple", "orange", "cyan", "magenta", "yellow"]
        for i, (label, values) in enumerate(self.data.items()):
            color = colors[i % len(colors)]
            self.ax.plot(x_data[-self.max_points:], values[-self.max_points:], label=label, color=color)

        self.ax.set_title("ADC Values Over Time")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("ADC Values")
        self.ax.set_ylim(self.y_min, self.y_max)

        self.ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
        self.canvas.draw()


class STM32Flasher(QWidget):
    def __init__(self):
        super().__init__()

        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE)

        self.ser = None
        self.reader_thread = None
        self.flash_thread = None
        self.selected_file = self.config.get("Settings", "flash_file", fallback="")

        self.red_icon = QPixmap(20, 20)
        self.red_icon.fill(Qt.GlobalColor.red)
        self.green_icon = QPixmap(20, 20)
        self.green_icon.fill(Qt.GlobalColor.green)

        self.initUI()

    def initUI(self):
        self.setWindowTitle('STM32 Flasher & Serial Monitor')
        self.resize(800, 600)

        self.port_label = QLabel('COMポート:')
        self.port_select = QComboBox()
        self.port_select.addItems(['COM4', 'COM5', 'COM6'])
        self.port_select.setEditable(True)

        self.status_label = QLabel()
        self.status_label.setPixmap(self.red_icon)

        self.connect_btn = QPushButton('接続')
        self.connect_btn.clicked.connect(self.toggle_connection)

        self.file_label = QLabel(f'ファームウェア: {self.selected_file if self.selected_file else "未選択"}')
        self.file_select_btn = QPushButton('ファイル選択')
        self.file_select_btn.clicked.connect(self.select_file)

        self.flash_btn = QPushButton('フラッシュ')
        self.flash_btn.clicked.connect(self.flash_firmware)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)

        self.graph_widget = GraphWidget()
        self.device_info_widget = DeviceInfoWidget(self)  # 機体情報ウィジェットを追加

        self.tabs = QTabWidget()
        self.tabs.addTab(self.log_area, "シリアルログ")
        self.tabs.addTab(self.graph_widget, "グラフ")
        self.tabs.addTab(self.device_info_widget, "機体情報")  # 機体情報タブを追加

        self.clear_log_btn = QPushButton('ログクリア')
        self.clear_log_btn.clicked.connect(self.clear_log)

        port_layout = QHBoxLayout()
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_select, 1)
        port_layout.addWidget(self.status_label)
        port_layout.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(port_layout)
        layout.addWidget(self.connect_btn)
        layout.addWidget(self.file_label)
        layout.addWidget(self.file_select_btn)
        layout.addWidget(self.flash_btn)
        layout.addWidget(self.tabs)
        layout.addWidget(self.clear_log_btn)

        self.setLayout(layout)

    def toggle_connection(self):
        port = self.port_select.currentText()
        if self.ser and self.ser.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial(port)

    def connect_serial(self, port):
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
            self.connect_btn.setText('切断')
            self.status_label.setPixmap(self.green_icon)

            # 接続メッセージを赤字で表示
            self.log_system(f"{port} に接続しました")

            self.reader_thread = SerialReaderThread(self.ser)
            self.reader_thread.data_received.connect(self.log)
            self.reader_thread.graph_data_received.connect(self.graph_widget.add_data)
            self.reader_thread.device_info_received.connect(self.device_info_widget.update_info)
            self.reader_thread.start()
        except Exception as e:
            self.log_system(f"接続エラー: {e}")

    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread.wait()  # スレッドが確実に終了するのを待つ
            self.reader_thread = None

        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

        self.connect_btn.setText('接続')
        self.status_label.setPixmap(self.red_icon)

        # 切断メッセージを赤字で表示
        self.log_system("シリアル接続を切断しました")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "ファームウェアを選択", "", "ELF Files (*.elf)")
        if file_path:
            self.selected_file = file_path
            self.file_label.setText(f"選択: {file_path}")

    def flash_firmware(self):
        self.flash_thread = FlashThread(self.port_select.currentText(), self.selected_file)
        self.flash_thread.log_signal.connect(self.log)
        self.flash_thread.start()

    def log(self, message):
        if "Error" in message:
            color = "red"
        elif "complete" in message:
            color = "blue"
        elif "[info]@" in message:
            return
        else:
            color = "black"
        self.log_area.append(f'<span style="color: {color};">{message}</span>')

    def log_system(self, message):
        """ システムメッセージを赤字でログに表示 """
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
        self.log_area.append(f'<span style="color: red;"><b>[{timestamp}] {message}</b></span>')

    def clear_log(self):
        self.log_area.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = STM32Flasher()
    window.show()
    sys.exit(app.exec())
