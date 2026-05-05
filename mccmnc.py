"""
A module for matching Mobile Country Codes (MCC) and Mobile Network Codes (MNC)
against a JSON dataset from https://www.mcc-mnc.com/.
"""

import json
import os
import sys
from urllib.error import URLError
from urllib.request import urlopen

from tqdm import tqdm

MCC_MNC_API_URL = "https://mcc-mnc.com/api/v1/mcc-mnc.php"
JSON_PATH = os.path.join(os.path.dirname(__file__), "mccmnc.json")


def find_matches(
    user_cc=None, user_mcc=None, user_mnc=None, user_plmn=None, user_network=None
):
    """
    Match the given criteria against the JSON data.

    Args:
        user_cc (str, optional): User's desired Country Code (CC).
        user_mcc (str, optional): User's desired Mobile Country Code (MCC).
        user_mnc (str, optional): User's desired Mobile Network Code (MNC).
        user_plmn (str, optional): User's desired Public Land Mobile Network (PLMN).
        user_network (str, optional): User's desired Network.

    Returns:
        dict: Dictionary of matching PLMNs with their details.
    """
    match_list = {}

    with open(JSON_PATH, "r", encoding="utf-8") as json_file:
        json_data = json.load(json_file)

    for plmn, details in json_data.items():
        if user_plmn and user_plmn != plmn:
            continue
        if user_cc and str(user_cc) != details["CC"]:
            continue
        if user_mcc and str(user_mcc) != details["MCC"]:
            continue
        if user_mnc and str(user_mnc) != details["MNC"]:
            continue
        if user_network and user_network != details["NETWORK"].lower():
            continue
        match_list[plmn] = details

    return match_list


def update():
    """
    Update the JSON data by fetching from the MCC-MNC API.

    Returns:
        None
    """
    try:
        print(f"Fetching MCC-MNC data from API: {MCC_MNC_API_URL}")
        with urlopen(MCC_MNC_API_URL, timeout=30) as response:
            api_data = json.loads(response.read().decode("utf-8"))

        if "data" not in api_data:
            print("Error: Invalid API response format")
            sys.exit(1)

        entries = api_data["data"]
        total_entries = len(entries)
        print(f"Received {total_entries} entries from API")

        if os.path.exists(JSON_PATH):
            print(f"Removing old JSON dictionary {JSON_PATH}.")
            os.remove(JSON_PATH)

        print(f"Creating new JSON dictionary {JSON_PATH}.")
        json_data = {}

        progress_bar = tqdm(
            total=total_entries,
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
            colour="blue",
        )

        for i, entry in enumerate(entries, start=1):
            mcc = entry.get("mcc", "")
            mnc = entry.get("mnc", "")
            plmn = mcc + mnc  # MCC + MNC
            json_data[plmn] = {
                "MCC": mcc,
                "MNC": mnc,
                "ISO": entry.get("iso", ""),
                "COUNTRY": entry.get("country", ""),
                "CC": entry.get("countryCode", ""),
                "NETWORK": entry.get("network", "unknown"),
            }
            progress_bar.set_description(f"Processing entry {i}/{total_entries}")
            progress_bar.update(1)

        progress_bar.close()

        with open(JSON_PATH, "w+", encoding="utf-8") as json_file:
            print(f"\nSaving JSON dictionary to {JSON_PATH}.")
            json.dump(json_data, json_file, indent=4, sort_keys=True)

        print(f"Successfully updated MCC-MNC data with {len(json_data)} entries.")

    except URLError as e:
        print(f"Error downloading from API: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        sys.exit(1)
