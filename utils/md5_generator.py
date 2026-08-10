import hashlib

def generate_md5_hash(ecgain: str, bidno: str, filename: str) -> str:
    """
    Generates an MD5 hash based on the given parameters.

    Args:
        ecgain (str): The ecgain value to include in the hash.
        bidno (str): The bidno value to include in the hash.
        filename (str): The filename value to include in the hash.

    Returns:
        str: The MD5 hash as a hexadecimal string.
    """
    return hashlib.md5(f"{ecgain}{bidno}{filename}".encode("utf-8")).hexdigest()