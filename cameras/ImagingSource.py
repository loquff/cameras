try:
    # Import PyhtonNet
    import sys
    import os
    import clr
    # Load IC Imaging Control .NET
    ic35path = os.getenv('IC35PATH')
    if ic35path is None:
        raise OSError(
            """The 'IC35PATH' enviroment variable seems not to be set. \n
            On Windows, it should point to the full path of the folder Documents/IC Imaging Control 3.5. \n
            You can set this variable manually, but remember to restart your computer.""")
    else:
        sys.path.append(ic35path + "/redist/dotnet/x64")
    clr.AddReference('TIS.Imaging.ICImagingControl35')
    clr.AddReference('System')

    # Import the IC Imaging Control namespace.
    import TIS.Imaging
    from System import TimeSpan
except:
    raise Exception(("""
        There appears to be some sort of problem with the installation of the ImagingSource software. \n
        Check https://github.com/TheImagingSource/IC-Imaging-Control-Samples/tree/master/Python/Python%20NET for more information.
        """))

from cameras.AbstractCamera import Camera
import ctypes as C
import numpy as np


class ImagingSourceCamera(Camera):
    def __init__(self):
        super().__init__()
        self.imaging_control = TIS.Imaging.ICImagingControl()

        # Create the sink for snapping images on demand.
        snapsink = TIS.Imaging.FrameSnapSink(TIS.Imaging.MediaSubtypes.Y800)
        self.imaging_control.Sink = snapsink

        self.imaging_control.LiveDisplay = False

        # Try to open the last used video capture device.
        try:
            self.imaging_control.LoadDeviceStateFromFile("device.xml", True)
            if self.imaging_control.DeviceValid is True:
                self.imaging_control.LiveStart()

        except Exception as ex:
            self.imaging_control.ShowDeviceSettingsDialog()
            if self.imaging_control.DeviceValid is True:
                self.imaging_control.SaveDeviceStateToFile("device.xml")
                self.imaging_control.LiveStart()
            pass

    def capture(self, roi=None):
        image = self.imaging_control.Sink.SnapSingle(TimeSpan.FromSeconds(5))
        imgcontent = C.cast(image.GetIntPtr().ToInt64(), C.POINTER(
            C.c_ubyte * image.FrameType.BufferSize))
        result = np.ndarray(buffer=imgcontent.contents,
                            dtype=np.uint8,
                            shape=(image.FrameType.Height,
                                   image.FrameType.Width))

        if roi is None:
            return result
        else:
            return result[slice(roi[0], roi[1]), slice(roi[2], roi[3])]

    def close(self):
        self.imaging_control.LiveStop()
        self.imaging_control.Dispose()
