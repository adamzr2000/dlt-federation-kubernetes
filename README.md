# DLT Federation with K8s

Short description...

## Installation

1. Clone the repository:
```
git clone https://github.com/adamzr2000/federation_osm_k8s.git
```
2. Initialize the virtual environment:
```
cd federation_osm_k8s
source fastapi-env/bin/activate
```
3. Install the necessary dependencies:
```
pip install -r requirements.txt
```
4. Install nodejs (if you don't have it yet): [How to Install Node.js on Ubuntu 20.04](https://www.digitalocean.com/community/tutorials/how-to-install-node-js-on-ubuntu-20-04)

5. Install truffle:
```
npm install -g truffle
```
6. Install Ganache GUI: [How to Install Ganache](https://trufflesuite.com/ganache/)

*If you don't have a computer with a graphical interface you can install Ganache CLI*
```
npm install -g ganache-cli
```

## Usage 

1. Create a local Blockchain Network (e.g. Ganache, Hyperledger)

*Both VMs must have access to blockchain nodes of this network (10.5.50.X/16)*

*Use the mnemonic "netcom;"*

- If you are using Ganache GUI: start a server on *https://10.5.50.100:7545*

- If you are using Ganache CLI:
```
ganache-cli --host 10.5.50.100 --port 7545 --mnemonic "netcom;"
```

2. Deploy the Federation Smart Contract to the Blockchain Network:
```
cd contracts
truffle migrate 
```
3. Initialize the virtual environment
```
source fastapi-env/bin/activate
```
4. Start the web server of the API (By default, it runs on localhost, port 8000)
```
uvicorn main:app --reload
```
- Consumer VM
```
uvicorn main:app --reload --host 10.5.50.100 --port 8000
uvicorn main_geth:app --reload --host 10.5.50.100 --port 8000
uvicorn main_public:app --reload --host 10.5.50.100 --port 8000
```
Access the API documentation at: [http://10.5.50.100/docs](http://10.5.50.100:8000/docs)
- Provider VM
```
uvicorn main:app --reload --host 10.5.50.101 --port 8002 
uvicorn main_geth:app --reload --host 10.5.50.101 --port 8002
uvicorn main_public:app --reload --host 10.5.50.101 --port 8002
```
Access the API documentation at: [http://10.5.50.101:8002/docs](http://10.5.50.101:8002/docs)

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
