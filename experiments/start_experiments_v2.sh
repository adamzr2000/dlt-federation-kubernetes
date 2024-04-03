#!/bin/bash

# Script for experiments of migrating only the object detection component

# Base URL for consumer and provider
BASE_URL_CONSUMER="http://10.5.50.70:8000"
BASE_URL_PROVIDER="http://10.5.50.71:8000"

# Endpoints
CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/start_experiments_consumer_v2?export_to_csv=true"
PROVIDER_ENDPOINT="${BASE_URL_PROVIDER}/start_experiments_provider_v2?export_to_csv=true"

DELETE_RESOURCES_ENDPOINT_CONSUMER="${BASE_URL_CONSUMER}/delete_object_detection_federation_component"
DELETE_RESOURCES_ENDPOINT_PROVIDER="${BASE_URL_PROVIDER}/delete_object_detection_federation_component"

# Directory to store logs
LOGS_DIR="logs"

# Ask the user for the number of tests to run
read -p "Enter the number of tests to run (1-20): " num_tests

# Validate the input
if [[ $num_tests -lt 1 || $num_tests -gt 20 ]]; then
    echo "The number of tests must be between 1 and 20."
    exit 1
fi

# Execute deploy_object_detection_federation_component_endpoint once before starting the loop
curl -X POST "${BASE_URL_CONSUMER}/deploy_object_detection_federation_component?domain=consumer&service_to_wait=mediamtx-service" 


# Function to start experiments
function start_experiments {
    # Timestamp for file naming
    local timestamp=$1

    # Start the provider experiment in the background and save the log
    curl -X POST "${PROVIDER_ENDPOINT}" -d "export_to_csv=true" -o "${LOGS_DIR}/provider_output_${timestamp}.txt" &

    # Start the consumer experiment, wait for it to finish, and save the log
    curl -X POST "${CONSUMER_ENDPOINT}" -d "export_to_csv=true" -o "${LOGS_DIR}/consumer_output_${timestamp}.txt"

    # Ensure background processes have finished
    wait

    # Once the consumer experiment is done, delete all resources on the provider and save the log
    curl -X DELETE "${DELETE_RESOURCES_ENDPOINT_PROVIDER}" \
    -H "Content-Type: application/json" \
    -d '{
        "domain": "provider",
        "pod_prefixes": ["object-detector-"]
    }' \
    -o "${LOGS_DIR}/delete_resources_output_${timestamp}.txt"

    sleep 2
}


# Run the experiments N times
for ((i=1; i<=num_tests; i++))
do
    echo "Starting experiment $i of $num_tests..."
    start_experiments $i
    echo "Experiment $i completed."
done

curl -X DELETE "${DELETE_RESOURCES_ENDPOINT_CONSUMER}" \
-H "Content-Type: application/json" \
-d '{
    "domain": "consumer",
    "pod_prefixes": ["frontend-", "sampler-sender-", "receiver-encoder-publisher-", "mediamtx-"]

}' 

echo "All experiments completed."
