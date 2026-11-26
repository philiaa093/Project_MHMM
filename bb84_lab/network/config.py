"""Network-demo configuration and bounded frame payload sizes."""

from dataclasses import asdict

from bb84_lab.core.bb84 import Config


CHUNK_BYTES = 64 * 1024
DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_SIGNALS = 65536
DEFAULT_E91_SIGNALS = 8192
PROTOCOLS = ("bb84", "e91")
E91_PAIR_FRAME = "e91-pairs"
E91_REPLACED_STATE = 6
NETWORK_CONFIG_FIELDS = {"signals", "sample_fraction", "threshold", "min_samples", "seed"}


def network_config(value=None):
    value = {} if value is None else value
    if type(value) is not dict or value.keys() - NETWORK_CONFIG_FIELDS:
        raise ValueError("Cấu hình mạng không hợp lệ")
    config = Config(**value)
    if config.signals > MAX_SIGNALS or config.seed.bit_length() > 128:
        raise ValueError("Tối đa 65.536 tín hiệu, seed tối đa 128 bit")
    return config


def public_config(config):
    return {key: value for key, value in asdict(config).items() if key in NETWORK_CONFIG_FIELDS}
