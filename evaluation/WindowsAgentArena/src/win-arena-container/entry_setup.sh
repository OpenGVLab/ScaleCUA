#!/bin/bash

export NO_PROXY="${NO_PROXY},20.20.20.21"


echo "Starting WinArena VM..."

# Start the VM script in the background
cd / # Fix for Azure ML Job not using the correct root path
./start_vm.sh &

# Wait for the VM to start up
while true; do
  # Send a GET request to the specified URL
  response=$(curl --write-out '%{http_code}' --silent --output /dev/null 20.20.20.21:5000/probe)

  # If the response code is 200 (HTTP OK), break the loop
  if [ $response -eq 200 ]; then
    break
  fi

  echo "Waiting for a response from the windows server. This might take a while..."

  # Wait for a while before the next attempt
  sleep 5
done

echo "VM is up and running, and the Windows Arena Server is ready to use!"