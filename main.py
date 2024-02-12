import random
import sys
import os
import json
import time
import psutil
import requests

from web3 import Web3, HTTPProvider, IPCProvider
from web3.middleware import geth_poa_middleware

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse
from enum import Enum
from io import StringIO
from kubernetes import client, config

import yaml
import argparse
import subprocess


class DescriptorEnum(str, Enum):
    nginx = "nginx"
    openldap = "openldap"


app = FastAPI(
    title="Federation with DLT And OSM-K8s API Documentation",
    description="""
- This API provides endpoints for interacting with the DLT network.

- The federation procedures are stored and deployed on a Federation Smart Contract, which is running on top of a blockchain network.

- ADs communicate with the smart contract through transactions.

---

### Federation steps:

**1) REGISTRATION (initial procedure)**

Administrative Domains (ADs) register to the Federation SC with a single-transaction registration, using its unique blockchain address.

**2) ANNOUNCEMENT**

Consumer AD announces that it needs service federation (service extension or new service)

**3) NEGOTIATION**

Provider AD(s) listen for federation events. If they receive an offer, they analyze if they can satisfy the requirements and send back an answer with the price of the service

**4) ACCEPTANCE & DEPLOYMENT**

Consumer AD analyzes all collected answers and chooses an offer of a single provider domain.

Provider AD starts the deployment of the requested federated service

**5) USAGE & CHARGING**

Once the provider deploys the federated service, it notifies the consumer AD

---
### Access to OSM GUI:

User: **admin**

Password: **admin**

[Click here to access the OSM GUI (10.5.50.100)](http://10.5.50.100)

[Click here to access the OSM GUI (10.5.50.101)](http://10.5.50.101)

"""
)

while True:
    debug_txt = input("Domain function: ")
    if debug_txt == "consumer" or debug_txt == "provider":
        break
    else:
        print("Invalid input. Please enter 'consumer' or 'provider'.")

domain = debug_txt

if domain == "consumer":
    # Configure the web3 interface to the Blockchain and SC
    web3= Web3(Web3.WebsocketProvider("ws://10.5.50.100:3334")) 

if domain == "provider":
    # Configure the web3 interface to the Blockchain and SC
    web3= Web3(Web3.WebsocketProvider("ws://10.5.50.101:3335")) 

web3.middleware_onion.inject(geth_poa_middleware, layer=0) 

# Load the ABI of the smart contract from a JSON file
abi_path = "smart-contracts/build/contracts/"
with open(abi_path+"Federation.json") as c_json:
   contract_json = json.load(c_json)

contract_abi = contract_json["abi"]

# Contract address using the mnemonic "netcom;" on Ganache
contract_address = Web3.toChecksumAddress('0x1AbF5A30fea55787fe60f221a5491E3B8Fe08BfA')

private_key_account_1 = "7ce9df652098c219931198e24d9c2dbe952e140f24a6541dcd038f9a22123309"
private_key_account_2 = ""

# Instance of the smart contract
Federation_contract = web3.eth.contract(abi=contract_abi, address=contract_address)

# List of accounts available on the connected Ethereum node (Ganache)
eth_address = web3.eth.accounts

# Address of the miner (node that adds a block to the blockchain)
coinbase = eth_address[0] 


#-------------------------- Configure CONSUMER variables --------------------------#
timestamp = int(time.time())
service_id = ''
service_endpoint_consumer = ''
service_consumer_address = ''
service_requirements = 'service='
bids_event = None
#----------------------------------------------------------------------------------#


#-------------------------- Configure PROVIDER variables --------------------------#
service_endpoint_provider = ''
federated_host = ''
service_price = 0
bid_index = 0
winner = coinbase
manager_address = ''
winnerChosen_event = None
#----------------------------------------------------------------------------------#

#-------------------------- Configure TEST variables ------------------------------#
# Initialize a list to store the times of each federation step
federation_step_times = []
#----------------------------------------------------------------------------------#

# Configure the IP address
stream = os.popen('ip a | grep 10.5.50').read()
stream = stream.split('inet ',1)
ip_address = stream[1].split('/',1)
ipaddress = ip_address[0]

# Configure the domain variables
domain_registered = False

if domain == 'consumer':
   block_address = eth_address[1]
   private_key = private_key_account_1
   timestamp = int(time.time())
   service_id = 'service'+str(timestamp)
   service_endpoint_consumer = ipaddress
   service_consumer_address = block_address
   domain_name = "AD1"
   vim_name = "VIM_" + domain_name

else:
   block_address = eth_address[1]
   private_key = private_key_account_2
   service_endpoint_provider = ipaddress
   service_id = ''
   domain_name = "AD2"

nonce = web3.eth.getTransactionCount(block_address)

def send_signed_transaction(build_transaction):
    signed_txn = web3.eth.account.signTransaction(build_transaction, private_key)
    return web3.eth.sendRawTransaction(signed_txn.rawTransaction)

# Configure OSM variables: VIM account, K8s cluster, VNFD-NSD info
vim_name = "dummy_vim_" + domain_name
cluster_name = "cluster_" + domain_name
nsd_name = ''
vnfd_name = ''
member_vnf_index = ''
kdu_name = ''

def select_descriptor(descriptor):
    global nsd_name
    global vnfd_name
    global member_vnf_index
    global kdu_name

    global service_requirements
    service_requirements = service_requirements + descriptor

    if descriptor == "nginx":
        nsd_name = 'nginx_ns'
        vnfd_name = 'nginx_knf'
        member_vnf_index = 'nginx'
        kdu_name = 'nginx'
    elif descriptor == "openldap":
        nsd_name = 'openldap_ns'
        vnfd_name = 'openldap_knf'
        member_vnf_index = 'openldap'
        kdu_name = 'ldap'
    else:
        nsd_name = ''
        vnfd_name = ''
        member_vnf_index = ''
        kdu_name = ''

# Consumer AD announces that he needs a federated service and reveals his ip address (192.168.56.104)
def AnnounceService():
    global nonce

    # Build the transaction for the AnnounceService function
    announce_transaction = Federation_contract.functions.AnnounceService(
        _requirements=web3.toBytes(text=service_requirements),
        _endpoint_consumer=web3.toBytes(text=service_endpoint_consumer),
        _id=web3.toBytes(text=service_id)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })
    
    # Send the signed transaction
    tx_hash = send_signed_transaction(announce_transaction)
    
    # Increment the nonce
    nonce += 1
    
    block = web3.eth.getBlock('latest')
    block_number = block['number']
    
    event_filter = Federation_contract.events.NewBid.createFilter(fromBlock=web3.toHex(block_number))
    
    return event_filter

# Returns information about a specific bid (indicates the bid index)
def GetBidInfo(bid_index):
    bid_info = Federation_contract.functions.GetBid(_id=web3.toBytes(text=service_id), bider_index=bid_index, _creator=block_address).call()
    return bid_info

# Consumer AD choose a Provider (indicates the bid index)
def ChooseProvider(bid_index):
    global nonce

    # Build the transaction for the ChooseProvider function
    choose_transaction = Federation_contract.functions.ChooseProvider(
        _id=web3.toBytes(text=service_id),
        bider_index=bid_index
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(choose_transaction)
    nonce += 1

# Returns information about the service (0->Open, 1->Closed, 2->Deployed)
def GetServiceState(serviceid):
    service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=serviceid)).call()
    return service_state

# Returns the IP of the Provider
def GetDeployedInfo(service_id):
    #service_endpoint_provider = '192.168.191.x'
    #service_id, service_endpoint_provider, external_ip = Federation_contract.functions.GetServiceInfo(_id=web3.toBytes(text=serviceid), provider=False, call_address=block_address).call()
    service_id_bytes = web3.toBytes(text=service_id)  # Convert string to bytes
    service_id, service_endpoint_provider, external_ip = Federation_contract.functions.GetServiceInfo(_id=service_id_bytes, provider=False, call_address=block_address).call()
    _service_id = service_id.rstrip(b'\x00')  # Apply rstrip on bytes-like object
    _service_endpoint_provider = service_endpoint_provider.rstrip(b'\x00')
    _external_ip = external_ip.rstrip(b'\x00')
    return _external_ip, _service_endpoint_provider
    #return service_endpoint_provider

def ServiceAnnouncementEvent():
    block = web3.eth.getBlock('latest')
    blocknumber = block['number']
    print("\nLatest block:",blocknumber)
    event_filter = Federation_contract.events.ServiceAnnouncement.createFilter(fromBlock=web3.toHex(blocknumber))
    return event_filter


# Providers analyze the requirements and place a bid offer to the Federation SC
def PlaceBid(service_id, service_price):
    global nonce
    # Build the transaction for the PlaceBid function
    place_bid_transaction = Federation_contract.functions.PlaceBid(
        _id=web3.toBytes(text=service_id),
        _price=service_price,
        _endpoint=web3.toBytes(text=service_endpoint_provider)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(place_bid_transaction)
    nonce += 1

    block = web3.eth.getBlock('latest')
    block_number = block['number']
    print("\nLatest block:", block_number)

    event_filter = Federation_contract.events.ServiceAnnouncementClosed.createFilter(fromBlock=web3.toHex(block_number))

    return event_filter

# Returns True if the consumer has choosen a provider and False in other cases ***
def CheckWinner(service_id):
    state = GetServiceState(service_id)
    result = False
    if state == 1:
        result = Federation_contract.functions.isWinner(_id=web3.toBytes(text=service_id), _winner=block_address).call()
        print("Am I a Winner? ", result)
    return result

# Provider AD confirms the operation by sending transaction to the Federation SC.
# The Federation SC records the successful deployment and initiates charging for the federated service
def ServiceDeployed(service_id, external_ip):
    global nonce
    # Build the transaction for the ServiceDeployed function
    service_deployed_transaction = Federation_contract.functions.ServiceDeployed(
        info=web3.toBytes(text=external_ip),
        _id=web3.toBytes(text=service_id)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(service_deployed_transaction)
    nonce += 1

def DisplayServiceState(serviceID):
    current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=serviceID)).call()
    if current_service_state == 0:
        print("\nService state", "Open")
    elif current_service_state == 1:
        print("\nService state", "Closed")
    elif current_service_state == 2:
        print("\nService state", "Deployed")
    else:
        print(f"Error: state for service {serviceID} is {current_service_state}")


def get_kubernetes_server_version():
    try:
        # Load the Kubernetes configuration
        config.load_kube_config()

        # Create an instance of the Kubernetes API client
        api_client = client.VersionApi()

        # Retrieve the server version
        api_response = api_client.get_code()
        server_version = api_response.git_version

        return server_version
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None


def get_service_deployed_info():
    # Execute the 'osm project-list' command and capture the output
    output = subprocess.check_output(['osm', 'project-list']).decode('utf-8')

    # Process the output to extract the ID of the OSM project
    lines = output.strip().split('\n')
    header = [column.strip() for column in lines[1].split('|') if column.strip()]
    data = [value.strip() for value in lines[3].split('|') if value.strip()]
    id_index = header.index('id')
    project_id = data[id_index]

    # Execute the 'kubectl get services' command and capture the output
    output = subprocess.check_output(['kubectl', 'get', 'services', '-n', project_id]).decode('utf-8')

    # Process the output to extract the external ip assigned by the loadbalancer of the provider, so that it can be used by the consumer.
    lines = output.strip().split('\n')
    header = lines[0].split()
    data = lines[1].split()
    external_ip_index = header.index('EXTERNAL-IP')
    external_ip = data[external_ip_index]

    return external_ip

# Returns the id of the vnfd
def create_nfpkg(package_path):
    command = f"osm nfpkg-create {package_path}"
    output = subprocess.check_output(command, shell=True, text=True).strip().split('\n')[-1]
    return output

# Returns the id of the nsd
def create_nspkg(package_path):
    command = f"osm nspkg-create {package_path}"
    output = subprocess.check_output(command, shell=True, text=True).strip().split('\n')[-1]
    return output


def create_nsi(ns_name, wait):
    config_file = f"descriptors/{nsd_name}/params/params.yaml"
    command = f"osm ns-create --ns_name {ns_name} --nsd_name {nsd_name} --vim_account {vim_name} --config_file {config_file}"
    if wait: 
        command += " --wait"
    output = subprocess.check_output(command, shell=True, text=True).strip().split('\n')[-1]
    return output


def upgrade_nsi(ns_name, replicas, wait):
    # openldap_ns -> string, nginx_ns -> integer
    if nsd_name == "openldap_ns":
        params = f'{{"replicaCount": "{replicas}"}}' 
    if nsd_name == "nginx_ns":
        params = f'{{"replicaCount": {replicas}}}'
    command = f"osm ns-action {ns_name} --vnf_name {member_vnf_index} --kdu_name {kdu_name} --action_name upgrade --params '{params}'"
    if wait:
        command += " --wait"
    output = subprocess.check_output(command, shell=True, text=True).strip().split('\n')[-1]
    return output

def delete_nsi(ns_name, wait):
    command = f"osm ns-delete {ns_name}"
    if wait:
        command += " --wait"
    subprocess.check_output(command, shell=True)


def clean_all():
    command = f'osm nsd-delete {nsd_name}'
    subprocess.check_output(command, shell=True)
    command = f'osm vnfd-delete {vnfd_name}'
    subprocess.check_output(command, shell=True)
    command = f'osm k8scluster-delete {cluster_name} --wait'
    subprocess.check_output(command, shell=True)
    command = f'osm repo-delete bitnami'
    subprocess.check_output(command, shell=True)
    command = f'osm vim-delete {vim_name} --wait'
    subprocess.check_output(command, shell=True)


def create_csv_file(file_name, header, data):
    with open(file_name, 'w', encoding='UTF8', newline='') as f:
        writer = csv.writer(f)

        # Write the header
        writer.writerow(header)

        # Write the data
        writer.writerows(data)


# -------------------------------------------- OSM API FUNCTIONS --------------------------------------------#
@app.post("/osm_create_dummy_vim", summary="Create a new dummy VIM account", tags=["OSM Functions"],
description="""
```bash
osm vim-create --name {vim_name} --user u --password p --tenant p --account_type dummy --auth_url http://localhost/dummy
```
""")
def osm_create_dummy_vim():
    user = 'u'
    password = 'p'
    vim_type = 'dummy'
    auth_url = 'http://localhost/dummy'
    try:
        cmd = subprocess.run(
            ['osm', 'vim-create', '--name', vim_name, '--user', user, '--password', password, '--tenant', 'p', '--account_type', vim_type, '--auth_url', auth_url, '--wait'],
            capture_output=True,
            text=True,
            check=True
        )
        output = cmd.stdout.strip() if cmd.stdout is not None else ''  # Check if stdout is None
        return {"message": "New VIM account created", "ID": output, "Name": vim_name, "Type": vim_type, "User": user, "Password": password, "URL": auth_url}
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip() if e.stderr is not None else ''  # Check if stderr is None
        return {"message": "Error creating VIM account", "error": error_output}


@app.post("/osm_K8s_cluster_add", summary="Add a K8s cluster to OSM", tags=["OSM Functions"],
description="""
```bash
osm k8scluster-add {cluster_name} --creds ~/.kube/config --vim {vim_name} --k8s-nets '{k8s_net1: null}' --version "{k8s_cluster_version}" --description="Isolated K8s cluster"
```
""")
def osm_K8s_cluster_add():
    kube_config = os.path.expanduser("~/.kube/config")
    k8s_cluster_version = get_kubernetes_server_version()
    try:
        # Add helm repo to OSM for using nginx
        cmd = subprocess.run(
            ['osm', 'repo-add', '--type', 'helm-chart', '--description', 'Bitnami repo', 'bitnami', 'https://charts.bitnami.com/bitnami'],
            capture_output=True,
            text=True,
            check=True
        )
        cmd = subprocess.run(
            ['osm', 'k8scluster-add', cluster_name, '--creds', kube_config, '--vim', vim_name, '--k8s-nets', '{k8s_net1: null}', '--version', k8s_cluster_version, '--description=Isolated K8s cluster', '--wait'],
            capture_output=True,
            text=True,
            check=True
        )
        output = cmd.stdout.strip() if cmd.stdout is not None else ''  # Check if stdout is None
        return {"message": "New K8s cluster added to OSM", "Name": cluster_name, "ID": output, "Associated VIM": vim_name}
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip() if e.stderr is not None else ''  # Check if stderr is None
        return {"message": "Error adding K8s cluster to OSM", "error": error_output}

@app.post("/osm_select_descriptors/{descriptor}", summary="Select the descriptors you are going to use", tags=["OSM Functions"])
def osm_select_descriptors(descriptor: DescriptorEnum):
    select_descriptor(descriptor)
    return {"Descriptor selected": descriptor, "NSD": nsd_name, "VNFD": vnfd_name, "KDU": kdu_name}

@app.post("/osm_onboard_descriptors", summary="Creates the VNFD and NSD packages and upload them to OSM", tags=["OSM Functions"],
description="""
```bash
osm nfpkg-create {vnfd_name}
osm nspkg-create {nsd_name}
```
""")
def osm_onboard_descriptors():
    vnfd_path = "descriptors/" + vnfd_name
    nsd_path = "descriptors/" + nsd_name

    vnf_id = create_nfpkg(vnfd_path)
    ns_id = create_nspkg(nsd_path)
    vnf_info = {
        "Name": vnfd_name,
        "ID":  vnf_id,
        "KDU": kdu_name
    }
    ns_info = {
        "Name": nsd_name,
        "ID":  ns_id
    }
    return {"message": "VNFD/NSD packages onboarded to OSM", "VNFD info": vnf_info, "NSD info": ns_info}

@app.post("/osm_create_NS_instance/{ns_name}/{wait}", tags=["OSM Functions"], 
summary="Create a new Network Service instance",
description="""
```bash
osm ns-create --ns_name {ns_name} --nsd_name {nsd_name} --vim_account {vim_name} --config_file descriptors/{nsd_name}/params/params.yaml
```
""")
def osm_create_NS_instance(ns_name: str, wait: bool):
    nsi_id = create_nsi(ns_name, wait)
    nsi_info = {
        "Name": ns_name,
        #"Replicas": replicas,
        "ID":  nsi_id
    }
    return {"message": "Network Service instance created", "NSI info": nsi_info}


@app.patch("/osm_upgrade_NS_instance/{ns_name}/{replicas}/{wait}", tags=["OSM Functions"],
summary="Change the number of replicas (pods) of an existing service",
description="""
```bash
osm ns-action {ns_name} --vnf_name {vnf_name} --kdu_name {kdu_name} --action_name upgrade --params '{"replicaCount": "{replicas}"}'
```
""")
def osm_upgrade_NS_instance(ns_name: str, replicas: str, wait: bool):
    nsi_id = upgrade_nsi(ns_name, replicas, wait)
    nsi_info = {
        "Name": ns_name,
        "Replicas": replicas,
        "ID":  nsi_id
    }
    return {"message": "Network Service instance upgraded", "NSI info": nsi_info}


@app.delete("/osm_delete_NS_instance/{ns_name}/{wait}", tags=["OSM Functions"],
summary="Delete an existing Network Service instance",
description="""
```bash
osm ns-delete {ns_name} 
```
""")
def osm_delete_NS_instance(ns_name: str, wait: bool):
    delete_nsi(ns_name, wait)
    return {"message": f"{ns_name} instance has been deleted successfully"}


@app.delete("/osm_clean_all", tags=["OSM Functions"],
summary="Delete NSD and VNFD packages, K8s cluster and VIM account from OSM",
description="""
**Make sure you don't have any active Network Services!**

```bash
osm nsd-delete {nsd_name}
osm vnfd-delete {vnfd_name}
osm k8scluster-delete {cluster_name} --wait
osm vim-delete {vim_name} --wait
```
""")
def osm_clean_all():
    clean_all()
    return {"message": "All OSM components (NSD, VNFD, K8sCluster, VIM) have been deleted successfully"}


@app.post("/kubernetes_enable_monitoring", tags=["Kubernetes Functions"],
summary="Enable monitoring in the Kubernetes cluster with Grafana and Prometheus")
def kubernetes_enable_monitoring():
    #subprocess.run(['helm', 'repo', 'add', 'prom-repo', 'https://prometheus-community.github.io/helm-charts'])
    #time.sleep(3)
    command = [
        'helm',
        'install',
        'monitoring',
        'prom-repo/kube-prometheus-stack',
        '-n', 'monitoring',
        '--create-namespace',
        '--values=grafana_conf/grafana_values.yaml'
    ]   
    subprocess.run(command)
    return {"message": "Grafana and Prometheus have been installed successfully"}


@app.delete("/kubernetes_disable_monitoring", tags=["Kubernetes Functions"],
summary="Disable monitoring in the Kubernetes cluster with Grafana and Prometheus")
def kubernetes_disable_monitoring():
    command = [
        'helm',
        'uninstall',
        'monitoring',
        '-n', 'monitoring'
    ]
    subprocess.run(command)
    #subprocess.run(['helm', 'repo', 'remove', 'prom-repo'])
    #time.sleep(3)
    return {"message": "Grafana and Prometheus have been disabled successfully"}
# ------------------------------------------------------------------------------------------------------------------------------#



# -------------------------------------------- DLT API FUNCTIONS --------------------------------------------#
@app.get("/", 
summary="Web3 and Ethereum node info",
tags=["Default DLT Functions"],
description="Get detailed information about the Web3 connection and Ethereum node")
def web3_info():
    print('\nAccounts:',eth_address)
    print("\nEtherbase:", coinbase)
    print("\n\033[1m" + "IP address: " + str(ipaddress) + "\033[0m")
    print("\033[1m" + "Ethereum address: " + str(block_address) + "\033[0m")
    print("Federation contract:\n", Federation_contract.functions)
    message = {
        "Accounts": eth_address,
        "Miner address": coinbase,
        "IP address": ipaddress,
        "Ethereum address": block_address,
        "Contract address": contract_address,
        "Domain name": domain_name,
        "Service ID": service_id
    }
    return {"Web3 info": message}

@app.post("/register_domain",
tags=["Default DLT Functions"],
description="""
This function registers a domain in the smart contract by calling the addOperator function
""")
def register_domain():
    global domain_registered  
    global nonce
    if domain_registered == False:
        
        # Build the transaction for the addOperator function
        add_operator_transaction = Federation_contract.functions.addOperator(Web3.toBytes(text=domain_name)).buildTransaction({
            'from': block_address,
            'nonce': nonce
        })

        # Send the signed transaction
        tx_hash = send_signed_transaction(add_operator_transaction)
        nonce += 1

        domain_registered = True
        print("\n\033[1;32m(TX) Domain has been registered\033[0m")
        return {"Transaction": f"Domain {domain_name} has been registered"}
    else:
        return {"error": "Domain already registered"}


@app.post("/create_service_announcement", 
tags=["Consumer Functions"],
description="""
Triggered by the consumer domain, once it has beed decided the need of federate part of a service, 
an announcement is broadcast to all potential provider ADs. The announcement conveys the requirements for a given service.
""")
def create_service_announcement():
    global bids_event
    bids_event = AnnounceService()
    print("\n\033[1;32m(TX-1) Service announcement sent to the SC\033[0m")
    return {"Transaction": "Service announcement sent to the SC", "From": f"{domain_name} - {block_address}"}


@app.get("/check_service_state/{service_id}",
tags=["Default DLT Functions"],
description="""
This function retrieves the current state of a service specified by its ID by calling the GetServiceState function of the smart contract. 
If the state is 0, it means the service is open, 1 means the service is closed, and 2 means the service has been deployed
""")
def check_service_state(service_id: str):
    current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=service_id)).call()
    if current_service_state == 0:
        return {"Service ID": service_id, "State": "Open"}
    elif current_service_state == 1:
        return {"Service ID": service_id, "State": "Closed"}
    elif current_service_state == 2:
        return {"Service ID": service_id, "State": "Deployed"}
    else:
        return { "Error" : f"Service ID {service_id}, state is {current_service_state}"}
    



@app.get("/check_deployed_info/{service_id}", tags=["Default DLT Functions"])
def check_deployed_info(service_id: str):
    service_id_bytes = web3.toBytes(text=service_id)  # Convert string to bytes
    service_id, service_endpoint_provider, external_ip = Federation_contract.functions.GetServiceInfo(_id=service_id_bytes, provider=False, call_address=block_address).call()
    _service_id = service_id.rstrip(b'\x00')  # Apply rstrip on bytes-like object
    _service_endpoint_provider = service_endpoint_provider.rstrip(b'\x00')
    _external_ip = external_ip.rstrip(b'\x00')
    return {"Service ID": _service_id, "Service endpoint provider": _service_endpoint_provider, "External IP": _external_ip}


@app.get("/check_service_announcements", 
tags=["Provider Functions"],
description=""" 
Retrieves new service announcements, checks their state, and returns a JSON response with the details of any open services found or a message indicating no new events. 
""")
def check_service_announcements():

    new_service_event = ServiceAnnouncementEvent()
    open_services = []
    new_events = new_service_event.get_all_entries()

    message = ""
    for event in new_events:
        service_id = web3.toText(event['args']['id']).rstrip('\x00')
        requirements = web3.toText(event['args']['requirements']).rstrip('\x00')
        tx_hash = web3.toHex(event['transactionHash'])
        address =  event['address']
        block_number = event['blockNumber']
        if 'event' in event['args']:
            event_name = web3.toText(event['args']['event'])
        else:
            event_name = ""

        if GetServiceState(service_id) == 0:
            open_services.append(service_id)
    
    if len(open_services) > 0:
        message = {
            "Service ID": service_id,
            "Requirements": requirements,
            "TX HASH": tx_hash,
            "Contract address": address,
            "Block": block_number
        }
        print('Announcement received:')
        print(new_events)

        return {"Announcement received": message}
    else:
        return {"No new events found": message}


@app.post("/place_bid/{service_id}-{service_price}", tags=["Provider Functions"],
description="""
This function allows a provider to place a bid for a service by providing the service ID and the bid price. 
It sends the bid offer to the smart contract and returns a JSON response indicating the transaction details.
""")
def place_bid(service_id: str, service_price: int):
    global winnerChosen_event 
    winnerChosen_event  = PlaceBid(service_id, service_price)
    print("\n\033[1;32m(TX-2) Bid offer sent to the SC\033[0m")
    return {"Transaction": "Bid offer sent to the Smart Contract", "Price(₿)": service_price, "From": f"{domain_name} - {block_address}"}


@app.get('/check_bids/{service_id}', tags=["Consumer Functions"],
description="""
This function allows a consumer to check for new bids for a specific service by providing the service ID. 
It retrieves the new bid events, checks for the highest bid index, and returns a JSON response with the bid information if any new bids are found
""")
def check_bids(service_id: str):
    global bids_event
    message = ""
    new_events = bids_event.get_all_entries()
    bidderArrived = False
    for event in new_events:
        # New bid received
        event_id = str(web3.toText(event['args']['_id']))
        # service id, service id, index of the bid
        print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
                
        bid_index = int(event['args']['max_bid_index'])
        bidderArrived = True 
        if int(bid_index) < 2:
            print("\nBids-info = [provider address , service price , bid index]\n")
            bid_info = GetBidInfo(int(bid_index-1))
            print(bid_info)
            message = {
                "Provider address": bid_info[0],
                "Service price": bid_info[1],
                "Bid index": bid_info[2]
            }
            break
    if bidderArrived:
        return {"message": f"There are new bids for the service {service_id}", "Bid info": message}

    else:
        return {"message": f"There are no bids yet for the service {service_id}"}


@app.post('/choose_provider/{bid_index}', tags=["Consumer Functions"],
description="""
This function allows a consumer to choose a provider for a service by specifying the bid index. 
It retrieves the bid events, chooses the provider associated with the specified bid index, and returns a JSON response indicating the transaction details.
""")
def choose_provider(bid_index: int):
    global bids_event
    new_events = bids_event.get_all_entries()
    for event in new_events:
        event_id = str(web3.toText(event['args']['_id'])).rstrip('\x00')
        print("\n\033[1;32m(TX-3) Provider choosen! (bid index=" + str(bid_index) + ")\033[0m")
        ChooseProvider(bid_index)
        # Service closed (state 1)
    return {"Transaction": f"Provider choosen!", "Service ID": event_id, "Bid index": bid_index}    


@app.get("/check_winner/{service_id}", tags=["Provider Functions"],
description="""
Ths function allows a provider to check if there is a winner for a specific service by providing the service ID. 
""")
def check_winner(service_id: str):
    global winnerChosen_event 

    new_events = winnerChosen_event.get_all_entries()

    winnerChosen = False
    # Ask to the Federation SC if there is a winner
    for event in new_events:
        event_serviceid = web3.toText(event['args']['_id']).rstrip('\x00')
        if event_serviceid == service_id:
            # Winner choosen
            winnerChosen = True
            break
    if winnerChosen:
        return {"message": f"There is a winner for the service {service_id}"}

    else:
        return {"message": f"There is no winner yet for the service {service_id}"}


@app.get("/check_if_I_am_Winner/{service_id}", tags=["Provider Functions"],
description="""
Ths function allows a provider to check if he is the winner for a specific service by providing the service ID. 
""")
def check_if_I_am_Winner(service_id: str):
     # Provider AD ask if he is the winner
    am_i_winner = CheckWinner(service_id)
    if am_i_winner == True:
        print("I am a Winner")
        return {"message": f"I am the winner for the service {service_id}"}
    else:
        print("I am not a Winner")
        return {"message": f"I am not the winner for the service {service_id}"}


@app.post("/deploy_service/{service_id}", tags=["Provider Functions"],
description="""
Provider AD starts the deployment of the requested federated service. Once it has been deployed, he confirms the operation by sending transaction to the smart contract.
The smart contract records the successful deployment and initiates charging for the federated service
""")
def deploy_service(service_id: str):
    if CheckWinner(service_id):

        federated_ns_name = "federated_service"
        federated_nsi_id = create_nsi(federated_ns_name, True)
        #federated_nsi_id = 5
        federated_nsi_info = {
            "Name": federated_ns_name,
            "ID":  federated_nsi_id
        }
        ServiceDeployed(service_id, ipaddress)
        print("\n\033[1;32m(TX-4) Service deployed\033[0m")
        return {"Transaction": "Service deployed", "Service Info": federated_nsi_info}
    else:
        return {"Error": "You are not the winner"}   
# ------------------------------------------------------------------------------------------------------------------------------#

def check_federated_service_connection(external_ip):
    url = "http://" + external_ip  # IP of the requested federated service
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return True, response.content.decode('utf-8')
    except requests.exceptions.RequestException:
        pass

    return False, None



# -------------------------------------------- TEST DEPLOYMENT: DLT WITH OSM-K8s --------------------------------------------#
@app.get("/consumer_code", tags=["Test deployment: federation of a K8s service in OSM"])
def consumer_code():

    header = ['step', 'timestamp']
    data = []
    
    if domain == 'consumer':
        
        # Start time of the process
        process_start_time = time.time()
        
        global bids_event

        # Consumer creates a Network Service Instance composed of 1 KNF (Kubernetes Network Function)
        #nsi_id = create_nsi("test", True)
       
        print("\nSERVICE_ID:", service_id) # service + timestamp
        
        # Service Announcement Sent
        t_serviceAnnouncementSent = time.time() - process_start_time
        data.append(['serviceAnnouncementSent', t_serviceAnnouncementSent])
        bids_event = AnnounceService()

        print("\n\033[1;32m(TX-1) Service announcement sent to the SC\033[0m")

        # Consumer AD wait for provider bids
        bidderArrived = False

        print("Waiting for bids...\n")
        while bidderArrived == False:
            new_events = bids_event.get_all_entries()
            for event in new_events:
                
                # Bid Offer Received
                t_bidOfferReceived = time.time() - process_start_time
                data.append(['bidOfferReceived', t_bidOfferReceived])

                event_id = str(web3.toText(event['args']['_id']))
                
                # Choosing provider
                t_choosingProvider = time.time() - process_start_time
                data.append(['choosingProvider', t_choosingProvider])

                # service id, service id, index of the bid
                print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
                print("BIDS ENTERED")
                bid_index = int(event['args']['max_bid_index'])
                bidderArrived = True 
                if int(bid_index) < 2:

                    #print("\nBids-info = [provider address , service price , bid index]\n")
                    bid_info = GetBidInfo(int(bid_index-1))
                    print(bid_info)
                    
                    # Provider choosen
                    t_providerChoosen = time.time() - process_start_time
                    data.append(['providerChoosen', t_providerChoosen])
                    ChooseProvider(int(bid_index)-1)

                    # Winner choosen sent
                    t_winnerChoosenSent = t_providerChoosen
                    data.append(['winnerChoosenSent', t_winnerChoosenSent])

                    print("\n\033[1;32m(TX-3) Provider choosen! (bid index=" + str(bid_index-1) + ")\033[0m")

                    # Service closed (state 1)
                    #DisplayServiceState(service_id)
                    break

        # Consumer AD wait for provider confirmation
        serviceDeployed = False 
        while serviceDeployed == False:
            serviceDeployed = True if GetServiceState(service_id) == 2 else False
        
        # Confirmation received
        t_confirmDeploymentReceived = time.time() - process_start_time
        data.append(['confirmDeploymentReceived', t_confirmDeploymentReceived])
        
        t_checkConnectivityFederatedServiceStart = time.time() - process_start_time
        data.append(['checkConnectivityFederatedServiceStart', t_checkConnectivityFederatedServiceStart])

        # Service deployed info
        external_ip, service_endpoint_provider = GetDeployedInfo(service_id)
        
        external_ip = external_ip.decode('utf-8')
        service_endpoint_provider = service_endpoint_provider.decode('utf-8')

        print("Service deployed info:")
        print("External IP:", external_ip)
        print("Service endpoint provider:", service_endpoint_provider)


        # Establish connectivity with the federated service
        connected = False
        while not connected:
            connected, response_content = check_federated_service_connection(external_ip)
            if not connected:
                print("Failed to establish connection with the federated service. Retrying...")
        
        t_checkConnectivityFederatedServiceFinished = time.time() - process_start_time
        data.append(['checkConnectivityFederatedServiceFinished', t_checkConnectivityFederatedServiceFinished])

        print("Successfully connected to the federated service")
        print(response_content)

        # Export the data to a csv file
        create_csv_file('federation_private_network_consumer.csv', header, data)

        return {"message": "Federation process (which involves announcement offer, negotiation and acceptance) successful"}
    else:
        return {"error": "You must be consumer to run this code"}


@app.get("/provider_code", tags=["Test deployment: federation of a K8s service in OSM"])
def provider_code():
    
    header = ['step', 'timestamp']
    data = []
    
    if domain == 'provider':
        
        # Start time of the process
        process_start_time = time.time()

        global winnerChosen_event 
        service_id = ''
        print("\nSERVICE_ID:",service_id)

        newService_event = ServiceAnnouncementEvent()
        newService = False
        open_services = []

        # Provider AD wait for service announcements
        while newService == False:
            new_events = newService_event.get_all_entries()
            for event in new_events:
                service_id = web3.toText(event['args']['id'])
                
                requirements = web3.toText(event['args']['requirements'])

                requested_service = requirements.split("=")[1]
                # Removes null characters at the end of the string
                requested_service = requested_service.rstrip('\x00') 
                
                if GetServiceState(service_id) == 0:
                    open_services.append(service_id)
            print("OPEN =", len(open_services)) 
            if len(open_services) > 0:
                
                # Announcement received
                t_serviceAnnouncementReceived = time.time() - process_start_time
                data.append(['serviceAnnouncementReceived', t_serviceAnnouncementReceived])

                print('Announcement received:')
                print(new_events)
                print("\n\033[1;33mRequested service: " + repr(requested_service) + "\033[0m")
                newService = True
            
        service_id = open_services[-1]

        # Place a bid offer to the Federation SC
        t_bidOfferSent = time.time() - process_start_time
        data.append(['bidOfferSent', t_bidOfferSent])
        winnerChosen_event = PlaceBid(service_id, 10)

        print("\n\033[1;32m(TX-2) Bid offer sent to the SC\033[0m")
        
        # Ask to the Federation SC if there is a winner (wait...)
    
        winnerChosen = False
        while winnerChosen == False:
            new_events = winnerChosen_event.get_all_entries()
            for event in new_events:
                event_serviceid = web3.toText(event['args']['_id'])
                if event_serviceid == service_id:
                    
                    # Winner choosen received
                    t_winnerChoosenReceived = time.time() - process_start_time
                    data.append(['winnerChoosenReceived', t_winnerChoosenReceived])

                    winnerChosen = True
                    break
        
        # Provider AD ask if he is the winner
        am_i_winner = CheckWinner(service_id)
        if am_i_winner == True:
            
            # Start deployment of the requested federated service
            t_deploymentStart = time.time() - process_start_time
            data.append(['deploymentStart', t_deploymentStart])

            # Deployment of the NSI in OSM...
            nsi_id = create_nsi("federated_service", True)


            # IP address of the service deployed by the provider
            external_ip = get_service_deployed_info()

            # Deployment finished
            t_deploymentFinished = time.time() - process_start_time
            data.append(['deploymentFinished', t_deploymentFinished])
            
    
            # Deployment confirmation sent
            t_confirmDeploymentSent = time.time() - process_start_time
            data.append(['confirmDeploymentSent', t_confirmDeploymentSent])
            ServiceDeployed(service_id, external_ip)
            
            print("\n\033[1;32m(TX-4) Service deployed\033[0m")
            print("External IP:", external_ip)
            DisplayServiceState(service_id)
            
            # Export the data to a csv file
            create_csv_file('federation_private_network_provider.csv', header, data)
            
            return {"message": "Federation process (which involves announcement offer, negotiation and acceptance) successful"}

        else:
            print("I am not a Winner")
            return {"error": "I am not a Winner"}

    else:
        return {"error": "You must be provider to run this code"}
# ------------------------------------------------------------------------------------------------------------------------------#



