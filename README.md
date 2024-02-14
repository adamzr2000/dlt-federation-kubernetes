# DLT Federation with K8s

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
2.2. For each of the following subdirectories (`dlt-node`, `truffle`), execute the `build.sh` script. Example:
```bash
cd ../dlt-node
./build.sh
cd ../truffle
./build.sh
```

3. Install the necessary python3 dependencies:
```bash
pip install -r requirements.txt
```

## Usage 

1. Create a private Blockchain Network (Ethereum Network based on container Geth nodes)

*Both VMs must have access to blockchain nodes of this network (10.5.50.X/16)*

```bash
./start_dlt_network.sh
```

2. Deploy the Federation Smart Contract to the Blockchain Network:
```bash
cd smart-contracts
./deploy.sh 
```

3. Start the web server of the API 
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

<Enter each IP address range (e.g. 10.5.50.80-10.5.50.90)>
```

2. Verify the installation: Use the following commands to check if the MetalLB driver is running:
```
kubectl get pods -n metallb-system
kubectl get configmap -n metallb-system
```
