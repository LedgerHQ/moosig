# moosig

Fun with MuSig2 and Ledger devices 🎵

Do not use for real funds. Only for testing!

This repository contains a simple script to test the implementation of MuSig2 support in the [BIP-388](https://github.com/bitcoin/bips/blob/master/bip-0388.mediawiki)-compliant wallet policies that are supported in the Ledger bitcoin app.

## Implementation details

In wallet policies, `musig(...)/**` or `musig(...)/<NUM;NUM>/*` key expressions are added in taproot script. Such wallet policies map to a subset of the [proposed descriptor extensions for MuSig2](https://github.com/bitcoin/bips/pull/1540).

Note that expressions like `musig(@0/**,@1/**)` or `musig(@0/<0;1>/*,@1/<0;1>/*)`, despite the corresponding descriptors being allowed in the BIP drafts. Aggregate-then-derive pattern is significantly more efficient for Mu

For the supported policies, the implementation should be complient with the spec in the proposed BIPs. However, it has not yet been cross-tested with bitcoin-core implementation, and testing in general is still quite minimal. Therefore, bugs are likely!

## Preliminaries

### Ledger Bitcoin Test app with MuSig2 support

The alpha version of the MuSig2-enabled Ledger Bitcoin app can be installed from Ledger Live.

Make sure that `My Ledger ==> Experimental Features ==> Developer Mode` setting is enabled.

Search the app called `Bitcoin Test Musig`. Like the `Bitcoin Test` app, it is compatible with all the bitcoin test networks.

Remember to close Ledger Live before continuing, as it might interfere with other programs interacting with the device simultaneously.

### Install dependencies

Create a python environment:

```bash
$ python -m venv venv
$ source venv/bin/activate
```

Install dependencies with:

```bash
$ pip install -r requirements.txt
```

## Run

Have a Ledger device unlocked on the `Bitcoin Test Musig` app, and run:

```bash
$ python moosig.py
```

If all goes well, you will register a musig2 policy using the Ledger device for one key, and a hot cosigner for the second key. Then you will be prompted to sign a (fake) transaction[^1].

At this time, the transaction needs to be approved twice (as each round of the MuSig2 protocol is an independent psbt signing request). A future release will avoid this problem by letting the second round proceed silently if the app is not closed, and no other requests to sign a psbt are sent to the app in between the two signature. This will allow a smooth user experience for those cases when the cosigners are online simultaneously.

If all goes well, the final psbt produced by the script can be finalized by the `bitcoin-cli -regtest finalizepsbt` command (as long as the version of bitcoin-core you are using supports the descriptor you are using - but not the `musig()` key expressions).

Feel free to play around with the code in [moosig.py](moosig.py) to experiment with different policies.

[^1]: Unfortunately, you will have to provide your own testnet/regtest coins if you want to test with a real transaction!</footnote>
