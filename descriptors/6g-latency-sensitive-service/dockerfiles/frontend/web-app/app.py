from flask import Flask, render_template, request
import zmq
import os

# Initialize Flask app
app = Flask(__name__)

current_parameters = {"bitrate":"4000", "speed_preset":"ultrafast", "resolution":"1920x1080"}

sockets = None

args = ['streaming_server_ip', 'streaming_parameters_controller_ip','ros_bridge_server_ip', 'bitrate_port', 'speed_preset_port', 'resolution_port']
params = {arg: os.getenv(arg) for arg in args}

def socket_manager():
    global sockets
    context = zmq.Context()
    
    sockets = {
        'bitrate': context.socket(zmq.REQ),
        'speed_preset': context.socket(zmq.REQ),
        'resolution': context.socket(zmq.REQ)
    }
    
    for property, socket in sockets.items():
        socket.connect(f'tcp://{params["streaming_parameters_controller_ip"]}:{params[f"{property}_port"]}')
    print('Sockets are open!')


@app.route('/send', methods=['POST'])
def send_parameters_to_server():
    """Send parameters to server"""
    global sockets
    
    for property, socket in sockets.items():
        property_value = request.form.get(property)
        
        if property_value and property_value.strip() != current_parameters[property]:
            socket.send_string(f'{property_value}')
            res = socket.recv_string()
            print(res)
            current_parameters[property] = property_value

    return "Parameters sent to server"

@app.route('/streaming')
def display_streaming_page():
    """Render streaming page"""
    global sockets_generator, sockets

    socket_manager()
    return render_template('streaming-page.html', **params)

@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == "__main__":
    app.run(host='0.0.0.0', port='5000', debug="True")