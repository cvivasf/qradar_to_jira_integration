import requests
import time
import os
import json
from typing import Dict, List
from app_config import ServerConfig, offenses_to_jira_logger


qradar_headers = {'SEC': None, 'Accept': 'application/json'} #Headers for QRadar API. Paritally obtained from config.ini file
config: ServerConfig = None
jira_auth = ()

def load_last_processed_id()-> int:
    """Load the last processed offense ID from a file.
    
    :return: ID of the last processed offense ID.
    :rtype: int
    :raises OSError,FileNotFoundError,ValueError: if an error occurs when opening/reading the file
    """
    if os.path.exists(config.last_processed_id_file):
        with open(config.last_processed_id_file, 'r') as file:
            return int(file.read().strip())
    return None



def save_last_processed_id(offense_id:int) -> None:
    """Save the last processed offense ID to a file and updates the script variable
    
    :param int offense_id: The ID of the offense to write on the file as the latest offense processed.
    :return: Nothing.
    :rtype: None
    :raises OSError,FileNotFoundError,ValueError: if an error occurs when opening/writing the file"""
    with open(config.last_processed_id_file, 'w') as file:
        file.write(str(offense_id))
    global last_processed_id
    last_processed_id = offense_id



def save_failed_offense_update_on_jira(offense_id_that_failed:int) -> None:
    """Appends a numeric offense ID the failed JIRA uploaded offenses file, separated by commas.

    :param int offense_id_that_failed: The ID of the offense to write on the Failed Offenses file as the latest offense that failed to be uploaded to JIRA.
    :return: Nothing.
    :rtype: None
    :raises OSError,FileNotFoundError,ValueError: if an error occurs when opening/writing the file"""
    with open(config.failed_processed_id_file, 'a') as file:
        if file.tell() > 0:  # Check if the file is not empty
            file.write(',')
        file.write(str(offense_id_that_failed))



def get_latest_offenses() -> List[Dict[any,any]]:
    """Retrieve the latest offense from QRadar. Filtering by status as OPEN, the ID being bigger than the offset ID of the last processed ID from QRADAR, and filtering by start_time in ascendant mode to get the latest one.
    
    :return: JSON response of the offenses obtained.
    :rtype: Dict[any,any]
    :raises HttpError: if an error occurred making the HTTP request"""
    params = { "filter": 'status=OPEN and id > ' + str(last_processed_id), "sort": "+start_time" }
    global qradar_headers
    qradar_headers = qradar_headers.copy()
    qradar_headers["RANGE"] = "items=0-0"
    qradar_headers["VERSION"] = "20.0"
    response = requests.get(config.qradar_url, headers=qradar_headers, verify=False, params=params)
    response.raise_for_status()
    return response.json()



def create_jira_ticket(offense):
    """Create a new JIRA ticket for the given offense.
    
    :param Dict[any,any] offense: The offense obtained from QRADAR SIEM
    :return: The json response from creating the JIRA ticket
    :rtype: Dict[any,any]
    :raises HttpError: if an error occurred making the HTTP request"""
    issue_data = {
        "fields": {
            "project": {
                "key": config.jira_project_key
            },
            "summary": f"QRadar Offense {offense['id']}: {offense['description']}",
            "description": (
                f"Offense ID: {offense['id']}\n"
                f"Offense Description: {offense['description']}\n"
                f"Offense Type: {offense['offense_type']}\n"
                f"Source IPs: {', '.join(offense.get('source_address_ids', []))}\n"
                f"Destination IPs: {', '.join(offense.get('destination_address_ids', []))}\n"
                f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(offense['start_time'] / 1000))}\n"
                f"Last Updated: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(offense['last_updated_time'] / 1000))}\n"
            ),
            "issuetype": {
                "name": "Task"
            }
        }
    }

    response = requests.post(config.jira_url, json=issue_data, auth=jira_auth)
    response.raise_for_status()
    return response.json()



def process_offense():
    """Process the next unprocessed offense and create a JIRA ticket for it."""
    global last_processed_id
    last_processed_id = load_last_processed_id()
    if not last_processed_id:
        raise Exception("ERROR! Provide a minimum Offense ID on the Offense ID index File!")
    
    offenses_to_jira_logger.info("Last processed Offense ID stored on memory file: " + str(last_processed_id) + " . Getting offense from QRADAR SIEM...")
    latest_offense = get_latest_offenses()
    offenses_to_jira_logger.info("Call succesfully made to QRADAR SIEM...")
    offenses_to_jira_logger.debug("Offense to process and send to JIRA: " + json.dumps(latest_offense))
    # Sort offenses by ID in ascending order
    #latest_offense.sort(key=lambda x: x.get('id',None))

    if (not latest_offense or len(latest_offense) == 0):
        offenses_to_jira_logger.info("No offenses obtained from QRADAR SIEM.")
    #For the first offense obtained, create the jira ticked and update the file containing the last processed ID.
    for offense in latest_offense:
        offense_id = offense.get('id', None)
        if last_processed_id is not None and offense_id > last_processed_id:
            offenses_to_jira_logger.info(f"Processing offense with ID. About to create ticket on JIRA!: {offense_id}")
            try:
                #create_jira_ticket(offense)
                save_last_processed_id(offense_id)
                pass
            except Exception as e:
                offenses_to_jira_logger.error(f"Exception creating JIRA ticket for offense with ID: {str(offense_id)}: {str(e)}")
                save_failed_offense_update_on_jira(offense_id) #store the failed offense to be uploaded to jira in a file
            break #Process only one offense at a time
        else:
            offenses_to_jira_logger.error(f"Offense {offense_id} has already been processed. Please, increase the Offense ID offset on the file to start scanning new offenses!.")

def init_vars(passedconfig: ServerConfig):
    '''
    Initializates variables for the script

    :param int passedconfig: Configuration received from the config.ini file
    :return: None
    :rtype: None
    '''
    global config
    config = passedconfig
    global qradar_headers
    qradar_headers = {'SEC': config.qradar_api_key, 'Accept': 'application/json'}
    global jira_auth
    jira_auth = (config.jira_user, config.jira_api_token)

def main(passedconfig: ServerConfig):
    
    init_vars(passedconfig)

    """Main loop to continuously check for new offenses and process them."""
    while True:
        try:
            process_offense()
        except Exception as e:
            offenses_to_jira_logger.error(f"Error pulling and/or sending tickets to JIRA from QRADAR SIEM Offenses obtention: {str(e)}")
        time.sleep(config.polling_rate_new_offenses_checking)

if __name__ == "__main__":
    main()