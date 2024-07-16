import os
import tqdm
import time
import wandb
import streamlit as st
import pandas as pd
import bittensor as bt


# TODO: Store the runs dataframe (as in sn1 dashboard) and top up with the ones created since the last snapshot
# TODO: Store relevant wandb data in a database for faster access


MIN_STEPS = 10 # minimum number of steps in wandb run in order to be worth analyzing
MAX_RUNS = 100#0000
NETUID = 1
BASE_PATH = 'macrocosmos/prompting-validators'
NETWORK = 'finney'
KEYS = None
ABBREV_CHARS = 8
ENTITY_CHOICES = ('identity', 'hotkey', 'coldkey')


api = wandb.Api(timeout=600)

IDENTITIES = {
    '5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3': 'opentensor',
    '5Hddm3iBFD2GLT5ik7LZnT3XJUnRnN8PoeCFgGQgawUVKNm8': 'taostats',
    '5HEo565WAy4Dbq3Sv271SAi7syBSofyfhhwRNjFNSM2gP9M2': 'foundry',
    '5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN': 'bittensor-guru',
    '5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v': 'roundtable-21',
    '5EhvL1FVkQPpMjZX4MAADcW42i3xPSF1KiCpuaxTYVr28sux': 'tao-validator',
    '5FKstHjZkh4v3qAMSBa1oJcHCLjxYZ8SNTSz1opTv4hR7gVB': 'datura',
    '5DvTpiniW9s3APmHRYn8FroUWyfnLtrsid5Mtn5EwMXHN2ed': 'first-tensor',
    '5HbLYXUBy1snPR8nfioQ7GoA9x76EELzEq9j7F32vWUQHm1x': 'tensorplex',
    '5CsvRJXuR955WojnGMdok1hbhffZyB4N5ocrv82f3p5A2zVp': 'owl-ventures',
    '5CXRfP2ekFhe62r7q3vppRajJmGhTi7vwvb2yr79jveZ282w': 'rizzo',
    '5HNQURvmjjYhTSksi8Wfsw676b4owGwfLR2BFAQzG7H3HhYf': 'neural-internet'
}

EXTRACTORS = {
    'state': lambda x: x.state,
    'run_id': lambda x: x.id,
    'run_path': lambda x: os.path.join(BASE_PATH, x.id),
    'user': lambda x: x.user.name[:16],
    'username': lambda x: x.user.username[:16],
    'created_at': lambda x: pd.Timestamp(x.created_at),
    'last_event_at': lambda x: pd.Timestamp(x.summary.get('_timestamp'), unit='s'),

    'netuid': lambda x: x.config.get('netuid'),
    'mock': lambda x: x.config.get('neuron').get('mock'),
    'sample_size': lambda x: x.config.get('neuron').get('sample_size'),
    'timeout': lambda x: x.config.get('neuron').get('timeout'),
    'epoch_length': lambda x: x.config.get('neuron').get('epoch_length'),
    'disable_set_weights': lambda x: x.config.get('neuron').get('disable_set_weights'),

    # This stuff is from the last logged event
    'num_steps': lambda x: x.summary.get('_step'),
    'runtime': lambda x: x.summary.get('_runtime'),
    'query': lambda x: x.summary.get('query'),
    'challenge': lambda x: x.summary.get('challenge'),
    'reference': lambda x: x.summary.get('reference'),
    'completions': lambda x: x.summary.get('completions'),

    'version': lambda x: x.tags[0],
    'spec_version': lambda x: x.tags[1],
    'vali_hotkey': lambda x: x.tags[2],
    # 'tasks_selected': lambda x: x.tags[3:],

    # System metrics
    'disk_read': lambda x: x.system_metrics.get('system.disk.in'),
    'disk_write': lambda x: x.system_metrics.get('system.disk.out'),
    # Really slow stuff below
    # 'started_at': lambda x: x.metadata.get('startedAt'),
    # 'disk_used': lambda x: x.metadata.get('disk').get('/').get('used'),
    # 'commit': lambda x: x.metadata.get('git').get('commit')
}


def get_leaderboard(df, ntop=10, entity_choice='identity'):

    df = df.loc[df.validator_permit==False]
    df.index = range(df.shape[0])
    return df.groupby(entity_choice).I.sum().sort_values().reset_index().tail(ntop)

@st.cache_data()
def get_metagraph(time):
    print(f'Loading metagraph with time {time}')
    subtensor = bt.subtensor(network=NETWORK)
    m = subtensor.metagraph(netuid=NETUID)
    meta_cols = ['I','stake','trust','validator_trust','validator_permit','C','R','E','dividends','last_update']

    df_m = pd.DataFrame({k: getattr(m, k) for k in meta_cols})
    df_m['uid'] = range(m.n.item())
    df_m['hotkey'] = list(map(lambda a: a.hotkey, m.axons))
    df_m['coldkey'] = list(map(lambda a: a.coldkey, m.axons))
    df_m['ip'] = list(map(lambda a: a.ip, m.axons))
    df_m['port'] = list(map(lambda a: a.port, m.axons))
    df_m['coldkey'] = df_m.coldkey.str[:ABBREV_CHARS]
    df_m['hotkey'] = df_m.hotkey.str[:ABBREV_CHARS]
    df_m['identity'] = df_m.apply(lambda x: f'{x.hotkey} @ uid {x.uid}', axis=1)
    return df_m


@st.cache_data()
def load_run(run_path, keys=KEYS):

    print('Loading run:', run_path)
    run = api.run(run_path)
    df = pd.DataFrame(list(run.scan_history(keys=keys)))
    for col in ['updated_at', 'created_at']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    print(f'+ Loaded {len(df)} records')
    return df

@st.cache_data(show_spinner=False)
def build_data(timestamp=None, path=BASE_PATH, min_steps=MIN_STEPS, use_cache=True):

    save_path = '_saved_runs.csv'
    filters = {}
    df = pd.DataFrame()
    # Load the last saved runs so that we only need to update the new ones
    if use_cache and os.path.exists(save_path):
        df = pd.read_csv(save_path)
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['last_event_at'] = pd.to_datetime(df['last_event_at'])

        timestamp_str = df['last_event_at'].max().isoformat()
        filters.update({'updated_at': {'$gte': timestamp_str}})

    progress = st.progress(0, text='Loading data')

    runs = api.runs(path, filters=filters)

    run_data = []
    n_events = 0
    for i, run in enumerate(tqdm.tqdm(runs, total=len(runs))):
        num_steps = run.summary.get('_step',0)
        if num_steps<min_steps:
            continue
        n_events += num_steps
        prog_msg = f'Loading data {i/len(runs)*100:.0f}%, {n_events:,.0f} events)'
        progress.progress(i/len(runs),text=f'{prog_msg}... **downloading** `{os.path.join(*run.path)}`')

        run_data.append(run)

    progress.empty()

    df_new = pd.DataFrame([{k: func(run) for k, func in EXTRACTORS.items()} for run in tqdm.tqdm(run_data, total=len(run_data))])
    df = pd.concat([df, df_new], ignore_index=True)
    df['duration'] = (df.last_event_at - df.created_at).round('s')
    df['identity'] = df['vali_hotkey'].map(IDENTITIES).fillna('unknown')
    df['vali_hotkey'] = df['vali_hotkey'].str[:ABBREV_CHARS]

    df.to_csv(save_path, index=False)
    return df


def load_state_vars():
    UPDATE_INTERVAL = 600

    df = build_data(time.time()//UPDATE_INTERVAL)
    runs_alive_24h_ago = (df.last_event_at > pd.Timestamp.now() - pd.Timedelta('1d'))
    df_24h = df.loc[runs_alive_24h_ago]

    df_m = get_metagraph(time.time()//UPDATE_INTERVAL)

    return {
        'dataframe': df,
        'dataframe_24h': df_24h,
        'metagraph': df_m,
    }


if __name__ == '__main__':

    print('Loading runs')
    df = load_runs()

    df.to_csv('test_wandb_data.csv', index=False)
    print(df)
