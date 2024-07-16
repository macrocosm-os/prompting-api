import time
import pandas as pd
import streamlit as st
import plotly.express as px

import utils

_ = """
Proteins folded (delta 24hr)
Current proteins folding (24hr)
Average time to fold trend
Refolded proteins (group by run id and pdb id and get unique)
Simulation duration distribution
"""

UPDATE_INTERVAL = 3600


st.title('Folding Subnet Dashboard')
st.markdown('<br>', unsafe_allow_html=True)

# reload data periodically
df = utils.build_data(time.time()//UPDATE_INTERVAL)
st.toast(f'Loaded {len(df)} runs')

# TODO: fix the factor for 24 hours ago
runs_alive_24h_ago = (df.last_event_at > pd.Timestamp.now() - pd.Timedelta('1d'))
df_24h = df.loc[runs_alive_24h_ago]
# correction factor to account for the fact that the data straddles the 24h boundary
# correction factor is based on the fraction of the run which occurred in the last 24h
# factor = (df_24h.last_event_at - pd.Timestamp.now() + pd.Timedelta('1d')) / pd.Timedelta('1d')


#### ------ PRODUCTIVITY ------

# Overview of productivity
st.subheader('Productivity overview')
st.info('Productivity metrics show how many proteins have been folded, which is the primary goal of the subnet. Metrics are estimated using weights and biases data combined with heuristics.')

productivity = utils.get_productivity(df)
productivity_24h = utils.get_productivity(df_24h)


m1, m2, m3 = st.columns(3)
m1.metric('Unique proteins folded', f'{productivity.get("unique_folded"):,.0f}', delta=f'{productivity_24h.get("unique_folded"):,.0f} (24h)')
m2.metric('Total proteins folded', f'{productivity.get("total_simulations"):,.0f}', delta=f'{productivity_24h.get("total_simulations"):,.0f} (24h)')
m3.metric('Total simulation steps', f'{productivity.get("total_md_steps"):,.0f}', delta=f'{productivity_24h.get("total_md_steps"):,.0f} (24h)')

st.markdown('<br>', unsafe_allow_html=True)

time_binned_data = df.set_index('last_event_at').groupby(pd.Grouper(freq='12h'))

PROD_CHOICES = {
    'Unique proteins folded': 'unique_pdbs',
    'Total simulations': 'total_pdbs',
    'Total simulation steps': 'total_md_steps',
}
prod_choice_label = st.radio('Select productivity metric', list(PROD_CHOICES.keys()), index=0, horizontal=True)
prod_choice = PROD_CHOICES[prod_choice_label]
steps_running_total = time_binned_data[prod_choice].sum().cumsum()
st.plotly_chart(
    # add fillgradient to make it easier to see the trend
    px.area(steps_running_total, y=prod_choice, 
            labels={'last_event_at':'', prod_choice: prod_choice_label},
    ).update_traces(fill='tozeroy'),
    use_container_width=True,
)

st.markdown('<br>', unsafe_allow_html=True)


#### ------ THROUGHPUT ------
st.subheader('Throughput overview')

st.info('Throughput metrics show the total amount of data sent and received by the validators. This is a measure of the network activity and the amount of data that is being processed by the subnet.')

MEM_UNIT = 'GB' #st.radio('Select memory unit', ['TB','GB', 'MB'], index=0, horizontal=True)

data_transferred = utils.get_data_transferred(df,unit=MEM_UNIT)
data_transferred_24h = utils.get_data_transferred(df_24h, unit=MEM_UNIT)

m1, m2, m3 = st.columns(3)
m1.metric(f'Total sent data ({MEM_UNIT})', f'{data_transferred.get("sent"):,.0f}', delta=f'{data_transferred_24h.get("sent"):,.0f} (24h)')
m2.metric(f'Total received data ({MEM_UNIT})', f'{data_transferred.get("received"):,.0f}', delta=f'{data_transferred_24h.get("received"):,.0f} (24h)')
m3.metric(f'Total transferred data ({MEM_UNIT})', f'{data_transferred.get("total"):,.0f}', delta=f'{data_transferred_24h.get("total"):,.0f} (24h)')


IO_CHOICES = {'total_data_sent':'Sent', 'total_data_received':'Received'}
io_running_total = time_binned_data[list(IO_CHOICES.keys())].sum().rename(columns=IO_CHOICES).cumsum().melt(ignore_index=False)
io_running_total['value'] = io_running_total['value'].apply(utils.convert_unit, args=(utils.BASE_UNITS, MEM_UNIT))

st.plotly_chart(
    px.area(io_running_total, y='value', color='variable',
            labels={'last_event_at':'', 'value': f'Data transferred ({MEM_UNIT})', 'variable':'Direction'},
    ),
    use_container_width=True,
)

st.markdown('<br>', unsafe_allow_html=True)


#### ------ LEADERBOARD ------

st.subheader('Leaderboard')
st.info('The leaderboard shows the top miners by incentive.')
m1, m2 = st.columns(2)
ntop = m1.slider('Number of top miners to display', value=10, min_value=3, max_value=50, step=1)
entity_choice = m2.radio('Select entity', utils.ENTITY_CHOICES, index=0, horizontal=True)

df_m = utils.get_metagraph(time.time()//UPDATE_INTERVAL)
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
st.info('The timeline shows the creation and last event time of each run.')
st.plotly_chart(
    px.timeline(df, x_start='created_at', x_end='last_event_at', y='username', color='state',
                labels={'created_at':'Created at', 'last_event_at':'Last event at', 'username':''},
                ),
    use_container_width=True
)

with st.expander('Show raw run data'):
    st.dataframe(df)