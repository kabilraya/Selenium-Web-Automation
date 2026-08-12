from urllib.parse import quote
import boto3
import os
def boto_client_insertion(
        bid_no:str,
        download_dir:str,
        filename:str,
        server_path:str,
        region_name:str,
        endpoint_url:str,
        aws_access_key_id:str,
        aws_secret_access_key:str
) -> None:
    """Takes the local file and insert them in an AWS S3 bucket with a particular 'Key'

    Args:
        bid_no (str): Unique bid number of a specific bid
        download_dir (str): Local download directory where the files has been saved locally 
        filename (str): Local filename of the download files
        server_path (str): base_directory in the S3 bucket
        region_name (str): Region of the S3 bucket service
        endpoint_url (str): Specific AWS S3 service compatible server URL
        aws_access_key_id (str): AWS Key ID
        aws_secret_access_key (str): Secret AWS Key
    """
    # We make the path to the local files 
    file_path = os.path.join(download_dir,filename)

    # We create a boto client with S3 as the service provider
    s3 = boto3.client(
        "s3",
        region_name = region_name,
        endpoint_url = endpoint_url,
        aws_access_key_id = aws_access_key_id,
        aws_secret_access_key = aws_secret_access_key
    )

    do_path = os.path.join(server_path,quote(str(bid_no)[:25]))
    s3.put_object(Bucket = "generaldatasl",Key=f'{do_path}')
    bid_location = os.path.join(do_path,filename).replace("\\","/")
    s3.upload_file(file_path,"generaldatasl",bid_location)
    print(bid_location)