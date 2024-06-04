from abc import ABC, abstractmethod
import numpy as np

class Camera(ABC):
    @abstractmethod
    def capture(self):
        pass

    @abstractmethod
    def close(self):
        pass


class TestCamera(Camera):
    def __init__(self, resX = 1920, resY=1080):
        self.resX = resX
        self.resY = resY

    def capture(self, roi=None):
        size = (self.resY, self.resX) if roi is None else (
            roi[1]-roi[0], roi[3]-roi[2])
        return np.random.randint(0, 255, size=size, dtype='uint8')

    def close(self):
        pass
