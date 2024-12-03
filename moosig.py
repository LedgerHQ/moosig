from typing import List
from ledger_bitcoin import createClient, Chain, WalletPolicy, TransportClient, Client
from ledger_bitcoin.psbt import PSBT
from ledger_bitcoin.key import ExtendedKey

from utils import txmaker
from utils.cow import print_cow
from utils.musig2 import HotMusig2Cosigner, LedgerMusig2Cosigner, PsbtMusig2Cosigner, add_aggregate_signatures_and_check


def main(client: Client):
    # Get the master fingerprint from the device
    fpr = client.get_master_fingerprint().hex()

    print(f"Device master fingerprint: {fpr}\n")

    # We use a Ledger for the first key in the musig
    cosigner_1_path = "m/48'/1'/0'/2'"
    cosigner_1_xpub = client.get_extended_pubkey(cosigner_1_path)
    cosigner_1_key_info = f"[{cosigner_1_path.replace('m', fpr)}]{cosigner_1_xpub}"

    print(f"Ledger device key: {cosigner_1_key_info}")

    # The other key is a hot cosigner
    cosigner_2_xpriv = "tprv8gFWbQBTLFhbX3EK3cS7LmenwE3JjXbD9kN9yXfq7LcBm81RSf8vPGPqGPjZSeX41LX9ZN14St3z8YxW48aq5Yhr9pQZVAyuBthfi6quTCf"
    cosigner_2_xpub = ExtendedKey.deserialize(
        cosigner_2_xpriv).neutered().to_string()

    print(f"Hot cosigner xpub: {cosigner_2_xpub}\n")

    wallet_policy = WalletPolicy(
        name="Musig for my ears",
        descriptor_template="tr(musig(@0,@1)/**)",
        keys_info=[cosigner_1_key_info, cosigner_2_xpub]
    )

    # Here is a walletpolicy using the taproot script path, instead:

    # unspendable_xpub = "tpubD6NzVbkrYhZ4WLczPJWReQycCJdd6YVWXubbVUFnJ5KgU5MDQrD998ZJLSmaB7GVcCnJSDWprxmrGkJ6SvgQC6QAffVpqSvonXmeizXcrkN"
    # wallet_policy = WalletPolicy(
    #     name="Musig for the #teamscript",
    #     descriptor_template="tr(@0/**,pk(musig(@1,@2)/**))",
    #     keys_info=[unspendable_xpub, cosigner_1_key_info, cosigner_2_xpub]
    # )

    print(f"Descriptor template: {wallet_policy.descriptor_template}\n")

    print(f"Internal descriptor: {wallet_policy.get_descriptor(False)}")
    print(f"  Change descriptor: {wallet_policy.get_descriptor(True)}\n")

    print(f"\n🐮 Please inspect and register the wallet policy on your device...")
    # Register the wallet
    _, wallet_hmac = client.register_wallet(wallet_policy)

    print(f"Wallet policy HMAC: {wallet_hmac.hex()}\n")

    # Create a plausible PSBT for this policy
    USE_FAKE_PSBT = True
    if USE_FAKE_PSBT:
        # This allucinates a transaction spending from this wallet
        n_ins = 2
        n_outs = 2

        in_amounts = [10000 + 10000 * i for i in range(n_ins)]
        sum_in = sum(in_amounts)
        out_amounts = [sum_in // n_outs - i for i in range(n_outs)]

        change_index = 1

        psbt = txmaker.createPsbtForFakeTransaction(
            wallet_policy,
            in_amounts,
            out_amounts,
            [i == change_index for i in range(n_outs)]
        )
    else:
        # If you have a real PSBT, set USE_FAKE_PSBT = False above
        psbt_base64 = "cHNid..."  # TODO
        psbt = PSBT()
        psbt.deserialize(psbt_base64)

    signer_1 = LedgerMusig2Cosigner(client, wallet_policy, wallet_hmac)
    signer_2 = HotMusig2Cosigner(wallet_policy, cosigner_2_xpriv)

    cosigners: List[PsbtMusig2Cosigner] = [signer_1, signer_2]

    print("🐮 Signing time!")

    print("Initial psbt:", psbt.serialize())

    print("\n🐮 Requesting pubnonces (Round 1)")
    for signer in cosigners:
        signer.generate_public_nonces(psbt)

    print("\nPsbt after pubnonces:", psbt.serialize())

    print("\n🐮 Please approve the transaction on your device (Round 2)")
    for signer in cosigners:
        signer.generate_partial_signatures(psbt)

    print("\nPsbt after partial signatures:", psbt.serialize())

    add_aggregate_signatures_and_check(psbt, wallet_policy)

    print("\nPsbt with the final signatures (if complete, `bitcoin-cli -regtest finalizepsbt` should be able to finalize it):")
    print(psbt.serialize())

    print("\n\n🐮 My job here is done. Good luck!")


if __name__ == "__main__":
    USE_SPECULOS = False  # Set to True to use the emulator

    print_cow()

    if USE_SPECULOS:
        # Test with the testnet app running on speculos
        with createClient(TransportClient(), chain=Chain.TEST) as client:
            main(client)
    else:
        # Ledger Nano connected via USB
        with createClient(chain=Chain.TEST) as client:
            main(client)
