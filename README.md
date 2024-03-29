# YouTube\_RSS

YouTube\_RSS is a simple YouTube client I've made for fun. The goal is to have a simple
user interface for those who want to preserve their privacy when using YouTube, but who
still want to be able to keep track of their favourite channels, etc.

YouTube\_RSS manages subscriptions to channels using RSS, rather than YouTube's
internal subscription system that requires a privacy violating Google account.

It also (optionally) uses Tor to hide the IP address of the user.

## Dependencies

YouTube\_RSS is developed and tested on Ubuntu Linux. It will probably work just fine in
similar Unix-like operating systems, but probably not on Windows (at least not without
a little bit of pain).

The following python modules are used and may need to be installed, e.g. using pip:
```
aiohttp
aiohttp-socks
feedparser
urllib3
```

The program also assumes that [mpv](https://github.com/mpv-player/mpv) is
installed in the environment. In, for example, Ubuntu, this can be accomplished
by running `sudo apt-get install mpv`. [youtube-dl](https://github.com/ytdl-org) also
needs to be installed (I use the latest version on their [official website](https://youtube-dl.org/), and
at the time of this writing, the version in the Ubuntu rebository seems too old to work 
the way this project uses it).

For using Tor, YouTube\_RSS assumes that Tor is installed and currently running
on port `9050` (which is the default for the Tor daemon anyway). It also requires that
torsocks is installed.

## Disclaimer

Note that while I am enthusiastic about privacy and security,
I am not a professional, and may have missed something important. However, the surface to protect
should be relatively small, and I've taken care to get rid of DNS-leaks, etc. as well as I can.
If you are more knowledgable than I, then I would appreciate input on how to make YouTube\_RSS
more privacy preserving and secure.

# Manual
Most of the way the application works is self-explanatory; I won't tell you that to search for a
video, you enter the "search for video" option (although I guess I just did), but rather focus on
the things not immediately obvious when opening the program.

## Key binds
The keybindings are designed so that the user can do almost everything necessary by just
using the arrow keys (except, of course, when writing search queries), or by using the
`hjkl` keys for vi users.

When in a menu, the user can press `KEY_UP` or `k` to move to the previous menu item.

When in a menu, the user can press `KEY_DOWN` or `j` to move to the next menu item.

When in a menu, the user can press `g` (lower case) to go to the first menu item.

When in a menu, the user can press `G` (upper case) to go to the last menu item.

When in a menu, the user can type a number and then press either `Enter` or `l` or `KEY_RIGHT`
to jump to the item indicated by the number typed by the user.

When in a menu, the user can press `ENTER`, `l` or `KEY_RIGHT` to select the highlighted item, if no
number has been typed since last jump.

When in a menu, the user can press `q`, `<Ctrl>-C`, `h` or `KEY_LEFT` to go back to the previous menu.

When browsing subscriptions, in the menu where channels are displayed as menu items, the user can press
`a` to toggle all entries of the currently highlighted channel as seen or unseen

When browsing subscriptions, in the menu where videos from a particular channel are displayed as menu
items, the user can press `a` to toggle the highlighted entry as seen or unseen

## Thumbnails
YouTube\_RSS used to support thumbnails, using
[ueberzug](https://github.com/seebye/ueberzug), but no longer does, since that project
has sadly been discontinued.

If you used YouTube\_RSS with thumbnails in the past, you need to manually delete
thumbnail files, which are stored under `~/.youtube_rss/thumbnails`.
