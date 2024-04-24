import psutil
import time
import sys

def monitor_cpu_usage(threshold=80, alert_duration=5):
    alert_triggered_time = None  # Time when CPU usage first exceeds threshold

    while True:
        # Get per-CPU and overall average CPU usage
        cpu_usages = psutil.cpu_percent(interval=1, percpu=True)
        overall_cpu_usage = sum(cpu_usages) / len(cpu_usages)  # Calculate overall average manually

        # Clear the screen and print the CPU usages
        sys.stdout.write("\033[H\033[J")
        print("Individual CPU Usage:")
        for i, usage in enumerate(cpu_usages):
            # Display each CPU core's usage with a visual bar
            bar = '█' * int(usage / 10)  # Create a simple bar based on usage
            print(f"Core {i}: [{bar:<10}] {usage:.2f}%")

        # Check if CPU usage is above the threshold
        if overall_cpu_usage > threshold:
            print(f"High CPU usage detected! Overall CPU usage is at {overall_cpu_usage:.2f}%")
            if alert_triggered_time is None:
                # Record the time when CPU first exceeds threshold
                alert_triggered_time = time.time()
            else:
                # Check if the CPU has been above the threshold for the alert duration
                if (time.time() - alert_triggered_time) >= alert_duration:
                    print("Federation triggered due to a lack of resources in the system.")
                    break  # Stop the script after the alert
        else:
            print(f"Overall CPU usage is normal at {overall_cpu_usage:.2f}%")
            # Reset the timer since CPU usage is below the threshold
            alert_triggered_time = None

if __name__ == '__main__':
    # Inform users about the threshold and how alerts are triggered
    print(f"Starting CPU monitoring. Alert threshold is set to 80%.")
    print(f"Federation will be triggered if CPU usage stays above the threshold for 5 seconds.")
    time.sleep(8)  # Pause to allow user to read the information
    try:
        monitor_cpu_usage()
    except KeyboardInterrupt:
        print("Stopped CPU monitoring.")
