import hashlib


def md5file(filename):
    with open(filename, "rb") as f:
        content = f.read()
    return md5digest(content)


def md5digest(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()
