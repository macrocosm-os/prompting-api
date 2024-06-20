from typing import List
from prompting.utils.uids import check_uid_availability


def get_top_incentive_uids(metagraph, k: int, vpermit_tao_limit: int) -> List[int]:
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
    uid_incentive_pairs = list(
        zip(all_miners_incentives["miners_uids"], all_miners_incentives["incentives"])
    )

    # Sort the list of tuples by the incentive value in descending order
    uid_incentive_pairs_sorted = sorted(
        uid_incentive_pairs, key=lambda x: x[1], reverse=True
    )

    # Extract the top 10 uids
    top_k_uids = [uid for uid, incentive in uid_incentive_pairs_sorted[:k]]

    return top_k_uids
