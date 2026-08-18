import os

def delete_files_in_directory(directory_path: str):
    """
    Deletes all the files in the specified directory.

    Args:
        directory_path (str): The path to the directory.

    Returns:
        None
    """
    for filename in os.listdir(directory_path):
        os.remove(os.path.join(directory_path, filename))