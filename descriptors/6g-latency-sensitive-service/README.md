# Robot Video Streaming & Navigation Demo App

<div align="center">

[![Static Badge](https://img.shields.io/badge/Latest_Release-dev-orange)](https://gitlab.com/netmode/6g-latency-sensitive-service)
[![Static Badge](https://img.shields.io/badge/K3s-v1.29.1%2Bk3s2-blue)](https://github.com/k3s-io/k3s/releases/tag/v1.29.1%2Bk3s2)
[![Static Badge](https://img.shields.io/badge/MediaMTX-latest-blue?link=https%3A%2F%2Fgithub.com%2Fbluenviron%2Fmediamtx)](https://github.com/bluenviron/mediamtx)
[![Static Badge](https://img.shields.io/badge/Robotic_Vehicle-TurtleBot3-blue)](https://emanual.robotis.com/docs/en/platform/turtlebot3/overview/)
[![Static Badge](https://img.shields.io/badge/ROS_1_Noetic-latest-blue)](https://wiki.ros.org/noetic)

[![Static Badge](https://img.shields.io/badge/Docker_Images-Container_Registry-blue)](https://gitlab.com/netmode/6g-latency-sensitive-service/container_registry/6081751)
[![pipeline status](https://gitlab.com/netmode/6g-latency-sensitive-service/badges/main/pipeline.svg)](https://gitlab.com/netmode/6g-latency-sensitive-service/-/pipelines)

</div>

## Overview
This project showcases an interactive application that communicates with a robotic vehicle. The robot is outfitted with a video capture device, enhancing its mobility capabilities. The application, deployed within a Kubernetes cluster, primarily operates by establishing a connection with the on-site robot to exchange two key types of information:
1. It relays video streams from the robot to both the user interface of the web application and an object detection module.
2. It sends motion commands to the robot, which are determined by the user based on the environment observed via the video stream displayed on the frontend.

Here is a diagram that represents visually the architecture of the application:

![k8s-cluster.svg](/uploads/813842fcfa4c8cbd07437a4ee4f0ae2a/k8s-cluster.svg)


## Testing Environment
The code in this repository was tested in a two-part system configuration. One part of the system is a Kubernetes cluster, and the other part is a robotic vehicle.

### Specifications for Kubernetes Cluster
- **Operating System**: Ubuntu 20.04
- **Architecture**: AMD64
- **Python Version**: Python 3.8 or later
- **Docker Images**: Built using GitLab CI/CD. **Please note that the Docker images are currently not configured to work with ARM architecture.**
- **Kubernetes Distribution**: K3s v1.29.1+k3s2
- **Streaming Server**: MediaMTX (Latest Version)

### Specifications for Robotic Vehicle
- **Model**: Turtlebot3 (burger)
- **Controller**: Raspberry Pi 4
- **Controller Architecture**: ARM
- **Operating System**: Ubuntu Server 20.04
- **ROS Version**: ROS1 Noetic (Latest Version)

## Table of Contents
* [K3s Setup](#k3s-cluster-setup)
	* [Cluster Installation](#cluster-installation)
    * [Helm Integration](#helm-integration)
	* [Cluster Configuration](#cluster-configuration)
* [ROS1 Noetic Setup (if on-site robot provided)](#ros1-noetic-setup-if-on-site-robot-provided)
	* [ROS 1 Noetic Installation](#ros-1-noetic-installation)
	* [Rosbridge Server Installation](#rosbridge-server-installation)
	* [TurtleBot3 Dependencies Installation](#turtlebot3-dependencies-installation)
	* [TurtleBot3 Model Definition](#turtlebot3-model-definition)
* [Python Scripts Description](#python-scripts-description)
	* [Dependencies Installation](#dependencies-installation)
		* [PyGObject](#pygobject)
		* [PyZMQ](#pyzmq)
	* [Script 1: split-sender.py](#script-1-split-senderpy)
	* [Script 2: request-parameter-update.py](#script-2-request-parameter-updatepy)
* [Usage Instructions](#usage-instructions)
	* [Streaming Video](#streaming-video)
    * [Starting ROS Bridge Server (if on-site robot provided)](#starting-ros-bridge-server-if-on-site-robot-provided)
	* [Accessing the Frontend](#accessing-the-frontend)
	* [Checking Detected Objects](#checking-detected-objects)
	* [Dynamically Adjusting Framerate](#dynamically-adjusting-framerate)

## K3s Setup
### Cluster Installation
Ensure your system meets the specified [requirements](https://docs.k3s.io/installation/requirements) before establishing a K3s cluster.

To effortlessly set up a fully-functional, single-node Kubernetes cluster, execute the following command:

```sh
$ curl -sfL https://get.k3s.io | sh -
```

### Helm Integration
To integrate Helm, the Kubernetes package manager, with your K3s cluster, follow the [official documentation](https://helm.sh/docs/intro/install/) and choose the installation method that suits your needs.

### Cluster Configuration
Begin by cloning the [6g-latency-sensitive-service](https://gitlab.com/netmode/6g-latency-sensitive-service) repository, a comprehensive resource containing all necessary files for cluster configuration. Navigate to the project directory using the following commands:

```sh
$ git clone https://gitlab.com/netmode/6g-latency-sensitive-service.git
$ cd 6g-latency-sensitive-service
```

You could proceed with the configuration through the [apply-k8s-config.sh](https://gitlab.com/netmode/6g-latency-sensitive-service/-/blob/main/chart/apply-k8s-config.sh) script. Run it directly with the following commands:

```sh
$ cd chart
$ ./apply-k8s-config.sh
```

During this process, you will be prompted to confirm whether you’re utilizing a robot. Rest assured, you can configure your cluster, whether or not you’re utilizing a robot – a simple camera will suffice.

Docker images will be fetched, and Kubernetes components will be seamlessly created. Once completed, consider it done! **All Kubernetes components have been successfully applied.**

> Note: For your information, the Docker images are built using GitLab's CI/CD pipelines and are stored in the [GitLab Container Registry](https://gitlab.com/netmode/6g-latency-sensitive-service/container_registry/6081751). The Dockerfiles used for building these images can be found in the [dockerfiles](https://gitlab.com/netmode/6g-latency-sensitive-service/-/tree/main/dockerfiles) directory of this repository, should you wish to inspect them.

## ROS1 Noetic Setup (if on-site robot provided)
Setting up TurtleBot3? Check out the official [Documentation](https://emanual.robotis.com/docs/en/platform/turtlebot3/quick-start/#pc-setup) for guidance. Navigate the 'Quick Start Guide' on your left sidebar.

**Given your possession of a TurtleBot3 robot with ROS1 Noetic, the subsequent instructions can be followed.** 

The OpenCR board, integral to TurtleBot3, acts as a link between the ROS system on the Raspberry Pi and the robot's hardware. When a command is transmitted through the rosbridge server, it undergoes processing by ROS, is transmitted to the OpenCR, and is subsequently translated into physical movements by the robot's hardware. In essence, the OpenCR translates high-level commands into tangible robot movements.

### ROS 1 Noetic Installation
Update your system, download the ROS1 Noetic installation script, grant execution permissions, and run it with these commands:

```sh
$ sudo apt update
$ sudo apt upgrade
$ wget https://raw.githubusercontent.com/ROBOTIS-GIT/robotis_tools/master/install_ros_noetic.sh
$ chmod 755 ./install_ros_noetic.sh 
$ bash ./install_ros_noetic.sh
```

### Rosbridge Server Installation
Install the ROS Bridge server, facilitating a WebSocket interface to ROS, with the following command:

```sh
$ sudo apt-get install ros-noetic-rosbridge-server
```

### TurtleBot3 Dependencies Installation
Install the essential drivers, libraries, and software tools to interface with TurtleBot3 hardware by executing the following commands:

```sh
$ sudo apt install ros-noetic-dynamixel-sdk
$ sudo apt install ros-noetic-turtlebot3-msgs
$ sudo apt install ros-noetic-turtlebot3
```

### TurtleBot3 Model Definition
To ensure proper recognition of your TurtleBot3 model, set the TURTLEBOT3_MODEL environment variable using the following commands:

```sh
$ echo "export TURTLEBOT3_MODEL=burger" >> ~/.bashrc
$ source ~/.bashrc
```

> Note: Make sure your Raspberry Pi (slave) and the ROS master are connected to the **same LAN**. After the installation, you need to update the `ROS_MASTER_URI` environment variable in the `~/.bashrc file` on your Raspberry Pi. This variable tells ROS where to find the master node, which coordinates the other nodes in the system.

## Python Scripts Description
### Dependencies Installation

---

#### PyGObject
Before proceeding with the installation of PyGObject, GStreamer, a multimedia processing framework, needs to be installed on your system. Execute the following command to update your package lists and install GStreamer with its associated packages:

```bash
$ sudo apt-get update && apt-get install -y \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    gstreamer1.0-alsa \
    gstreamer1.0-gl \
    gstreamer1.0-gtk3 \
    gstreamer1.0-qt5 \
    gstreamer1.0-pulseaudio \
    libgirepository1.0-dev \
    gcc \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    gir1.2-gtk-4.0
```

After the successful installation of GStreamer, proceed with the installation of PyGObject. PyGObject is a Python package that provides bindings for GObject-based libraries such as GStreamer. Use pip to install PyGObject by running the following command:

```sh
$ pip3 install pycairo PyGObject
```

#### PyZMQ
PyZMQ is a Python package that provides bindings for ZeroMQ, an efficient messaging library. It allows seamless communication with ZeroMQ sockets using Python syntax and objects.

To install PyZMQ, use pip by executing the following command:

```sh
$ pip3 install pyzmq
```

---

### Script 1: split-sender.py
The first script, `split-sender.py`, is a powerful tool for video streaming. It captures a video stream from a camera and transmits MJPG video streams over UDP to two designated receivers.

To execute this script, use the following command:

```sh
$ python3 split-sender.py <host1> <port1> <host2> <port2> [options]
```

#### Positional Arguements
- `host1`: The IP address of the first receiver.
- `port1`: The UDP port number for the first receiver.
- `host2`: The IP address of the second receiver.
- `port2`: The UDP port number for the second receiver.

#### Optional Arguments
- `-d` or `--device`: The video device (default is /dev/video0).
- `-w` or `--width`: The frame width in pixels (default is 1920).
- `-H` or `--height`: The frame height in pixels (default is 1080).
- `-f` or `--frame-rate`: The frames per second (default is 30).

---

### Script 2: request-parameter-update.py
The second script, `request-parameter-update.py`, is designed to update the parameters of a streaming process. It sends these modifications to a dedicated server, allowing for real-time adjustments to the streaming process.

To execute this script, use the following command:

```sh
$ python3 request-parameter-update.py <server_ip> <port> [-p <parameter>]
```

#### Positional Arguments
- `server_ip`: The IP address of the encoder/sampler server.
- `port`: The TCP port number to which the request will be sent.

#### Optional Arguments
- `-p` or `--parameter`: The parameter to be updated. `<parameter>` can be one of the following: *bitrate*, *speed-preset*, *resolution*, *sampling-rate* (default is *bitrate*).


## Usage Instructions
### Streaming Video
In the specific context of this application, the same video feed needs to be accessed by two different locations simultaneously, the **streaming-controller** and the **frame-sampler**. The **streaming-controller** is responsible for encoding and publishing the video stream to the web application. The **frame-sampler** is responsible for selecting and sending frames to the **object-detector** component for analysis. 

Use this command:
```sh
$ python3 split-sender.py <receiver-encoder-publisher-service-ip> 5555 <sampler-sender-service-ip> 5554 [options]
```
Replace  `<receiver-encoder-publisher-service-ip>`  and `<sampler-sender-service-ip>` with the external IP address of the **receiver-encoder-publisher-service** and **sampler-service** respectively obtained using:
```sh
$ kubectl get service receiver-encoder-publisher-service
$ kubectl get service sampler-sender-service
```

### Starting ROS Bridge Server (if on-site robot provided)
To start the ROS Bridge Server, execute the following commands in a terminal:

```sh
$ roslaunch rosbridge_server rosbridge_websocket.launch
```

The ROS Bridge Server is launched and provides a WebSocket interface to ROS, enabling external programs (like the **remote operation center**) to interact with ROS cluster over a WebSocket connection.

Ensure that you run the following command on your robot:

```sh
$ roslaunch turtlebot3_bringup turtlebot3_robot.launch
```

This command not only starts the necessary processes for the TurtleBot3, ensuring a smooth connection to the ROS Bridge Server but also facilitates hardware access through the OpenCR board

### Accessing the Frontend
The **remote-operation-center** provides a user-friendly interface for monitoring the robot surroundings while at the same time issuing motion commands back to it.
Open your web browser and the web application (frontend) can be accessed at the following URL:

```
http://<frontend-service-ip>:5000/streaming
```

Replace  `<frontend-service-ip>` with the external IP address of the **frontend-service**. You can find this by running this command:

```sh
$ kubectl get service frontend-service
```

The frontend interface is divided into two main sections:
1. **Monitoring Section**: This section provides a live feed of the robot’s surroundings, allowing you to observe its environment in real-time.
2. **Control Panel**: This section allows you to manually drive the robot. It includes a set of control buttons that correspond to different motion commands. Alternatively, you can efficiently execute these commands by employing designated key mappings on the keyboard.

The control buttons and their corresponding keyboard commands are:
- **w**: Increase linear velocity (move forward).
- **x**: Decrease linear velocity (move backward).
- **d**: Increase angular velocity (turn right).
- **a**: Decrease angular velocity (turn left).
- **s**: Stop all motion.

Pressing the **w**, **x**, **d**, or **a** keys allows for precise control over velocity adjustments. When these keys are held down, they enable smooth acceleration in the corresponding direction. By using these keys in combination, users can achieve both linear and angular velocity simultaneously. This enables the execution of complex maneuvers, such as moving forward while turning. This state of motion continues even after the keys are released and persists until the **s** key is pressed, which immediately halts all movement. A maximum speed limit is in place to ensure optimal control and prioritize the safety of the equipment.

### Checking Detected Objects
The **object-detector** pod is responsible for analyzing the video frames and detecting the objects in them. Employing a pre-trained deep neural network model, this pod executes object detection tasks and meticulously logs the identified objects. To inspect the detected objects, delve into the pod's logs.

To find the name of the object-detector pod, execute the following command and identify the pod containing the term *object-detector*:

```sh
$ kubectl get pods
```

Once you've identified the pod, retrieve its logs with the following command:

```sh
$ kubectl logs <object-detector-pod-name>
```

Replace `<object-detector-pod-name>` with the name of the pod obtained in the previous step.

### Dynamically Adjusting Framerate
For real-time adjustments to the framerate utilized in the **frame-sampler**, execute the python script:
```sh
$ python3 request-parameter-update.py <sampler-sender-service-ip> 5560 -p sampling-rate
```

Substitute  `<sampler-sender-service-ip>` with the external IP address of the **sampler-sender-service** found through:

```sh
$ kubectl get service sampler-sender-service
```

Now, effortlessly fine-tune the framerate to meet your specific requirements on the fly.

> Note: **streaming-controller** features adjustable parameters such as *bitrate*, *speed-preset*, *resolution* beyond *sampling-rate*. These parameters can be manually updated through the **request-parameter-update.py** script by specifying the **-p** flag accordingly. However, the frontend provides a more user-friendly environment for these adjustments.
