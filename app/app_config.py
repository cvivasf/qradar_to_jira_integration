import configparser
import logging
from logging.handlers import RotatingFileHandler

class ServerConfig:
    '''Class for app configuration. Contains main configuration variables that are used for the app.'''
    def __init__(self):
        self.qradar_url = None
        self.qradar_api_key = None
        self.failed_processed_id_file = None
        self.last_processed_id_file = None
        self.jira_url = None
        self.jira_user = None
        self.jira_api_token = None
        self.jira_project_key = None
        self.logging_level = None
        self.cli_logging_enabled = None
        self.polling_rate_new_offenses_checking = None
        self.polling_rate_offenses_failure_reuploading = None

def get_logging_level(level:str):
    '''Maps the logging level string to a corresponding logging level integer valule. If an invalid one is passed, will default to INFO.

    Accepted levels:

    - DEBUG/debug: 10
    - INFO/info:  20
    - WARNING/warning: 30
    - ERROR/error: 40
    - CRITICAL/critical: 50
    
    :param: str level: Level of logging to set based on the level received as an string.
    :return: Level of the logging to be used on the files.
    :rtype: int 
    '''
    
    if level is None:
        level = ''
    else:
        level = level.strip().upper()

    log_level_mapping = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    # Set the logging level for the app logger based on the config value
    if level in log_level_mapping:
        return log_level_mapping[level]
    else:
        print(f"An invalid logging level has been retrieved from the config.ini file. Using default level INFO.")
        return logging.INFO

def init_server_config():
    '''Initializes ServerConfig object to be used by app modules by using the config.ini file and the configparser module.
    
    :return: ServerConfig object with the configuration for the app
    :rtype: ServerConfig'''
    #Read the configuration file
    print('[QRadar2Jira_Integration] Building App configparser...')
    config = configparser.ConfigParser()
    print('[QRadar2Jira_Integration] Reading config.ini file...')
    config.read('config.ini')
    print('[QRadar2Jira_Integration] Config.ini file read succesfully!...')

    # Create an instance of server_config
    server_config = ServerConfig()

    # Retrieve the variables and assign them to server_config
    server_config.qradar_url = config.get('MainConfig', 'qradar_url')
    server_config.qradar_api_key = config.get('MainConfig', 'qradar_api_key')
    server_config.failed_processed_id_file = config.get('MainConfig', 'failed_processed_id_file')
    server_config.last_processed_id_file = config.get('MainConfig', 'last_processed_id_file')
    server_config.jira_url = config.get('MainConfig', 'jira_url')
    server_config.jira_user = config.get('MainConfig', 'jira_user')
    server_config.jira_api_token = config.get('MainConfig', 'jira_api_token')
    server_config.jira_project_key = config.get('MainConfig', 'jira_project_key')

    config_level = config.get('Logging','logging_level')
    server_config.logging_level = get_logging_level(config_level)
    # Get the 'enabled CLI logging' value from the config, defaulting to 'True'
    enabled_value = config.get('Logging', 'cli_logging_enabled', fallback='True')
    
    # Convert the value to a boolean
    try:
        cli_logs_enabled = (enabled_value is not None and enabled_value.lower() == 'true')
        print(cli_logs_enabled)
    except ValueError as e:
        print(e)
        # Handle invalid boolean values
        cli_logs_enabled = True  # Default to True if the value is invalid

    server_config.cli_logging_enabled = cli_logs_enabled

    try:
        server_config.polling_rate_new_offenses_checking = config.getint("OffensesPollingRate",'polling_rate_new_offenses_checking')
        if (server_config.polling_rate_new_offenses_checking is None or server_config.polling_rate_new_offenses_checking < 1):
            print(f"[QRadar2Jira_Integration] WARNING New offenses to jira polling time in seconds is misconfigured. Should be an integer value bigger or equal than 1. Defaulting to 5 (seconds)")
            server_config.polling_rate_new_offenses_checking = 5
    except:
        print(f"[QRadar2Jira_Integration] WARNING New offenses to jira polling time in seconds is misconfigured. Should be an integer value from 5 to 3600. Defaulting to 15 (seconds)")
        server_config.polling_rate_new_offenses_checking = 5

    try:
        server_config.polling_rate_offenses_failure_reuploading = config.getint("OffensesPollingRate",'polling_rate_offenses_failure_reuploading')
        if (server_config.polling_rate_offenses_failure_reuploading is None or server_config.polling_rate_offenses_failure_reuploading < 1):
            print(f"[QRadar2Jira_Integration] WARNING Reuploading failed offenses to jira polling time in seconds is misconfigured. Should be an integer value bigger or equal than 1. Defaulting to 1800 (seconds)")
            server_config.polling_rate_offenses_failure_reuploading = 1800
    except:
        print(f"[QRadar2Jira_Integration]  WARNING Reuploading failed offenses to jira polling time in seconds is misconfigured. Should be an integer value from 5 to 3600. Defaulting to 15 (seconds)")
        server_config.polling_rate_offenses_failure_reuploading = 1800

    return server_config

server_config = init_server_config()

########################################LOGGERS CONFIGURATION!!!!!##################################################

def get_formatter_for_logger(formatter_identifier:str = None):
    '''Generates a formatter for a handler inside a logger. Pass a formatter identifier to identify the handler in a unique way
    
    :param str formatter_identifier: Identifier to add at the start of the formatted log
    :return: Formatter to be used when generating logs in the file
    :rtype: Formatter
    '''
    if formatter_identifier:
        formatter = logging.Formatter(formatter_identifier  + ' %(asctime)s %(levelname)s: %(message)s [in %(funcName)s():%(lineno)d] [%(filename)s]')
    else:
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    return formatter

def configure_logger(logger_to_config:logging.Logger, handler_formatter_identifier:str,log_file_name:str):
    '''
    Configures a logger. Pass a Logger Instance, an identifier to use on the handler formatter and the file name where to store the logs.
    
    :param  Logger logger_to_config: Logger to configure.
    :param str handler_formatter_identifier:  Handler formatter identifier to add in the logger configured. get_formatter_for_logger(formatter) is called to configure the format of the logs for the affected logger.
    :param str log_file_name: Log file to use to store the logs for the configured logger.
    :return: None
    :rtype: None
    '''
    handler_formatter = get_formatter_for_logger(handler_formatter_identifier)
    #By default files will have a max of 15MB and rotate when reached. 3 historical rotated files will be stored.
    handler = RotatingFileHandler('logs/' + log_file_name, maxBytes=15728640, backupCount=3)
    handler.setLevel(server_config.logging_level)
    handler.setFormatter(handler_formatter)
    logger_to_config.addHandler(handler)

    if (server_config.cli_logging_enabled == True):
        print("Logging seems to be enabled...")
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(server_config.logging_level)
        stream_handler.setFormatter(handler_formatter)
        logger_to_config.addHandler(stream_handler)
    else:
        print("You seem to have disabled CLI logging. Most logs will no longer appear on the CLI. Check log files for log information.")
    #Test handler
    logger_to_config.debug(f'{handler_formatter_identifier} is properly configured and working.')

# Defined loggers for different server processes
app_bootstrap_logger = logging.getLogger("app_bootstraping")
offenses_to_jira_logger = logging.getLogger("offenses_to_jira_logger")
failed_offenses_to_jira_retries_logger = logging.getLogger("failed_offenses_to_jira_retries_logger")

logging.getLogger().setLevel(server_config.logging_level)

configure_logger(app_bootstrap_logger, '[app_bootstrap_logger]','app_bootstrap.log')
configure_logger(offenses_to_jira_logger, '[offenses_to_jira_logger]','offenses_to_jira.log')
configure_logger(failed_offenses_to_jira_retries_logger, '[failed_offenses_to_jira_retries_logger]','failed_offenses_to_jira.log')

###FINAL MESSAGE:

app_bootstrap_logger.critical(f'''
   ___  ____      _    ____    _    ____    ____        _              
  / _ \|  _ \    / \  |  _ \  / \  |  _ \  |___ \      | (_)_ __ __ _ 
 | | | | |_) |  / _ \ | | | |/ _ \ | |_) |   __) |  _  | | | '__/ _` |
 | |_| |  _ <  / ___ \| |_| / ___ \|  _ <   / __/  | |_| | | | | (_| |
  \__\_\_| \_\/_/   \_\____/_/   \_\_| \_\ |_____|  \___/|_|_|  \__,_|                                                               
                                                                                                                                                                                                                                                                                                                                      
Developed by cvivasf
''')
app_bootstrap_logger.critical(f"#######################################################################")
app_bootstrap_logger.critical('[QRadar2Jira_Integration] Configuration of QRADAR 2 JIRA Application:')
app_bootstrap_logger.critical(f"    Current LOG LEVEL: {server_config.logging_level}")
app_bootstrap_logger.critical(f"    CLI Logging enabled?: {server_config.cli_logging_enabled}")
app_bootstrap_logger.critical(f"    QRADAR URL: {server_config.qradar_url}")
app_bootstrap_logger.critical(f"    Last Processed Offense ID file location: {server_config.last_processed_id_file}")
app_bootstrap_logger.critical(f"    Failed Processed Offense IDs file location: {server_config.failed_processed_id_file}")
app_bootstrap_logger.critical(f"    JIRA URL: {server_config.jira_url}")
app_bootstrap_logger.critical(f"    JIRA USER: {server_config.jira_user}")
app_bootstrap_logger.critical(f"    JIRA Project Key: {server_config.jira_project_key}")
app_bootstrap_logger.critical(f"    Time to wait for polling new offenses from QRADAR and sending them to JIRA: {server_config.polling_rate_new_offenses_checking}")
app_bootstrap_logger.critical(f"    Time to wait for sending new failed offenses from QRADAR to JIRA: {server_config.polling_rate_offenses_failure_reuploading}")
app_bootstrap_logger.critical(f"Integrating QRADAR Offenses with JIRA Now!...")
app_bootstrap_logger.critical(f"#######################################################################")