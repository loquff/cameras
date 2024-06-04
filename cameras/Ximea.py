try:
    from ximea import xiapi
except ModuleNotFoundError:
    """There seems to be a problem with the instalation of the Ximea software. \n
                      Check https://www.ximea.com/support/wiki/apis/APIs for details."""

from cameras.AbstractCamera import Camera

class XimeaCamera(Camera):
    def __init__(self):
        self.camera = xiapi.Camera()
        self.camera.open_device()
        self.camera.set_exposure(1000)
        self.image = xiapi.Image()
        self.camera.start_acquisition()

    def capture(self, roi=None):
        self.camera.get_image(self.image)
        if roi is None:
            return self.image.get_image_data_numpy()
        else:
            return self.image.get_image_data_numpy()[roi[0]:roi[1], roi[2]:roi[3]]

    def set_exposure(self, exposure):
        self.camera.set_exposure(exposure)

    def close(self):
        self.camera.stop_acquisition()
        self.camera.close_device()
