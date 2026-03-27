import numpy as np
from typing import Optional, cast

from ids_peak import ids_peak
from ids_peak_icv.pipeline import DefaultPipeline
from ids_peak_common import PixelFormat

from abc import ABC
from time import sleep
from cameras.AbstractCamera import Camera


class IDSCamera(Camera):
    def __init__(self, exposure: Optional[float] = None, gain: Optional[float] = None):
        self.device = None
        self.remote_nodemap = None
        self.data_stream = None

        self._exposure = exposure
        self._gain = gain

        self._image_pipeline = DefaultPipeline()
        self._image_pipeline.output_pixel_format = PixelFormat.BGRA_8

        self._initialized = False

        self._init_camera()

    # -------------------------
    # Initialization
    # -------------------------
    def _init_camera(self):
        ids_peak.Library.Initialize()

        # Find and open device
        ids_peak.DeviceManager.Instance().Update()

        for dev in ids_peak.DeviceManager.Instance().Devices():
            if dev.IsOpenable(ids_peak.DeviceAccessType_Control):
                self.device = dev.OpenDevice(ids_peak.DeviceAccessType_Control)
                break

        if self.device is None:
            raise RuntimeError("No IDS camera found")

        self.remote_nodemap = self.device.RemoteDevice().NodeMaps()[0]
        self.data_stream = self.device.DataStreams()[0].OpenDataStream()

        # Load defaults
        self._load_defaults()

        self._enable_trigger_mode()

        # Apply user config
        if self._exposure is not None:
            self.set_exposure(self._exposure)

        if self._gain is not None:
            self.set_gain(self._gain)

        # Buffers + acquisition
        self._alloc_buffers()
        self._start_acquisition()

        self._initialized = True

    def _enable_trigger_mode(self):
        # Ensure TL params are unlocked
        tl_lock = cast(ids_peak.IntegerNode,
                    self.remote_nodemap.FindNode("TLParamsLocked"))
        tl_lock.SetValue(0)

        # 1. Disable trigger first (important!)
        trigger_mode = cast(ids_peak.EnumerationNode,
                            self.remote_nodemap.FindNode("TriggerMode"))
        trigger_mode.SetCurrentEntry("Off")

        # 2. Select trigger type
        trigger_selector = cast(ids_peak.EnumerationNode,
                                self.remote_nodemap.FindNode("TriggerSelector"))
        trigger_selector.SetCurrentEntry("FrameStart")

        # 3. Set source
        trigger_source = cast(ids_peak.EnumerationNode,
                            self.remote_nodemap.FindNode("TriggerSource"))
        trigger_source.SetCurrentEntry("Software")

        # 4. Enable trigger
        trigger_mode.SetCurrentEntry("On")

    def _trigger(self):
        cmd = cast(ids_peak.CommandNode,
                self.remote_nodemap.FindNode("TriggerSoftware"))
        cmd.Execute()

    def _load_defaults(self):
        node = cast(ids_peak.EnumerationNode,
                    self.remote_nodemap.FindNode("UserSetSelector"))
        node.SetCurrentEntry("Default")

        cmd = cast(ids_peak.CommandNode,
                   self.remote_nodemap.FindNode("UserSetLoad"))
        cmd.Execute()
        cmd.WaitUntilDone()

    # -------------------------
    # Configuration
    # -------------------------
    def set_exposure(self, exposure_us: float):
        node = cast(ids_peak.FloatNode,
                    self.remote_nodemap.FindNode("ExposureTime"))

        if not node.IsWriteable():
            raise RuntimeError("ExposureTime not writable (auto exposure enabled?)")

        node.SetValue(exposure_us)
        self._exposure = exposure_us

    def set_gain(self, gain: float):
        gain_selector = cast(ids_peak.EnumerationNode,
                             self.remote_nodemap.FindNode("GainSelector"))

        available = [x.StringValue() for x in gain_selector.AvailableEntries()]
        for preferred in ["AnalogAll", "DigitalAll", "All"]:
            if preferred in available:
                gain_selector.SetCurrentEntry(preferred)
                break
        else:
            raise RuntimeError("No valid gain selector")

        gain_node = cast(ids_peak.FloatNode,
                         self.remote_nodemap.FindNode("Gain"))

        if not gain_node.IsWriteable():
            raise RuntimeError("Gain not writable (auto gain enabled?)")

        gain_node.SetValue(gain)
        self._gain = gain

    # -------------------------
    # Buffers / Acquisition
    # -------------------------
    def _alloc_buffers(self):
        payload_size = cast(ids_peak.IntegerNode,
                            self.remote_nodemap.FindNode("PayloadSize")).Value()

        buffer_count = self.data_stream.NumBuffersAnnouncedMinRequired()

        for _ in range(buffer_count):
            buf = self.data_stream.AllocAndAnnounceBuffer(payload_size)
            self.data_stream.QueueBuffer(buf)

    def _start_acquisition(self):
        cast(ids_peak.IntegerNode,
             self.remote_nodemap.FindNode("TLParamsLocked")).SetValue(1)

        self.data_stream.StartAcquisition()

        cmd = cast(ids_peak.CommandNode,
                   self.remote_nodemap.FindNode("AcquisitionStart"))
        cmd.Execute()
        cmd.WaitUntilDone()

    def _stop_acquisition(self):
        cast(ids_peak.CommandNode,
             self.remote_nodemap.FindNode("AcquisitionStop")).Execute()

        if self.data_stream.IsGrabbing():
            self.data_stream.StopAcquisition(ids_peak.AcquisitionStopMode_Kill)

        self.data_stream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)

        cast(ids_peak.IntegerNode,
             self.remote_nodemap.FindNode("TLParamsLocked")).SetValue(0)

    # -------------------------
    # Capture (MAIN API)
    # -------------------------
    def capture(self, roi=None) -> np.ndarray:
        if not self._initialized:
            raise RuntimeError("Camera not initialized")

        # 🔥 Trigger acquisition
        self._trigger()

        # Wait for the triggered frame
        try:
            buffer = self.data_stream.WaitForFinishedBuffer(ids_peak.Timeout(10000))
        except Exception as e:
            raise RuntimeError(f"Trigger capture failed: {e}")

        image_view = buffer.ToImageView()
        image = self._image_pipeline.process(image_view)

        np_img = image.to_numpy_array()

        # Convert BGRA → grayscale
        if np_img.shape[-1] == 4:
            np_img = np_img[:, :, :3]
            np_img = np.mean(np_img, axis=2).astype(np.uint8)

        # Requeue buffer immediately
        self.data_stream.QueueBuffer(buffer)

        if roi:
            return np_img[roi[0]:roi[1], roi[2]:roi[3]]
        return np_img

    # -------------------------
    # Cleanup
    # -------------------------
    def close(self):
        if self.data_stream is not None:
            self._stop_acquisition()

            # 🔥 Restore continuous mode
            trigger_mode = cast(ids_peak.EnumerationNode,
                                self.remote_nodemap.FindNode("TriggerMode"))
            trigger_mode.SetCurrentEntry("Off")

            self.data_stream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)

            for buf in self.data_stream.AnnouncedBuffers():
                self.data_stream.RevokeBuffer(buf)

        ids_peak.Library.Close()