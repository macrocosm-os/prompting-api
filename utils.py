import os
import tqdm
import time
import glob
import wandb
from traceback import print_exc
import streamlit as st
import pandas as pd
import bittensor as bt
import plotly.express as px
from loguru import logger


# TODO: Store the runs dataframe (as in sn1 dashboard) and top up with the ones created since the last snapshot
# TODO: Store relevant wandb data in a database for faster access


MIN_STEPS = 10  # minimum number of steps in wandb run in order to be worth analyzing
NETUID = 1
BASE_PATH = "macrocosmos/prompting-validators"
NETWORK = "finney"
KEYS = [
    "_step",
    "_timestamp",
    "task",
    "query",
    "reference",
    "challenge",
    "topic",
    "subtopic",
]
ABBREV_CHARS = 8
ENTITY_CHOICES = ("identity", "hotkey", "coldkey")
LOCAL_WANDB_PATH = "./data/wandb"
USERNAME = "opentensor"

api = wandb.Api(timeout=600)

IDENTITIES = {
    "5F4tQyWrhfGVcNhoqeiNsR6KjD4wMZ2kfhLj4oHYuyHbZAc3": "opentensor",
    "5Hddm3iBFD2GLT5ik7LZnT3XJUnRnN8PoeCFgGQgawUVKNm8": "taostats",
    "5HEo565WAy4Dbq3Sv271SAi7syBSofyfhhwRNjFNSM2gP9M2": "foundry",
    "5HK5tp6t2S59DywmHRWPBVJeJ86T61KjurYqeooqj8sREpeN": "bittensor-guru",
    "5FFApaS75bv5pJHfAp2FVLBj9ZaXuFDjEypsaBNc1wCfe52v": "roundtable-21",
    "5EhvL1FVkQPpMjZX4MAADcW42i3xPSF1KiCpuaxTYVr28sux": "tao-validator",
    "5FKstHjZkh4v3qAMSBa1oJcHCLjxYZ8SNTSz1opTv4hR7gVB": "datura",
    "5DvTpiniW9s3APmHRYn8FroUWyfnLtrsid5Mtn5EwMXHN2ed": "first-tensor",
    "5HbLYXUBy1snPR8nfioQ7GoA9x76EELzEq9j7F32vWUQHm1x": "tensorplex",
    "5CsvRJXuR955WojnGMdok1hbhffZyB4N5ocrv82f3p5A2zVp": "owl-ventures",
    "5CXRfP2ekFhe62r7q3vppRajJmGhTi7vwvb2yr79jveZ282w": "rizzo",
    "5HNQURvmjjYhTSksi8Wfsw676b4owGwfLR2BFAQzG7H3HhYf": "neural-internet",
}

EXTRACTORS = {
    "state": lambda x: x.state,
    "run_id": lambda x: x.id,
    "run_path": lambda x: os.path.join(BASE_PATH, x.id),
    "user": lambda x: x.user.name[:16],
    "username": lambda x: x.user.username[:16],
    "created_at": lambda x: pd.Timestamp(x.created_at),
    "last_event_at": lambda x: pd.Timestamp(x.summary.get("_timestamp"), unit="s"),
    "netuid": lambda x: x.config.get("netuid"),
    "mock": lambda x: x.config.get("neuron").get("mock"),
    "sample_size": lambda x: x.config.get("neuron").get("sample_size"),
    "timeout": lambda x: x.config.get("neuron").get("timeout"),
    "epoch_length": lambda x: x.config.get("neuron").get("epoch_length"),
    "disable_set_weights": lambda x: x.config.get("neuron").get("disable_set_weights"),
    # This stuff is from the last logged event
    "num_steps": lambda x: x.summary.get("_step"),
    "runtime": lambda x: x.summary.get("_runtime"),
    "query": lambda x: x.summary.get("query"),
    "challenge": lambda x: x.summary.get("challenge"),
    "reference": lambda x: x.summary.get("reference"),
    "completions": lambda x: x.summary.get("completions"),
    "version": lambda x: x.tags[0],
    "spec_version": lambda x: x.tags[1],
    "vali_hotkey": lambda x: x.tags[2],
    # 'tasks_selected': lambda x: x.tags[3:],
    # System metrics
    "disk_read": lambda x: x.system_metrics.get("system.disk.in"),
    "disk_write": lambda x: x.system_metrics.get("system.disk.out"),
    # Really slow stuff below
    # 'started_at': lambda x: x.metadata.get('startedAt'),
    # 'disk_used': lambda x: x.metadata.get('disk').get('/').get('used'),
    # 'commit': lambda x: x.metadata.get('git').get('commit')
}


def get_leaderboard(df, ntop=10, entity_choice="identity"):
    df = df.loc[df.validator_permit is False]
    df.index = range(df.shape[0])
    return df.groupby(entity_choice).I.sum().sort_values().reset_index().tail(ntop)


@st.cache_data()
def get_metagraph(time):
    print(f"Loading metagraph with time {time}")
    subtensor = bt.subtensor(network=NETWORK)
    m = subtensor.metagraph(netuid=NETUID)
    meta_cols = [
        "I",
        "stake",
        "trust",
        "validator_trust",
        "validator_permit",
        "C",
        "R",
        "E",
        "dividends",
        "last_update",
    ]

    df_m = pd.DataFrame({k: getattr(m, k) for k in meta_cols})
    df_m["uid"] = range(m.n.item())
    df_m["hotkey"] = list(map(lambda a: a.hotkey, m.axons))
    df_m["coldkey"] = list(map(lambda a: a.coldkey, m.axons))
    df_m["ip"] = list(map(lambda a: a.ip, m.axons))
    df_m["port"] = list(map(lambda a: a.port, m.axons))
    df_m["coldkey"] = df_m.coldkey.str[:ABBREV_CHARS]
    df_m["hotkey"] = df_m.hotkey.str[:ABBREV_CHARS]
    df_m["identity"] = df_m.apply(lambda x: f"{x.hotkey} @ uid {x.uid}", axis=1)
    return df_m


@st.cache_data(show_spinner=False)
def load_downloaded_runs(time, cols=KEYS):
    list_cols = ["rewards", "uids"]
    extra_cols = ["turn"]
    df_all = pd.DataFrame()

    progress = st.progress(0, text="Loading downloaded data")
    paths = glob.glob(os.path.join(LOCAL_WANDB_PATH, "*.parquet"))
    for i, path in enumerate(paths):
        run_id = path.split("/")[-1].split(".")[0]
        frame = pd.read_parquet(path).dropna(subset=cols)
        frame._timestamp = frame._timestamp.apply(pd.to_datetime, unit="s")
        # handle missing extra cols such as turn which depend on the version of the codebase
        found_extra_cols = [c for c in frame.columns if c in extra_cols]
        df_long = frame[cols + list_cols + found_extra_cols].explode(list_cols)

        prog_msg = f"Downloading data {i/len(paths)*100:.0f}%"
        progress.progress(i / len(paths), text=f"{prog_msg}... **downloading** `{run_id}`")

        df_all = pd.concat([df_all, df_long.assign(run_id=run_id)], ignore_index=True)

    progress.empty()

    # Ensure we have consistent naming schema for tasks
    task_mapping = {
        "date-based question answering": "date_qa",
        "question-answering": "qa",
    }
    df_all.task = df_all.task.apply(lambda x: task_mapping.get(x, x))

    # Runs which do not have a turn field are imputed to be turn zero (single turn)
    df_all.turn.fillna(0, inplace=True)

    df_all.sort_values(by=["_timestamp"], inplace=True)

    return df_all


@st.cache_data(show_spinner=False)
def build_data(timestamp=None, path=BASE_PATH, min_steps=MIN_STEPS, use_cache=True):
    save_path = "_saved_runs.csv"
    filters = {}
    df = pd.DataFrame()
    # Load the last saved runs so that we only need to update the new ones
    if use_cache and os.path.exists(save_path):
        df = pd.read_csv(save_path)
        df["created_at"] = pd.to_datetime(df["created_at"])
        df["last_event_at"] = pd.to_datetime(df["last_event_at"])

        timestamp_str = df["last_event_at"].max().isoformat()
        filters.update({"updated_at": {"$gte": timestamp_str}})

    progress = st.progress(0, text="Loading data")

    runs = api.runs(path, filters=filters)

    run_data = []
    n_events = 0
    for i, run in enumerate(tqdm.tqdm(runs, total=len(runs))):
        num_steps = run.summary.get("_step", 0)
        if num_steps < min_steps:
            continue
        n_events += num_steps
        prog_msg = f"Loading data {i/len(runs)*100:.0f}%, (total {n_events:,.0f} events)"
        progress.progress(
            i / len(runs),
            text=f"{prog_msg}... **downloading** `{os.path.join(*run.path)}`",
        )

        run_data.append(run)

    progress.empty()

    df_new = pd.DataFrame(
        [{k: func(run) for k, func in EXTRACTORS.items()} for run in tqdm.tqdm(run_data, total=len(run_data))]
    )
    df = pd.concat([df, df_new], ignore_index=True)
    df["duration"] = (df.last_event_at - df.created_at).round("s")
    df["identity"] = df["vali_hotkey"].map(IDENTITIES).fillna("unknown")
    df["vali_hotkey"] = df["vali_hotkey"].str[:ABBREV_CHARS]

    # Drop events that are not related to validator queries
    df.dropna(subset="query", inplace=True)

    print(df.completions.apply(type).value_counts())
    # Assumes completions is in the frame
    df["completions"] = df["completions"].apply(lambda x: x if isinstance(x, list) else eval(x))

    df["completion_words"] = df.completions.apply(
        lambda x: sum([len(xx.split()) for xx in x]) if isinstance(x, list) else 0
    )
    df["validator_words"] = df.apply(
        lambda x: len(str(x.query).split()) + len(str(x.challenge).split()) + len(str(x.reference).split()),
        axis=1,
    )

    df.to_csv(save_path, index=False)

    return df


@st.cache_data()
def normalize_rewards(df, turn=0, percentile=0.98):
    top_reward_stats = df.loc[df.turn == turn].astype({"rewards": float}).groupby("task").rewards.quantile(percentile)

    df["best_reward"] = df.task.map(top_reward_stats)
    df["normalized_rewards"] = df["rewards"].astype(float) / df["best_reward"]
    return df


@st.cache_data(show_spinner=False)
def download_runs(time, df_vali):
    pbar = tqdm.tqdm(df_vali.index, total=len(df_vali))

    progress = st.progress(0, text="Loading data")

    for i, idx in enumerate(pbar):
        row = df_vali.loc[idx]

        prog_msg = f"Downloading data {i/len(df_vali)*100:.0f}%"
        progress.progress(
            i / len(df_vali),
            text=f"{prog_msg}... **downloading** `{os.path.join(*row.run_id)}`",
        )

        save_path = f"data/wandb/{row.run_id}.parquet"
        if os.path.exists(save_path):
            pbar.set_description(f">> Skipping {row.run_id!r} because file {save_path!r} already exists")
            continue

        try:
            pbar.set_description(f"* Downloading run {row.run_id!r}", flush=True)
            run = api.run(row.run_path)

            # By default we just download a subset of events (500 most recent)
            df = run.history()
            df.to_parquet(save_path)
        except KeyboardInterrupt:
            break
        except Exception:
            pbar.set_description(f"- Something went wrong with {row.run_id!r}: {print_exc()}\n")

    progress.empty()


def get_productivity(df_runs):
    total_duration = df_runs.last_event_at.max() - df_runs.created_at.min()
    total_steps = df_runs.num_steps.sum()
    total_completions = (df_runs.num_steps * df_runs.sample_size).sum()
    total_completion_words = (df_runs.num_steps * df_runs.completion_words).sum()
    total_completion_tokens = round(total_completion_words / 0.75)
    total_validator_words = (
        df_runs.num_steps
        * df_runs.apply(
            lambda x: len(str(x.query).split()) + len(str(x.challenge).split()) + len(str(x.reference).split()),
            axis=1,
        )
    ).sum()
    total_validator_tokens = round(total_validator_words / 0.75)
    total_dataset_tokens = total_completion_tokens + total_validator_tokens

    return {
        "duration": total_duration,
        "total_events": total_steps,
        "total_completions": total_completions,
        "total_completion_tokens": total_completion_tokens,
        "total_validator_tokens": total_validator_tokens,
        "total_tokens": total_dataset_tokens,
    }


@st.cache_data(show_spinner=False)
def get_reward_stats(
    df,
    exclude_multiturn=True,
    freq="1D",
    remove_zero_rewards=True,
    agg="mean",
    date_min="2024-01-22",
    date_max="2024-06-25",
):
    df = df.loc[df._timestamp.between(pd.Timestamp(date_min), pd.Timestamp(date_max))]
    if exclude_multiturn:
        df = df.loc[df.turn == 0]
    if remove_zero_rewards:
        df = df.loc[df.rewards > 0]

    groups = ["run_id", pd.Grouper(key="_timestamp", freq=freq), "task"]
    return df.groupby(groups).agg({"rewards": agg, "normalized_rewards": agg})


def get_release_dates():
    release_dates = pd.DataFrame(
        [
            {
                "version": "1.0.0",
                "release_date": pd.Timestamp(month=1, day=22, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": ["qa", "summarization"],
            },
            {
                "version": "1.0.1",
                "release_date": pd.Timestamp(month=1, day=22, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": [],
            },
            {
                "version": "1.0.2",
                "release_date": pd.Timestamp(month=1, day=24, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": ["qa", "summarization"],
            },
            {
                "version": "1.0.3",
                "release_date": pd.Timestamp(month=2, day=14, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": [],
            },
            {
                "version": "1.0.4",
                "release_date": pd.Timestamp(month=2, day=15, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": [],
            },
            {
                "version": "1.1.0",
                "release_date": pd.Timestamp(month=2, day=21, year=2024),
                "note": "decay scores",
                "model": "zephyr",
                "tasks_affected": ["date_qa", "math"],
            },
            {
                "version": "1.1.1",
                "release_date": pd.Timestamp(month=2, day=28, year=2024),
                "note": "reduce penalty weight",
                "model": "zephyr",
                "tasks_affected": ["date_qa", "qa", "summarization"],
            },
            {
                "version": "1.1.2",
                "release_date": pd.Timestamp(month=2, day=29, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": [],
            },
            {
                "version": "1.1.3",
                "release_date": pd.Timestamp(month=3, day=11, year=2024),
                "note": "",
                "model": "zephyr",
                "tasks_affected": [],
            },
            {
                "version": "1.2.0",
                "release_date": pd.Timestamp(month=3, day=19, year=2024),
                "note": "vllm",
                "model": "zephyr",
                "tasks_affected": [],
            },
            {
                "version": "1.3.0",
                "release_date": pd.Timestamp(month=3, day=27, year=2024),
                "note": "",
                "model": "solar",
                "tasks_affected": ["all", "math"],
            },
            {
                "version": "2.0.0",
                "release_date": pd.Timestamp(month=4, day=4, year=2024),
                "note": "streaming",
                "model": "solar",
                "tasks_affected": ["math", "qa", "summarization"],
            },
            {
                "version": "2.1.0",
                "release_date": pd.Timestamp(month=4, day=18, year=2024),
                "note": "chattensor prompt",
                "model": "solar",
                "tasks_affected": ["generic"],
            },
            {
                "version": "2.2.0",
                "release_date": pd.Timestamp(month=5, day=1, year=2024),
                "note": "multiturn + paraphrase",
                "model": "solar",
                "tasks_affected": ["sentiment", "translation", "math"],
            },
            {
                "version": "2.3.0",
                "release_date": pd.Timestamp(month=5, day=20, year=2024),
                "note": "llama + freeform date",
                "model": "llama",
                "tasks_affected": ["all", "date_qa"],
            },
            {
                "version": "2.3.1",
                "release_date": pd.Timestamp(month=5, day=21, year=2024),
                "note": "",
                "model": "llama",
                "tasks_affected": ["date_qa"],
            },
            {
                "version": "2.4.0",
                "release_date": pd.Timestamp(month=6, day=5, year=2024),
                "note": "streaming penalty",
                "model": "llama",
                "tasks_affected": [],
            },
            {
                "version": "2.4.1",
                "release_date": pd.Timestamp(month=6, day=6, year=2024),
                "note": "",
                "model": "llama",
                "tasks_affected": [],
            },
            {
                "version": "2.4.2",
                "release_date": pd.Timestamp(month=6, day=7, year=2024),
                "note": "",
                "model": "llama",
                "tasks_affected": [],
            },
            {
                "version": "2.4.2",
                "release_date": pd.Timestamp(month=6, day=7, year=2024),
                "note": "",
                "model": "llama",
                "tasks_affected": [],
            },
            {
                "version": "2.5.0",
                "release_date": pd.Timestamp(month=6, day=18, year=2024),
                "note": "reduce multiturn",
                "model": "llama",
                "tasks_affected": ["translation", "sentiment"],
            },
            {
                "version": "2.5.1",
                "release_date": pd.Timestamp(month=6, day=25, year=2024),
                "note": "reduce timeout",
                "model": "llama",
                "tasks_affected": [],
            },
        ]
    )
    return release_dates


def plot_reward_trends(
    df_stats,
    task="qa",
    window=14,
    col="normalized_reward",
    annotate=False,
    task_label="Question answering",
):
    stats = df_stats.reset_index()
    release_dates = get_release_dates()
    stats_task = stats.loc[(stats.task == task)].sort_values(by="_timestamp")
    stats_task["rewards_ma"] = stats_task[col].rolling(window, min_periods=0).mean()
    fig = px.area(
        stats_task,
        x="_timestamp",
        y="rewards_ma",
        title=f"Reward Trend for {task_label} Task",
        labels={"rewards_ma": f"Rewards [{window} day avg.]", "_timestamp": ""},
        width=800,
        height=600,
    )

    if not annotate:
        return fig

    # Add annotations based on relevant releases
    for idx, row in release_dates.iterrows():
        line_color = "grey"
        if task in row["tasks_affected"]:
            line_color = "red"
        elif "all" not in row["tasks_affected"]:
            line_color = "blue"
        # TODO add annotation or something
        fig.add_vline(
            row["release_date"], line_color=line_color, opacity=0.6, line_dash="dot", line_width=1
        )  # , annotation_text=str(v))

    return fig


@st.cache_data()
def get_task_counts(df_runs, df_events):
    # Get mapping from run id to prompting repo version
    run_to_version = df_runs.set_index("run_id").version.to_dict()

    df_events["version"] = df_events.run_id.map(run_to_version)

    def version_to_spec(version):
        major, minor, patch = version.split(".")
        return 10_000 * major + 100 * minor + patch

    def get_closest_prev_version(version, my_versions):
        ref_spec = version_to_spec(version)
        my_specs = list(map(version_to_spec, my_versions))

        match = my_specs[0]
        for spec in my_specs[1:]:
            if spec > ref_spec:
                break

            match = spec

        return my_versions[my_specs.index(match)]

    # Now estimate the distribution of tasks for each version using the event data
    task_rate = df_events.groupby("version").task.value_counts(normalize=True).unstack().fillna(0)
    # Impute missing versions
    for v in sorted(df_runs.version.unique()):
        if v not in task_rate.index:
            prev_version = get_closest_prev_version(v, list(task_rate.index))
            print(f"Imputing version {v} with task rate from closes previous version {prev_version!r}")
            task_rate.loc[v] = task_rate.loc[prev_version]

    # get esimated number of each task generated in every run using summary dataframe
    task_counts = (
        df_runs.set_index("created_at")
        .sort_index()
        .apply(lambda x: round(task_rate.loc[x.version] * x.num_steps), axis=1)
        .cumsum()
    )
    return task_counts


def load_state_vars(username=USERNAME, percentile=0.95):
    UPDATE_INTERVAL = 600

    df_runs = build_data(time.time() // UPDATE_INTERVAL, use_cache=True)

    df_runs = df_runs.loc[df_runs.netuid.isin([1, 61, 102])]
    st.toast(f"Loaded {len(df_runs)} runs")

    df_vali = df_runs.loc[df_runs.username == username]

    download_runs(time.time() // UPDATE_INTERVAL, df_vali)

    df_events = load_downloaded_runs(time.time() // UPDATE_INTERVAL)
    df_events = normalize_rewards(df_events, percentile=percentile)

    yesterday = pd.Timestamp.now() - pd.Timedelta("1d")
    runs_alive_24h_ago = df_runs.last_event_at > yesterday

    df_runs_24h = df_runs.loc[runs_alive_24h_ago]

    # weight factor indicates the fraction of events that happened within the last 24 hour.
    fraction = 1 - (yesterday - df_runs_24h.created_at) / (pd.Timestamp.now() - df_runs_24h.created_at)
    df_runs_24h["fraction"] = fraction.clip(0, 1)
    df_runs_24h["num_steps"] *= fraction.clip(0, 1)

    df_task_counts = get_task_counts(df_runs, df_events)

    df_m = get_metagraph(time.time() // UPDATE_INTERVAL)

    return {
        "df_runs": df_runs,
        "df_runs_24h": df_runs_24h,
        "df_vali": df_vali,
        "df_events": df_events,
        "metagraph": df_m,
        "df_task_counts": df_task_counts,
    }


if __name__ == "__main__":

    pass
