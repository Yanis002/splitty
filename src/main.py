#!/usr/bin/env python3

# pip requirements: PyQt6 and PyQt6-WebEngine

import argparse
import sys

from pathlib import Path
from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QIcon, QPixmap, QKeyEvent
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineDownloadRequest
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from player import VideoPlayer


def get_arguments():
    parser = argparse.ArgumentParser(description="Utility for speedruns.")
    parser.add_argument("-p", "--player", action="store_true", default=False, help="Start the video player too")
    args = parser.parse_args()
    return args


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.args = get_arguments()

        self.webview = QWebEngineView()

        self.profile = QWebEngineProfile("livesplitone-storage", self.webview)
        self.profile.setPersistentStoragePath(str(Path("data").resolve()))
        self.profile.downloadRequested.connect(self.download)

        self.webpage = QWebEnginePage(self.profile, self.webview)
        self.webview.setPage(self.webpage)
        self.webview.load(QUrl("https://one.livesplit.org/"))

        self.nam = QNetworkAccessManager()
        self.nam.finished.connect(self.set_window_icon_from_response)
        self.nam.get(QNetworkRequest(QUrl("https://raw.githubusercontent.com/LiveSplit/LiveSplitOne/refs/heads/master/src/assets/icon.png")))

        self.setWindowTitle("LiveSplit One")
        self.setMinimumSize(850, 750)
        self.setCentralWidget(self.webview)

        if self.args.player:
            self.video_player = VideoPlayer()
            self.video_player.show()

    def download(self, download: QWebEngineDownloadRequest):
        download.setDownloadDirectory(str(Path("downloads").resolve()))
        download.accept()

    def keyPressEvent(self, event: QKeyEvent):
        super().keyPressEvent(event)

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_F5:
            self.webview.reload()

    def closeEvent(self, a0):
        self.webview.close()
        super().closeEvent(a0)

    # from https://stackoverflow.com/a/48921358
    def set_window_icon_from_response(self, http_response):
        pixmap = QPixmap()
        pixmap.loadFromData(http_response.readAll())
        icon = QIcon(pixmap)
        self.setWindowIcon(icon)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
