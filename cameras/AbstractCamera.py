from abc import ABC, abstractmethod
import numpy as np
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QVBoxLayout,
    QWidget,
    QStatusBar,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QImage, QPixmap, QMouseEvent
import sys


class Camera(ABC):
    @abstractmethod
    def capture(self) -> np.ndarray:
        pass

    @abstractmethod
    def close(self):
        pass

    def show_live_feed(self, window_title="Camera Feed", fps=30, roi=None):
        """
        Display a live feed from the camera in a Qt window.

        Args:
            window_title (str): Title of the window
            fps (int): Frames per second for the display
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        # Create main window
        window = QMainWindow()
        window.setWindowTitle(window_title)
        window.resize(800, 600)

        # Add status bar for coordinates
        status_bar = QStatusBar()
        window.setStatusBar(status_bar)
        status_bar.showMessage("Mouse coordinates: ---, ---")

        # Handle window close event properly
        def closeEvent(event):
            timer.stop()
            event.accept()
            app.quit()

        window.closeEvent = closeEvent

        # Create central widget and layout
        central_widget = QWidget()
        window.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create label to display the image
        class ImageLabel(QLabel):
            def __init__(self):
                super().__init__()
                self.setMouseTracking(True)
                self.original_image_size = None
                self.scaled_pixmap_size = None
                self.status_bar = None

            def set_status_bar(self, status_bar):
                self.status_bar = status_bar

            def set_image_info(self, original_size, scaled_size):
                self.original_image_size = original_size
                self.scaled_pixmap_size = scaled_size

            def mouseMoveEvent(self, event):
                if (
                    self.status_bar
                    and self.original_image_size
                    and self.scaled_pixmap_size
                    and self.pixmap()
                ):
                    # Get mouse position relative to the label
                    mouse_x = event.position().x()
                    mouse_y = event.position().y()

                    # Get the label size
                    label_width = self.width()
                    label_height = self.height()

                    # Get the scaled pixmap size
                    scaled_width = self.scaled_pixmap_size[0]
                    scaled_height = self.scaled_pixmap_size[1]

                    # Calculate the offset of the image within the label (centering)
                    x_offset = (label_width - scaled_width) / 2
                    y_offset = (label_height - scaled_height) / 2

                    # Check if mouse is within the image area
                    if (
                        x_offset <= mouse_x <= x_offset + scaled_width
                        and y_offset <= mouse_y <= y_offset + scaled_height
                    ):
                        # Convert to coordinates within the scaled image
                        image_x = mouse_x - x_offset
                        image_y = mouse_y - y_offset

                        # Convert to original image coordinates
                        scale_x = self.original_image_size[0] / scaled_width
                        scale_y = self.original_image_size[1] / scaled_height

                        orig_x = int(image_x * scale_x)
                        orig_y = int(image_y * scale_y)

                        # Clamp to image bounds
                        orig_x = max(0, min(orig_x, self.original_image_size[0] - 1))
                        orig_y = max(0, min(orig_y, self.original_image_size[1] - 1))

                        self.status_bar.showMessage(
                            f"Mouse coordinates: {orig_x}, {orig_y}"
                        )
                    else:
                        self.status_bar.showMessage("Mouse coordinates: ---, ---")

                super().mouseMoveEvent(event)

        image_label = ImageLabel()
        image_label.setStyleSheet("border: 1px solid black;")
        image_label.setMinimumSize(400, 300)  # Set minimum size
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the image
        image_label.set_status_bar(status_bar)
        layout.addWidget(image_label)

        # Timer for updating the feed
        timer = QTimer()

        def update_frame():
            try:
                # Capture frame from camera
                frame = self.capture()
                if roi is not None:
                    frame = frame[roi[0]:roi[1], roi[2]:roi[3]]

                # Convert numpy array to QImage
                if len(frame.shape) == 2:  # Grayscale
                    height, width = frame.shape
                    q_image = QImage(
                        frame.data,
                        width,
                        height,
                        width,
                        QImage.Format.Format_Grayscale8,
                    )
                else:  # Assume RGB
                    height, width, channels = frame.shape
                    bytes_per_line = channels * width
                    q_image = QImage(
                        frame.data,
                        width,
                        height,
                        bytes_per_line,
                        QImage.Format.Format_RGB888,
                    )

                # Convert to pixmap and display
                pixmap = QPixmap.fromImage(q_image)
                # Scale to fit the window size, not the current label size
                target_size = window.size()
                target_size.setWidth(target_size.width() - 50)  # Account for margins
                target_size.setHeight(target_size.height() - 100)  # Account for margins
                scaled_pixmap = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                # Update image label with size information
                image_label.set_image_info(
                    (width, height),  # Original image size
                    (scaled_pixmap.width(), scaled_pixmap.height()),  # Scaled size
                )
                image_label.setPixmap(scaled_pixmap)

            except Exception as e:
                print(f"Error updating frame: {e}")

        # Connect timer to update function
        timer.timeout.connect(update_frame)
        timer.start(int(1000 / fps))  # Convert fps to milliseconds

        # Show window
        window.show()

        # Store references to prevent garbage collection
        self._live_feed_window = window
        self._live_feed_timer = timer

        # Run the application event loop
        try:
            app.exec()
        except KeyboardInterrupt:
            timer.stop()
            window.close()
            app.quit()


class TestCamera(Camera):
    def __init__(self, resX=1920, resY=1080):
        self.resX = resX
        self.resY = resY

    def capture(self, roi=None):
        size = (
            (self.resY, self.resX)
            if roi is None
            else (roi[1] - roi[0], roi[3] - roi[2])
        )
        return np.random.randint(0, 255, size=size, dtype="uint8")

    def close(self):
        pass
