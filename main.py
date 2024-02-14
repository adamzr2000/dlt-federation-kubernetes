import os
import json
import time
import yaml

from dotenv import load_dotenv
from web3 import Web3, HTTPProvider, WebsocketProvider
from web3.middleware import geth_poa_middleware
from fastapi import FastAPI, HTTPException
from kubernetes import client, config
from kubernetes.client.rest import ApiException


# Define your tags
tags_metadata = [
    {
        "name": "Default DLT Functions",
        "description": "General DLT operations that are applicable to both consumers and providers.",
    },
    {
        "name": "Consumer Functions",
        "description": "Operations specifically designed for consumers in the DLT network.",
    },
    {
        "name": "Provider Functions",
        "description": "Operations specifically designed for providers in the DLT network.",
    },
]

app = FastAPI(
    title="DLT Federation with K8s API Documentation",
    openapi_tags=tags_metadata,
    description="""
- This API provides endpoints for interacting with the DLT network and Kubernetes orchestrator.

- The federation procedures are stored and deployed on a Federation Smart Contract, which is running on top of a private blockchain network (Ethereum).

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
"""
)



# Initial setup: Determine domain and load environment variables
domain = input("Domain function (consumer/provider): ").strip().lower()
while domain not in ["consumer", "provider"]:
    print("Invalid input. Please enter 'consumer' or 'provider'.")
    domain = input("Domain function (consumer/provider): ").strip().lower()

# Load environment variables
load_dotenv('./dlt-network-docker/.env')
load_dotenv('./smart-contracts/.env', override=True)

# Configure Web3
eth_node_url = os.getenv(f'WS_NODE_{"1" if domain == "consumer" else "2"}_URL')
try:
    web3 = Web3(WebsocketProvider(eth_node_url))
    web3.middleware_onion.inject(geth_poa_middleware, layer=0)

    # Check if connected to the Ethereum node
    if web3.isConnected():
        # Attempt to get the Geth version to confirm a successful connection
        geth_version = web3.clientVersion
        print(f"Successfully connected to Ethereum node successfully (version={geth_version}")
    else:
        print("Failed to connect to the Ethereum node.")
except Exception as e:
    print(f"An error occurred while trying to connect to the Ethereum node: {e}")

# Load smart contract ABI
contract_abi = json.load(open("smart-contracts/build/contracts/Federation.json"))["abi"]
contract_address = web3.toChecksumAddress(os.getenv('CONTRACT_ADDRESS'))
Federation_contract = web3.eth.contract(abi=contract_abi, address=contract_address)

# Retrieve private key and blockchain address for the domain
private_key = os.getenv(f'PRIVATE_KEY_NODE_{"1" if domain == "consumer" else "2"}')
block_address = os.getenv(f'ETHERBASE_NODE_{"1" if domain == "consumer" else "2"}')

# General setup
ip_address = os.popen('ip a | grep 10.5.50').read().split('inet ', 1)[1].split('/', 1)[0]

# Number that is used to prevent transaction replay attacks and ensure the order of transactions.
nonce = web3.eth.getTransactionCount(block_address)

# Address of the miner (node that adds a block to the blockchain)
coinbase = block_address

# Initialize variables
service_id = ''
service_endpoint_consumer = ''
service_consumer_address = ''
service_requirements = ''
bids_event = None
service_endpoint_provider = ''
federated_host = ''
service_price = 0
bid_index = 0
winner = coinbase
manager_address = ''
winnerChosen_event = None
service_endpoint = ''
domain_registered = False

# Initialize domain-specific configurations and variables
if domain == "consumer":
    # Consumer-specific variables
    service_id = 'service' + str(int(time.time()))
    service_endpoint_consumer = ip_address
    service_consumer_address = block_address
    service_requirements = 'service='
    bids_event = None  # Placeholder for event listener setup
    domain_name = "AD1"

    # Load Kubernetes configuration
    config.load_kube_config(config_file=os.path.join(os.getcwd(), "k8s-cluster-config", "microk8s-1-config"))

else:  # Provider
    # Provider-specific variables
    service_endpoint_provider = ip_address
    federated_host = ''  # Placeholder for federated service deployment
    service_price = 0
    bid_index = 0
    winner = web3.eth.accounts[0]  # Assuming the first account as the default winner for simplicity
    manager_address = ''  # Placeholder for manager contract address
    winnerChosen_event = None  # Placeholder for event listener setup
    domain_name = "AD2"

    # Load Kubernetes configuration
    config.load_kube_config(config_file=os.path.join(os.getcwd(), "k8s-cluster-config", "microk8s-2-config"))

print(f"Configuration complete for {domain_name} with IP {ip_address}.")

# CoreV1Api provides access to core components of Kubernetes such as pods, namespaces, and services.
api_instance_coreV1 = client.CoreV1Api()

# AppsV1Api provides access to functionalities related to deploying and managing applications within Kubernetes. 
# This includes managing deployments, stateful sets, and other application controllers
api_instance_appsV1 = client.AppsV1Api()

# Validate connectivity to Kubernetes and get the version information
try:
    version_info = client.VersionApi().get_code()
    print(f"Successfully connected to Kubernetes client API (version={version_info.git_version})")
except Exception as e:
    print(f"Failed to connect to Kubernetes client API: {e}")

#-------------------------- Initialize TEST variables ------------------------------#
# List to store the timestamps of each federation step
federation_step_times = []
#----------------------------------------------------------------------------------#

def send_signed_transaction(build_transaction):
    """
    Sends a signed transaction to the blockchain network using the private key.
    
    Args:
        build_transaction (dict): The transaction data to be sent.
    
    Returns:
        str: The transaction hash of the sent transaction.
    """
    global nonce
    # Sign the transaction
    signed_txn = web3.eth.account.signTransaction(build_transaction, private_key)

    # Send the signed transaction
    tx_hash = web3.eth.sendRawTransaction(signed_txn.rawTransaction)

    # Increment the nonce
    nonce += 1

    return tx_hash

def AnnounceService():
    """
    Consumer AD announces the need for a federated service. 
    This transaction includes the service requirements, consumer's endpoint, and a unique service identifier.
    
    Returns:
        Filter: A filter for catching the 'NewBid' event that is emitted when a new bid is placed for the announced service.
    """
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
    
    block = web3.eth.getBlock('latest')
    block_number = block['number']
    
    event_filter = Federation_contract.events.NewBid.createFilter(fromBlock=web3.toHex(block_number))
    
    return event_filter

def GetBidInfo(bid_index):
    """
    Consumer AD retrieves information about a specific bid based on its index.
    
    Args:
        bid_index (int): The index of the bid for which information is requested.
    
    Returns:
        tuple: Contains information about the bid.
    """
    bid_info = Federation_contract.functions.GetBid(_id=web3.toBytes(text=service_id), bider_index=bid_index, _creator=block_address).call()
    return bid_info

def ChooseProvider(bid_index):
    """
    Consumer AD chooses a provider from the list of bids based on the bid index. 
    
    Args:
        bid_index (int): The index of the bid that identifies the chosen provider.
    """
    choose_transaction = Federation_contract.functions.ChooseProvider(
        _id=web3.toBytes(text=service_id),
        bider_index=bid_index
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(choose_transaction)

def GetServiceState(serviceid):
    """
    Returns the current state of the service identified by the service ID.
    
    Args:
        serviceid (str): The unique identifier of the service.
    
    Returns:
        int: The state of the service (0 for Open, 1 for Closed, 2 for Deployed).
    """    
    service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=serviceid)).call()
    return service_state

def GetDeployedInfo(service_id):
    """
    Consumer AD retrieves the deployment information of a service, including the service ID, provider's endpoint, and external IP (exposed IP for the federated service).
    
    Args:
        service_id (str): The unique identifier of the service.
    
    Returns:
        tuple: Contains the external IP and provider's endpoint of the deployed service.
    """    
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
    """
    Creates a filter to catch the 'ServiceAnnouncement' event emitted when a service is announced. This function
    can be used to monitor new service announcements in real-time.
    
    Returns:
        Filter: A filter for catching the 'ServiceAnnouncement' event.
    """    
    block = web3.eth.getBlock('latest')
    blocknumber = block['number']
    print("\nLatest block:",blocknumber)
    event_filter = Federation_contract.events.ServiceAnnouncement.createFilter(fromBlock=web3.toHex(blocknumber))
    return event_filter


def PlaceBid(service_id, service_price):
    """
    Provider AD places a bid offer for a service, including the service ID, offered price, and provider's endpoint.
    
    Args:
        service_id (str): The unique identifier of the service for which the bid is placed.
        service_price (int): The price offered for providing the service.
    
    Returns:
        Filter: A filter for catching the 'ServiceAnnouncementClosed' event that is emitted when a service
                announcement is closed.
    """
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

    block = web3.eth.getBlock('latest')
    block_number = block['number']
    print("\nLatest block:", block_number)

    event_filter = Federation_contract.events.ServiceAnnouncementClosed.createFilter(fromBlock=web3.toHex(block_number))

    return event_filter

def CheckWinner(service_id):
    """
    Checks if the caller is the winning provider for a specific service after the consumer has chosen a provider.
    
    Args:
        service_id (str): The unique identifier of the service.
    
    Returns:
        bool: True if the caller is the winning provider, False otherwise.
    """
    state = GetServiceState(service_id)
    result = False
    if state == 1:
        result = Federation_contract.functions.isWinner(_id=web3.toBytes(text=service_id), _winner=block_address).call()
        print("Am I a Winner? ", result)
    return result


def ServiceDeployed(service_id, external_ip):
    """
    Provider AD confirms the operation of a service deployment.
    This transaction includes the external IP and the service ID, and it records the successful deployment.
    
    Args:
        service_id (str): The unique identifier of the service.
        external_ip (str): The external IP address for the deployed service (~ exposed IP).
    """
    service_deployed_transaction = Federation_contract.functions.ServiceDeployed(
        info=web3.toBytes(text=external_ip),
        _id=web3.toBytes(text=service_id)
    ).buildTransaction({
        'from': block_address,
        'nonce': nonce
    })

    # Send the signed transaction
    tx_hash = send_signed_transaction(service_deployed_transaction)

def DisplayServiceState(serviceID):
    """
    Displays the current state of a service based on its ID. The state is printed to the console.
    
    Args:
        serviceID (str): The unique identifier of the service.
    """    
    current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=serviceID)).call()
    if current_service_state == 0:
        print("\nService state", "Open")
    elif current_service_state == 1:
        print("\nService state", "Closed")
    elif current_service_state == 2:
        print("\nService state", "Deployed")
    else:
        print(f"Error: state for service {serviceID} is {current_service_state}")


# def create_pod_from_yaml(k8s_api, yaml_file_path):
#     """
#     Creates a Kubernetes pod from a specified YAML file.

#     Parameters:
#     - k8s_api: CoreV1Api instance for Kubernetes API interactions.
#     - yaml_file_path: Path to the YAML file containing pod configuration.

#     Reads pod configuration from the YAML, creates the pod in the specified or default namespace, and prints the pod name.
#     """
#     try:
#         with open(yaml_file_path, 'r') as file:
#             pod_manifest = yaml.safe_load(file)
#         namespace = pod_manifest.get("metadata", {}).get("namespace", "default")
#         resp = k8s_api.create_namespaced_pod(body=pod_manifest, namespace=namespace)
#         print("Pod created:", resp.metadata.name)
#     except ApiException as e:
#         print(f"Exception when calling Kubernetes API: {e}")
#         raise

# def create_service_from_yaml(k8s_api, yaml_file_path):
#     """
#     Creates a Kubernetes service from a specified YAML file.

#     Parameters:
#     - k8s_api: An instance of CoreV1Api for Kubernetes API interactions.
#     - yaml_file_path: Path to the YAML file containing the service configuration.
#     """
#     try:
#         with open(yaml_file_path, 'r') as file:
#             service_manifest = yaml.safe_load(file)
#         resp = k8s_api.create_namespaced_service(body=service_manifest, namespace="default")
#         print("Service created:", resp.metadata.name)
#     except ApiException as e:
#         print(f"Exception when calling Kubernetes API: {e}")
#         raise

# def create_deployment_from_yaml(k8s_api, yaml_file_path):
#     """
#     Creates a Kubernetes deployment from a specified YAML file.

#     Parameters:
#     - k8s_api: An instance of AppsV1Api for Kubernetes API interactions.
#     - yaml_file_path: Path to the YAML file containing the deployment configuration.
#     """
#     try:
#         with open(yaml_file_path, 'r') as file:
#             deployment_manifest = yaml.safe_load(file)
#         resp = k8s_api.create_namespaced_deployment(body=deployment_manifest, namespace="default")
#         print("Deployment created:", resp.metadata.name)
#     except ApiException as e:
#         print(f"Exception when calling Kubernetes API: {e}")
#         raise

def create_resource_from_yaml(yaml_file_path):
    """
    Creates a Kubernetes resource (Pod, Service, Deployment) from a specified YAML file.

    Parameters:
    - yaml_file_path: Path to the YAML file containing the resource configuration.
    """
    try:
        with open(yaml_file_path, 'r') as file:
            resources = yaml.safe_load_all(file)
            for resource in resources:
                kind = resource.get("kind")
                namespace = resource.get("metadata", {}).get("namespace", "default")

                # Using dynamic dispatch to call the appropriate function based on the resource kind
                if kind == "Pod":
                    resp = client.CoreV1Api().create_namespaced_pod(body=resource, namespace=namespace)
                elif kind == "Service":
                    resp = client.CoreV1Api().create_namespaced_service(body=resource, namespace=namespace)
                elif kind == "Deployment":
                    resp = client.AppsV1Api().create_namespaced_deployment(body=resource, namespace=namespace)
                else:
                    raise ValueError(f"Unsupported resource kind: {kind}")

                print(f"{kind} created: {resp.metadata.name}")
    except ApiException as e:
        print(f"Exception when calling Kubernetes API: {e}")
        raise
    except ValueError as e:
        print(e)
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise

def delete_pod(k8s_api, pod_name, namespace='default'):
    """
    Deletes a specified pod within a given namespace.

    Parameters:
    - k8s_api: CoreV1Api instance of the Kubernetes client.
    - pod_name: String name of the pod to delete.
    - namespace: String name of the namespace where the pod is located. Defaults to 'default'.
    """
    try:
        # Delete the pod
        resp = k8s_api.delete_namespaced_pod(name=pod_name,
                                             namespace=namespace,
                                             body=client.V1DeleteOptions(),
                                             grace_period_seconds=0)
        print(f"Pod '{pod_name}' deleted.")
        return resp
    except ApiException as e:
        if e.status == 404:
            print(f"Pod '{pod_name}' not found.")
        else:
            print(f"Error deleting pod '{pod_name}': {e}")
        return None

def delete_service(k8s_api, service_name, namespace='default'):
    """
    Deletes a specified service within a given namespace.

    Parameters:
    - k8s_api: CoreV1Api instance of the Kubernetes client.
    - service_name: String name of the service to delete.
    - namespace: String name of the namespace where the service is located. Defaults to 'default'.
    """
    try:
        # Delete the service
        resp = k8s_api.delete_namespaced_service(name=service_name,
                                                 namespace=namespace,
                                                 body=client.V1DeleteOptions())
        print(f"Service '{service_name}' deleted.")
        return resp
    except ApiException as e:
        if e.status == 404:
            print(f"Service '{service_name}' not found.")
        else:
            print(f"Error deleting service '{service_name}': {e}")
        return None


# -------------------------------------------- K8S API FUNCTIONS --------------------------------------------#
@app.post("/create-pod",
tags=["K8s Functions"])
async def create_pod_endpoint():
    """
    Endpoint to create a Kubernetes pod from a YAML file.
    """
    try:
        yaml_file_path = "./descriptorss/nginx-pod.yaml"
        create_resource_from_yaml(yaml_file_path)
        return {"message": f"Pod creation initiated from {yaml_file_path}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-pod",
tags=["K8s Functions"])
async def delete_pod_endpoint(pod_name: str):
    """
    Endpoint to delete a specified Kubernetes pod.
    """
    try:
        delete_pod(api_instance_coreV1, pod_name)
        return {"message": f"Pod '{pod_name}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ------------------------------------------------------------------------------------------------------------------------------#



# -------------------------------------------- DLT API FUNCTIONS --------------------------------------------#
@app.get("/", 
summary="Web3 and Ethereum node info",
tags=["Default DLT Functions"],
description="Get detailed information about the Web3 connection and Ethereum node")
def web3_info_endpoint():
    print("\n\033[1m" + "IP address: " + str(ip_address) + "\033[0m")
    print("\033[1m" + "Ethereum address: " + str(block_address) + "\033[0m")
    print("Federation contract:\n", Federation_contract.functions)
    message = {
        "ip-address": ip_address,
        "ethereum-address": block_address,
        "contract-address": contract_address,
        "domain-name": domain_name,
        "service-id": service_id
    }
    return {"web3-info": message}

@app.post("/register_domain",
tags=["Default DLT Functions"],
description="""
This function registers a domain in the smart contract by calling the addOperator function
""")
def register_domain_endpoint():
    global domain_registered  
    if domain_registered == False:
        
        # Build the transaction for the addOperator function
        add_operator_transaction = Federation_contract.functions.addOperator(Web3.toBytes(text=domain_name)).buildTransaction({
            'from': block_address,
            'nonce': nonce
        })

        # Send the signed transaction
        tx_hash = send_signed_transaction(add_operator_transaction)

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
def create_service_announcement_endpoint():
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
def check_service_state_endpoint(service_id: str):
    current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=service_id)).call()
    if current_service_state == 0:
        return {"service-id": service_id, "state": "open"}
    elif current_service_state == 1:
        return {"service-id": service_id, "state": "closed"}
    elif current_service_state == 2:
        return {"service-id": service_id, "state": "deployed"}
    else:
        return { "error" : f"service-id {service_id}, state is {current_service_state}"}
    

@app.get("/check_deployed_info/{service_id}", tags=["Default DLT Functions"])
def check_deployed_info_endpoint(service_id: str):
    service_id_bytes = web3.toBytes(text=service_id)  # Convert string to bytes
    service_id, service_endpoint_provider, external_ip = Federation_contract.functions.GetServiceInfo(_id=service_id_bytes, provider=False, call_address=block_address).call()
    _service_id = service_id.rstrip(b'\x00')  # Apply rstrip on bytes-like object
    _service_endpoint_provider = service_endpoint_provider.rstrip(b'\x00')
    _external_ip = external_ip.rstrip(b'\x00')
    return {"service-id": _service_id, "service-endpoint-provider": _service_endpoint_provider, "external-ip": _external_ip}


@app.get("/check_service_announcements", 
tags=["Provider Functions"],
description=""" 
Retrieves new service announcements, checks their state, and returns a JSON response with the details of any open services found or a message indicating no new events. 
""")
def check_service_announcements_endpoint():

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
            "service-id": service_id,
            "requirements": requirements,
            "tx-hash": tx_hash,
            "contract-address": address,
            "block": block_number
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
def place_bid_endpoint(service_id: str, service_price: int):
    global winnerChosen_event 
    winnerChosen_event  = PlaceBid(service_id, service_price)
    print("\n\033[1;32m(TX-2) Bid offer sent to the SC\033[0m")
    return {"Transaction": "Bid offer sent to the Smart Contract", "price(₿)": service_price, "from": block_address}


@app.get('/check_bids/{service_id}', tags=["Consumer Functions"],
description="""
This function allows a consumer to check for new bids for a specific service by providing the service ID. 
It retrieves the new bid events, checks for the highest bid index, and returns a JSON response with the bid information if any new bids are found
""")
def check_bids_endpoint(service_id: str):
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
                "provider-address": bid_info[0],
                "service-price": bid_info[1],
                "bid-index": bid_info[2]
            }
            break
    if bidderArrived:
        return {"message": f"There are new bids for the service {service_id}", "bid-info": message}

    else:
        return {"message": f"There are no bids yet for the service {service_id}"}


@app.post('/choose_provider/{bid_index}', tags=["Consumer Functions"],
description="""
This function allows a consumer to choose a provider for a service by specifying the bid index. 
It retrieves the bid events, chooses the provider associated with the specified bid index, and returns a JSON response indicating the transaction details.
""")
def choose_provider_endpoint(bid_index: int):
    global bids_event
    new_events = bids_event.get_all_entries()
    for event in new_events:
        event_id = str(web3.toText(event['args']['_id'])).rstrip('\x00')
        print("\n\033[1;32m(TX-3) Provider choosen! (bid index=" + str(bid_index) + ")\033[0m")
        ChooseProvider(bid_index)
        # Service closed (state 1)
    return {"Transaction": f"Provider choosen!", "service-id": event_id, "bid-index": bid_index}    


@app.get("/check_winner/{service_id}", tags=["Provider Functions"],
description="""
Ths function allows a provider to check if there is a winner for a specific service by providing the service ID. 
""")
def check_winner_endpoint(service_id: str):
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
def check_if_I_am_Winner_endpoint(service_id: str):
     # Provider AD ask if he is the winner
    am_i_winner = CheckWinner(service_id)
    if am_i_winner == True:
        print("I am a Winner")
        return {"message": f"I am the winner for the service {service_id}"}
    else:
        print("I am not a Winner")
        return {"message": f"I am not the winner for the service {service_id}"}


# Fix
@app.post("/deploy_service/{service_id}", tags=["Provider Functions"],
description="""
Provider AD starts the deployment of the requested federated service. Once it has been deployed, he confirms the operation by sending transaction to the smart contract.
The smart contract records the successful deployment and initiates charging for the federated service
""")
def deploy_service_endpoint(service_id: str):
    if CheckWinner(service_id):

        federated_ns_name = "federated_service"
        federated_nsi_id = create_nsi(federated_ns_name, True)
        #federated_nsi_id = 5
        federated_nsi_info = {
            "name": federated_ns_name,
            "id":  federated_nsi_id
        }
        ServiceDeployed(service_id, ipaddress)
        print("\n\033[1;32m(TX-4) Service deployed\033[0m")
        return {"Transaction": "Service deployed", "service-info": federated_nsi_info}
    else:
        return {"Error": "You are not the winner"}   
# ------------------------------------------------------------------------------------------------------------------------------#





# -------------------------------------------- TEST DEPLOYMENT: DLT WITH OSM-K8s --------------------------------------------#
# @app.get("/consumer_code", tags=["Test deployment: federation of a K8s service in OSM"])
# def consumer_code():

#     header = ['step', 'timestamp']
#     data = []
    
#     if domain == 'consumer':
        
#         # Start time of the process
#         process_start_time = time.time()
        
#         global bids_event

#         # Consumer creates a Network Service Instance composed of 1 KNF (Kubernetes Network Function)
#         #nsi_id = create_nsi("test", True)
       
#         print("\nSERVICE_ID:", service_id) # service + timestamp
        
#         # Service Announcement Sent
#         t_serviceAnnouncementSent = time.time() - process_start_time
#         data.append(['serviceAnnouncementSent', t_serviceAnnouncementSent])
#         bids_event = AnnounceService()

#         print("\n\033[1;32m(TX-1) Service announcement sent to the SC\033[0m")

#         # Consumer AD wait for provider bids
#         bidderArrived = False

#         print("Waiting for bids...\n")
#         while bidderArrived == False:
#             new_events = bids_event.get_all_entries()
#             for event in new_events:
                
#                 # Bid Offer Received
#                 t_bidOfferReceived = time.time() - process_start_time
#                 data.append(['bidOfferReceived', t_bidOfferReceived])

#                 event_id = str(web3.toText(event['args']['_id']))
                
#                 # Choosing provider
#                 t_choosingProvider = time.time() - process_start_time
#                 data.append(['choosingProvider', t_choosingProvider])

#                 # service id, service id, index of the bid
#                 print(service_id, web3.toText(event['args']['_id']), event['args']['max_bid_index'])
#                 print("BIDS ENTERED")
#                 bid_index = int(event['args']['max_bid_index'])
#                 bidderArrived = True 
#                 if int(bid_index) < 2:

#                     #print("\nBids-info = [provider address , service price , bid index]\n")
#                     bid_info = GetBidInfo(int(bid_index-1))
#                     print(bid_info)
                    
#                     # Provider choosen
#                     t_providerChoosen = time.time() - process_start_time
#                     data.append(['providerChoosen', t_providerChoosen])
#                     ChooseProvider(int(bid_index)-1)

#                     # Winner choosen sent
#                     t_winnerChoosenSent = t_providerChoosen
#                     data.append(['winnerChoosenSent', t_winnerChoosenSent])

#                     print("\n\033[1;32m(TX-3) Provider choosen! (bid index=" + str(bid_index-1) + ")\033[0m")

#                     # Service closed (state 1)
#                     #DisplayServiceState(service_id)
#                     break

#         # Consumer AD wait for provider confirmation
#         serviceDeployed = False 
#         while serviceDeployed == False:
#             serviceDeployed = True if GetServiceState(service_id) == 2 else False
        
#         # Confirmation received
#         t_confirmDeploymentReceived = time.time() - process_start_time
#         data.append(['confirmDeploymentReceived', t_confirmDeploymentReceived])
        
#         t_checkConnectivityFederatedServiceStart = time.time() - process_start_time
#         data.append(['checkConnectivityFederatedServiceStart', t_checkConnectivityFederatedServiceStart])

#         # Service deployed info
#         external_ip, service_endpoint_provider = GetDeployedInfo(service_id)
        
#         external_ip = external_ip.decode('utf-8')
#         service_endpoint_provider = service_endpoint_provider.decode('utf-8')

#         print("Service deployed info:")
#         print("External IP:", external_ip)
#         print("Service endpoint provider:", service_endpoint_provider)


#         # Establish connectivity with the federated service
#         connected = False
#         while not connected:
#             connected, response_content = check_federated_service_connection(external_ip)
#             if not connected:
#                 print("Failed to establish connection with the federated service. Retrying...")
        
#         t_checkConnectivityFederatedServiceFinished = time.time() - process_start_time
#         data.append(['checkConnectivityFederatedServiceFinished', t_checkConnectivityFederatedServiceFinished])

#         print("Successfully connected to the federated service")
#         print(response_content)

#         # Export the data to a csv file
#         create_csv_file('federation_private_network_consumer.csv', header, data)

#         return {"message": "Federation process (which involves announcement offer, negotiation and acceptance) successful"}
#     else:
#         return {"error": "You must be consumer to run this code"}


# @app.get("/provider_code", tags=["Test deployment: federation of a K8s service in OSM"])
# def provider_code():
    
#     header = ['step', 'timestamp']
#     data = []
    
#     if domain == 'provider':
        
#         # Start time of the process
#         process_start_time = time.time()

#         global winnerChosen_event 
#         service_id = ''
#         print("\nSERVICE_ID:",service_id)

#         newService_event = ServiceAnnouncementEvent()
#         newService = False
#         open_services = []

#         # Provider AD wait for service announcements
#         while newService == False:
#             new_events = newService_event.get_all_entries()
#             for event in new_events:
#                 service_id = web3.toText(event['args']['id'])
                
#                 requirements = web3.toText(event['args']['requirements'])

#                 requested_service = requirements.split("=")[1]
#                 # Removes null characters at the end of the string
#                 requested_service = requested_service.rstrip('\x00') 
                
#                 if GetServiceState(service_id) == 0:
#                     open_services.append(service_id)
#             print("OPEN =", len(open_services)) 
#             if len(open_services) > 0:
                
#                 # Announcement received
#                 t_serviceAnnouncementReceived = time.time() - process_start_time
#                 data.append(['serviceAnnouncementReceived', t_serviceAnnouncementReceived])

#                 print('Announcement received:')
#                 print(new_events)
#                 print("\n\033[1;33mRequested service: " + repr(requested_service) + "\033[0m")
#                 newService = True
            
#         service_id = open_services[-1]

#         # Place a bid offer to the Federation SC
#         t_bidOfferSent = time.time() - process_start_time
#         data.append(['bidOfferSent', t_bidOfferSent])
#         winnerChosen_event = PlaceBid(service_id, 10)

#         print("\n\033[1;32m(TX-2) Bid offer sent to the SC\033[0m")
        
#         # Ask to the Federation SC if there is a winner (wait...)
    
#         winnerChosen = False
#         while winnerChosen == False:
#             new_events = winnerChosen_event.get_all_entries()
#             for event in new_events:
#                 event_serviceid = web3.toText(event['args']['_id'])
#                 if event_serviceid == service_id:
                    
#                     # Winner choosen received
#                     t_winnerChoosenReceived = time.time() - process_start_time
#                     data.append(['winnerChoosenReceived', t_winnerChoosenReceived])

#                     winnerChosen = True
#                     break
        
#         # Provider AD ask if he is the winner
#         am_i_winner = CheckWinner(service_id)
#         if am_i_winner == True:
            
#             # Start deployment of the requested federated service
#             t_deploymentStart = time.time() - process_start_time
#             data.append(['deploymentStart', t_deploymentStart])

#             # Deployment of the NSI in OSM...
#             nsi_id = create_nsi("federated_service", True)


#             # IP address of the service deployed by the provider
#             external_ip = get_service_deployed_info()

#             # Deployment finished
#             t_deploymentFinished = time.time() - process_start_time
#             data.append(['deploymentFinished', t_deploymentFinished])
            
    
#             # Deployment confirmation sent
#             t_confirmDeploymentSent = time.time() - process_start_time
#             data.append(['confirmDeploymentSent', t_confirmDeploymentSent])
#             ServiceDeployed(service_id, external_ip)
            
#             print("\n\033[1;32m(TX-4) Service deployed\033[0m")
#             print("External IP:", external_ip)
#             DisplayServiceState(service_id)
            
#             # Export the data to a csv file
#             create_csv_file('federation_private_network_provider.csv', header, data)
            
#             return {"message": "Federation process (which involves announcement offer, negotiation and acceptance) successful"}

#         else:
#             print("I am not a Winner")
#             return {"error": "I am not a Winner"}

#     else:
#         return {"error": "You must be provider to run this code"}
# ------------------------------------------------------------------------------------------------------------------------------#



