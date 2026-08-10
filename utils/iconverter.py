def get_iconverted_value(filename: str) -> int:
    """
    Returns an integer value based on the given filename.

    Args:
        filename (str): The name of the file to check the extension of.

    Returns:
        int: The converted value based on the file extension. Returns -2 if the file extension is in the set of allowed extensions, 0 otherwise.
    """
    allowed_extensions = {".doc", ".docx", ".txt", ".html", ".rtf", ".htm"}

    file_extension = filename[filename.rfind('.'):].lower()

    if file_extension in allowed_extensions:
        return -2
    else:
        return 0