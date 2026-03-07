#!/usr/bin/env python3

import json
import sys

from pathlib import Path
from pynput import keyboard
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QSlider, QHBoxLayout, QLabel, QLineEdit, QSpinBox, QFileDialog
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal


class VideoPlayerSettings:
    default_path = Path.cwd() / "settings.json"

    def __init__(self):
        self.load_default()

        if self.default_path.exists():
            self.from_json()

    def load_default(self):
        self.video_path = Path.home() / "Videos" / "video.mp4"
        self.video_offset = 0
        self.split_sequence = "<ctrl>+<alt>+<shift>+<f1>"
        self.reset_sequence = "<ctrl>+<alt>+<shift>+<f2>"
        self.pause_sequence = "<pause>"
        self.full_time_format = True

    def from_json(self, path: Path = default_path):
        json_file = json.loads(path.read_text())
        self.video_path = Path(json_file["video_path"])

        if "video_offset" in json_file:
            self.video_offset = json_file["video_offset"]

        if "split_sequence" in json_file:
            self.split_sequence = json_file["split_sequence"]

        if "reset_sequence" in json_file:
            self.reset_sequence = json_file["reset_sequence"]

        if "pause_sequence" in json_file:
            self.pause_sequence = json_file["pause_sequence"]

        if "full_time_format" in json_file:
            self.full_time_format = json_file["full_time_format"]

    def to_json(self, path: Path = default_path):
        json_file = dict()
        json_file["video_path"] = str(self.video_path)
        json_file["video_offset"] = self.video_offset
        json_file["split_sequence"] = self.split_sequence
        json_file["reset_sequence"] = self.reset_sequence
        json_file["pause_sequence"] = self.pause_sequence
        json_file["full_time_format"] = self.full_time_format

        with path.open("w") as f:
            json.dump(json_file, f, indent=2)

    def open(self, path: Path):
        self.from_json(path)

    def save(self, path: Path):
        self.to_json(path)
    
    def get_time(self, start_ms: int):
        assert start_ms >= 0
        temp_sec, ms = divmod(start_ms, 1000)
        temp_min, sec = divmod(temp_sec, 60)
        hour, min = divmod(temp_min, 60)

        ms_str = f"{ms}"[:2]
        if len(ms_str) < 2:
            ms_str = f"{ms:02}"

        if self.full_time_format:
            text = f"{hour:02}:{min:02}:{sec:02}"
        else:
            if hour > 0:
                text = f"{hour:02}:{min:02}:{sec:02}"
            elif min > 0:
                text = f"{min:02}:{sec:02}"
            else:
                text = f"{sec}"

        return f"{text}"


g_settings = VideoPlayerSettings()


class KeyThread(QThread):
    split_pressed = pyqtSignal()
    reset_pressed = pyqtSignal()
    pause_pressed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.do_run = True
        self.listener: keyboard.GlobalHotKeys | None = None

    def get_gh_map(self):
        gh_map = {
            g_settings.split_sequence: self.split_pressed.emit,
            g_settings.reset_sequence: self.reset_pressed.emit,
            g_settings.pause_sequence: self.pause_pressed.emit,
        }

        return gh_map
    
    def create_listener(self):
        if self.listener is None:
            self.listener = keyboard.GlobalHotKeys(self.get_gh_map())
            self.listener.start()

    def destroy_listener(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener = None

    def restart_listener(self):
        self.destroy_listener()
        self.create_listener()

    def run(self):
        while self.do_run:
            if self.listener is None:
                self.create_listener()

    def stop(self):
        self.do_run = False

        if self.listener is not None:
            self.listener.stop()

        self.wait()
        self.quit()


class VideoPlayerControls(QWidget):
    def __init__(self, player: QMediaPlayer):
        super().__init__()

        self.media_player = player
        self.is_started = False
        self.is_paused = False

        self.video_path = QLineEdit(str(g_settings.video_path))
        self.video_offset = QSpinBox()
        self.open_button = QPushButton("Open Video")
        self.open_settings_button = QPushButton("Open Settings")
        self.save_settings_button = QPushButton("Save Settings")
        self.start_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.lbl_time = QLabel(f"{g_settings.get_time(0)} / {g_settings.get_time(self.media_player.duration())}")
        self.key_thread = KeyThread()

        # setup the ui
        layout_player_row1 = QHBoxLayout()
        layout_player_row1.addWidget(self.start_button)
        layout_player_row1.addWidget(self.pause_button)
        layout_player_row1.addWidget(self.stop_button)
        layout_player_row1.addWidget(self.open_settings_button)
        layout_player_row1.addWidget(self.save_settings_button)

        layout_player_row2 = QHBoxLayout()
        layout_player_row2.addWidget(self.open_button)
        layout_player_row2.addWidget(self.video_path)
        layout_player_row2.addWidget(self.video_offset)

        layout_player_row3 = QHBoxLayout()
        layout_player_row3.addWidget(self.slider)
        layout_player_row3.addWidget(self.lbl_time)

        self.layout_player = QVBoxLayout()
        self.layout_player.setContentsMargins(10, 0, 10, 5)
        self.layout_player.addLayout(layout_player_row1)
        self.layout_player.addLayout(layout_player_row2)
        self.layout_player.addLayout(layout_player_row3)

        self.setWindowTitle("Video Player Controls")
        self.video_offset.setMaximum(9999999)
        self.video_offset.setSuffix(" ms")
        self.video_offset.setValue(g_settings.video_offset)
        self.media_player.setPosition(g_settings.video_offset)
        self.key_thread.start()

        # connections
        self.video_path.textChanged.connect(self.update_video)
        self.video_offset.valueChanged.connect(self.set_video_offset)
        self.open_button.clicked.connect(self.open_video)
        self.open_settings_button.clicked.connect(self.open_settings)
        self.save_settings_button.clicked.connect(self.save_settings)
        self.start_button.clicked.connect(self.start_video)
        self.key_thread.split_pressed.connect(self.start_video)
        self.pause_button.clicked.connect(self.pause_video)
        self.key_thread.pause_pressed.connect(self.pause_video)
        self.stop_button.clicked.connect(self.stop_video)
        self.key_thread.reset_pressed.connect(self.stop_video)
        self.slider.sliderMoved.connect(self.set_position)

    def closeEvent(self, e):
        self.key_thread.stop()
        super().closeEvent(e)

    def apply_settings(self):
        self.video_offset.setValue(g_settings.video_offset)
        self.video_path.setText(str(g_settings.video_path))
        self.key_thread.restart_listener()

    def open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(None, "Open PB Video", str(Path.home()), "Videos (*.mp4 *.mkv);;All Files (*)")

        if len(file_path) > 0:
            g_settings.video_path = Path(file_path).resolve()
            self.video_path.setText(str(g_settings.video_path))
            self.update_video()

    def open_settings(self):
        file_path, _ = QFileDialog.getOpenFileName(None, "Open Settings", str(Path.cwd()), "JSON files (*.json)")

        if len(file_path) > 0:
            if not file_path.lower().endswith(".json"):
                file_path += ".json"

            g_settings.open(Path(file_path).resolve())
            self.apply_settings()

    def save_settings(self):
        file_path, _ = QFileDialog.getSaveFileName(None, "Save Settings", str(g_settings.default_path), "JSON files (*.json)")

        if len(file_path) > 0:
            if not file_path.lower().endswith(".json"):
                file_path += ".json"

            g_settings.save(Path(file_path).resolve())

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

    def set_video_offset(self):
        g_settings.video_offset = self.video_offset.value()


class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.duration = None

        # player
        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()

        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

        self.controls = VideoPlayerControls(self.media_player)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget, stretch=1)
        layout.addLayout(self.controls.layout_player)

        wid = QWidget(self)
        self.setCentralWidget(wid)
        wid.setLayout(layout)

        self.setWindowTitle("Video Player")
        self.setFixedSize(640, 480 + self.controls.layout_player.sizeHint().height() + 6)

        self.media_player.setSource(QUrl.fromLocalFile(str(g_settings.video_path)))
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.pause() # trick to show the first frame
        self.media_player.setPosition(self.controls.video_offset.value())

    def closeEvent(self, e):
        self.controls.close()
        super(QMainWindow, self).closeEvent(e)

    def position_changed(self, position):
        if self.duration is None:
            self.duration = g_settings.get_time(self.media_player.duration())

        self.controls.slider.setValue(position)
        self.controls.lbl_time.setText(f"{g_settings.get_time(position)} / {self.duration}")

    def duration_changed(self, duration):
        self.controls.slider.setRange(0, duration)
        self.controls.video_offset.setMaximum(duration)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    video_player = VideoPlayer()
    video_player.show()
    sys.exit(app.exec())
