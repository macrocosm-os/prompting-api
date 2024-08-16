import bittensor as bt
import settings
from loguru import logger
import random

from network.meta.schemas import QueryChatRequest


# TODO: consider using an LRU (or similiar) to cache the UIDs


def sample_uids(metagraph: "bt.metagraph.Metagraph", wallet: "bt.wallet", params: QueryChatRequest) -> list[int]:
    """Samples UIDs based on the sampling mode.  If querying validators, we will only ever return one.

    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object.
        wallet (bt.wallet): The wallet the API is using.
        params (QueryChatRequest): Request parameters

    Raises:
        ValueError: Invalid sampling mode

    Returns:
        list[int]: list of sampled UIDs
    """
    if params.sampling_mode == "list":
        if params.query_validators:
            # Return only 1 random validator from the list
            return random.sample(params.uid_list, 1)
        else:
            # Return k random miners from the list
            return random.sample(params.uid_list, params.k)
    if params.sampling_mode == "random":
        return get_random_uids(
            metagraph=metagraph,
            wallet=wallet,
            params=params,
        )
    if params.sampling_mode == "top_incentive":
        return get_top_incentive_uids(
            metagraph=metagraph,
            wallet=wallet,
            params=params,
        )

    raise ValueError(f"Invalid sampling mode: {params.sampling_mode}")


def get_random_uids(metagraph: "bt.metagraph.Metagraph", wallet: "bt.wallet", params: QueryChatRequest) -> list[int]:
    """Returns k available random uids from the metagraph.
    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object.
        wallet (bt.wallet): The wallet the API is using.
        params (QueryChatRequest): Request parameters
    Returns:
        uids (list[int]): Randomly sampled available uids.
    Notes:
        If `k` is larger than the number of available `uids`, set `k` to the number of available `uids`.
    """
    candidate_uids = get_all_valid_uids(metagraph, wallet, params)

    # Check if candidate_uids contain enough for querying, if not grab all avaliable uids
    if len(candidate_uids) == 0:
        raise ValueError("No eligible uids were found. Cannot return any uids")

    if 0 < len(candidate_uids) < params.k:
        logger.warning(
            f"Requested {params.k} uids but only {len(candidate_uids)} were available. To disable this warning reduce the sample size (--neuron.sample_size)"
        )
        return candidate_uids

    if params.query_validators:
        # Always return just one validator (k = number of miners)
        return random.sample(candidate_uids, 1)

    return random.sample(candidate_uids, params.k)


def get_top_incentive_uids(
    metagraph: "bt.metagraph.Metagraph", wallet: "bt.wallet", params: QueryChatRequest
) -> list[int]:
    """Returns the top k uids with the highest incentives.

    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object
        wallet (bt.wallet): The wallet the API is using.
        params (QueryChatRequest): Request parameters

    Returns:
        list[int]: the top k uids (miners) with the highest incentives.
    """
    candidate_uids = get_all_valid_uids(metagraph, wallet, params)

    # Builds a dictionary of uids and their corresponding incentives
    all_miners_incentives = {
        "miners_uids": candidate_uids,
        "incentives": list(map(lambda uid: metagraph.I[uid], candidate_uids)),
    }

    # Zip the uids and their corresponding incentives into a list of tuples
    uid_incentive_pairs = list(zip(all_miners_incentives["miners_uids"], all_miners_incentives["incentives"]))

    # Sort the list of tuples by the incentive value in descending order
    uid_incentive_pairs_sorted = sorted(uid_incentive_pairs, key=lambda x: x[1], reverse=True)
    logger.debug(f"Top uids by incentive: {uid_incentive_pairs_sorted[:params.k]}")

    if params.query_validators:
        # Always return just one validator (k = number of miners)
        return [uid_incentive_pairs_sorted[0][0]]

    # Extract the top k uids
    top_k_uids = [uid for uid, _ in uid_incentive_pairs_sorted[: params.k]]
    return top_k_uids


def get_all_valid_uids(metagraph: "bt.metagraph.Metagraph", wallet: "bt.wallet", params: QueryChatRequest) -> list[int]:
    """_summary_

    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object
        wallet (bt.wallet): The wallet the API is using.
        params (QueryChatRequest): Request parameters

    Returns:
        list[int]: All UIDs that are valid for querying
    """
    candidate_uids = []
    unique_coldkeys = set()
    unique_ips = set()
    self_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)

    for uid in metagraph.uids:
        if uid == self_uid:
            continue

        if params.excluded_uids and uid in params.excluded_uids:
            continue

        if (coldkey := metagraph.axons[uid].coldkey) in unique_coldkeys:
            continue
        elif settings.QUERY_UNIQUE_COLDKEYS:
            unique_coldkeys.add(coldkey)

        if (ip := metagraph.axons[uid].ip) in unique_ips:
            continue
        elif settings.QUERY_UNIQUE_IPS:
            unique_ips.add(ip)

        if not is_uid_valid(uid, metagraph, params):
            continue

        candidate_uids.append(uid)
    return candidate_uids


def is_uid_valid(
    uid: int,
    metagraph: "bt.metagraph.Metagraph",
    params: QueryChatRequest,
) -> bool:
    """Check if uid is valid. The UID is valid if it is serving and matches the params

    Args:
        metagraph (bt.metagraph.Metagraph): Metagraph object
        uid (int): uid to be checked
        vpermit_tao_limit (int): Validator permit tao limit

    Returns:
        bool: True if uid is available for querying, False otherwise
    """
    # Filter non serving axons.
    if not metagraph.axons[uid].is_serving:
        logger.trace(f"uid: {uid} is not serving")
        return False

    if params.query_validators != is_uid_validator(metagraph, uid):
        # if querying validators (query_validators==True), validator check must pass
        # if querying miners (query_validators==False), validator check must fail
        return False

    # Available otherwise.
    return True


def is_uid_validator(metagraph: "bt.metagraph.Metagraph", uid: int) -> bool:
    """Is the UID a validator or a miner -
    there is no really good way to do this but we should make validators most restictive
    and, otherwise, assume the UID is a miner.  Validators should have a permit and enough stake
    as well as be active (updated extrinsics in the last ~1k blocks)"""
    return (
        (settings.VALIDATOR_MIN_STAKE <= metagraph.S[uid])
        and bool(metagraph.validator_permit[uid])
        and bool(metagraph.active[uid])
    )
