import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Set the seaborn style for aesthetics
sns.set_style("whitegrid")

# Function to calculate durations and their mean, std for each step, including total duration
def calculate_durations(directory):
    steps_definitions = {
        'Service Announced': ('service_announced', 'announce_received'),
        'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
        'Winner Choosen': ('winner_choosen', 'winner_received'),
        'Service Deployment': ('deployment_start', 'deployment_finished'),
        'Confirm Deployment': ('confirm_deployment_sent', 'confirm_deployment_received'),
    }
    times_data = {step: [] for step in steps_definitions}
    times_data['Federation Completed'] = []  # Add total duration entry

    # Process each file
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        df = pd.read_csv(filepath)

        total_start = df['timestamp'].iloc[0]  # Assume first timestamp is the start
        total_end = df['timestamp'].iloc[-1]  # Assume last timestamp is the end
        total_duration = total_end - total_start
        times_data['Federation Completed'].append(total_duration)  # Add total duration

        # Calculate durations for each step
        for step, (start, end) in steps_definitions.items():
            if start in df.step.values and end in df.step.values:
                start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                duration = end_time - start_time
                times_data[step].append(duration)

    # Calculate mean and std
    stats_data = []
    for step, durations in times_data.items():
        mean_duration = np.mean(durations)
        std_duration = np.std(durations)
        stats_data.append({'Step': step, 'Mean Duration': mean_duration, 'Std Duration': std_duration})

    return pd.DataFrame(stats_data)

# Directory containing merged test results
merged_dir = '../merged'

# Calculate durations, mean, and std for each step
times_df = calculate_durations(merged_dir)
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Deployment', 'Federation Completed']
times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x) if x in ordered_steps else len(ordered_steps))
times_df = times_df.sort_values('Order', ascending=True)

plt.figure(figsize=(12, 8))
x_ticks = np.arange(len(ordered_steps))
bar_colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(ordered_steps)))  # Use a colormap for varied but harmonious colors


# Adjusting the loop to ensure labels are added only once
for i, row in times_df.iterrows():
    step = row['Step']
    mean_duration = row['Mean Duration']
    std_duration = row['Std Duration']
    
    # Apply labels only for the first iteration to avoid duplication
    if i == 0:
        plt.bar(x_ticks[i], mean_duration, color=bar_colors[i], edgecolor='grey', yerr=std_duration, capsize=5, error_kw={'elinewidth':2, 'ecolor':'tomato'}, label='Mean Duration')
        plt.errorbar(x_ticks[i], mean_duration, yerr=std_duration, fmt='none', ecolor='tomato', elinewidth=2, capsize=5, label='Standard Deviation')
    else:
        plt.bar(x_ticks[i], mean_duration, color=bar_colors[i], edgecolor='grey', yerr=std_duration, capsize=5, error_kw={'elinewidth':2, 'ecolor':'tomato'})
        plt.errorbar(x_ticks[i], mean_duration, yerr=std_duration, fmt='none', ecolor='tomato', elinewidth=2, capsize=5)

    text_position = mean_duration + std_duration + 0.05 * (mean_duration + std_duration)
    plt.text(x_ticks[i], text_position, f"{mean_duration:.2f}s ± {std_duration:.2f}", va='bottom', ha='center', color='black', fontweight='bold')

plt.xticks(x_ticks, ordered_steps, rotation=45, ha='right')
plt.ylabel('Time (s)')
plt.xlabel('Phases')
# plt.title('Mean durations and standard deviation of each federation step')
plt.legend()
plt.tight_layout()
plt.savefig('federation_events_mean_std.svg')
plt.show()