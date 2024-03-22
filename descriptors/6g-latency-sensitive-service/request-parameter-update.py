import zmq
import argparse
import ipaddress
import re


def client(server_ip, port, new_value):
    context = zmq.Context()
    client_socket = context.socket(zmq.REQ)
    client_socket.connect(f"tcp://{server_ip}:{port}")

    # Send the new parameter value to the server
    client_socket.send_string(new_value)
    
    # Receive a response from the server if needed
    response = client_socket.recv_string()
    print(f"Server response: {response}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser('Request parameter update from encoder or sampler')

    # positional arguments
    parser.add_argument('server_ip',
        type=ipaddress.IPv4Address, 
        help='IP address of encoder/sampler, e.g., 192.168.100.68')
    parser.add_argument('port',
        type=int, 
        help='TCP port number to which the request will be sent, e.g., 5556')

    # options
    parser.add_argument(
        '-p', '--parameter', 
        default='bitrate', 
        choices=['bitrate', 'speed-preset', 'resolution', 'sampling-rate'],
        help='parameter to be updated (default: bitrate)')

    args = parser.parse_args()
    # print(args)

    allowed_presets = [
        'ultrafast', 'superfast', 'veryfast', 
        'faster', 'fast', 'medium', 
        'slow', 'slower', 'veryslow'
    ]

    while True:
        try:
            if args.parameter=='bitrate':
                new_bitrate_input = input("Enter new bitrate value: ")
                # check for value error
                new_bitrate_value = int(new_bitrate_input)
                client(args.server_ip, args.port, new_bitrate_input)
            elif args.parameter == 'speed-preset':
                new_speed_preset = input("Enter new speed-preset: ")
                if new_speed_preset not in allowed_presets:
                    raise ValueError
                client(args.server_ip, args.port, new_speed_preset)
            elif args.parameter == 'resolution':
                new_resolution = input('Enter new resolution (width)x(height): ')
                # check for value error
                new_w, new_h = map(int, new_resolution.split('x'))
                client(args.server_ip, args.port, new_resolution)
            if args.parameter=='sampling-rate':
                new_rate_input = input("Enter new sampling rate (frames/s): ")
                # check for value error
                if not re.match(r'^\d+/\d+$', new_rate_input):
                    print('Invalid input: sampling rate must be in the form (frames/seconds)')
                    continue
                client(args.server_ip, args.port, new_rate_input)
        except ValueError:
            print("Invalid input. Please enter a valid value.")
            continue
        except KeyboardInterrupt:
            print()
            break
