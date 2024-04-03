# DLT Service Federation using Kubernetes

## Introduction

The DLT-federation is a component that enables fast, secure and dynamic service federation across 
different administrative domains (ADs) by using distributed ledger technologies (DLTs). More specifically, the federation procedures are stored and deployed on a Federation Smart Contract which is running on top of a permissioned blockchain. Each domain sets up a blockchain node to gain access to the blockchain network. 

**Author:** Adam Zahir Rodriguez

## Scenario setup

![Experimental Setup](images/experimental-setup.svg)

The configuration of the simulation:

- 2 VMs, each represented as an AD, containing [Docker](https://docs.docker.com/engine/install/ubuntu) and [Microk8s](https://microk8s.io/#install-microk8s)
- Both interconnected in bridge mode within [KVM](https://help.ubuntu.com/community/KVM/Networking)
- Both VMs have access to a blockchain node

# Installation

1. Clone the repository:
```bash
git clone git@github.com:adamzr2000/dlt-federation-kubernetes.git
```

2. Build Docker Images:
Navigate to the `docker-images` directory and proceed to build the required Docker images for the project by executing their respective `build.sh` scripts:

```bash
cd docker-images
cd dlt-node && ./build.sh && cd ../truffle && ./build.sh && cd ../eth-netstats && ./build.sh
```

- `dlt-node`: Based on [Go-Ethereum (Geth)](https://geth.ethereum.org/docs) software, serving as nodes within the peer-to-peer blockchain network

- `truffle`: Development framework for Ethereum-based blockchain applications. It provides a suite of tools that allows developers to write, test, and deploy smart contracts on the blockchain network

- `eth-netstats`: Dashboard for monitoring Geth nodes within the blockchain network

**Note:** For building images corresponding to the object detection service, please consult the README file located in the `descriptors/6g-latency-sensitive-service` directory

3. Install the necessary python dependencies:
```bash
pip3 install -r requirements.txt
```

# Blockchain Network Setup

Firstly, we will create a blockchain network using `dlt-node` container images. The network will consist of two nodes, corresponding to VM1 and VM2, respectively. **VM1** will act as the bootnode, facilitating the association of both nodes with each other.

1. Initialize the network:

**(VM1)** Navigate to the `dlt-network-docker` directory and start the network setup:

**Note:** Please make sure to modify the IP addresses in the `.env` file according to your setup before executing the script. Replace `IP_NODE_1` with the IP address of your **VM1** and `IP_NODE_2` with the IP address of your **VM2**.

```bash
./start_dlt_network.sh
```

2. Join the network from a second node

**(VM2)** Navigate to the `dlt-network-docker` directory and execute:

```bash
./join_dlt_network.sh node2
```

3. Verify node association

After starting the blockchain network, you can verify that the nodes have associated correctly by executing the following commands:
```bash
# VM1
docker exec -it node1 geth --exec "net.peerCount" attach ws://<vm1-ip-address>:3334

# VM2  
docker exec -it node2 geth --exec "net.peerCount" attach ws://<vm2-ip-address>:3335
```

Each command should report `1 peer`, indicating that the nodes have successfully connected to each other.

Access the [eth-netsats](http://<vm1-ip-address>:3000) web interface for additional information.

4. Stop the network:

**(VM1)** When needed, use the following command to stop the network:

```bash
./stop_dlt_network.sh
```

# Usage

**Note:** Before starting, ensure to export the Kubernetes cluster configuration file for each VM. Navigate to the `k8s-cluster-config` directory and execute `./export_k8s_cluster_config`

1. Deploy the Federation Smart Contract to the blockchain Network:

**(VM1 or VM2)** Execute the following commands:
```bash
cd smart-contracts
./deploy.sh 
```

2. Start the orchestrator's web server and specify the domain role for the federation (e.g., VM1 as consumer and VM2 as provider)

```bash
./start_app.sh
```

For detailed information about the federation functions, refer to the REST API documentation, which is based on Swagger UI, at: [http://<vm-ip-address>:8000/docs](http://<vm-ip-address>:8000/docs)



## Kubernetes configuration utilities

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