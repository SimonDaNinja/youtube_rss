# YouTube_RSS

YouTube\_RSS is a simple YouTube client I've made for fun. The goal is to have a simple
user interface for those who want to preserve their privacy when using YouTube, but who
still want to be able to keep track of their favourite channels, etc.

YouTube\_RSS manages subscriptions to channels using RSS, rather than YouTube's
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

The program also assumes that [mpv](https://github.com/mpv-player/mpv) is
installed in the environment. In, for example, Ubuntu, this can be accomplished
by running `sudo apt-get install mpv`. [youtube-dl](https://github.com/ytdl-org) also
needs to be installed (I use the latest version on their [official website](https://youtube-dl.org/), and
at the time of this writing, the version in Ubuntu seems too old to work the way this
project uses it).

For using Tor, YouTube\_RSS assumes that Tor is installed and currently running
on port `9050` (which is the default for the Tor daemon anyway). It also requires that
torsocks is installed.

## Disclaimer

Note that while I am enthusiastic about privacy and security,
I am not a professional, and may have missed something important. However, the surface to protect
should be relatively small, and I've taken care to get rid of DNS-leaks, etc. as well as I can.
If you are more knowledgable than I, then I would appreciate input on how to make YouTube\_RSS
more privacy preserving and secure.
