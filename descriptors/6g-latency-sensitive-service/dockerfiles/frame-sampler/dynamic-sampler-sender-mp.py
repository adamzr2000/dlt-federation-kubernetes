import traceback
import argparse
import multiprocessing
import re
import os
import zmq

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


def sample(pipeline_desc: str, args:dict):
    print(f'Receiving MJPG video stream at UDP port {args["port"]}')
    print(f'Sampling rate: {args["framerate"]} frames/s')
    print(f'Sending samples at {args["dest"]}:{args["dport"]}')

    # create a new pipeline based on command line syntax
    pipeline = Gst.parse_launch(pipeline_desc)

    # retrieve the bus associated with the pipeline
    bus = pipeline.get_bus()
    # allow bus to emit signals for events
    bus.add_signal_watch()

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


def update_rate(pipeline_desc:str, 
                    gst_process: multiprocessing.Process, 
                    args: dict):
    # control port
    c_port = args["control_port"]

    context = zmq.Context()
    # create REP socket
    rate_socket =  context.socket(zmq.REP)
    # bind socket to port
    rate_socket.bind(f'tcp://*:{c_port}')
    
    # create a poller and register the socket for polling
    poller = zmq.Poller()
    poller.register(rate_socket, zmq.POLLIN)
   
    print(f"Listening for interval update requests on port {c_port}")
   
    while True:
        try:
            # poll for events
            events = dict(poller.poll())
            # check for events on rate_socket
            if rate_socket in events and events[rate_socket] == zmq.POLLIN:
                new_rate = rate_socket.recv_string()
                print(f"Received new sampling rate value: {new_rate} frames/s")

                # kill the child process
                gst_process.terminate()
                # wait for child process to finish
                gst_process.join()
                # use regular expression to replace value for frame-rate
                pipeline_desc = re.sub(
                    r'framerate=\d+/\d+',
                    f'framerate={new_rate}', 
                    pipeline_desc
                )
                # print(pipeline_desc)
                # update args
                args["framerate"] = new_rate
                # start a separate process running the gstreamer pipeline
                gst_process = multiprocessing.Process(
                    target=sample, args=(pipeline_desc, args))
                gst_process.start()

                # send a response back to the client if needed
                rate_socket.send_string(f"Changed sampling rate to {new_rate} frames/s")
        except KeyboardInterrupt:
            # kill the child process
            gst_process.terminate()
            # wait for child process to finish
            gst_process.join()
            break


if __name__ == '__main__':
    args = {'port': os.getenv('port'), 
        'framerate': os.getenv('framerate'),
        'dest': os.getenv('destination_ip'),
        'dport': os.getenv('destination_port'),
        'control_port': os.getenv('framerate_port')
    }

    # initialize the gstreamer library
    Gst.init(None) 

    pipeline_desc = (
        f'udpsrc port={args["port"]} ! '
        'application/x-rtp, encoding-name=JPEG, payload=26 ! '
        'queue ! '
        'rtpjpegdepay ! '
        'queue ! '
        'jpegparse ! '
        'videorate ! '
        f'image/jpeg, framerate={args["framerate"]} ! '
        'queue ! '
        'rtpjpegpay ! '
        'queue ! '
        f'udpsink host={args["dest"]} port={args["dport"]} sync=False'
    )

    gst_process = multiprocessing.Process(
        target=sample, args=(pipeline_desc, args))
    gst_process.start()

    update_rate(pipeline_desc, gst_process, args)