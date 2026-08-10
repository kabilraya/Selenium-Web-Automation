import os 
from dotenv import load_dotenv

def get_env(env_path:str) -> tuple:
    """Load the environment variables from the .env file into various variables and returns a tuple in an order

    Args:
        env_path (str): os path of the .env file

    Returns:
        tuple: A tuple containing the loaded environment variables in the following order:
               - ecgains (str): The value of the ECGAINS variable.
               - module_name (str): The value of the MODULE_NAME variable.
               - main_url (str): The value of the MAIN_URL variable.
               - executable_path (str): The value of the EXECUTABLE_PATH variable.
               - download_path (str): The value of the DOWNLOAD_PATH variable.
               - server_path (str): The value of the SERVER_PATH variable.
               - json_path (str): The value of the JSON_PATH variable.
               - browser_type (str): The value of the BROWSER_TYPE variable.
               - smi_data_url (str): The value of the SMI_DATA_URL variable.
               - smi_record_url (str): The value of the SMI_RECORD_URL variable.
               - region_name (str): The value of the REGION_NAME variable.
               - endpoint_url (str): The value of the ENDPOINT_URL variable.
               - aws_access_key_id (str): The value of the AWS_ACCESS_KEY_ID variable.
               - aws_secret_access_key (str): The value of the AWS_SECRET_ACCESS_KEY variable.
    """
    load_dotenv(env_path)

    main_url = os.getenv("MAIN_URL")
    download_path = os.getenv("DOWNLOAD_PATH")

    return (
        main_url,
        download_path
    )