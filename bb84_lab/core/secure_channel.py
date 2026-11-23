"""Authenticated messages and one-way AEAD for educational simulations."""

from dataclasses import dataclass, field, replace
import hashlib
import hmac
import json
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


VERSION = 1
MAX_SEQUENCE = 2**96 - 1
ROLES = ("alice", "bob")


class AuthenticationError(ValueError):
    """A message cannot be authenticated in the expected session."""


class ReplayError(AuthenticationError):
    """A message is replayed or arrives outside its expected order."""


def _json_bytes(value):
    """Use one unambiguous representation, rejecting non-JSON input."""
    def validate(item):
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            for nested in item.values():
                validate(nested)
        elif type(item) is list:
            for nested in item:
                validate(nested)
        elif item is not None and type(item) not in (bool, int, float, str):
            raise ValueError("Only JSON values are supported")

    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _session_id(value):
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise ValueError("session_id must contain 1 to 128 characters")
    value.encode("utf-8")
    return value


def _metadata(version, session_id, sender, sequence):
    if type(version) is not int or version != VERSION:
        raise AuthenticationError("Unsupported protocol version")
    if type(sender) is not str or sender not in ROLES:
        raise AuthenticationError("Invalid sender role")
    if type(sequence) is not int or not 0 <= sequence <= MAX_SEQUENCE:
        raise AuthenticationError("Invalid sequence number")
    return {"version": version, "session_id": _session_id(session_id),
            "sender": sender, "sequence": sequence}


@dataclass(frozen=True)
class Envelope:
    version: int
    session_id: str
    sender: str
    sequence: int
    payload: dict = field(repr=False)
    tag: bytes = field(repr=False)


class AuthenticatedTranscript:
    """In-memory HMAC authentication with a counter for each sender role."""

    def __init__(self, psk: bytes, session_id: str):
        if type(psk) is not bytes or len(psk) < 32:
            raise ValueError("The independent preshared key must be at least 32 bytes")
        self._psk = psk
        self._session_id = _session_id(session_id)
        self._sent = dict.fromkeys(ROLES, 0)
        self._received = dict.fromkeys(ROLES, 0)

    @property
    def session_id(self):
        return self._session_id

    def _signed_data(self, version, session_id, sender, sequence, payload):
        metadata = _metadata(version, session_id, sender, sequence)
        if type(payload) is not dict:
            raise ValueError("Transcript payload must be a JSON object")
        return b"qkd-demo/transcript/v1\0" + _json_bytes({**metadata, "payload": payload})

    def seal(self, sender: str, payload: dict) -> Envelope:
        if type(sender) is not str or sender not in ROLES:
            raise ValueError("sender must be alice or bob")
        sequence = self._sent[sender]
        data = self._signed_data(VERSION, self.session_id, sender, sequence, payload)
        snapshot = json.loads(data.split(b"\0", 1)[1])["payload"]
        tag = hmac.digest(self._psk, data, hashlib.sha256)
        self._sent[sender] += 1
        return Envelope(VERSION, self.session_id, sender, sequence, snapshot, tag)

    def receive(self, envelope: Envelope) -> dict:
        if type(envelope) is not Envelope:
            raise AuthenticationError("Invalid transcript envelope")
        try:
            data = self._signed_data(envelope.version, envelope.session_id,
                                     envelope.sender, envelope.sequence, envelope.payload)
        except (ValueError, TypeError, UnicodeError, RecursionError) as error:
            raise AuthenticationError("Invalid transcript envelope") from error
        if envelope.session_id != self.session_id or type(envelope.tag) is not bytes:
            raise AuthenticationError("Wrong transcript session or tag")
        expected = hmac.digest(self._psk, data, hashlib.sha256)
        if not hmac.compare_digest(expected, envelope.tag):
            raise AuthenticationError("Transcript authentication failed")
        if envelope.sequence != self._received[envelope.sender]:
            raise ReplayError("Replayed or out-of-order transcript message")
        self._received[envelope.sender] += 1
        return json.loads(data.split(b"\0", 1)[1])["payload"]


@dataclass(frozen=True)
class Packet:
    version: int
    session_id: str
    sender: str
    sequence: int
    ciphertext: bytes = field(repr=False)


class DemoChannel:
    """One-way AEAD with OS randomness or matching postprocessed model keys."""

    # One-way educational channel. The network runner serializes access to each
    # fresh endpoint instance; do not share it between concurrent transfers or
    # persist/recreate a session key with its counters reset.
    def __init__(self):
        self._session_id = secrets.token_hex(16)
        self._cipher = ChaCha20Poly1305(ChaCha20Poly1305.generate_key())
        self._receiver_cipher = self._cipher
        self._key_source = "OS random; độc lập với BB84"
        self._sent = 0
        self._received = 0

    @property
    def session_id(self):
        return self._session_id

    @property
    def key_source(self):
        return self._key_source

    @classmethod
    def from_simulated_keys(cls, alice_key, bob_key):
        if type(alice_key) is not bytes or type(bob_key) is not bytes or len(alice_key) != 32 or len(bob_key) != 32:
            raise ValueError("Both confirmed model keys must contain 32 bytes")
        if not hmac.compare_digest(alice_key, bob_key):
            raise AuthenticationError("Model keys differ; encryption aborted")
        channel = cls()
        # HKDF binds the already processed model keys to a fresh session. It
        # adds no secret entropy and does not replace Cascade or Toeplitz.
        def derive(key):
            return HKDF(algorithm=hashes.SHA256(), length=32,
                        salt=bytes.fromhex(channel.session_id),
                        info=b"bb84-model/aead/v1").derive(key)

        channel._cipher = ChaCha20Poly1305(derive(alice_key))
        channel._receiver_cipher = ChaCha20Poly1305(derive(bob_key))
        channel._key_source = "BB84 mô phỏng + Cascade + Toeplitz; không bảo vệ dữ liệu thật"
        return channel

    @classmethod
    def from_local_model_key(cls, key, session_id):
        """One endpoint's confirmed key; network orchestration owns serialization.

        The network protocol confirms the retained strings before applying the
        same authenticated Toeplitz seed. Never transport the key to its peer.
        Each instance is used in exactly one direction under a per-session lock.
        """
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("Confirmed local model key must contain 32 bytes")
        _session_id(session_id)
        channel = cls()
        channel._session_id = session_id
        derived = HKDF(algorithm=hashes.SHA256(), length=32,
                       salt=hashlib.sha256(session_id.encode("utf-8")).digest(),
                       info=b"bb84-network-model/aead/v1").derive(key)
        channel._cipher = channel._receiver_cipher = ChaCha20Poly1305(derived)
        channel._key_source = "BB84 mạng mô phỏng + Cascade + Toeplitz; chỉ dùng demo"
        return channel

    @staticmethod
    def _aad(version, session_id, sender, sequence):
        return b"qkd-demo/aead/v1\0" + _json_bytes(
            _metadata(version, session_id, sender, sequence))

    def encrypt(self, plaintext: bytes) -> Packet:
        if type(plaintext) is not bytes:
            raise ValueError("plaintext must be bytes")
        if self._sent > MAX_SEQUENCE:
            raise OverflowError("Nonce space exhausted; create a fresh channel")
        sequence = self._sent
        self._sent += 1  # Consume the nonce even if the encryption operation fails.
        aad = self._aad(VERSION, self.session_id, "alice", sequence)
        ciphertext = self._cipher.encrypt(sequence.to_bytes(12, "big"), plaintext, aad)
        return Packet(VERSION, self.session_id, "alice", sequence, ciphertext)

    def decrypt(self, packet: Packet) -> bytes:
        if type(packet) is not Packet:
            raise AuthenticationError("Invalid encrypted packet")
        try:
            aad = self._aad(packet.version, packet.session_id, packet.sender,
                            packet.sequence)
        except (ValueError, TypeError, UnicodeError) as error:
            raise AuthenticationError("Invalid encrypted metadata") from error
        if packet.session_id != self.session_id or packet.sender != "alice":
            raise AuthenticationError("Wrong encrypted session or sender")
        if type(packet.ciphertext) is not bytes:
            raise AuthenticationError("ciphertext must be bytes")
        if packet.sequence != self._received:
            raise ReplayError("Replayed or out-of-order encrypted packet")
        try:
            plaintext = self._receiver_cipher.decrypt(packet.sequence.to_bytes(12, "big"),
                                             packet.ciphertext, aad)
        except InvalidTag as error:
            raise AuthenticationError("Ciphertext authentication failed") from error
        self._received += 1
        return plaintext


def check_secure_channel():
    """Runnable assert-based checks; no keys or raw key material are printed."""
    def rejected(operation, exception=AuthenticationError):
        try:
            operation()
        except exception:
            return
        raise AssertionError("An invalid message was accepted")

    psk = secrets.token_bytes(32)
    transcript = AuthenticatedTranscript(psk, "test-session")
    payload = {"indices": [1, 2], "sample": [0, 1]}
    envelope = transcript.seal("alice", payload)
    payload["sample"][0] = 1
    assert envelope.payload["sample"] == [0, 1]
    rejected(lambda: transcript.receive(replace(envelope, payload={"sample": [1, 1]})))
    rejected(lambda: transcript.receive(replace(envelope, tag=b"\0" * 32)))
    for changes in ({"version": 2}, {"version": True}, {"session_id": "other"},
                    {"sender": "bob"}, {"sender": "eve"}, {"sequence": True},
                    {"sequence": -1}, {"sequence": 1}):
        rejected(lambda changes=changes: transcript.receive(replace(envelope, **changes)))
    wrong_key = AuthenticatedTranscript(secrets.token_bytes(32), "test-session")
    rejected(lambda: wrong_key.receive(envelope))
    wrong_session = AuthenticatedTranscript(psk, "other")
    rejected(lambda: wrong_session.receive(envelope))
    assert transcript.receive(envelope) == {"indices": [1, 2], "sample": [0, 1]}
    rejected(lambda: transcript.receive(envelope), ReplayError)
    bob = transcript.seal("bob", {"accepted": True})
    assert transcript.receive(bob) == {"accepted": True}
    first = transcript.seal("alice", {"step": 1})
    second = transcript.seal("alice", {"step": 2})
    rejected(lambda: transcript.receive(second), ReplayError)
    assert transcript.receive(first) == {"step": 1}
    assert transcript.receive(second) == {"step": 2}
    rejected(lambda: AuthenticatedTranscript(b"short", "session"), ValueError)
    rejected(lambda: transcript.seal("alice", {"bad": float("nan")}), ValueError)
    rejected(lambda: transcript.seal("alice", {"bad": float("inf")}), ValueError)
    rejected(lambda: transcript.seal("alice", {"bad": {1: "integer key"}}), ValueError)

    channel = DemoChannel()
    message = "Thông điệp kiểm chứng BB84".encode("utf-8")
    packet = channel.encrypt(message)
    corrupted = bytes([packet.ciphertext[0] ^ 1]) + packet.ciphertext[1:]
    rejected(lambda: channel.decrypt(replace(packet, ciphertext=corrupted)))
    rejected(lambda: channel.decrypt(replace(packet, ciphertext=b"")))
    for changes in ({"version": 2}, {"version": True}, {"session_id": "other"},
                    {"sender": "bob"}, {"sequence": True}, {"sequence": -1},
                    {"sequence": 2**96}):
        rejected(lambda changes=changes: channel.decrypt(replace(packet, **changes)))
    other_channel = DemoChannel()
    rejected(lambda: other_channel.decrypt(packet))
    assert channel.decrypt(packet) == message
    rejected(lambda: channel.decrypt(packet), ReplayError)
    packets = [channel.encrypt(str(index).encode()) for index in range(100)]
    nonces = {item.sequence.to_bytes(12, "big") for item in [packet, *packets]}
    assert len(nonces) == 101
    rejected(lambda: channel.decrypt(packets[1]), ReplayError)
    for index, item in enumerate(packets):
        assert channel.decrypt(item) == str(index).encode()
    assert other_channel.decrypt(other_channel.encrypt(b"separate session")) == b"separate session"
    exhausted = DemoChannel()
    exhausted._sent = MAX_SEQUENCE
    last_packet = exhausted.encrypt(b"last nonce")
    assert last_packet.sequence == MAX_SEQUENCE
    rejected(lambda: exhausted.encrypt(b"too late"), OverflowError)

    class FailingCipher:
        def encrypt(self, nonce, plaintext, aad):
            raise RuntimeError("simulated encryption failure")

    failure = DemoChannel()
    original_cipher = failure._cipher
    failure._cipher = FailingCipher()
    rejected(lambda: failure.encrypt(b"failed send"), RuntimeError)
    failure._cipher = original_cipher
    assert failure.encrypt(b"next nonce").sequence == 1
    assert not hasattr(channel, "key")
    assert "ciphertext" not in repr(packet) and "payload" not in repr(envelope)


if __name__ == "__main__":
    check_secure_channel()
    print("secure_channel: checks passed; AEAD uses a separate random key.")
