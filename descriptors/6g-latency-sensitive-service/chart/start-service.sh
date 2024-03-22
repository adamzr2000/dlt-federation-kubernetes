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
