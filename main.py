import os
import json
import time
import yaml

from dotenv import load_dotenv
from web3 import Web3, HTTPProvider, WebsocketProvider
from web3.middleware import geth_poa_middleware
from fastapi import FastAPI, HTTPException, Query
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from enum import Enum


class YAMLFile(str, Enum):
    nginx_deployment = "nginx-deployment.yaml"
    nginx_pod = "nginx-pod.yaml"
    nginx_service = "nginx-service.yaml"

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

Once the provider deploys the federated service, it notifies the consumer AD with connection details

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
    global nonce
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
    global nonce
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
    global nonce
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
    global nonce
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

def delete_resource_from_yaml(yaml_file_path):
    """
    Deletes a Kubernetes resource (Pod, Service, Deployment) specified in a YAML file.

    Parameters:
    - yaml_file_path: Path to the YAML file containing the resource configuration.
    """
    try:
        with open(yaml_file_path, 'r') as file:
            resources = yaml.safe_load_all(file)
            for resource in resources:
                kind = resource.get("kind")
                metadata = resource.get("metadata", {})
                namespace = metadata.get("namespace", "default")
                name = metadata.get("name")

                # Dynamically dispatch to the appropriate deletion function based on the resource kind
                if kind == "Pod":
                    client.CoreV1Api().delete_namespaced_pod(name=name, namespace=namespace)
                elif kind == "Service":
                    client.CoreV1Api().delete_namespaced_service(name=name, namespace=namespace)
                elif kind == "Deployment":
                    client.AppsV1Api().delete_namespaced_deployment(name=name, namespace=namespace)
                else:
                    raise ValueError(f"Unsupported resource kind for deletion: {kind}")

                print(f"{kind} '{name}' deleted from namespace '{namespace}'.")
    except ApiException as e:
        print(f"Exception when calling Kubernetes API for deletion: {e}")
        raise
    except ValueError as e:
        print(e)
        raise
    except Exception as e:
        print(f"Unexpected error during deletion: {e}")
        raise


# -------------------------------------------- K8S API FUNCTIONS --------------------------------------------#
@app.post("/create_resource", tags=["K8s Functions"])
async def create_resource_endpoint(yaml_file: YAMLFile):
    """
    Endpoint to create a Kubernetes resource based on selected YAML file.
    """
    # The value of yaml_file is now one of the Enum's values, e.g., "nginx-pod.yaml"
    yaml_file_path = f"descriptors/{yaml_file.value}"

    try:
        # Assuming create_resource_from_yaml is a function you've defined to handle the creation
        create_resource_from_yaml(yaml_file_path)
        return {"message": f"Resource creation initiated from {yaml_file.value}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_resource", tags=["K8s Functions"])
async def delete_resource_endpoint(yaml_file: YAMLFile):
    """
    Endpoint to delete a Kubernetes resource based on selected YAML file.
    """
    yaml_file_path = f"descriptors/{yaml_file.value}"

    # Ensure the file exists before attempting deletion
    if not os.path.isfile(yaml_file_path):
        raise HTTPException(status_code=404, detail=f"File {yaml_file.value} not found.")

    try:
        # Call the deletion function
        delete_resource_from_yaml(yaml_file_path)
        return {"message": f"Deletion initiated for resource defined in {yaml_file.value}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ------------------------------------------------------------------------------------------------------------------------------#



# -------------------------------------------- DLT API FUNCTIONS --------------------------------------------#
@app.get("/",
         summary="Get Web3 and Ethereum node info",
         tags=["Default DLT Functions"],
         description="Endpoint to get Web3 and Ethereum node info")
def web3_info_endpoint():
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/register_domain", 
          summary="Register a domain",
          tags=["Default DLT Functions"],
          description="Endpoint to register a domain in the smart contract")  
def register_domain_endpoint():
    global domain_registered  
    global nonce
    try:
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
            return {"message": f"Domain {domain_name} has been registered"}
        else:
            return {"error": "Domain already registered in the SC"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_service_announcement",
          summary="Create a service announcement", 
          tags=["Consumer Functions"],
          description="Endpoint to create a service announcement")
def create_service_announcement_endpoint():
    global bids_event
    try:
        bids_event = AnnounceService()
        print("\n\033[1;32m(TX-1) Service announcement sent to the SC\033[0m")
        return {"message": "Service announcement sent to the SC", "from": f"{domain_name} - {block_address}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_service_state/{service_id}",
         summary="Get service state",
         tags=["Default DLT Functions"],
         description="Endpoint to get the state of a service (specified by its ID)")
def check_service_state_endpoint(service_id: str):
    try:
        current_service_state = Federation_contract.functions.GetServiceState(_id=web3.toBytes(text=service_id)).call()
        if current_service_state == 0:
            return {"service-id": service_id, "state": "open"}
        elif current_service_state == 1:
            return {"service-id": service_id, "state": "closed"}
        elif current_service_state == 2:
            return {"service-id": service_id, "state": "deployed"}
        else:
            return { "error" : f"service-id {service_id}, state is {current_service_state}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_deployed_info/{service_id}",
         summary="Get deployed info",
         tags=["Default DLT Functions"],
         description="Endpoint to get deployed info for a service") 
def check_deployed_info_endpoint(service_id: str):
    try:
        service_id_bytes = web3.toBytes(text=service_id)  # Convert string to bytes
        service_id, service_endpoint_provider, external_ip = Federation_contract.functions.GetServiceInfo(_id=service_id_bytes, provider=False, call_address=block_address).call()
        _service_id = service_id.rstrip(b'\x00')  # Apply rstrip on bytes-like object
        _service_endpoint_provider = service_endpoint_provider.rstrip(b'\x00')
        _external_ip = external_ip.rstrip(b'\x00')
        message = {
            "service-id": _service_id,
            "service-endpoint-provider": _service_endpoint_provider,
            "external-ip": _external_ip
        }
        return {"message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_service_announcements",
         summary="Check announcements",
         tags=["Provider Functions"], 
         description="Endpoint to check for new announcements")
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
        

@app.post("/place_bid/{service_id}-{service_price}",
          summary="Place a bid",
          tags=["Provider Functions"],
          description="Endpoint to place a bid for a service")
def place_bid_endpoint(service_id: str, service_price: int):
    global winnerChosen_event 
    try:
        winnerChosen_event  = PlaceBid(service_id, service_price)
        print("\n\033[1;32m(TX-2) Bid offer sent to the SC\033[0m")
        return {"message": f"Bid offer sent to the SC, from {block_address}, price={service_price} ₿"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/check_bids/{service_id}',
         summary="Check bids",
         tags=["Consumer Functions"],
         description="Endpoint to check bids for a service")  
def check_bids_endpoint(service_id: str):
    global bids_event
    message = ""
    new_events = bids_event.get_all_entries()
    bidderArrived = False
    try:
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
            return {"bids": message}

        else:
            return {"message": f"No bids found for the service {service_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/choose_provider/{bid_index}',
          summary="Choose provider",
          tags=["Consumer Functions"],
          description="Endpoint to choose a provider")
def choose_provider_endpoint(bid_index: int):
    global bids_event
    try:
        new_events = bids_event.get_all_entries()
        for event in new_events:
            event_id = str(web3.toText(event['args']['_id'])).rstrip('\x00')
            print("\n\033[1;32m(TX-3) Provider choosen! (bid index=" + str(bid_index) + ")\033[0m")
            ChooseProvider(bid_index)
            # Service closed (state 1)
        return {"message": f"Provider chosen!", "service-id": event_id, "bid-index": bid_index}    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_winner/{service_id}", 
         summary="Check for winner",
         tags=["Provider Functions"],
         description="Endpoint to check if there is a winner for a service")
def check_winner_endpoint(service_id: str):
    global winnerChosen_event 
    try:
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
            return {"message": f"No winner yet for the service {service_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check_if_i_am_winner/{service_id}",
         summary="Check if I am winner",
         tags=["Provider Functions"],
         description="Endpoint to check if provider is the winner")
def check_if_I_am_Winner_endpoint(service_id: str):
    try:
        am_i_winner = CheckWinner(service_id)
        if am_i_winner == True:
            print("I am a Winner")
            return {"message": f"I am the winner for the service {service_id}"}
        else:
            print("I am not a Winner")
            return {"message": f"I am not the winner for the service {service_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/deploy_service/{service_id}",
          summary="Deploy service",
          tags=["Provider Functions"],
          description="Endpoint for provider to deploy service")
def deploy_service_endpoint(service_id: str):
    try:
        if CheckWinner(service_id):
            create_resource_from_yaml(f"descriptors/{YAMLFile.nginx_pod}")
            create_resource_from_yaml(f"descriptors/{YAMLFile.nginx_service}")
            external_ip = "6.6.6.6"
            ServiceDeployed(service_id, external_ip)
            print("\n\033[1;32m(TX-4) Service deployed\033[0m")
            return {"message": "Service deployed"}
        else:
            return {"message": "You are not the winner"}   
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))            
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



