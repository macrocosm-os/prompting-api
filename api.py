
import atexit
import datetime

from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

import utils

app = Flask(__name__)


# Global variables (saves time on loading data)
state_vars = None
reload_timestamp = datetime.datetime.now().strftime('%D %T')


def load_data():
    """
    Reload the state variables
    """
    global state_vars, reload_timestamp
    state_vars = utils.load_state_vars()

    reload_timestamp = datetime.datetime.now().strftime('%D %T')

    print(f'Reloaded data at {reload_timestamp}')


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=load_data, trigger="interval", seconds=60*30)
    scheduler.start()

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())


@app.route('/', methods=['GET'])
def home():
    return "Welcome to the Bittensor Protein Folding Leaderboard API!"


@app.route('/updated', methods=['GET'])
def updated():
    return reload_timestamp


@app.route('/data', methods=['GET'])
@app.route('/data/<period>', methods=['GET'])
def data(period=None):
    """
    Get the productivity metrics
    """
    assert period in ('24h', None), f"Invalid period: {period}. Must be '24h' or None."
    df = state_vars["dataframe_24h"] if period == '24h' else state_vars["dataframe"]
    return jsonify(
        df.astype(str).to_dict(orient='records')
    )

@app.route('/productivity', methods=['GET'])
@app.route('/productivity/<period>', methods=['GET'])
def productivity_metrics(period=None):
    """
    Get the productivity metrics
    """

    assert period in ('24h', None), f"Invalid period: {period}. Must be '24h' or None."
    df = state_vars["dataframe_24h"] if period == '24h' else state_vars["dataframe"]
    return jsonify(
        utils.get_productivity(df)
    )


@app.route('/throughput', methods=['GET'])
@app.route('/throughput/<period>', methods=['GET'])
def throughput_metrics(period=None):
    """
    Get the throughput metrics
    """
    assert period in ('24h', None), f"Invalid period: {period}. Must be '24h' or None."
    df = state_vars["dataframe_24h"] if period == '24h' else state_vars["dataframe"]
    return jsonify(utils.get_data_transferred(df))


@app.route('/metagraph', methods=['GET'])
def metagraph():
    """
    Get the metagraph data
    Returns:
    - metagraph_data: List of dicts (from pandas DataFrame)
    """

    df_m = state_vars["metagraph"]

    return jsonify(
        df_m.to_dict(orient='records')
    )

@app.route('/leaderboard', methods=['GET'])
@app.route('/leaderboard/<entity>', methods=['GET'])
@app.route('/leaderboard/<entity>/<ntop>', methods=['GET'])
def leaderboard(entity='identity',ntop=10):
    """
    Get the leaderboard data
    Returns:
    - leaderboard_data: List of dicts (from pandas DataFrame)
    """

    assert entity in utils.ENTITY_CHOICES, f"Invalid entity choice: {entity}"

    df_miners = utils.get_leaderboard(
        state_vars["metagraph"],
        ntop=int(ntop),
        entity_choice=entity
        )

    return jsonify(
        df_miners.to_dict(orient='records')
    )

@app.route('/validator', methods=['GET'])
def validator():
    """
    Get the validator data
    Returns:
    - validator_data: List of dicts (from pandas DataFrame)
    """
    df_m = state_vars["metagraph"]
    df_validators = df_m.loc[df_m.validator_trust > 0]

    return jsonify(
        df_validators.to_dict(orient='records')
    )


if __name__ == '__main__':

    load_data()
    start_scheduler()

    app.run(host='0.0.0.0', port=5001, debug=True)
    

    # to test locally
    # curl -X GET http://0.0.0.0:5001/data
    
