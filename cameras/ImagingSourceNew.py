try:
    import imagingcontrol4 as ic4
except ModuleNotFoundError:
    print("Could not find library imagingcontrol4. The user should install it. It is avaliable through pip. The documentation can be found in https://www.theimagingsource.com/en-us/documentation/ic4python/programmers-guide.html")

from cameras.AbstractCamera import Camera

class ImagingSourceCamera(Camera):
    def __init__(self, device_id:int=0):
        ic4.Library.init()
        self.grabber = ic4.Grabber()
        device_info = ic4.DeviceEnum.devices()[device_id]
        self.grabber.device_open(device_info)
        self.sink = ic4.SnapSink()
        self.grabber.stream_setup(self.sink, setup_option=ic4.StreamSetupOption.ACQUISITION_START)

    def capture(self, roi=None, timeout=1000):
        try:
            image = self.sink.snap_single(timeout).numpy_wrap()

        except ic4.IC4Exception as ex:
            print(ex.message)

        if roi is None:
            return image
        else:
            return image[roi[0]:roi[1], roi[2]:roi[3]]

    def set_exposure(self, exposure):
        self.grabber.device_property_map.set_value(ic4.PropId.EXPOSURE_TIME, exposure)

    def set_gain(self, gain):
        self.grabber.device_property_map.set_value(ic4.PropId.GAIN, gain)

    def close(self):
        self.grabber.stream_stop()