import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Function to calculate mean accumulated time
def calculate_mean_accumulated_time(directory):
    accumulated_times = []
    for filename in os.listdir(directory):
        if filename.endswith(".csv"):
            df = pd.read_csv(os.path.join(directory, filename))
            accumulated_time = df['timestamp'].iloc[-1] - df['timestamp'].iloc[0]
            accumulated_times.append(accumulated_time)
    return np.mean(accumulated_times)

# Set the seaborn style for aesthetics
sns.set_style("darkgrid")

# --- Plot 1: Mean start and end times of each federation step ---
# Directory containing merged test results
merged_dir = '../merged'
times_data = []

# Process each merged file
for filename in os.listdir(merged_dir):
    filepath = os.path.join(merged_dir, filename)
    df = pd.read_csv(filepath)

    # Capture start and end times for each step
    steps_definitions = {
        'Service Announced': ('service_announced', 'announce_received'),
        'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
        'Winner Choosen': ('winner_choosen', 'winner_received'),
        'Service Deployment': ('deployment_start', 'deployment_finished'),
        'Confirm Deployment': ('confirm_deployment_sent', 'confirm_deployment_received'),
    }
    for step, (start, end) in steps_definitions.items():
        if start in df.step.values and end in df.step.values:
            start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
            end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
            times_data.append({'Step': step, 'Start Time': start_time, 'End Time': end_time})

times_df = pd.DataFrame(times_data)
times_df = times_df.groupby('Step').agg({'Start Time': 'mean', 'End Time': 'mean'}).reset_index()
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Deployment']
times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x))
times_df = times_df.sort_values('Order', ascending=True)

plt.figure(figsize=(10, 6))
for i, step in enumerate(ordered_steps):
    mean_start = times_df.loc[times_df['Step'] == step, 'Start Time'].values[0]
    mean_end = times_df.loc[times_df['Step'] == step, 'End Time'].values[0]
    mean_duration = mean_end - mean_start
    plt.barh(i, mean_duration, left=mean_start, color='skyblue', edgecolor='grey')
    plt.text(mean_start + mean_duration / 2, i, f"{mean_duration:.2f}s", va='center', ha='center', color='black',fontweight='bold')

plt.yticks(range(len(ordered_steps)), ordered_steps)
plt.xlabel('Time (s)')
plt.ylabel('Phases')
plt.title('Mean start and end times of each federation step')
plt.tight_layout()
plt.gca().invert_yaxis()
plt.savefig('federation_events_mean.png')
plt.show()



# --- Plot 2: Mean accumulated time for consumer and provider ---
consumer_dir = '../consumer'
provider_dir = '../provider'
mean_accumulated_time_consumer = calculate_mean_accumulated_time(consumer_dir)
mean_accumulated_time_provider = calculate_mean_accumulated_time(provider_dir)

domains = ['Consumer', 'Provider']
mean_times = [mean_accumulated_time_consumer, mean_accumulated_time_provider]

plt.figure(figsize=(8, 4))
barplot = plt.barh(domains, mean_times, color='skyblue', edgecolor='grey')
for bar, time in zip(barplot, mean_times):
    plt.text(time, bar.get_y() + bar.get_height()/2, f"{time:.2f}s", va='center', ha='right', color='black', fontweight='bold')


plt.xlabel('Time (s)')
plt.ylabel('Domain')
plt.title('Mean accumulated time')
plt.tight_layout()
plt.gca().invert_yaxis() 
plt.savefig('accumulated_time_mean.png')
plt.show()


