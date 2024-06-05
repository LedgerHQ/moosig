# musigfun
Fun with MuSig2 and Ledger devices 🎵


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


