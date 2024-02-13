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

**Install & Activate Metallb in the K8s cluster:**

*MetalLB is an open-source, software-based load balancer solution for Kubernetes clusters. It provides a network load balancing functionality by enabling the assignment of external IP addresses to services running within the cluster* 

1. Install MetalLB: Begin by installing MetalLB on your cluster. You can use *kubectl* to apply the MetalLB manifest from its GitHub repository
```
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.10.2/manifests/namespace.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.10.2/manifests/metallb.yaml
```

2. Configure MetalLB: After installing MetalLB, you need to configure it with the appropriate address pool. Create a *config.yaml* file using your preferred text editor:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  namespace: metallb-system
  name: config
data:
  config: |
    address-pools:
    - name: default
      protocol: layer2
      addresses:
      - <YOUR_DESIRED_IP_RANGE>
```

Replace *<YOUR_DESIRED_IP_RANGE>* with the IP range you want MetalLB to assign services from. For example, you can use a range within your local network, such as *10.5.50.180-10.5.50.190*. Save the file.

3. Apply the configuration:
```bash
kubectl apply -f config.yaml
```
4. Verify the installation: Use the following commands to check if the MetalLB driver is running:
```
kubectl get pods -n metallb-system
kubectl get configmap -n metallb-system
```
