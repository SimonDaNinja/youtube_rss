# youtube_rss

This is a collection of tools I'm developing for use in a (hopefully) upcoming
anonymous YouTube client.

As my current plan is to use RSS to keep track of "subscriptions" to channels
(not to be confused with YouTube's own subscription system, which requires a
Google account and is not compatible with anonymity), much of the material is
focused on getting ahold of and parsing RSS-content.

This is not primarilly intended as an application, but rather it is a module
meant to help with application development. However, it does pack a
proof-of-concept demo application in the main section of the file.

## Dependencies

The following python modules must be installed, e.g. using pip:
```
feedparser
urllib3
pysocks
```
The project also uses [Tor-Requests](https://github.com/SimonDaNinja/tor_requests/tree/db191029791e12a73d02f6533f17371fea6aeed1)
as a submodule, so make sure to run `git submodule update --init --recursive`
before using youtube\_rss.

The program also assumes that [Mpv](https://github.com/mpv-player/mpv) is
installed in the environment. In, for example, Ubuntu, this can be accomplished
by running `sudo apt-get install mpv`.

For using Tor, youtube\_rss assumes that Tor is installed and currently running
on port `9050`.
