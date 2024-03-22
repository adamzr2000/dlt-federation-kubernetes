import traceback
import multiprocessing
import zmq
import re
import os
import time

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
        

def receive_encode_publish(pipeline: Gst.Pipeline, args: dict):
    print(f'Receiving MJPG video stream at UDP port {args["port"]}')
    print('Encoding to H.264 with the following properties:')
    print(f'\tBit rate:          {args["bit_rate"]}')
    print(f'\tSpeed preset:      {args["speed_preset"]}')
    print(f'\tResolution:        {args["width"]}x{args["height"]}')
    print(f'Sending to mediamtx server: rtsp://{args["server"]}:8554/bot_stream')
    print(f'In a browser, open: http://{args["server"]}:8889/bot_stream')

    # retrieve the bus associated with the pipeline
    bus = pipeline.get_bus()
    # allow bus to emit signals for events
    bus.add_signal_watch()

    

    while True :
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
            time.sleep(2)


def update_bitrate(pipeline: Gst.Pipeline, 
                   pipeline_desc: str, 
                   new_bitrate: int, 
                   gst_process:multiprocessing.Process,
                   args: dict):
    # stop the pipeline
    pipeline.set_state(Gst.State.NULL)
    # kill the child process
    gst_process.terminate()
    # wait for child process to finish
    gst_process.join()

    # use regular expression to replace value for bit-rate
    new_pipeline_desc = re.sub(
        r'bitrate=\d+', 
        f'bitrate={new_bitrate}', 
        pipeline_desc
    )
    # create a new pipeline based on command line syntax
    new_pipeline = Gst.parse_launch(new_pipeline_desc)
    # update args
    args['bit_rate'] = new_bitrate
    # start a separate process running the gstreamer pipeline
    new_gst_process = multiprocessing.Process(
        target=receive_encode_publish, args=(new_pipeline, args))
    new_gst_process.start()

    return (new_pipeline_desc, new_pipeline, new_gst_process)


def update_speed_preset(pipeline: Gst.Pipeline, 
                        pipeline_desc: str, 
                        new_speed_preset: str, 
                        gst_process:multiprocessing.Process,
                        args: dict):
    # stop the pipeline
    pipeline.set_state(Gst.State.NULL)
    # kill the child process
    gst_process.terminate()
    # wait for child process to finish
    gst_process.join()

    # use regular expression to replace value for speed-preset
    new_pipeline_desc = re.sub(
        r'speed-preset=\w+', 
        f'speed-preset={new_speed_preset}', 
        pipeline_desc
    )
    # create a new pipeline based on command line syntax
    new_pipeline = Gst.parse_launch(new_pipeline_desc)
    # update args
    args['speed_preset'] = new_speed_preset
    # start a separate process running the gstreamer pipeline
    new_gst_process = multiprocessing.Process(
        target=receive_encode_publish, args=(new_pipeline, args))
    new_gst_process.start()

    return (new_pipeline_desc, new_pipeline, new_gst_process)


def update_resolution(pipeline: Gst.Pipeline, 
                      pipeline_desc: str, 
                      new_width: int,
                      new_height: int, 
                      gst_process:multiprocessing.Process,
                      args: dict):
    # stop the pipeline
    pipeline.set_state(Gst.State.NULL)
    # kill the child process
    gst_process.terminate()
    # wait for child process to finish
    gst_process.join()

    # Use a regular expression to replace width and height values
    modified_pipeline_desc = re.sub(
        r'width=\d+', 
        f'width={new_width}', 
        pipeline_desc
    )
    new_pipeline_desc = re.sub(
        r'height=\d+', 
        f'height={new_height}', 
        modified_pipeline_desc
    )
    # create a new pipeline based on command line syntax
    new_pipeline = Gst.parse_launch(new_pipeline_desc)
    # update args
    args['width'] = new_width
    args['height'] = new_height
    # start a separate process running the gstreamer pipeline
    new_gst_process = multiprocessing.Process(
        target=receive_encode_publish, args=(new_pipeline, args))
    new_gst_process.start()

    return (new_pipeline_desc, new_pipeline, new_gst_process)


def update_parameter_loop(pipeline: Gst.Pipeline, 
                          pipeline_desc: str, 
                          gst_process: multiprocessing.Process, 
                          args: dict):
    # control ports
    b_port, s_port, r_port = (os.getenv(var) for var in ('bit_rate_port', 'speed_preset_port', 'resolution_port'))

    context = zmq.Context()

    # create REP sockets
    bitrate_socket =  context.socket(zmq.REP)
    speed_socket =  context.socket(zmq.REP)
    resolution_socket = context.socket(zmq.REP)

    # bind sockets to different ports
    bitrate_socket.bind(f'tcp://*:{b_port}')
    speed_socket.bind(f'tcp://*:{s_port}')
    resolution_socket.bind(f'tcp://*:{r_port}')

    # create a poller and register the sockets for polling
    poller = zmq.Poller()
    poller.register(bitrate_socket, zmq.POLLIN)
    poller.register(speed_socket, zmq.POLLIN)
    poller.register(resolution_socket, zmq.POLLIN)

    print(f"Listening for bitrate update requests on port {b_port}")
    print(f"Listening for speed-preset update requests on port {s_port}")
    print(f"Listening for resolution update requests on port {r_port}")

    while True:
        try:
            # poll for events
            events = dict(poller.poll())
            # check for events on bitrate_socket
            if bitrate_socket in events and events[bitrate_socket] == zmq.POLLIN:
                message = bitrate_socket.recv_string()
                new_bitrate = int(message)
                print(f"Received new bitrate value: {new_bitrate} kpbs")
                # update bitrate
                pipeline_desc, pipeline, gst_process = update_bitrate(
                    pipeline, pipeline_desc, new_bitrate, gst_process, args)
                # send a response back to the client if needed
                bitrate_socket.send_string(f"Changed encoding bitrate to {new_bitrate} bps")
            # check for events on speed_socket
            if speed_socket in events and events[speed_socket] == zmq.POLLIN:
                new_speed_preset = speed_socket.recv_string()
                print(f"Received new speed-preset value: {new_speed_preset}")
                # update speed-preset
                pipeline_desc, pipeline, gst_process = update_speed_preset(
                    pipeline, pipeline_desc, new_speed_preset, gst_process, args)
                # send a response back to the client if needed
                speed_socket.send_string(f"Changed speed-preset to {new_speed_preset}")
            if resolution_socket in events and events[resolution_socket] == zmq.POLLIN:
                new_resolution = resolution_socket.recv_string()
                new_width, new_height = map(int, new_resolution.split('x'))
                print(f"Received new resolution value: {new_width}x{new_height}")
                # update resolution
                pipeline_desc, pipeline, gst_process = update_resolution(
                    pipeline, pipeline_desc, new_width, new_height, gst_process, args)
                # send a response back to the client if needed
                resolution_socket.send_string(f"Changed resolution to {new_width}x{new_height}")
        except KeyboardInterrupt:
            # stop the pipeline
            pipeline.set_state(Gst.State.NULL)
            # kill the child process
            gst_process.terminate()
            # wait for child process to finish
            gst_process.join()
            break


if __name__ == '__main__':

    args = {'port': os.getenv('port'), 
            'width': os.getenv('width'),
            'height': os.getenv('height'),
            'bit_rate': os.getenv('bit_rate'),
            'speed_preset': os.getenv('speed_preset'),
            'server': os.getenv('server')}

    # initialize the gstreamer library
    Gst.init(None)

    pipeline_desc = None
    publishing_protocol = os.environ['publishing_protocol']

    if publishing_protocol == 'rtsp' :
        pipeline_desc = (
            f'udpsrc port={args["port"]} ! '
            'application/x-rtp, encoding-name=JPEG, payload=26 ! '
            'queue ! '
            'rtpjpegdepay ! '
            'queue ! '
            'jpegdec ! '
            'queue ! '
            'videoconvert ! '
            'videoscale ! '
            f'video/x-raw, width={args["width"]}, height={args["height"]} ! '
            f'x264enc name=my_enc bitrate={args["bit_rate"]} '
            f'speed-preset={args["speed_preset"]} '
            'bframes=0 tune=zerolatency ! '
            'h264parse ! '
            'queue ! '
            f'rtspclientsink protocols=udp location=rtsp://{args["server"]}:8554/bot_stream'
        )
    elif publishing_protocol == 'srt' :
        pipeline_desc = (
            f'udpsrc port={args["port"]} ! '
            'application/x-rtp, encoding-name=JPEG, payload=26 ! '
            'rtpjpegdepay ! '
            'jpegdec ! '
            'videoconvert ! '
            'videoscale ! '
            f'video/x-raw, width={args["width"]}, height={args["height"]} ! '
            f'x264enc name=my_enc bitrate={args["bit_rate"]} '
            f'speed-preset={args["speed_preset"]} key-int-max=10 '
            'bframes=0 tune=zerolatency ! '
            'h264parse ! '
            'mpegtsmux alignment=7 ! '
            f'srtsink uri="srt://{args["server"]}:8890?streamid=publish:bot_stream" sync=False'
        )

    else :
        print("Invalid publishing protocol! Opt for either 'rtsp' or 'srt'.")

    # create a new pipeline based on command line syntax
    pipeline = Gst.parse_launch(pipeline_desc)

    # start a separate process running the gstreamer pipeline
    gst_process = multiprocessing.Process(target=receive_encode_publish, args=(pipeline, args))
    gst_process.start()

    # enter loop for dynamic parameter updates
    update_parameter_loop(pipeline, pipeline_desc, gst_process, args)