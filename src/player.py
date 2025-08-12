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
        self.split_sequence = [keyboard.Key.ctrl.value, keyboard.Key.alt.value, keyboard.Key.shift.value, keyboard.Key.f1.value]
        self.reset_sequence = [keyboard.Key.ctrl.value, keyboard.Key.shift.value, keyboard.KeyCode(65511), keyboard.Key.f2.value]
        self.pause_sequence = [keyboard.Key.pause.value]
        self.split_index = 0
        self.reset_index = 0
        self.pause_index = 0

    def validate_sequence(self, index_attr: str, key: keyboard.KeyCode, sequence: list[keyboard.Key], signal_attr: pyqtSignal):
        if key in sequence and getattr(self, index_attr) == sequence.index(key):
            setattr(self, index_attr, getattr(self, index_attr) + 1)
        else:
            setattr(self, index_attr, 0)

        if getattr(self, index_attr) == len(sequence):
            getattr(self, signal_attr).emit()

    def on_press(self, key: keyboard.Key | keyboard.KeyCode):
        if isinstance(key, keyboard.Key):
            val = key.value
        else:
            val = key

        self.validate_sequence("split_index", val, self.split_sequence, "split_pressed")
        self.validate_sequence("reset_index", val, self.reset_sequence, "reset_pressed")
        self.validate_sequence("pause_index", val, self.pause_sequence, "pause_pressed")

    def on_release(self, key):
        if key == keyboard.Key.esc:
            # Stop listener
            return False

    def run(self):
        # Collect events until released
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
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
        self.widget.show()

        self.key_thread = KeyThread()
        self.key_thread.split_pressed.connect(self.start_video)
        self.key_thread.reset_pressed.connect(self.stop_video)
        self.key_thread.pause_pressed.connect(self.pause_video)
        self.key_thread.start()

        self.media_player.pause() # trick to show the first frame
        self.media_player.setPosition(self.video_offset.value())

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
