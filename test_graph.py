import sys
import random
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from main import GraphWidget  # ✅ メインのコードを変更せず、そのまま使う

class TestGraph:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.graph_widget = GraphWidget()
        self.graph_widget.show()

        # ✅ 100msごとにランダムなデータを送る
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.test_add_data)
        self.test_timer.start(100)

        self.data_count = 0  # ✅ 追加データ数のカウント用

    def test_add_data(self):
        """テスト用の擬似データを生成し、グラフに追加"""
        fake_data = [random.randint(0, 4096) for _ in range(5)]  # 0～4096のランダム値
        self.graph_widget.add_data(fake_data)

        # ✅ データ数を確認（500以上なら削除されているはず）
        self.data_count += 1
        if self.data_count % 50 == 0:  # 50データごとに確認
            print(f"現在のデータ数: {len(self.graph_widget.times)}")  # ✅ 確認用

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    test = TestGraph()
    test.run()
