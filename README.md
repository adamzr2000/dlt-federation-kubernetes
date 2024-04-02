# DLT Service Federation using Kubernetes

## Introduction

Description of the repo.

**Author:** Adam Zahir Rodriguez


## Scenario setup

![Experimental Setup](images/experimental-setup.png)

The configuration of the simulation:
- 2 VMs containing the Docker and MicroK8s
- Both interconnected in bridge mode within KVM
- Both VMs have access to a blockchain node

## Prerequisites

Before getting started, make sure you have the following installed on your system:

- [Microk8s](https://microk8s.io/#install-microk8s)
- [Docker](https://docs.docker.com/engine/install/ubuntu)
- [Docker Compose](https://docs.docker.com/compose/install/linux)

## Installation

1. Clone the repository:
```
git clone git@github.com:adamzr2000/dlt-federation-kubernetes.git
```

2. Build Docker Images:
Follow these steps to build the necessary Docker images:

2.1. Navigate to the `docker-images` directory in your project.
```bash
cd docker-images
```

2.2. For each of the following subdirectories (`dlt-node`, `truffle`, `eth-netstats`), execute the `build.sh` script. 
```bash
cd dlt-node
./build.sh
cd ../truffle
./build.sh
cd ../eth-netstats
./build.sh
```

3. Install the necessary python3 dependencies:
```bash
pip install -r requirements.txt
```

## Usage 

1. Creating a DLT Network

Initiate your private Ethereum Network on [VM1], which relies on containerized Geth nodes, by running:

Note: Please make sure to modify the IP addresses in the `.env` file according to your setup before executing the script. For example, replace 10.5.50.70 with the IP address of your VM1 and 10.5.50.71 with the IP address of your VM2.

```bash
cd dlt-network-docker
./start_dlt_network.sh
```

2. Joining the DLT Network

On [VM2], to join the DLT network from a second node, execute:

```bash
./join_dlt_network.sh node2
```

## Verifying Node Association

After starting the DLT network, you can verify that the nodes have associated correctly by executing the following commands:
```bash
docker exec -it node1 geth --exec "net.peerCount" attach ws://10.5.50.70:3334
```

```bash
docker exec -it node2 geth --exec "net.peerCount" attach ws://10.5.50.71:3335
```

Each command should report `1 peer`, indicating that the nodes have successfully connected to each other.


Access the [eth-netsats](http://10.5.50.70:3000) web interface for additional information.

2. Deploy the Federation Smart Contract to the Blockchain Network:
```bash
cd smart-contracts
./deploy.sh 
```

3. Start the web server of the API 

Note: Before starting the web server, ensure to export the Kubernetes cluster configuration file for each VM. Navigate to the `k8-scluster-config` directory and execute `./export_k8s_cluster_config`.

```bash
./start_app.sh
```

Consumer API documentation at: [http://10.5.50.70:8000/docs](http://10.5.50.70:8000/docs)


Provider API documentation at: [http://10.5.50.71:8000/docs](http://10.5.50.71:8000/docs)


## Kubernetes configuration

**Activate Metallb in the K8s cluster:**

*MetalLB is an open-source, software-based load balancer solution for Kubernetes clusters. It provides a network load balancing functionality by enabling the assignment of external IP addresses to services running within the cluster* 

1. Configure MetalLB: After installing Microk8s, you need to configure metallb with the appropriate address pool.
```bash
microk8s enable metallb

<Enter IP address range>
(e.g. 10.5.50.80-10.5.50.90)
```

2. Verify the installation: Use the following commands to check if the MetalLB driver is running:
```
kubectl get pods -n metallb-system
kubectl get configmap -n metallb-system
```
