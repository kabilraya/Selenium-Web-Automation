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
    ecgains = os.getenv("ECGAINS")
    module_name = os.getenv("MODULE_NAME")

    main_url = os.getenv("MAIN_URL")
    download_path = os.getenv("DOWNLOAD_PATH")
    server_path = os.getenv("SERVER_PATH")
    smi_data_url = os.getenv("SMI_DATA_URL")
    smi_record_url = os.getenv("SMI_RECORD_URL")
    region_name = os.getenv("REGION_NAME")
    endpoint_url = os.getenv("ENDPOINT_URL")
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    return (
        ecgains,
        module_name,
        main_url,
        download_path,
        server_path,
        smi_data_url,
        smi_record_url,
        region_name,
        endpoint_url,
        aws_access_key_id,
        aws_secret_access_key
    )