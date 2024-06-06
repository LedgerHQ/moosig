from io import BytesIO
from random import randint

from typing import List, Tuple, Optional

import base58

from ledger_bitcoin import WalletPolicy, WalletType
from ledger_bitcoin.key import ExtendedKey, KeyOriginInfo
from ledger_bitcoin.psbt import PSBT, PartiallySignedInput, PartiallySignedOutput
from ledger_bitcoin.tx import CTransaction, CTxIn, CTxOut, COutPoint, CTxWitness, uint256_from_str

from ledger_bitcoin.embit.descriptor import Descriptor
from ledger_bitcoin.embit.descriptor.miniscript import Miniscript
from ledger_bitcoin.embit.script import Script

from utils import hash160
import utils.bip0327 as bip0327


# TODO: move the wallet policy helpers out of the musig2 module
from utils.musig2 import Musig2KeyPlaceholder, PlainKeyPlaceholder, TrDescriptorTemplate, aggregate_musig_pubkey, derive_plain_descriptor, deserialize_pubkeys, tapleaf_hash
from utils.taproot import G, point_mul


def random_numbers_with_sum(n: int, s: int) -> List[int]:
    """Returns a list of n random numbers with sum s."""
    assert n > 1

    separators = list(sorted([randint(0, s) for _ in range(n - 1)]))
    return [
        separators[0],
        *[separators[i + 1] - separators[i]
            for i in range(len(separators) - 1)],
        s - separators[-1]
    ]


def random_bytes(n: int) -> bytes:
    """Returns n random bytes. Not cryptographically secure."""
    return bytes([randint(0, 255) for _ in range(n)])


def random_txid() -> bytes:
    """Returns 32 random bytes. Not cryptographically secure."""
    return random_bytes(32)


def random_p2tr() -> bytes:
    """Returns 32 random bytes. Not cryptographically secure."""
    privkey = random_bytes(32)
    pubkey = point_mul(G, int.from_bytes(privkey, 'big'))

    return b'\x51\x20' + (pubkey[0]).to_bytes(32, 'big')


def musig_aggr_xpub(pubkeys: List[bytes]) -> str:
    BIP_MUSIG_CHAINCODE = bytes.fromhex(
        "868087ca02a6f974c4598924c36b57762d32cb45717167e300622c7167e38965")
    # sort the pubkeys prior to aggregation
    ctx = bip0327.key_agg(list(sorted(pubkeys)))
    compressed_pubkey = bip0327.cbytes(ctx.Q)

    # Serialize according to BIP-32
    version = 0x043587CF  # testnet

    return base58.b58encode_check(b''.join([
        version.to_bytes(4, byteorder='big'),
        b'\x00',  # depth
        b'\x00\x00\x00\x00',  # parent fingerprint
        b'\x00\x00\x00\x00',  # child number
        BIP_MUSIG_CHAINCODE,
        compressed_pubkey
    ])).decode()


# Given a valid descriptor, replaces each musig() (if any) with the
# corresponding synthetic xpub/tpub.
def replace_musigs_with_aggr_xpubs(desc: str) -> str:
    while True:
        musig_start = desc.find("musig(")
        if musig_start == -1:
            break
        musig_end = desc.find(")", musig_start)
        if musig_end == -1:
            raise ValueError("Invalid descriptor template")

        key_and_origs = desc[musig_start+6:musig_end].split(",")
        pubkeys = []
        for key_orig in key_and_origs:
            orig_end = key_orig.find("]")
            xpub = key_orig if orig_end == -1 else key_orig[orig_end+1:]
            pubkeys.append(base58.b58decode_check(xpub)[-33:])

        # replace with the aggregate xpub
        desc = desc[:musig_start] + \
            musig_aggr_xpub(pubkeys) + desc[musig_end+1:]

    return desc


def getScriptPubkeyFromWallet(wallet: WalletPolicy, change: bool, address_index: int) -> Script:
    descriptor_str = wallet.descriptor_template

    # Iterate in reverse order, as strings identifying a small-index key (like @1) can be a
    # prefix of substrings identifying a large-index key (like @12), but not the other way around
    # A more structural parsing would be more robust
    for i, key_info_str in reversed(list(enumerate(wallet.keys_info))):
        if wallet.version == WalletType.WALLET_POLICY_V1 and key_info_str[-3:] != "/**":
            raise ValueError("All the keys must have wildcard (/**)")

        if f"@{i}" not in descriptor_str:
            raise ValueError(f"Invalid policy: not using key @{i}")

        descriptor_str = descriptor_str.replace(f"@{i}", key_info_str)

    # by doing the text substitution of '/**' at the end, this works for either V1 or V2
    descriptor_str = descriptor_str.replace("/**", f"/{1 if change else 0}/*")

    descriptor_str = replace_musigs_with_aggr_xpubs(descriptor_str)

    return Descriptor.from_string(descriptor_str).derive(address_index).script_pubkey()


def createFakeWalletTransaction(n_inputs: int, n_outputs: int, output_amount: int, wallet: WalletPolicy) -> Tuple[CTransaction, int, int, int]:
    """
    Creates a (fake) transaction that has n_inputs inputs and n_outputs outputs, with a random output equal to output_amount.
    Each output of the transaction is a spend to wallet (possibly to a change address); the change/address_index of the
    derivation of the selected output are also returned.
    """
    assert n_inputs > 0 and n_outputs > 0

    assert wallet.descriptor_template.startswith(
        "tr("), "Only taproot wallet policies are supported"

    selected_output_index = randint(0, n_outputs - 1)
    selected_output_change = randint(0, 1)
    selected_output_address_index = randint(0, 10_000)

    vout: List[CTxOut] = []
    for i in range(n_outputs):
        if i == selected_output_index:
            scriptPubKey: bytes = getScriptPubkeyFromWallet(
                wallet, selected_output_change, selected_output_address_index).data
            vout.append(CTxOut(output_amount, scriptPubKey))
        else:
            # could use any other script for the other outputs; doesn't really matter
            scriptPubKey: bytes = getScriptPubkeyFromWallet(
                wallet, randint(0, 1), randint(0, 10_000)).data
            vout.append(CTxOut(randint(0, 100_000_000), scriptPubKey))

    vin: List[CTxIn] = []
    for _ in range(n_inputs):
        txIn = CTxIn()
        txIn.prevout = COutPoint(
            uint256_from_str(random_txid()), randint(0, 20))
        txIn.nSequence = 0
        txIn.scriptSig = random_bytes(80)  # dummy
        vin.append(txIn)

    tx = CTransaction()
    tx.vin = vin
    tx.vout = vout
    tx.nVersion = 2
    tx.nLockTime = 0

    tx.wit = CTxWitness()

    tx.rehash()

    return tx, selected_output_index, selected_output_change, selected_output_address_index


def get_placeholder_root_key(placeholder: PlainKeyPlaceholder | Musig2KeyPlaceholder, keys_info: List[str]) -> Tuple[ExtendedKey, Optional[KeyOriginInfo]]:
    if isinstance(placeholder, PlainKeyPlaceholder):
        key_info = keys_info[placeholder.key_index]
        key_origin_end_pos = key_info.find("]")
        if key_origin_end_pos == -1:
            xpub = key_info
            root_key_origin = None
        else:
            xpub = key_info[key_origin_end_pos+1:]
            root_key_origin = KeyOriginInfo.from_string(
                key_info[1:key_origin_end_pos])
        root_pubkey = ExtendedKey.deserialize(xpub)
    elif isinstance(placeholder, Musig2KeyPlaceholder):
        root_pubkey, _ = aggregate_musig_pubkey(
            keys_info[i] for i in placeholder.key_indexes)
        root_key_origin = KeyOriginInfo(
            hash160(root_pubkey.pubkey)[:4],
            []
        )
    else:
        raise ValueError("Unsupported placeholder type")

    return root_pubkey, root_key_origin


def fill_inout(desc_tmpl: TrDescriptorTemplate, wallet_policy: WalletPolicy, inout: PartiallySignedInput | PartiallySignedOutput, is_change: bool, address_index: int):
    keypath_der_subpath = [
        desc_tmpl.key.num1 if not is_change else desc_tmpl.key.num2,
        address_index
    ]

    keypath_pubkey, _ = get_placeholder_root_key(
        desc_tmpl.key, wallet_policy.keys_info)

    inout.tap_internal_key = keypath_pubkey.derive_pub_path(
        keypath_der_subpath).pubkey[1:]

    if desc_tmpl.tree is not None:
        inout.tap_merkle_root = desc_tmpl.get_taptree_hash(
            wallet_policy.keys_info, is_change, address_index)

    for placeholder, tapleaf_desc in desc_tmpl.placeholders():
        root_pubkey, root_pubkey_origin = get_placeholder_root_key(
            placeholder, wallet_policy.keys_info)

        if isinstance(placeholder, Musig2KeyPlaceholder):
            keys_info_in_musig = [wallet_policy.keys_info[i]
                                  for i in placeholder.key_indexes]
            root_pubkey, _ = aggregate_musig_pubkey(keys_info_in_musig)
            pubkeys, _ = deserialize_pubkeys(keys_info_in_musig)
            inout.musig2_participant_pubkeys[root_pubkey.pubkey] = list(
                sorted(pubkeys))

        placeholder_der_subpath = [
            placeholder.num1 if not is_change else placeholder.num2,
            address_index
        ]

        leaf_script = None
        if tapleaf_desc is not None:
            leaf_desc = derive_plain_descriptor(
                tapleaf_desc, wallet_policy.keys_info, is_change, address_index)
            s = BytesIO(leaf_desc.encode())
            desc: Miniscript = Miniscript.read_from(s, taproot=True)
            leaf_script = desc.compile()

        derived_pubkey = root_pubkey.derive_pub_path(
            placeholder_der_subpath)

        if root_pubkey_origin is not None:
            derived_key_origin = KeyOriginInfo(
                root_pubkey_origin.fingerprint, root_pubkey_origin.path + placeholder_der_subpath)

            leaf_hashes = []
            if leaf_script is not None:
                # In BIP-388 compliant wallet policies, there will be only one tapleaf with a given key
                leaf_hashes = [tapleaf_hash(leaf_script)]

            inout.tap_bip32_paths[derived_pubkey.pubkey[1:]] = (
                leaf_hashes, derived_key_origin)


def createPsbtForFakeTransaction(wallet_policy: WalletPolicy, input_amounts: List[int], output_amounts: List[int], output_is_change: List[bool]) -> PSBT:
    assert wallet_policy.descriptor_template.startswith(
        "tr("), "Only taproot wallet policies are supported"

    assert output_is_change.count(
        True) <= 1, "At most one change output is supported"

    assert len(output_amounts) == len(output_is_change)
    assert sum(output_amounts) <= sum(input_amounts)

    vin: List[CTxIn] = [CTxIn() for _ in input_amounts]
    vout: List[CTxOut] = [CTxOut() for _ in output_amounts]

    # create some credible prevout transactions
    prevouts: List[CTransaction] = []
    prevout_ns: List[int] = []
    prevout_path_change: List[int] = []
    prevout_path_addr_idx: List[int] = []
    for i, prevout_amount in enumerate(input_amounts):
        n_inputs = randint(1, 10)
        n_outputs = randint(1, 10)
        prevout, idx, is_change, addr_idx = createFakeWalletTransaction(
            n_inputs, n_outputs, prevout_amount, wallet_policy)
        prevouts.append(prevout)
        prevout_ns.append(idx)
        prevout_path_change.append(is_change)
        prevout_path_addr_idx.append(addr_idx)

        vin[i].prevout = COutPoint(prevout.sha256, idx)
        vin[i].scriptSig = b''
        vin[i].nSequence = 0

    psbt = PSBT()
    psbt.version = 0

    tx = CTransaction()
    tx.vin = vin
    tx.vout = vout
    tx.wit = CTxWitness()

    # TODO: add participant pubkeys

    change_address_index = randint(0, 10_000)
    for i, output_amount in enumerate(output_amounts):
        tx.vout[i].nValue = output_amount
        if output_is_change[i]:
            script = getScriptPubkeyFromWallet(
                wallet_policy, output_is_change[i], change_address_index)

            tx.vout[i].scriptPubKey = script.data
        else:
            # a random P2TR output
            tx.vout[i].scriptPubKey = random_p2tr()

    psbt.inputs = [PartiallySignedInput(0) for _ in input_amounts]
    psbt.outputs = [PartiallySignedOutput(0) for _ in output_amounts]

    desc_tmpl = TrDescriptorTemplate.from_string(
        wallet_policy.descriptor_template)

    for input_index, input in enumerate(psbt.inputs):
        # add witness UTXO
        input.witness_utxo = prevouts[input_index].vout[prevout_ns[input_index]]

        is_change = bool(prevout_path_change[input_index])
        address_index = prevout_path_addr_idx[input_index]

        fill_inout(desc_tmpl, wallet_policy, input, is_change, address_index)

    # only for the change output, we need to do the same
    for output_index, output in enumerate(psbt.outputs):
        if output_is_change[output_index]:
            fill_inout(desc_tmpl, wallet_policy, output,
                       is_change=True, address_index=change_address_index)

    psbt.tx = tx

    return psbt
