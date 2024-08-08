import bittensor as bt
import settings
from loguru import logger
import random


def check_uid_availability(
    metagraph: "bt.metagraph.Metagraph",
    uid: int,
    vpermit_tao_limit: int,
    coldkeys: set = None,
    ips: set = None,
) -> bool:
    """Check if uid is available. The UID should be available if it is serving and has less than vpermit_tao_limit stake
    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object
        uid (int): uid to be checked
        vpermit_tao_limit (int): Validator permit tao limit
        coldkeys (set): Set of coldkeys to exclude
        ips (set): Set of ips to exclude
    Returns:
        bool: True if uid is available, False otherwise
    """
    # Filter non serving axons.
    if not metagraph.axons[uid].is_serving:
        logger.debug(f"uid: {uid} is not serving")
        return False

    # Filter validator permit > 1024 stake.
    if metagraph.validator_permit[uid] and metagraph.S[uid] > vpermit_tao_limit:
        logger.debug(f"uid: {uid} has vpermit and stake ({metagraph.S[uid]}) > {vpermit_tao_limit}")
        logger.debug(f"uid: {uid} has vpermit and stake ({metagraph.S[uid]}) > {vpermit_tao_limit}")
        return False

    if coldkeys and metagraph.axons[uid].coldkey in coldkeys:
        return False

    if ips and metagraph.axons[uid].ip in ips:
        return False

    # Available otherwise.
    return True


def get_random_uids(
    metagraph: "bt.metagraph.Metagraph", wallet: "bt.wallet", k: int, exclude: list[int] = None
) -> list[int]:
    """Returns k available random uids from the metagraph.
    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object.
        wallet (bt.wallet): The wallet the API is using.
        k (int): Number of uids to return.
        exclude (list[int]): List of uids to exclude from the random sampling.
    Returns:
        uids (list[int]): Randomly sampled available uids.
    Notes:
        If `k` is larger than the number of available `uids`, set `k` to the number of available `uids`.
    """
    candidate_uids = []
    coldkeys = set()
    ips = set()
    self_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)

    for uid in range(metagraph.n.item()):
        if uid == self_uid:
            continue

        uid_is_available = check_uid_availability(
            metagraph,
            uid,
            settings.QUERY_VPERMIT_TAO_LIMIT,
            coldkeys,
            ips,
        )
        if not uid_is_available:
            continue

        if settings.QUERY_UNIQUE_COLDKEYS:
            coldkeys.add(metagraph.axons[uid].coldkey)

        if settings.QUERY_UNIQUE_IPS:
            ips.add(metagraph.axons[uid].ip)

        if exclude is None or uid not in exclude:
            candidate_uids.append(uid)

    # Check if candidate_uids contain enough for querying, if not grab all avaliable uids
    if len(candidate_uids) == 0:
        raise ValueError(f"No eligible uids were found. Cannot return any uids")

    if 0 < len(candidate_uids) < k:
        logger.warning(
            f"Requested {k} uids but only {len(candidate_uids)} were available. To disable this warning reduce the sample size (--neuron.sample_size)"
        )
        return candidate_uids

    return random.sample(candidate_uids, k)


def get_top_incentive_uids(metagraph: "bt.metagraph.Metagraph", k: int, vpermit_tao_limit: int) -> list[int]:
    """Returns the top k uids with the highest incentives.

    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object
        k (int): Number of uids to return.
        vpermit_tao_limit (int): The minimal amount of stake a validator must have to be included in the query.

    Returns:
        list[int]: the top k uids with the highest incentives.
    """
    miners_uids = list(
        map(
            int,
            filter(
                lambda uid: check_uid_availability(metagraph, uid, vpermit_tao_limit),
                metagraph.uids,
            ),
        )
    )

    # Builds a dictionary of uids and their corresponding incentives
    all_miners_incentives = {
        "miners_uids": miners_uids,
        "incentives": list(map(lambda uid: metagraph.I[uid], miners_uids)),
    }

    # Zip the uids and their corresponding incentives into a list of tuples
    uid_incentive_pairs = list(zip(all_miners_incentives["miners_uids"], all_miners_incentives["incentives"]))

    # Sort the list of tuples by the incentive value in descending order
    uid_incentive_pairs_sorted = sorted(uid_incentive_pairs, key=lambda x: x[1], reverse=True)
    logger.debug(f"Top uids by incentive: {uid_incentive_pairs_sorted[:k]}")

    # Extract the top k uids
    top_k_uids = [uid for uid, _ in uid_incentive_pairs_sorted[:k]]
    return [218]
    return top_k_uids
