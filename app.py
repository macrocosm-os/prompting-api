import time
import pandas as pd
import streamlit as st
import plotly.express as px

import utils

_ = """
[x] Define KPIs: Number of steps, number of completions and total generated tokens
[x] Data pipeline I: pull run summary data from wandb
[x] Data pipeline II: pull run event data from wandb (max 500 steps per run)
[x] Task trends: Number of tasks over time
[x] Reward trends I: average reward over time, by task
[x] Reward trends II: average nonzero reward over time, by task
[x] Reward trends III: average nonzero normalized reward over time, by task
[x] Explain trends: show release dates to indicate sudden changes 
[ ] Miner trends: associate uids with miner rankings and plot top miner rewards vs network avg 
[ ] Baseline rewards I: compare the network trends with baseline model gpt-3.5-turbo
[ ] Baseline rewards II: compare the network trends with baseline model gpt-4o
[ ] Baseline rewards III: compare the network trends with baseline model zephyr
[ ] Baseline rewards IV: compare the network trends with baseline model solar
[ ] Baseline rewards V: compare the network trends with baseline model llama3 8B
[ ] Baseline rewards VI: compare the network trends with baseline model llama3 70B

---------
"""

st.title('Prompting Subnet Dashboard')
st.markdown('<br>', unsafe_allow_html=True)

# reload data periodically
state_vars = utils.load_state_vars()

df_runs = state_vars['df_runs']
df_runs_24h = state_vars['df_runs_24h']
df_vali = state_vars['df_vali']
df_events = state_vars['df_events']
df_task_counts = state_vars['df_task_counts']
df_m = state_vars['metagraph']
st.toast(f'Loaded {len(df_runs)} runs')

#### ------ PRODUCTIVITY ------

# Overview of productivity
st.subheader('Productivity overview')
st.info('Productivity metrics show how much data has been created by subnet 1')

productivity = utils.get_productivity(df_runs)
productivity_24h = utils.get_productivity(df_runs_24h)


m1, m2, m3, m4 = st.columns(4)
m1.metric('Competition duration', f'{productivity.get("duration").days} days')
m2.metric('Total events', f'{productivity.get("total_events")/1e6:,.2f}M', delta=f'{productivity_24h.get("total_events")/1e6:,.2f}M (24h)')
m3.metric('Total completions', f'{productivity.get("total_completions")/1e9:,.2f}B', delta=f'{productivity_24h.get("total_completions")/1e9:,.2f}B (24h)')
m4.metric('Total dataset tokens', f'{productivity.get("total_tokens")/1e9:,.2f}B', delta=f'{productivity_24h.get("total_tokens")/1e9:,.2f}B (24h)')

st.markdown('<br>', unsafe_allow_html=True)

st.plotly_chart(
    px.area(df_task_counts, y=df_task_counts.columns, title='Data Created by Task', 
            labels={'created_at':'','value':'Total data created'},
            ),
    use_container_width=True,
)

st.markdown('<br>', unsafe_allow_html=True)

# Overview of productivity
st.subheader('Improvement overview')
st.info('Subnet 1 is an endlessly improving system, where miners compete to produce high quality responses to a range of challenging tasks')


TASK_CHOICES = {
    'Question answering': 'qa',
    'Summarization': 'summarization',
    'Date-based question answering': 'date_qa',
    'Math': 'math',
    'Generic instruction': 'generic',
    'Sentiment analysis': 'sentiment',
    'Translation': 'translation',
}

with st.expander('Advanced settings'):
    c1, c2 = st.columns(2)
    remove_zero_rewards = c1.checkbox('Exclude zero rewards', value=True, help='Remove completions which scored zero rewards (failed responses, timeouts etc.)')
    normalize_rewards = c1.checkbox('Normalize rewards', value=True, help='Scale rewards for each task to a maximium value of 1 (approx)')
    show_releases = c1.checkbox('Show releases', value=False, help='Add annotations which indicate when major releases may have impacted network performance')
    moving_avg_window = c2.slider('Moving avg. window', min_value=1, max_value=30, value=14, help='Window size to smooth data and make long term trends clearer')

reward_col = 'normalized_rewards' if normalize_rewards else 'rewards'

df_stats = utils.get_reward_stats(df_events, exclude_multiturn=True, freq='1D', remove_zero_rewards=remove_zero_rewards)


task_choice_label = st.radio('Select task', list(TASK_CHOICES.keys()), index=0, horizontal=True)
task_choice = TASK_CHOICES[task_choice_label]

st.plotly_chart(
    # add fillgradient to make it easier to see the trend
    utils.plot_reward_trends(df_stats, task=task_choice, window=moving_avg_window, col=reward_col, annotate=show_releases, task_label=task_choice_label),
    use_container_width=True,
)

st.markdown('<br>', unsafe_allow_html=True)


#### ------ LEADERBOARD ------

st.subheader('Leaderboard')
st.info('The leaderboard shows the top miners by incentive.')
m1, m2 = st.columns(2)
ntop = m1.slider('Number of top miners to display', value=10, min_value=3, max_value=50, step=1)
entity_choice = m2.radio('Select entity', utils.ENTITY_CHOICES, index=0, horizontal=True)

df_miners = utils.get_leaderboard(df_m, ntop=ntop, entity_choice=entity_choice)

# hide colorbar and don't show y axis
st.plotly_chart(
    px.bar(df_miners, x='I', color='I', hover_name=entity_choice, text=entity_choice if ntop < 20 else None,
            labels={'I':'Incentive', 'trust':'Trust', 'stake':'Stake', '_index':'Rank'},
    ).update_layout(coloraxis_showscale=False, yaxis_visible=False),
    use_container_width=True,
)


with st.expander('Show raw metagraph data'):
    st.dataframe(df_m)

st.markdown('<br>', unsafe_allow_html=True)


#### ------ LOGGED RUNS ------

st.subheader('Logged runs')
# st.info('The timeline shows the creation and last event time of each run.')
# st.plotly_chart(
#     px.timeline(df_runs, x_start='created_at', x_end='last_event_at', y='user', color='state',
#                 labels={'created_at':'Created at', 'last_event_at':'Last event at', 'username':''},
#                 ),
#     use_container_width=True
# )

with st.expander('Show raw run data'):
    st.dataframe(df_runs)