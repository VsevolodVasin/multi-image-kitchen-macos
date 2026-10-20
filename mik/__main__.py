import sys
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from mik.window import MikWindow

def main() -> None:
    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    app.setStyle("Fusion")
    win = MikWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
