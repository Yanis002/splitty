#!/usr/bin/env python3

import json
import sys
import ffmpeg

from pathlib import Path
from pynput import keyboard

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QSlider,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QFileDialog,
    QKeySequenceEdit,
    QMenu,
    QMenuBar,
)

from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import QUrl, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction


SPECIAL_KEYS = ["ctrl", "alt", "shift", "cmd", "stealth", "pause"] + [f"f{i}" for i in range(1, 21)]


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


class VideoPlayerControls(QMainWindow):
    def __init__(self, parent: "VideoPlayer"):
        super().__init__()

        self.player = parent
        self.media_player = parent.media_player
        self.is_started = False
        self.is_paused = False
        self.is_separated = False

        self.video_path = QLineEdit(str(g_settings.video_path))
        self.video_offset = QSpinBox()
        self.open_button = QPushButton("Open Video")
        self.start_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.split_button = QPushButton("Separate Controls")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.lbl_time = QLabel(f"{g_settings.get_time(0)} / {g_settings.get_time(self.media_player.duration())}")
        self.action_hotkeys = QPushButton("Set Hotkeys")

        self.key_thread = KeyThread()

        self.hotkey_mgr = QWidget()
        self.hotkey_split = QKeySequenceEdit()
        self.hotkey_reset = QKeySequenceEdit()
        self.hotkey_pause = QKeySequenceEdit()
        self.hotkey_split.setClearButtonEnabled(True)
        self.hotkey_reset.setClearButtonEnabled(True)
        self.hotkey_pause.setClearButtonEnabled(True)
        self.hotkey_ok = QPushButton("Ok")
        self.hotkey_ok.pressed.connect(self.set_hotkeys)
        layout = QVBoxLayout()
        layout.addWidget(self.hotkey_split)
        layout.addWidget(self.hotkey_reset)
        layout.addWidget(self.hotkey_pause)
        layout.addWidget(self.hotkey_ok)
        self.hotkey_mgr.setLayout(layout)
        self.hotkey_mgr.setWindowTitle("Hotkeys")
        self.hotkey_mgr.setFixedSize(200, 150)

        # setup the ui
        self.menu = QMenuBar()
        self.menu.setObjectName("menu")
        self.menu.setVisible(False)

        self.menu_file = QMenu()
        self.menu_file.setObjectName("menu_file")
        self.menu_file.setTitle("File")

        self.action_open_settings = QAction()
        self.action_open_settings.setObjectName("action_open_settings")
        self.action_open_settings.setText("Open Settings")
        self.action_open_settings.triggered.connect(self.open_settings)

        self.action_save_settings = QAction()
        self.action_save_settings.setObjectName("action_save_settings")
        self.action_save_settings.setText("Save Settings")
        self.action_save_settings.triggered.connect(self.save_settings)

        self.menu_file.addAction(self.action_open_settings)
        self.menu_file.addAction(self.action_save_settings)

        self.menu.addAction(self.menu_file.menuAction())
        self.setMenuBar(self.menu)

        self.setWindowTitle("Video Player Controls")
        self.video_offset.setMaximum(9999999)
        self.video_offset.setSuffix(" ms")
        self.video_offset.setValue(g_settings.video_offset)
        self.media_player.setPosition(g_settings.video_offset)
        self.key_thread.start()

        # connections
        self.video_path.textChanged.connect(self.update_video)
        self.video_offset.valueChanged.connect(self.set_video_offset)
        self.open_button.pressed.connect(self.open_video)
        self.start_button.pressed.connect(self.start_video)
        self.key_thread.split_pressed.connect(self.start_video)
        self.pause_button.pressed.connect(self.pause_video)
        self.key_thread.pause_pressed.connect(self.pause_video)
        self.stop_button.pressed.connect(self.stop_video)
        self.key_thread.reset_pressed.connect(self.stop_video)
        self.slider.sliderMoved.connect(self.set_position)
        self.split_button.pressed.connect(self.separate_windows)
        self.action_hotkeys.pressed.connect(self.get_hotkeys)

    def closeEvent(self, e):
        self.key_thread.stop()
        super().closeEvent(e)

    def apply_settings(self):
        self.video_offset.setValue(g_settings.video_offset)
        self.video_path.setText(str(g_settings.video_path))
        self.key_thread.restart_listener()

    def get_layout(self):
        layour_row_buttons = QHBoxLayout()
        layour_row_buttons.addWidget(self.start_button)
        layour_row_buttons.addWidget(self.pause_button)
        layour_row_buttons.addWidget(self.stop_button)
        layour_row_buttons.addWidget(self.split_button)
        layour_row_buttons.addWidget(self.action_hotkeys)

        layout_video = QHBoxLayout()
        layout_video.addWidget(self.open_button)
        layout_video.addWidget(self.video_path)
        layout_video.addWidget(self.video_offset)

        layout_progression = QHBoxLayout()
        layout_progression.addWidget(self.slider)
        layout_progression.addWidget(self.lbl_time)

        layout_player = QVBoxLayout()
        layout_player.addLayout(layout_video)
        layout_player.addLayout(layout_progression)
        layout_player.addLayout(layour_row_buttons)
        layout_player.setContentsMargins(10, 5 if self.is_separated else 0, 10, 5)

        return layout_player

    def open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Open PB Video", str(Path.home()), "Videos (*.mp4 *.mkv);;All Files (*)"
        )

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
        file_path, _ = QFileDialog.getSaveFileName(
            None, "Save Settings", str(g_settings.default_path), "JSON files (*.json)"
        )

        if len(file_path) > 0:
            if not file_path.lower().endswith(".json"):
                file_path += ".json"

            g_settings.save(Path(file_path).resolve())

    def update_video(self):
        self.media_player.setSource(QUrl.fromLocalFile(self.video_path.text()))
        self.is_paused = False
        self.media_player.pause()  # trick to show the first frame
        self.player.update_window()

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
        self.media_player.pause()  # trick to show the first frame
        self.media_player.setPosition(self.video_offset.value())

    def set_position(self, position):
        self.media_player.setPosition(position)

    def set_video_offset(self):
        g_settings.video_offset = self.video_offset.value()

    def set_window_layout(self):
        if self.is_separated:
            self.menu.setVisible(True)

            central_widget = QWidget(self)
            central_widget.setLayout(self.get_layout())
            self.setCentralWidget(central_widget)
        else:
            self.menu.setVisible(False)
            self.setCentralWidget(None)

    def separate_windows(self):
        if not self.is_separated:
            self.is_separated = True
            self.show()
            self.move(self.player.pos().x(), self.player.pos().y() + self.player.height() + 30)
        else:
            self.is_separated = False
            self.close()

        self.split_button.setText(f"{'Merge' if self.is_separated else 'Separate'} Controls")
        self.player.set_window_layout()
        self.set_window_layout()

    def get_hotkeys(self):
        self.hotkey_split.setKeySequence(g_settings.split_sequence.replace("<", "").replace(">", ""))
        self.hotkey_reset.setKeySequence(g_settings.reset_sequence.replace("<", "").replace(">", ""))
        self.hotkey_pause.setKeySequence(g_settings.pause_sequence.replace("<", "").replace(">", ""))
        self.hotkey_mgr.show()

    def set_hotkeys(self):
        def get_sequence(sequence: str):
            split = sequence.split("+")
            out_seq = []

            for elem in split:
                if elem in SPECIAL_KEYS:
                    out_seq.append(f"<{elem}>")
                else:
                    out_seq.append(elem)

            return "+".join(out_seq)

        g_settings.split_sequence = get_sequence(self.hotkey_split.keySequence().toString().lower())
        g_settings.reset_sequence = get_sequence(self.hotkey_reset.keySequence().toString().lower())
        g_settings.pause_sequence = get_sequence(self.hotkey_pause.keySequence().toString().lower())
        self.hotkey_mgr.close()


class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        self.duration = None

        self.media_player = QMediaPlayer()
        self.video_widget = QVideoWidget()
        self.controls = VideoPlayerControls(self)

        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.setSource(QUrl.fromLocalFile(str(g_settings.video_path)))
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.pause()  # trick to show the first frame
        self.media_player.setPosition(self.controls.video_offset.value())

        self.control_layout = self.controls.get_layout()

        self.menu = QMenuBar()
        self.menu.addMenu(self.controls.menu_file)
        self.setMenuBar(self.menu)

        self.setWindowTitle("Video Player")
        self.set_window_layout()

    def closeEvent(self, e):
        self.controls.close()
        super(QMainWindow, self).closeEvent(e)

    def moveEvent(self, a0):
        super().moveEvent(a0)

        if self.controls.is_separated:
            self.controls.move(self.pos().x(), self.pos().y() + self.height() + 30)

    def get_layout(self):
        self.control_layout = self.controls.get_layout()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget, stretch=1)
        layout.addLayout(self.control_layout)
        return layout

    def set_window_layout(self):
        if self.controls.is_separated:
            self.menu.setVisible(False)
            self.centralWidget().deleteLater()
            self.setCentralWidget(self.video_widget)
        else:
            self.menu.setVisible(True)
            central_widget = QWidget(self)
            central_widget.setLayout(self.get_layout())
            self.setCentralWidget(central_widget)

        self.update_window()

    def update_window(self):
        # TODO: find something that works without ffmpeg to limit dependencies
        probe = ffmpeg.probe(str(g_settings.video_path))
        video_stream = next((stream for stream in probe["streams"] if stream["codec_type"] == "video"), None)
        assert video_stream is not None, "video stream not found"
        video_width = int(video_stream["width"])
        offset = 6

        if video_width == 640 or video_width % 640:
            # 4:3 video
            width = 640
            height = 480
        elif video_width == 854 or video_width % 854:
            # 16:9 video
            width = 854 - 1
            height = 480
        else:
            print("warning: video isn't 4:3 or 16:9, using video's width and height")
            width = round(video_width / 2)
            height = round(int(video_stream["height"]) / 2)
            offset = 0

        if self.controls.is_separated:
            final_height = height
            self.controls.setFixedSize(width, 110)
        else:
            final_height = self.menu.sizeHint().height() + height + self.control_layout.sizeHint().height() + offset

        self.setFixedSize(width, final_height)

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
