from kubernetes import client, config
from kubernetes.client.rest import ApiException
import subprocess
import time
import sys
import os

from kubernetes import client, config

def get_service_external_ip(service_name, namespace="default", timeout=300):
    """
    Wait for the external IP to be assigned to a service.

    Parameters:
    - service_name: Name of the service.
    - namespace: Namespace of the service.
    - timeout: How long to wait for the external IP (in seconds).
    
    Returns:
    - string: External IP of the service or None if not assigned within the timeout.
    """
    v1 = client.CoreV1Api()
    start_time = time.time()

    while True:
        try:
            service = v1.read_namespaced_service(name=service_name, namespace=namespace)
            ingress = service.status.load_balancer.ingress[0] if service.status.load_balancer.ingress else None
            if ingress:
                if hasattr(ingress, 'ip') and ingress.ip:
                    return ingress.ip
                elif hasattr(ingress, 'hostname') and ingress.hostname:
                    return ingress.hostname
            if time.time() - start_time > timeout:
                print(f"Timeout waiting for external IP for service {service_name}")
                return None
            print(f"Waiting for external IP for service {service_name}...")
            time.sleep(2)
        except ApiException as e:
            print(f"Exception when calling CoreV1Api->read_namespaced_service: {e}")
            return None


# Function to load Kubernetes config
def load_kube_config():
    try:
        config.load_kube_config(config_file=os.path.join(os.getcwd(), "k8s-cluster-config", "microk8s-1-config"))
        #config.load_kube_config(config_file=os.path.join(os.getcwd(), "k8s-cluster-config", "microk8s-2-config"))
    except:
        print("Could not load kubeconfig")
        sys.exit(1)

# Function to wait for specific pods to terminate
def check_pods_terminated(prefixes):
    v1 = client.CoreV1Api()
    while True:
        pods = v1.list_pod_for_all_namespaces().items
        active_pods = [
            pod for pod in pods
            if any(pod.metadata.name.startswith(prefix) for prefix in prefixes)
        ]

        if not active_pods:
            print("All specified pods have been terminated.")
            break
        else:
            remaining_pods = [pod.metadata.name for pod in active_pods]
            print(f"Waiting for specific pods to terminate: {remaining_pods}")
            time.sleep(2)

# Function to deploy object detection service
def deploy_object_detection_service():
    dir_path = "../6g-latency-sensitive-service/chart"
    try:
        # Helm install commands for app-services and app-core
        subprocess.run(["helm", "install", "app-services", "./app", "-f", "./app/values/service-values.yaml"], cwd=dir_path, check=True)
        print("Services were applied successfully.")

        # Logic to wait for mediamtx_service IP could be implemented here using Kubernetes client
        # Wait for the mediamtx_service IP using Kubernetes client
        mediamtx_service_ip = get_service_external_ip("mediamtx-service")
        if mediamtx_service_ip is None:
            print("Failed to obtain mediamtx_service IP.")
            return
        print(f"Found mediamtx_service IP: {mediamtx_service_ip}")
        
        subprocess.run(["helm", "install", "app-core", "./app", "-f", "./app/values/config-map-values.yaml", "-f", "./app/values/deployment-values.yaml"], cwd=dir_path, check=True)
        print("Configmaps and deployments were applied successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply services: {e}")
        return

    print("\nConfiguration completed successfully.")

# Function to delete object detection service
def delete_object_detection_service():
    try:
        # Uninstall Helm releases for app-core and app-services
        subprocess.run(["helm", "uninstall", "app-core"], check=True)
        print("Release \"app-core\" uninstalled.")
        subprocess.run(["helm", "uninstall", "app-services"], check=True)
        print("Release \"app-services\" uninstalled.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to uninstall services: {e}")
        return

    # Wait for all deployments to terminate
    check_pods_terminated([
        "frontend-",
        "object-detector-",
        "sampler-sender-",
        "receiver-encoder-publisher-",
        "mediamtx-"
    ])

if __name__ == "__main__":
    load_kube_config()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "deploy":
            deploy_object_detection_service()
        elif sys.argv[1] == "delete":
            delete_object_detection_service()
        else:
            print("Unknown command. Please use 'deploy' or 'delete'.")
    else:
        print("No command provided. Please use 'deploy' or 'delete'.")

