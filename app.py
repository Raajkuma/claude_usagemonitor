import sys
from PyQt6.QtWidgets import QApplication
from floating_widget import JarvisHUDWidget

def main():
    app = QApplication(sys.argv)
    widget = JarvisHUDWidget()
    widget.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()