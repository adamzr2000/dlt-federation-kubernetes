# DLT Service Federation using Kubernetes

<div align="center">

[![Static Badge](https://img.shields.io/badge/MicroK8s-v1.28.7-orange)](https://github.com/canonical/microk8s/tree/1.28)

[![Static Badge](https://img.shields.io/badge/Docker-v25.0.3-blue)](https://github.com/docker)

</div>

## Overview

Federation of services aims to provide orchestration of services across multiple administrative domains (ADs). This project showcases how different ADs can establish federation efficiently using distributed ledger technologies (DLT) as a mediatior in the process. More specifically, the federation procedures are stored and deployed on a Federation Smart Contract, which is running on top of a permissioned blockchain. Each AD sets up a blockchain node to gain access to the blockchain network and they interact with the Federation Smart Contract by sending transactions.

Here is a diagram that represents visually the experimental setup:

![Experimental Setup](images/experimental-setup.svg)

- 2 VMs, each acting as a separate AD, containing [Docker](https://docs.docker.com/engine/install/ubuntu) and [MicroK8s](https://MicroK8s.io/#install-MicroK8s)
- Both interconnected in bridge mode within [KVM](https://help.ubuntu.com/community/KVM/Networking)
- Both VMs have access to a blockchain node

**Author:** Adam Zahir Rodriguez

## Installation

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

> Note: For building images corresponding to the object detection service, please consult the [README](https://gitlab.com/netmode/6g-latency-sensitive-service) file located in the `descriptors/6g-latency-sensitive-service` directory

3. Install the necessary python dependencies:
```bash
pip3 install -r requirements.txt
```

## Blockchain Network Setup

Firstly, we will create a blockchain network using `dlt-node` container images. The network will consist of two nodes, corresponding to VM1 and VM2, respectively. **VM1** will act as the bootnode, facilitating the association of both nodes with each other.

1. Initialize the network:

**(VM1)** Navigate to the `dlt-network-docker` directory and start the network setup:

> Note: Please make sure to modify the IP addresses in the `.env` file according to your setup before executing the script. Replace `IP_NODE_1` with the IP address of your **VM1** and `IP_NODE_2` with the IP address of your **VM2**.

```bash
cd dlt-network-docker
./start_dlt_network.sh
```

2. Join the network from a second node

**(VM2)** Navigate to the `dlt-network-docker` directory and execute:

```bash
cd dlt-network-docker
./join_dlt_network.sh node2
```

3. Verify node association

After starting the blockchain network, you can verify that the nodes have associated correctly by executing the following commands:
```bash
# VM1
docker exec -it node1 geth --exec "net.peerCount" attach ws://<vm1-ip>:3334

# VM2  
docker exec -it node2 geth --exec "net.peerCount" attach ws://<vm2-ip>:3335
```

Each command should report `1 peer`, indicating that the nodes have successfully connected to each other.

Access the `eth-netsats` web interface for additional information at `http://<vm1-ip>:3000`

4. Stop the network:

**(VM1)** When needed, use the following command to stop the network:

```bash
./stop_dlt_network.sh
```

## MicroK8s Setup
### Cluster Installation
To effortlessly set up a fully-functional, single-node Kubernetes cluster, execute the following command:

```bash
sudo snap install microk8s --classic
```

Add the following lines to your `~/.bash_aliases` file for direct usage of `kubectl` and `helm` commands with MicroK8s:
```bash
alias kubectl='microk8s kubectl'
alias helm='microk8s helm'
```

### Helm Integration
To integrate Helm, the Kubernetes package manager, with your MicroK8s cluster, run:
```bash
microk8s enable helm 
```

### MetalLB Integration
**MetalLB** is an open-source, software-based load balancer solution for Kubernetes clusters. It provides a network load balancing functionality by enabling the assignment of external IP addresses to services running within the cluster.

Integrate MetalLB with your MicroK8s cluster by executing the following command and specifying the appropriate address pool:
```bash
microk8s enable metallb

<Enter IP address range>
(e.g. 10.5.50.80-10.5.50.90)
```

Check if the MetalLB driver is running using the following commands:
```bash
kubectl get pods -n metallb-system
kubectl get configmap -n metallb-system
```

## Usage

> Note: Before starting, ensure to export the Kubernetes cluster configuration file for each VM. Navigate to the `k8s-cluster-config` directory and execute `./export_k8s_cluster_config`

1. Deploy the Federation Smart Contract to the blockchain Network:

**(VM1 or VM2)** Execute the following commands:
```bash
cd smart-contracts
./deploy.sh 
```

2. Start the orchestrator's web server on each VM and specify the domain role for the federation (e.g., VM1 as consumer and VM2 as provider)

```bash
./start_app.sh
```

For detailed information about the federation functions, refer to the REST API documentation, which is based on Swagger UI, at: `http://<vm-ip>:8000/docs`

3. Register each AD in the Smart Contract to enable their participation in the federation:

```bash
# VM1 
curl -X POST http://<vm1-ip>:8000/register_domain

# VM2 
curl -X POST http://<vm2-ip>:8000/register_domain
```

## Scenario 1: migration of the entire object detection service

The consumer AD initiates the service deployment:
```bash
curl -X POST http://<vm1-ip>:8000/deploy_object_detection_service
```

The provider AD listens for federation events and the consumer AD trigger federation process:
```bash
# VM2
curl -X POST http://<vm2-ip>:8000/start_experiments_provider_v1

# VM1
curl -X POST http://<vm1-ip>:8000/start_experiments_consumer_v1
```

> Note: These commands will automate all interactions during the federation, including *announcement*, *negotiation*, *acceptance*, and *deployment*.

Upon successful completion of the federation procedures, the entire service should be deployed in the provider AD, and the consumer AD can access it through the `external_ip` endpoint (shared via the smart contract)

To delete the service, execute:
```bash
# VM1
curl -X DELETE http://<vm1-ip>:8000/delete_object_detection_service

# VM2
curl -X DELETE http://<vm2-ip>:8000/delete_object_detection_service
```

## Scenario 2: migration of the object detection component

The consumer AD initiates the service deployment:
```bash
curl -X POST http://<vm1-ip>:8000/deploy_object_detection_service
```

The provider AD listens for federation events and the consumer AD trigger federation process:
```bash
# VM2
curl -X POST http://<vm2-ip>:8000/start_experiments_provider_v2

# VM1
curl -X POST http://<vm1-ip>:8000/start_experiments_consumer_v2
```

> Note: These commands will automate all interactions during the federation, including *announcement*, *negotiation*, *acceptance*, and *deployment*.

Upon successful completion of the federation procedures, the object detection component should be deployed in the provider AD. The consumer AD then terminates its object detection component and updates the configmap of the `sampler-sender` to direct the video stream to the `external IP address` endpoint of the object detection component (shared via the smart contract).

To verify, execute `kubectl get configmap sampler-sender-config-map -o yaml` in the consumer AD. The `destination_ip` value should match the `external IP address` of the object detection component deployed in the provider AD.

To delete the service, execute:
```bash
# VM1
curl -X DELETE http://<vm1-ip>:8000/delete_object_detection_service

# VM2
curl -X DELETE "http://<vm2-ip>:8000/delete_object_detection_federation_component" -H "Content-Type: application/json" -d '{"domain": "provider", "pod_prefixes": ["object-detector-"]}'
```

## Scenario 3: scaling of the object detection component

The consumer AD initiates the service deployment with N replicas (e.g., 6) of the object detector component:
```bash
curl -X POST http://<vm1-ip>:8000/deploy_object_detection_service?replicas=6
```

The provider AD listens for federation events and the consumer AD trigger the federation process, announcing its intention to scale M replicas (e.g., 4):
```bash
# VM2
curl -X POST http://<vm2-ip>:8000/start_experiments_provider_v3

# VM1
curl -X POST http://<vm1-ip>:8000/start_experiments_consumer_v3?replicas=4
```

> Note: These commands will automate all interactions during the federation, including *announcement*, *negotiation*, *acceptance*, and *deployment*.

Upon successful completion of the federation procedures, the object detection component should be deployed in the provider AD with M replicas, while the consumer AD should have N-M replicas deployed.

To delete the service, execute:
```bash
# VM1
curl -X DELETE http://<vm1-ip>:8000/delete_object_detection_service

# VM2
curl -X DELETE "http://<vm2-ip>:8000/delete_object_detection_federation_component" -H "Content-Type: application/json" -d '{"domain": "provider", "pod_prefixes": ["object-detector-"]}'
```