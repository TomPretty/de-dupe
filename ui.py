import glob
import io
import os
import sys
import time

import PyQt5.QtCore
from PIL import Image, ImageQt
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from find_dupes import ImageInfo, find_duplicates, get_image_info


class SelectDirectoryWindow(QWidget):
    def __init__(self, on_directory_selected) -> None:
        super().__init__()
        self.on_directory_selected = on_directory_selected

        layout = QHBoxLayout()

        btn_select_directory = QPushButton("Select directory")
        btn_select_directory.clicked.connect(self.on_select_directory_clicked)

        layout.addStretch(1)
        layout.addWidget(btn_select_directory)
        layout.addStretch(1)

        self.setLayout(layout)

    def on_select_directory_clicked(self):
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.DirectoryOnly)

        if dialog.exec_() == QDialog.Accepted:
            path = dialog.selectedFiles()[0]  # returns a list
            self.on_directory_selected(path)
        else:
            # error
            pass


class StartDetectionWindow(QWidget):
    def __init__(self, on_find_duplicates_clicked) -> None:
        super().__init__()
        self.on_find_duplicates_clicked = on_find_duplicates_clicked

    def set_paths(self, paths):
        hbox = QHBoxLayout()
        vbox = QVBoxLayout()

        label = QLabel(f"{len(paths)} images found")
        label.setAlignment(PyQt5.QtCore.Qt.AlignCenter)

        button = QPushButton("Find duplicates")
        button.clicked.connect(self.on_find_duplicates_clicked)

        vbox.addStretch(1)
        vbox.addWidget(label)
        vbox.addWidget(button)
        vbox.addStretch(1)

        hbox.addStretch(1)
        hbox.addLayout(vbox)
        hbox.addStretch(1)

        self.setLayout(hbox)


class DetectionThread(QThread):
    imageChanged = pyqtSignal(ImageInfo)
    finished = pyqtSignal()

    def __init__(self, paths) -> None:
        super().__init__()
        self.paths = paths

    def run(self):
        for path in self.paths:
            image_info = get_image_info(path)
            self.imageChanged.emit(image_info)
        self.finished.emit()


class DetectionWindow(QWidget):
    def __init__(self, on_image_infos_calculated):
        super().__init__()
        self.on_image_infos_calcuated = on_image_infos_calculated

    def set_paths(self, paths):
        hbox = QHBoxLayout()
        hbox.setAlignment(PyQt5.QtCore.Qt.AlignCenter)

        self.label = QLabel("Calculating similarities...")
        self.progress = QProgressBar()

        hbox.addStretch()
        hbox.addWidget(self.label)
        hbox.addWidget(self.progress)
        hbox.addStretch()

        self.setLayout(hbox)

        self.paths = paths
        self.image_infos = []
        self.detection_thread = DetectionThread(paths)
        self.detection_thread.imageChanged.connect(self.on_image_changed)
        self.detection_thread.finished.connect(self.on_finished)
        self.detection_thread.start()

    def on_image_changed(self, value):
        self.image_infos.append(value)
        self.progress.setValue(len(self.image_infos) / len(self.paths) * 100)

    def on_finished(self):
        self.on_image_infos_calcuated(self.image_infos)


class FindDuplicatesThread(QThread):
    imageProcessed = pyqtSignal(int)
    duplicatesFound = pyqtSignal(list)
    finished = pyqtSignal()

    def __init__(self, image_infos) -> None:
        super().__init__()
        self.image_infos = image_infos.copy()

    def run(self):
        while self.image_infos:
            image_info = self.image_infos.pop(0)

            duplicate_indices = find_duplicates(image_info, self.image_infos)
            if duplicate_indices:
                duplicates = [self.image_infos[i] for i in duplicate_indices]
                self.image_infos = [
                    image_info
                    for image_info in self.image_infos
                    if image_info not in duplicates
                ]
                self.duplicatesFound.emit([image_info] + duplicates)

            self.imageProcessed.emit(len(self.image_infos))
        self.finished.emit()


class FindDuplicatesWindow(QWidget):
    def __init__(self, on_duplicates_found) -> None:
        super().__init__()
        self.on_all_duplicates_found = on_duplicates_found

    def set_image_infos(self, image_infos):
        hbox = QHBoxLayout()
        hbox.setAlignment(PyQt5.QtCore.Qt.AlignCenter)

        self.label = QLabel("Finding duplicates...")
        self.progress = QProgressBar()

        hbox.addStretch()
        hbox.addWidget(self.label)
        hbox.addWidget(self.progress)
        hbox.addStretch()

        self.setLayout(hbox)

        self.image_infos = image_infos
        self.duplicates = []
        self.find_duplicates_thread = FindDuplicatesThread(image_infos)
        self.find_duplicates_thread.imageProcessed.connect(self.on_image_processed)
        self.find_duplicates_thread.duplicatesFound.connect(self.on_duplicates_found)
        self.find_duplicates_thread.finished.connect(self.on_finished)
        self.find_duplicates_thread.start()

    def on_image_processed(self, value):
        num_image_infos = len(self.image_infos)
        self.progress.setValue((num_image_infos - value) / num_image_infos * 100)

    def on_duplicates_found(self, duplicates):
        self.duplicates.append(duplicates)

    def on_finished(self):
        self.on_all_duplicates_found(self.duplicates)


class ResolveDuplicatesWindow(QWidget):
    def __init__(self, on_duplicates_resolved) -> None:
        super().__init__()
        self.on_duplicates_resolved = on_duplicates_resolved
        self.current_duplicates_index = 0

    def set_duplicates(self, duplicates, directory):
        self.duplicates = duplicates
        self.directory = directory

        hbox_outer = QHBoxLayout()

        vbox = QVBoxLayout()
        vbox.setAlignment(PyQt5.QtCore.Qt.AlignCenter)

        hbox = QHBoxLayout()
        hbox.setAlignment(PyQt5.QtCore.Qt.AlignCenter)

        self.label = QLabel("Resolving duplicates...")
        self.progress = QProgressBar()

        hbox.addWidget(self.label)
        hbox.addWidget(self.progress)

        self.scroll = QScrollArea()
        grid = DuplicatesGrid(
            duplicates[self.current_duplicates_index], self.on_discards_selected
        )
        self.scroll.setWidget(grid)
        self.scroll.setAlignment(PyQt5.QtCore.Qt.AlignCenter)
        self.scroll.setWidgetResizable(False)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedWidth(grid.width() + 10)

        vbox.addLayout(hbox)
        vbox.addWidget(self.scroll)

        hbox_outer.addStretch()
        hbox_outer.addLayout(vbox)
        hbox_outer.addStretch()

        self.setLayout(hbox_outer)

    def on_discards_selected(self, discards):
        self.move_to_discards_folder(discards)
        self.current_duplicates_index += 1
        self.progress.setValue(
            (self.current_duplicates_index) / len(self.duplicates) * 100
        )
        if self.current_duplicates_index >= len(self.duplicates):
            self.on_duplicates_resolved()
        else:
            grid = DuplicatesGrid(
                self.duplicates[self.current_duplicates_index],
                self.on_discards_selected,
            )
            self.scroll.setWidget(grid)

    def move_to_discards_folder(self, discards):
        self.ensure_discards_folder_exits()
        self.move_files(discards)

    def ensure_discards_folder_exits(self):
        path = os.path.join(self.directory, "duplicates")

        if not os.path.exists(path):
            os.makedirs(path)

    def move_files(self, discards):
        path = os.path.join(self.directory, "duplicates")
        for image_info in discards:
            in_name = os.path.split(image_info.path)[-1]
            out_path = os.path.join(path, in_name)

            os.rename(image_info.path, out_path)


class DuplicatesGrid(QWidget):
    def __init__(self, duplicates, on_discards_selected) -> None:
        super().__init__()
        self.on_discards_selected = on_discards_selected

        vbox = QVBoxLayout()

        button = QPushButton("Next")
        button.clicked.connect(self.on_next_clicked)

        self.duplicates = sorted(duplicates, key=lambda i: i.file_size_in_mb)
        self.keeps = [self.duplicates[0]]
        self.discards = self.duplicates[1:]

        self.labels = []
        self.buttons = []

        grid = QGridLayout()
        for i, image_info in enumerate(duplicates):
            row = i // 2
            col = i % 2
            keep = image_info in self.keeps
            grid.addLayout(self.get_image_layout(image_info, keep), row, col)

        vbox.addWidget(button)
        vbox.addLayout(grid)

        self.setLayout(vbox)

    def get_image_layout(self, image_info, keep):
        layout = QVBoxLayout()

        label = QLabel()
        pixmap = get_pixmap(image_info.path, keep)
        label.setPixmap(pixmap)
        label.setMaximumWidth(300)
        self.labels.append(label)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft)
        form.addRow("name:", self.get_form_label(os.path.split(image_info.path)[-1]))
        form.addRow(
            "size:", self.get_form_label(f"{image_info.file_size_in_mb:.2f} mb")
        )
        form.addRow(
            "dims:", self.get_form_label(f"{image_info.dims[0]}x{image_info.dims[1]}")
        )

        button = QPushButton("Discard" if keep else "Keep")
        button.clicked.connect(self.get_on_button_clicked(image_info))
        button.setMaximumWidth(300)
        self.buttons.append(button)

        layout.addWidget(label)
        layout.addLayout(form)
        layout.addWidget(button)

        return layout

    def get_form_label(self, value):
        label = QLabel(f"{value}")
        label.setFont(QFont("Courier"))

        return label

    def get_filename_label(self, path):
        label = QLabel(os.path.split(path)[-1])
        label.setFont(QFont("Courier"))

        return label

    def get_on_button_clicked(self, image_info):
        def on_button_clicked():
            if image_info in self.keeps:
                self.keeps.remove(image_info)
                self.discards.append(image_info)
                pixmap = get_pixmap(image_info.path, False)
                text = "Keep"
            else:
                self.keeps.append(image_info)
                self.discards.remove(image_info)
                pixmap = get_pixmap(image_info.path, True)
                text = "Discard"
            index = self.duplicates.index(image_info)
            self.labels[index].setPixmap(pixmap)
            self.buttons[index].setText(text)

        return on_button_clicked

    def on_next_clicked(self):
        self.on_discards_selected(self.discards)


def get_pixmap(path, keep):
    im = Image.open(path)
    filter_colour = (0, 255, 0) if keep else (255, 0, 0)
    im_filter = Image.new("RGB", (im.width, im.height), filter_colour)

    im_filtered = Image.blend(im, im_filter, 0.2)

    bytes_img = io.BytesIO()
    im_filtered.save(bytes_img, format="JPEG")

    qimg = QImage()
    qimg.loadFromData(bytes_img.getvalue())

    pixmap = QPixmap.fromImage(qimg)
    pixmap = pixmap.scaled(300, 300, PyQt5.QtCore.Qt.KeepAspectRatio)

    return pixmap


class SummaryWindow(QWidget):
    def set_summary(self, num_images, num_images_with_duplicates, num_duplicates):
        hbox = QHBoxLayout()
        vbox = QVBoxLayout()

        label = QLabel("All done! Here's a summary")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignLeft)
        form.addRow("# images found:", self.get_form_label(num_images))
        form.addRow(
            "# images with duplicates:", self.get_form_label(num_images_with_duplicates)
        )
        form.addRow("# duplicates removed:", self.get_form_label(num_duplicates))

        vbox.addStretch()
        vbox.addWidget(label)
        vbox.addLayout(form)
        vbox.addStretch()

        hbox.addStretch()
        hbox.addLayout(vbox)
        hbox.addStretch()

        self.setLayout(hbox)

    def get_form_label(self, value):
        label = QLabel(f"{value}")
        label.setFont(QFont("Courier"))

        return label


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.directory = None
        self.paths = None

        self.setWindowTitle("DE-DUPE")
        self.resize(800, 480)

        self.layout = QStackedLayout()

        self.select_directory = SelectDirectoryWindow(self.on_directory_selected)
        self.start_dectection = StartDetectionWindow(self.on_find_duplicates_clicked)
        self.detection = DetectionWindow(self.on_image_infos_calculated)
        self.find_duplicates = FindDuplicatesWindow(self.on_duplicates_found)
        self.resolve_duplicates = ResolveDuplicatesWindow(self.on_duplicates_resolved)
        self.summary = SummaryWindow()

        self.layout.addWidget(self.select_directory)
        self.layout.addWidget(self.start_dectection)
        self.layout.addWidget(self.detection)
        self.layout.addWidget(self.find_duplicates)
        self.layout.addWidget(self.resolve_duplicates)
        self.layout.addWidget(self.summary)

        self.setLayout(self.layout)

    def on_directory_selected(self, directory):
        self.directory = directory
        self.paths = glob.glob(os.path.join(directory, "*.jpg"))

        self.start_dectection.set_paths(self.paths)
        self.layout.setCurrentIndex(1)

    def on_find_duplicates_clicked(self):
        self.detection.set_paths(self.paths)
        self.layout.setCurrentIndex(2)

    def on_image_infos_calculated(self, image_infos):
        self.image_infos = image_infos
        self.find_duplicates.set_image_infos(image_infos)
        self.layout.setCurrentIndex(3)

    def on_duplicates_found(self, duplicates):
        self.duplicates = duplicates
        self.resolve_duplicates.set_duplicates(duplicates, self.directory)
        self.layout.setCurrentIndex(4)

    def on_duplicates_resolved(self):
        self.duplicate_paths = glob.glob(
            os.path.join(self.directory, "duplicates", "*.jpg")
        )
        self.summary.set_summary(
            len(self.paths), len(self.duplicates), len(self.duplicate_paths)
        )
        self.layout.setCurrentIndex(5)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())
