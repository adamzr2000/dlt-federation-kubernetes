import traceback
import cv2
import numpy as np
from ultralytics import YOLO
from termcolor import colored
import os

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib


def on_message(bus: Gst.Bus, message: Gst.Message, loop: GLib.MainLoop):
    msg_type = message.type

    # handle different types of messages
    if msg_type == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()
    elif msg_type == Gst.MessageType.ERROR:
        error, debug_info = message.parse_error()
        print(f"Error: {error.message}, Debug Info: {debug_info}")
        loop.quit()
    elif msg_type == Gst.MessageType.WARNING:
        warning, debug_info = message.parse_warning()
        print(f"Warning: {warning.message}, Debug Info: {debug_info}")

    return True


def on_sample(appsink, model):
    sample = appsink.emit("pull-sample")
    buffer = sample.get_buffer()

    # extract JPEG data from the buffer
    success, info = buffer.map(Gst.MapFlags.READ)
    if not success:
        print("Failed to map buffer")
        return Gst.FlowReturn.ERROR

    jpeg_data = info.data
    buffer.unmap(info)

    # decode JPEG data using OpenCV
    img = cv2.imdecode(np.frombuffer(jpeg_data, dtype=np.uint8), cv2.IMREAD_COLOR)
    # e.g., img.shape: (720, 1280, 3)
    height, width = img.shape[:2]

    # img dimensions must be a multiple of max stride 32
    new_height = (height // 32) * 32
    new_width = (width // 32) * 32
    resized_img = cv2.resize(img, (new_width, new_height))

    # use YOLO to do the inference
    # result = model.predict(img)[0] # we provided only one image
    result = model.predict(resized_img, imgsz=(new_height, new_width))[0] # set specific input image size

    # https://www.freecodecamp.org/news/how-to-detect-objects-in-images-using-yolov8/
    detected_objects = []
    for box in result.boxes:
        # the class of the detected object
        obj_class = result.names[box.cls[0].item()]
        # the confidence level of the model about this object
        # conf = round(box.conf[0].item(), 2)
        # detected_objects.append((obj_class, conf))
        detected_objects.append(obj_class)
    # print(detected_objects)

    # Example: an alert should be generated if a person is detected in the location
    if 'person' in detected_objects:
        # TODO: stop the operation of the robotic arm
        print(colored('ALERT!!!', 'red', attrs=['bold', 'underline']))

    return Gst.FlowReturn.OK


def receive(port, model_name):
    # initialize the gstreamer library
    Gst.init(None) 

    pipeline_desc = (
        f'udpsrc port={port} ! '
        'application/x-rtp, encoding-name=JPEG, payload=26 ! '
        'queue ! '
        'rtpjpegdepay ! '
        'queue ! '
        'appsink name=sink sync=False'
    )
    # print(pipeline_desc)

    # load a pretrained YOLOv8 model: yolov8n.pt, yolov8s.pt, yolov8m.pt, yolov8l.pt, or yolov8x.pt
    # yolov8n.pt is the smallest and fastest model, while yolov8x.pt is the largest and most accurate
    model = YOLO(model_name)

    # create a new pipeline based on command line syntax
    pipeline = Gst.parse_launch(pipeline_desc)

    # retrieve the bus associated with the pipeline
    bus = pipeline.get_bus()
    # allow bus to emit signals for events
    bus.add_signal_watch()

    # Connect the on_sample callback to the pull-sample signal
    sink = pipeline.get_by_name("sink")
    sink.set_property("emit-signals", True)
    sink.connect("new-sample", on_sample, model)

    # start pipeline
    pipeline.set_state(Gst.State.PLAYING)

    # create main event loop
    loop = GLib.MainLoop()
    # add callback to specific signal
    bus.connect("message", on_message, loop)

    try:
        loop.run()
    except KeyboardInterrupt:
        print('\nTerminating...')
    except Exception as e:
        print(f"Exception: {e}")
        # print exception information and stack trace entries
        traceback.print_exc()
    finally:
        # stop pipeline
        pipeline.set_state(Gst.State.NULL)
        loop.quit()


if __name__ == '__main__':
    args = {'port': os.getenv('port'), 
        'yolo_model': os.getenv('yolo_model'),
    }

    print(f'Receiving sampled frames at UDP port {args["port"]}')
    print(f'Using pre-trained model: {args["yolo_model"]}')
    receive(args["port"], args["yolo_model"])