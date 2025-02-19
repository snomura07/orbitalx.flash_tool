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
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QTabWidget, QTextEdit, QComboBox, QHBoxLayout, QSizePolicy, QFileDialog, QSpinBox, QFormLayout
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
    graph_data_received = pyqtSignal(list)

    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self.running = True

    def run(self):
        while self.running:
            if self.ser and self.ser.is_open:
                try:
                    data = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        self.data_received.emit(f"[{self.timestamp()}] {data}")
                        match = re.match(r'\[adc\]@([\d.-]+),([\d.-]+),([\d.-]+),([\d.-]+),([\d.-]+)', data)
                        if match:
                            values = [float(match.group(i)) for i in range(1, 6)]  # 5つの数値をリスト化
                            self.graph_data_received.emit(values)

                except Exception as e:
                    self.data_received.emit(f"[{self.timestamp()}] Error: {e}")

    def stop(self):
        self.running = False
        self.wait()

    def timestamp(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]


class GraphWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.data = [[] for _ in range(5)]  # 5本のグラフデータ
        self.times = []
        self.max_points = 500  # 最大保持データ数

        # ✅ Y軸の初期値
        self.y_min = 0
        self.y_max = 4096

        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.fig)

        # ✅ Y軸調整スピンボックス（間隔を統一）
        self.y_min_spinbox = QSpinBox()
        self.y_min_spinbox.setRange(0, 4096)
        self.y_min_spinbox.setValue(self.y_min)
        self.y_min_spinbox.setFixedWidth(80)  # ✅ 幅を固定
        self.y_min_spinbox.valueChanged.connect(self.update_y_limits)

        self.y_max_spinbox = QSpinBox()
        self.y_max_spinbox.setRange(0, 4096)
        self.y_max_spinbox.setValue(self.y_max)
        self.y_max_spinbox.setFixedWidth(80)  # ✅ 幅を固定
        self.y_max_spinbox.valueChanged.connect(self.update_y_limits)

        # ✅ ラベルとスピンボックスをきれいに整列
        control_layout = QFormLayout()
        control_layout.addRow("Y min:", self.y_min_spinbox)
        control_layout.addRow("Y max:", self.y_max_spinbox)

        # ✅ 既存のレイアウトに組み込む
        layout = QVBoxLayout()
        layout.addLayout(control_layout)  # ✅ 追加
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(100)

    def add_data(self, values):
        """ シリアル通信データを受け取り、グラフに追加 """
        self.times.append(datetime.now().strftime("%H:%M:%S"))
        for i in range(5):
            self.data[i].append(values[i])

        # ✅ 移動窓方式：500データを超えたら古いデータを削除
        if len(self.times) > self.max_points:
            self.times.pop(0)
            for i in range(5):
                self.data[i].pop(0)

    def update_y_limits(self):
        """ Y 軸の最小・最大をスピンボックスの値に合わせて更新 """
        self.y_min = self.y_min_spinbox.value()
        self.y_max = self.y_max_spinbox.value()
        self.update_plot()

    def update_plot(self):
        """ グラフの描画を最適化して、移動窓を実現 """
        if not self.times:
            return

        x_data = list(range(len(self.times)))  # X 軸をインデックスに変更

        self.ax.clear()
        self.ax.grid(True, linestyle="--", linewidth=0.5)

        if len(self.times) <= self.max_points:
            self.ax.set_xlim(0, self.max_points)
        else:
            self.ax.set_xlim(len(self.times) - self.max_points, len(self.times))

        tick_step = max(1, len(self.times) // 10)
        self.ax.set_xticks(x_data[::tick_step])
        self.ax.set_xticklabels(self.times[::tick_step], rotation=45, ha="right")

        colors = ["red", "blue", "green", "purple", "orange"]
        labels = [f"Value {i+1}" for i in range(5)]

        for i in range(5):
            self.ax.plot(x_data[-self.max_points:], self.data[i][-self.max_points:], label=labels[i], color=colors[i])

        self.ax.set_title("ADC Values Over Time")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("ADC Values")

        # ✅ スピンボックスの値を Y 軸に適用
        self.ax.set_ylim(self.y_min, self.y_max)

        # ✅ 凡例（線種ラベル）をグラフの外に移動
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

        self.tabs = QTabWidget()
        self.tabs.addTab(self.log_area, "シリアルログ")
        self.tabs.addTab(self.graph_widget, "グラフ")

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
            self.reader_thread = SerialReaderThread(self.ser)
            self.reader_thread.data_received.connect(self.log)
            self.reader_thread.graph_data_received.connect(self.graph_widget.add_data)
            self.reader_thread.start()

        except Exception as e:
            self.log(f"接続エラー: {e}")

    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread = None
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

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
        self.log_area.append(f'<span style="color: black;">{message}</span>')

    def clear_log(self):
        self.log_area.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = STM32Flasher()
    window.show()
    sys.exit(app.exec())
