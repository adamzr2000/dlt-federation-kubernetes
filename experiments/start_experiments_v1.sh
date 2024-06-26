#!/bin/bash

# Script for experiments of migrating the entire object detection service

# Base URL for consumer and provider
BASE_URL_CONSUMER="http://10.5.50.70:8000"
BASE_URL_PROVIDER="http://10.5.50.71:8000"

# Endpoints
CONSUMER_ENDPOINT="${BASE_URL_CONSUMER}/start_experiments_consumer?export_to_csv=true"
PROVIDER_ENDPOINT="${BASE_URL_PROVIDER}/start_experiments_provider?export_to_csv=true"
DELETE_RESOURCES_ENDPOINT="${BASE_URL_PROVIDER}/delete_object_detection_service"

# Directory to store logs
LOGS_DIR="logs"

# Ask the user for the number of tests to run
read -p "Enter the number of tests to run (1-20): " num_tests

# Validate the input
if [[ $num_tests -lt 1 || $num_tests -gt 20 ]]; then
    echo "The number of tests must be between 1 and 20."
    exit 1
fi

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
    curl -X DELETE "$DELETE_RESOURCES_ENDPOINT" 
    sleep 2
}

# Run the experiments N times
for ((i=1; i<=num_tests; i++))
do
    echo "Starting experiment $i of $num_tests..."
    start_experiments $i
    echo "Experiment $i completed."
done

echo "All experiments completed."
