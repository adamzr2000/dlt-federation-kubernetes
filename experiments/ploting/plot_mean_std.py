import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Set the seaborn style for aesthetics
sns.set_style("darkgrid")

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

# Convert to DataFrame
times_df = pd.DataFrame(times_data)

# Group by Step and calculate mean and standard deviation
agg_funcs = {'Start Time': ['mean', 'std'], 'End Time': ['mean', 'std']}
times_summary_df = times_df.groupby('Step').agg(agg_funcs).reset_index()

# Flatten MultiIndex columns
times_summary_df.columns = [' '.join(col).strip() for col in times_summary_df.columns.values]

# Order steps
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Deployment']
times_summary_df['Order'] = times_summary_df['Step'].apply(lambda x: ordered_steps.index(x))
times_summary_df = times_summary_df.sort_values('Order', ascending=True)

# Plotting
plt.figure(figsize=(12, 8))
for i, step in enumerate(ordered_steps):
    mean_start = times_summary_df.loc[times_summary_df['Step'] == step, 'Start Time mean'].values[0]
    std_start = times_summary_df.loc[times_summary_df['Step'] == step, 'Start Time std'].values[0]
    mean_end = times_summary_df.loc[times_summary_df['Step'] == step, 'End Time mean'].values[0]
    std_end = times_summary_df.loc[times_summary_df['Step'] == step, 'End Time std'].values[0]
    mean_duration = mean_end - mean_start
    duration_std = np.sqrt(std_start**2 + std_end**2)  # Combine std deviations

    plt.barh(i, mean_duration, xerr=duration_std, capsize=5, left=mean_start, color='skyblue', edgecolor='grey')
    plt.text(mean_start + mean_duration / 2, i, f"{mean_duration:.2f}s ± {duration_std:.2f}", va='center', ha='center', color='black', fontweight='bold')

plt.yticks(range(len(ordered_steps)), ordered_steps)
plt.xlabel('Time (s)')
plt.ylabel('Phases')
plt.title('Mean start and end times of each federation step with Standard Deviation')
plt.tight_layout()
plt.gca().invert_yaxis()
# plt.savefig('federation_events_mean_std.png')
plt.show()
