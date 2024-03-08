#!/bin/bash

################################################################################
# Script Description:
# This script is designed to automate the configuration of an existing 
# Kubernetes cluster. It uses Helm, a package manager for Kubernetes, to 
# deploy services, config-maps, and deployments.
#
# The script kicks off by deploying various services, with special emphasis on 
# the "mediamtx-service," a critical component for cluster operation. After 
# obtaining its external IP, the script seamlessly integrates it into the 
# Kubernetes cluster configuration within the "frontend-config-map" and 
# "mediamtx" pod.

# If the user confirms the presence of a ROS (Robot Operating System) cluster 
# with a ROS bridge server, the script prompts for the ROS Bridge Server IP. This 
# IP is validated and incorporated into the "frontend-config-map." However, it's 
# important to note that configuring the ROS cluster is optional and not 
# mandatory for overall Kubernetes cluster setup.

# Usage:
# Ensure you are inside the '6g-latency-sensitive-service/chart/' directory 
# before executing.
# ./apply-k8s-config.sh
################################################################################

# Uninstall the Helm releases if they exist
helm uninstall "app-services" > /dev/null 2>&1 || true
helm uninstall "app-core" > /dev/null 2>&1 || true

# This function validates the format of the ROS bridge server IP.
validate_ip() {
    local ip=$1
    local ip_regex="^([0-9]{1,3}\.){3}[0-9]{1,3}$"

    # Check if the IP matches the regular expression.
    if [[ $ip =~ $ip_regex ]]; then
        # Split the IP into octets and check each one.
        IFS='.' read -ra octets <<< "$ip"
        for octet in "${octets[@]}"; do
            # If an octet is out of range (0-255), it's an invalid IP.
            if ((octet < 0 || octet > 255)); then
                echo "Invalid IP address: $ip"
                exit 1  # Exit the script if IP is invalid
            fi
        done
    else
        echo "Invalid IP address: $ip"
        exit 1  # Exit the script if IP is invalid
    fi
}

# Ask the user about the ROS cluster
read -p "Are you currently operating a ROS cluster with the ROS bridge server enabled? (yes/no): " has_ros_cluster

# If the user has a ROS cluster, ask for the ROS Bridge Server IP and validate it.
if [ "$has_ros_cluster" == "yes" ]; then
    read -p "Enter the ROS Bridge Server IP: " ros_bridge_server_ip
    validate_ip "$ros_bridge_server_ip"
fi

# Try to install the services using Helm
# If the installation fails, print an error message and exit the script.
if helm install app-services ./app \
  -f ./app/values/service-values.yaml; then
    echo "Services were applied successfully."
else
    echo "Error: Failed to apply services. Please review the configuration and attempt the installation again."
    exit 1
fi

# Wait until the mediamtx_service IP is created.
mediamtx_service_ip=""
while [ -z "$mediamtx_service_ip" ]; do
    mediamtx_service_ip=$(kubectl get service mediamtx-service -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    # If the IP is not yet created, wait for 2 seconds before checking again.
    [ -z "$mediamtx_service_ip" ] && sleep 2
done
echo "Streaming Server IP: $mediamtx_service_ip"

# Try to apply the Helm installation for config-maps and deployments.
# If the installation fails, print an error message and exit the script.
if helm install app-core ./app \
  -f ./app/values/config-map-values.yaml \
  -f ./app/values/deployment-values.yaml \
  --set configMaps[0].data.ros_bridge_server_ip=$ros_bridge_server_ip \
  --set configMaps[0].data.streaming_server_ip=$mediamtx_service_ip:8889 \
  --set deployments[1].env[0].value=$mediamtx_service_ip; then
    echo "Configmaps, and deployments were applied successfully."
else
    echo "Error: Failed to apply either secrets, configmaps, or deployments. Please review the configuration and attempt the installation again."
    exit 1
fi

# Print a success message when the configuration is completed.
echo ""
echo "Configuration completed successfully."
