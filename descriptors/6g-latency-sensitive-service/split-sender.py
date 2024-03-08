import traceback
import argparse
import ipaddress

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


def send(device, width, height, framerate, host, port, host2, port2):
    # initialize the gstreamer library
    Gst.init(None)

    pipeline_desc = (
        f'v4l2src device={device} ! '
        f'image/jpeg, width={width}, height={height}, framerate={framerate}/1 ! '
        'queue ! '
        'rtpjpegpay ! '
        'tee name=t ! '
        'queue ! '
        f'udpsink host={host} port={port} sync=False '
        't. ! '
        'queue ! '
        f'udpsink host={host2} port={port2} sync=False'
    )
    # print(pipeline_desc)

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='GStreamer pipeline sender for MJPG video streaming over UDP')

    # positional arguments
    parser.add_argument('host',
        type=ipaddress.IPv4Address, 
        help='IP address of receiver, e.g., 192.168.100.68')
    parser.add_argument('port',
        type=int, 
        help='UDP port number to which the data will be sent, e.g., 5555')
    parser.add_argument('host2',
        type=ipaddress.IPv4Address, 
        help='IP address of second receiver, e.g., 192.168.100.69')
    parser.add_argument('port2',
        type=int, 
        help='UDP port number for second receiver, e.g., 5556')

    # options
    parser.add_argument(
        '-d', '--device', 
        default='/dev/video0', 
        type=str, 
        help='Video device (default: /dev/video0)')
    parser.add_argument(
        '-w', '--width', 
        default=1920, 
        type=int, 
        help='frame width in pixels (default: 1920)')
    parser.add_argument(
        '-H', '--height', 
        default=1080, 
        type=int, 
        help='frame height in pixels (default: 1080)')
    parser.add_argument(
        '-f', '--frame-rate', 
        default=30, 
        type=int, 
        help='frames per second (default: 30)')

    args = parser.parse_args()
    # print(args)

    print('Starting MJPG video stream with the following properties:')
    print(f'\tDevice:               {args.device}')
    print(f'\tWidth:                {args.width}')
    print(f'\tHeight:               {args.height}')
    print(f'\tFramerate:            {args.frame_rate}/1')
    print(f'\t1st Receiver\'s IP:    {args.host}')
    print(f'\t1st UDP port:         {args.port}')
    print(f'\t2nd Receiver\'s IP:    {args.host2}')
    print(f'\t2nd UDP port:         {args.port2}')

    send(
        args.device,
        args.width, 
        args.height, 
        args.frame_rate, 
        args.host, 
        args.port,
        args.host2,
        args.port2
    )