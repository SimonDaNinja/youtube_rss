# YouTube_RSS

YouTube\_RSS is a simple YouTube client I've made for fun. The goal is to have a simple
user interface for those who want to preserve their privacy when using YouTube, but who
still want to be able to keep track of their favourite channels, etc.

YouTube\_RSS manages subscriptions to channels with RSS, rather than using YouTube's
internal subscription system that requires a privacy violating Google account.

It also (optionally) uses Tor to hide the IP address of the user.

## Dependencies

YouTube\_RSS is developed and tested on Ubuntu Linux. It will probably work just fine in
similar Unix-like operating systems, but almost certainly not on Windows.

The following python modules are used and may need to be installed, e.g. using pip:
```
feedparser
urllib3
pysocks
curses
```
The project also uses [Tor-Requests](https://github.com/SimonDaNinja/tor_requests/tree/db191029791e12a73d02f6533f17371fea6aeed1)
as a submodule, so make sure to run `git submodule update --init --recursive`
before using YouTube\_RSS.

The program also assumes that [Mpv](https://github.com/mpv-player/mpv) is
installed in the environment. In, for example, Ubuntu, this can be accomplished
by running `sudo apt-get install mpv`.

For using Tor, YouTube\_RSS assumes that Tor is installed and currently running
on port `9050` (which is the default for the Tor daemon anyway). It also requires that
torsocks is installed.
