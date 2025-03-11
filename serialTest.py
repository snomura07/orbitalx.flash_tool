import serial
import time

# UART設定
PORT = "COM3"  # STM32の接続ポート
BAUD_RATE = 115200  # ボーレート

try:
    # シリアルポートを開く
    ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
    print(f"Opened {PORT} at {BAUD_RATE} baud")

    # 送信データ
    test_message = "[debug]@TEST\n"

    # 送信＆受信ループ
    for i in range(5):
        # STM32へデータを送信
        ser.write(test_message.encode())  # 文字列をバイト列に変換して送信
        print(f"Sent: {test_message.strip()}")

        # 受信データの取得（最大 5 秒間待つ）
        start_time = time.time()
        while time.time() - start_time < 5:
            response = ser.readline().decode(errors='ignore').strip()
            if response:
                print(f"Received: {response}")
                break  # 受信データがあったらループを抜ける
        
        time.sleep(1)  # 1秒待機

    ser.close()
    print("Serial connection closed.")

except serial.SerialException as e:
    print(f"Error: {e}")
