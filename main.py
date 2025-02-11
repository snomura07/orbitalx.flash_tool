import sys
import serial
import subprocess
import configparser
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout, QFileDialog, QTextEdit, QComboBox, QHBoxLayout, QSizePolicy
from PyQt6.QtCore import QThread, pyqtSignal, Qt
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

        # ✅ CMDウィンドウを開かないように設定
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
            startupinfo=startupinfo  # ✅ ここで CMD を非表示にする
        )

        for line in iter(process.stdout.readline, ''):
            self.log_signal.emit(f"[{self.timestamp()}] {line.strip()}")

        process.stdout.close()
        process.wait()
        self.log_signal.emit(f"[{self.timestamp()}] フラッシュ完了")

    def timestamp(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]  # ミリ秒付き


class SerialReaderThread(QThread):
    data_received = pyqtSignal(str)

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
                except Exception as e:
                    self.data_received.emit(f"[{self.timestamp()}] Error: {e}")
            else:
                break

    def stop(self):
        self.running = False
        self.wait()

    def timestamp(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]


class STM32Flasher(QWidget):
    def __init__(self):
        super().__init__()

        self.config = configparser.ConfigParser()
        self.config.read(CONFIG_FILE)

        self.ser = None
        self.reader_thread = None
        self.flash_thread = None
        self.selected_file = self.config.get("Settings", "flash_file", fallback="")  # 設定ファイルから取得

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
        self.port_select.lineEdit().setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.port_select.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed))

        # ✅ 設定ファイルのCOMポートを適用
        default_port = self.config.get("Settings", "com_port", fallback="COM4")
        if default_port in [self.port_select.itemText(i) for i in range(self.port_select.count())]:
            self.port_select.setCurrentText(default_port)

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
        layout.addWidget(QLabel('シリアル通信ログ:'))
        layout.addWidget(self.log_area)
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
            self.log_system(f"{port} に接続しました")

            self.reader_thread = SerialReaderThread(self.ser)
            self.reader_thread.data_received.connect(self.log)
            self.reader_thread.start()
        except Exception as e:
            self.log_system(f"接続エラー: {e}")

    def disconnect_serial(self):
        if self.reader_thread:
            self.reader_thread.stop()
            self.reader_thread = None

        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

        self.connect_btn.setText('接続')
        self.status_label.setPixmap(self.red_icon)
        self.log_system("シリアル接続を切断しました")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "ファームウェアを選択", "", "ELF Files (*.elf)")
        if file_path:
            self.selected_file = file_path
            self.file_label.setText(f"選択: {file_path}")
            self.save_config("flash_file", file_path)

    def save_config(self, key, value):
        """ 設定ファイルに値を保存 """
        self.config.set("Settings", key, value)
        with open(CONFIG_FILE, "w") as configfile:
            self.config.write(configfile)

    def flash_firmware(self):
        if not self.selected_file:
            self.log_system("ファイルが選択されていません")
            return

        self.disconnect_serial()

        self.flash_thread = FlashThread(self.port_select.currentText(), self.selected_file)
        self.flash_thread.log_signal.connect(self.log)
        self.flash_thread.start()

    def log(self, message):
        self.log_area.append(f'<span style="color: black;">{message}</span>')

    def log_system(self, message):
        timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
        self.log_area.append(f'<span style="color: red;"><b>[{timestamp}] {message}</b></span>')

    def clear_log(self):
        self.log_area.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = STM32Flasher()
    window.show()
    sys.exit(app.exec())
