import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import seaborn as sns

# Set the seaborn style for aesthetics
sns.set_style("whitegrid")

def calculate_durations(directory):
    steps_definitions = {
        'Service Announced': ('service_announced', 'announce_received'),
        'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
        'Winner Choosen': ('winner_choosen', 'winner_received'),
        'Service Deployment': ('deployment_start', 'deployment_finished'),
        'Confirm Deployment': ('confirm_deployment_sent', 'confirm_deployment_received'),
    }
    times_data = {step: [] for step in steps_definitions}
    times_data['Federation Completed'] = []

    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        df = pd.read_csv(filepath)

        total_start = df['timestamp'].iloc[0]
        total_end = df['timestamp'].iloc[-1]
        total_duration = total_end - total_start
        times_data['Federation Completed'].append(total_duration)

        for step, (start, end) in steps_definitions.items():
            if start in df.step.values and end in df.step.values:
                start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
                end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
                duration = end_time - start_time
                times_data[step].append(duration)

    stats_data = []
    for step, durations in times_data.items():
        mean_duration = np.mean(durations)
        std_duration = np.std(durations)
        stats_data.append({'Step': step, 'Mean Duration': mean_duration, 'Std Duration': std_duration})

    return pd.DataFrame(stats_data)

merged_dir = '../merged'
times_df = calculate_durations(merged_dir)
ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Deployment', 'Federation Completed']
times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x) if x in ordered_steps else len(ordered_steps))
times_df = times_df.sort_values('Order', ascending=True)

plt.figure(figsize=(12, 8))
x_ticks = np.arange(len(ordered_steps))

# Use vibrant color for the mean duration line
mean_duration_color = 'darkorange'

# Use contrasting color for the error bars
error_bar_color = 'deepskyblue'

# Plotting error bars for standard deviation and mean points separately
for i, row in times_df.iterrows():
    step = row['Step']
    mean_duration = row['Mean Duration']
    std_duration = row['Std Duration']

    # Only plot error bars once for the legend
    if i == 0:
        plt.errorbar(x_ticks[i], mean_duration, yerr=std_duration, fmt='o', color=mean_duration_color, ecolor=error_bar_color, elinewidth=3, capsize=5, alpha=0.7, label='Standard Deviation')
    else:
        plt.errorbar(x_ticks[i], mean_duration, yerr=std_duration, fmt='o', color=mean_duration_color, ecolor=error_bar_color, elinewidth=3, capsize=5, alpha=0.7)

# Adding mean values as a line plot for clarity and to include in the legend
plt.plot(x_ticks, times_df['Mean Duration'], label='Mean Duration', color=mean_duration_color, marker='o', linestyle='-', linewidth=2)

plt.xticks(x_ticks, ordered_steps, rotation=45, ha='right')
plt.ylabel('Time (s)')
plt.xlabel('Phases')
plt.title('Mean durations and standard deviation of each federation step')
plt.legend()
plt.tight_layout()
plt.savefig('federation_events_mean_std.png')
plt.show()


# old
# import pandas as pd
# import numpy as np
# import os
# import matplotlib.pyplot as plt
# import seaborn as sns
# from matplotlib.patches import Rectangle

# # Set the seaborn style for aesthetics
# sns.set_style("whitegrid")

# # Function to calculate durations and their mean, std for each step, including total duration
# def calculate_durations(directory):
#     steps_definitions = {
#         'Service Announced': ('service_announced', 'announce_received'),
#         'Bid Offered': ('bid_offer_sent', 'bid_offer_received'),
#         'Winner Choosen': ('winner_choosen', 'winner_received'),
#         'Service Deployment': ('deployment_start', 'deployment_finished'),
#         'Confirm Deployment': ('confirm_deployment_sent', 'confirm_deployment_received'),
#     }
#     times_data = {step: [] for step in steps_definitions}
#     times_data['Federation Completed'] = []  # Add total duration entry

#     # Process each file
#     for filename in os.listdir(directory):
#         filepath = os.path.join(directory, filename)
#         df = pd.read_csv(filepath)

#         total_start = df['timestamp'].iloc[0]  # Assume first timestamp is the start
#         total_end = df['timestamp'].iloc[-1]  # Assume last timestamp is the end
#         total_duration = total_end - total_start
#         times_data['Federation Completed'].append(total_duration)  # Add total duration

#         # Calculate durations for each step
#         for step, (start, end) in steps_definitions.items():
#             if start in df.step.values and end in df.step.values:
#                 start_time = df.loc[df['step'] == start, 'timestamp'].values[0]
#                 end_time = df.loc[df['step'] == end, 'timestamp'].values[0]
#                 duration = end_time - start_time
#                 times_data[step].append(duration)

#     # Calculate mean and std
#     stats_data = []
#     for step, durations in times_data.items():
#         mean_duration = np.mean(durations)
#         std_duration = np.std(durations)
#         stats_data.append({'Step': step, 'Mean Duration': mean_duration, 'Std Duration': std_duration})

#     return pd.DataFrame(stats_data)

# # Directory containing merged test results
# merged_dir = '../merged'

# # Calculate durations, mean, and std for each step
# times_df = calculate_durations(merged_dir)
# ordered_steps = ['Service Announced', 'Bid Offered', 'Winner Choosen', 'Service Deployment', 'Confirm Deployment', 'Federation Completed']
# times_df['Order'] = times_df['Step'].apply(lambda x: ordered_steps.index(x) if x in ordered_steps else len(ordered_steps))
# times_df = times_df.sort_values('Order', ascending=True)

# plt.figure(figsize=(12, 8))
# x_ticks = np.arange(len(ordered_steps))
# bar_colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(ordered_steps)))  # Use a colormap for varied but harmonious colors

# for i, row in times_df.iterrows():
#     step = row['Step']
#     mean_duration = row['Mean Duration']
#     std_duration = row['Std Duration']
    
#     # Plot a bar for the mean
#     plt.bar(x_ticks[i], mean_duration, color=bar_colors[i], edgecolor='grey')
    
#     # Draw a rectangle for the standard deviation
#     rect = Rectangle((x_ticks[i] - 0.4, mean_duration - std_duration), 0.8, 2*std_duration, color='lightgrey', alpha=0.5, edgecolor=None)
#     plt.gca().add_patch(rect)
    
#     # Adjust text position to be above the rectangle and include error
#     text_position = mean_duration + std_duration + 0.05 * (mean_duration + std_duration)  # Slightly above the rectangle
#     plt.text(x_ticks[i], text_position, f"{mean_duration:.2f}s ± {std_duration:.2f}", va='bottom', ha='center', color='black', fontweight='bold')

# plt.xticks(x_ticks, ordered_steps, rotation=45, ha='right')
# plt.ylabel('Time (s)')
# plt.xlabel('Phases')
# plt.title('Mean durations and standard deviation of each federation step with visual error representation')
# plt.tight_layout()
# plt.show()
