import subprocess
import time
import sys

def deploy_object_detection_service():
    dir_path = "descriptors/6g-latency-sensitive-service/chart"

    # Helm install for app-services
    try:
        print("Executing helm install for app-services...")
        output = subprocess.check_output([
            "helm", "install", "app-services", "./app",
            "-f", "./app/values/service-values.yaml"
        ], cwd=dir_path, stderr=subprocess.STDOUT)
        print(output.decode())
        print("Services were applied successfully.")
    except subprocess.CalledProcessError as e:
        print("Failed to apply services. Error output:")
        print(e.output.decode())
        return

    # Wait for the mediamtx_service IP
    mediamtx_service_ip = ""
    print("Waiting for the mediamtx_service IP...")
    while not mediamtx_service_ip:
        try:
            mediamtx_service_ip = subprocess.check_output([
                "kubectl", "get", "service", "mediamtx-service",
                "-o", "jsonpath={.status.loadBalancer.ingress[0].ip}"
            ], cwd=dir_path).decode().strip()
            print("Found mediamtx_service IP:", mediamtx_service_ip)
        except subprocess.CalledProcessError as e:
            print("Waiting for mediamtx_service IP...")
            time.sleep(2)

    # Helm install for app-core
    try:
        print("Executing helm install for app-core...")
        output = subprocess.check_output([
            "helm", "install", "app-core", "./app",
            "-f", "./app/values/config-map-values.yaml",
            "-f", "./app/values/deployment-values.yaml",
            "--set", f"configMaps[0].data.streaming_server_ip={mediamtx_service_ip}:8889",
            "--set", f"deployments[1].env[0].value={mediamtx_service_ip}"
        ], cwd=dir_path, stderr=subprocess.STDOUT)
        print(output.decode())
        print("Configmaps and deployments were applied successfully.")
    except subprocess.CalledProcessError as e:
        print("Failed to apply configmaps or deployments. Error output:")
        print(e.output.decode())
        return

    print("\nConfiguration completed successfully.")


def delete_object_detection_service():
    services = [
        "mediamtx-service",
        "frontend-service",
        "sampler-sender-service",
        "object-detector-service",
        "receiver-encoder-publisher-service"
    ]

    try:
        # Uninstall Helm releases for app-core and app-services
        print("Uninstalling Helm release for app-core...")
        subprocess.check_output(["helm", "uninstall", "app-core"], stderr=subprocess.STDOUT)
        print("Release \"app-core\" uninstalled.")

        print("Uninstalling Helm release for app-services...")
        subprocess.check_output(["helm", "uninstall", "app-services"], stderr=subprocess.STDOUT)
        print("Release \"app-services\" uninstalled.")
    except subprocess.CalledProcessError as e:
        print("Failed to uninstall services. Error output:")
        print(e.output.decode())
        return

    # Wait until the specified services are terminated
    print("Waiting for specified services to terminate...")
    for service in services:
        while True:
            try:
                subprocess.check_output(["kubectl", "get", "svc", service], stderr=subprocess.STDOUT)
                print(f"Waiting for {service} to terminate...")
                time.sleep(5)
            except subprocess.CalledProcessError:
                print(f"{service} has been terminated.")
                break

    print("\nService cleanup completed successfully.")



if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "deploy":
            deploy_object_detection_service()
        elif sys.argv[1] == "delete":
            delete_object_detection_service()
        else:
            print("Unknown command. Please use 'deploy' or 'delete'.")
    else:
        print("No command provided. Please use 'deploy' or 'delete'.")


