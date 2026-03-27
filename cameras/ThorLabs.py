from pylablib.devices import Thorlabs as TL
from cameras.AbstractCamera import Camera

class ThorLabsCamera(Camera):
    def __init__(self, device_id:int=0):
        cams_addr = TL.list_cameras_tlcam()
        self.camera  = TL.ThorlabsTLCamera(serial=cams_addr[device_id])

    def capture(self, roi=None, **kwargs):
        img = self.camera.snap(**kwargs)
        if roi is None:
            return img
        else:
            return img[roi[0]:roi[1], roi[2]:roi[3]]

    def close(self):
        self.camera.close()
