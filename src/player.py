#!/usr/bin/env python3

import sys

from pynput import keyboard
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QSlider, QHBoxLayout, QLabel, QLineEdit, QSpinBox
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal


class KeyThread(QThread):
    split_pressed = pyqtSignal()
    reset_pressed = pyqtSignal()
    pause_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.split_sequence = "<ctrl>+<alt>+<shift>+<f1>"
        self.reset_sequence = "<ctrl>+<alt>+<shift>+<f2>"
        self.pause_sequence = "<pause>"
        self.listener: keyboard.GlobalHotKeys | None = None
        self.gh_map = {
            self.split_sequence: self.split_pressed.emit,
            self.reset_sequence: self.reset_pressed.emit,
            self.pause_sequence: self.pause_pressed.emit,
        }
    
    def run(self):
        # Collect events until released
        while True:
            if self.listener is None:
                with keyboard.GlobalHotKeys(self.gh_map) as listener:
                    self.listener = listener
                    listener.join()


class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.video_path = QLineEdit("/home/yanis/Videos/pb-videos/gsr6.mp4")
        self.video_path.textChanged.connect(self.update_video)

        self.video_offset = QSpinBox()
        self.video_offset.setMaximum(9999999)

        # player
        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()

        self.media_player.setSource(QUrl.fromLocalFile(self.video_path.text()))
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

        self.setWindowTitle("Video Player")
        self.setCentralWidget(self.video_widget)
        self.setFixedSize(640, 480)

        self.full_format = True
        self.duration = None
        self.is_started = False
        self.is_paused = False

        # controls
        self.start_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.lbl_time = QLabel()

        self.start_button.clicked.connect(self.start_video)
        self.pause_button.clicked.connect(self.pause_video)
        self.stop_button.clicked.connect(self.stop_video)
        self.slider.sliderMoved.connect(self.set_position)

        layout2 = QHBoxLayout()
        layout2.addWidget(self.start_button)
        layout2.addWidget(self.pause_button)
        layout2.addWidget(self.stop_button)

        layout3 = QHBoxLayout()
        layout3.addWidget(self.video_path)
        layout3.addWidget(self.video_offset)

        layout4 = QHBoxLayout()
        layout4.addWidget(self.slider)
        layout4.addWidget(self.lbl_time)

        layout = QVBoxLayout()
        layout.addLayout(layout2)
        layout.addLayout(layout3)
        layout.addLayout(layout4)

        self.widget = QWidget()
        self.widget.setWindowTitle("Video Player Controls")
        self.widget.setLayout(layout)
        self.widget.setFixedSize(self.width(), layout.geometry().height())
        self.widget.show()

        self.key_thread = KeyThread()
        self.key_thread.split_pressed.connect(self.start_video)
        self.key_thread.reset_pressed.connect(self.stop_video)
        self.key_thread.pause_pressed.connect(self.pause_video)
        self.key_thread.start()

        self.media_player.pause() # trick to show the first frame
        self.media_player.setPosition(self.video_offset.value())

    def closeEvent(self, e):
        self.key_thread.quit()
        self.key_thread.deleteLater()
        super(QMainWindow, self).closeEvent(e)
        self.widget.close()

    def moveEvent(self, a0):
        super().moveEvent(a0)
        self.widget.move(self.pos().x(), self.pos().y() + self.height() + 30)

    def get_time(self, start_ms: int):
        assert start_ms >= 0
        temp_sec, ms = divmod(start_ms, 1000)
        temp_min, sec = divmod(temp_sec, 60)
        hour, min = divmod(temp_min, 60)

        ms_str = f"{ms}"[:2]
        if len(ms_str) < 2:
            ms_str = f"{ms:02}"

        if self.full_format:
            text = f"{hour:02}:{min:02}:{sec:02}"
        else:
            if hour > 0:
                text = f"{hour:02}:{min:02}:{sec:02}"
            elif min > 0:
                text = f"{min:02}:{sec:02}"
            else:
                text = f"{sec}"

        return f"{text}"
    
    def update_video(self):
        self.media_player.setSource(QUrl.fromLocalFile(self.video_path.text()))
        self.is_paused = False
        self.media_player.pause() # trick to show the first frame

    def start_video(self):
        if not self.is_started:
            self.media_player.setPosition(self.video_offset.value())
            self.media_player.play()
            self.is_paused = False
            self.is_started = True

    def pause_video(self):
        if not self.is_paused:
            self.media_player.pause()
            self.is_paused = True
        else:
            self.media_player.play()
            self.is_paused = False

    def stop_video(self):
        self.media_player.stop()
        self.is_paused = False
        self.is_started = False
        self.media_player.pause() # trick to show the first frame
        self.media_player.setPosition(self.video_offset.value())

    def set_position(self, position):
        self.media_player.setPosition(position)

    def position_changed(self, position):
        if self.duration is None:
            self.duration = self.get_time(self.media_player.duration())

        self.slider.setValue(position)
        self.lbl_time.setText(f"{self.get_time(position)} / {self.duration}")

    def duration_changed(self, duration):
        self.slider.setRange(0, duration)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    video_player = VideoPlayer()
    video_player.show()
    sys.exit(app.exec())
