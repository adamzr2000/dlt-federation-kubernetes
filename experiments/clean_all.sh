#!/bin/bash

# Delete all CSV files in consumer/ and provider/ directories
find consumer/ provider/ -type f -name "*.csv" -exec rm -f {} \;

echo "All CSV files in consumers/ and providers/ have been deleted."

