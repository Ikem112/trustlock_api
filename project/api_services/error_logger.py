import logging

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s [%(request_method)s %(endpoint)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
