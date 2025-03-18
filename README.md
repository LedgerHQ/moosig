# moosig

Fun with MuSig2 and Ledger devices 🎵

Do not use for real funds. Only for testing!

This repository contains a simple script to test the implementation of MuSig2 support in the [BIP-388](https://github.com/bitcoin/bips/blob/master/bip-0388.mediawiki)-compliant wallet policies that are supported in the Ledger bitcoin app since version <tt>2.4.0</tt>.

## Implementation details

In wallet policies, `musig(...)/**` or `musig(...)/<NUM;NUM>/*` key expressions are added in taproot script. Such wallet policies map to a subset of the [proposed descriptor extensions for MuSig2 in BIP-0390](https://github.com/bitcoin/bips/blob/master/bip-0390.mediawiki).

Note that expressions like `musig(@0/**,@1/**)` or `musig(@0/<0;1>/*,@1/<0;1>/*)` are _not_ supported, despite the corresponding descriptors being allowed in BIP-0390. Aggregate-then-derive pattern is significantly more efficient for MuSig2, especially in the context of signing devices.

For the supported policies, the implementation should be compliant with the spec in the proposed BIPs. However, it has not yet been extensively cross-tested with bitcoin-core implementation, and testing in general is still quite minimal. Therefore, bugs are likely!

## Preliminaries

### Ledger Bitcoin Test app with MuSig2 support

You can install version 2.4.0 of the `Bitcoin Test` app from Ledger Live if you have a Nano X, Nano S+, Flex or Stax. If you can't find it, make sure that your firmware OS is updated to the latest version.

Make sure that `My Ledger ==> Experimental Features ==> Developer Mode` setting is enabled. You should now be able to install the `Bitcoin Test` app.

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

Have a Ledger device unlocked on the `Bitcoin Test` app, and run:

```bash
$ python moosig.py
```

If all goes well, you will register a musig2 policy using the Ledger device for one key, and a hot cosigner for the second key. Then you will be prompted to sign a (fake) transaction[^1].

This script assumes that both rounds of MuSig2 are done in rapid succession, and the device is kept connected during the entire time.

If all goes well, the final psbt produced by the script can be finalized by the `bitcoin-cli -regtest finalizepsbt` command (as long as the version of bitcoin-core you are using supports the descriptor you are using - but not the `musig()` key expressions).

Feel free to play around with the code in [moosig.py](moosig.py) to experiment with different policies.

[^1]: Unfortunately, you will have to provide your own testnet/regtest coins if you want to test with a real transaction!</footnote>
