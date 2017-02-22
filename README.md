# Listen to your Git repo!

This little script converts your Git repository to MIDI music.

## Scales

There are 5 scales built in:

* C major
* A harmonic major
* Chromatic
* Pentatonic
* D major

## Programs

Programs in MIDI are effectively lists of instruments and effects to use.
This script doesn’t use effects (yet).

Here are the built-in programs you can use:

* Sitar and Tablah (Indian style)
* Bells (have you heard of Mike Oldfield? This will be familiar then)
* Metal (because obviously)
* Pure violin
* Space (for futuristic repositories)
* Sea-copter (Use this if you want some noise)

## Requirements

To create MIDI music, we use the MIDIUtil package. For reading Git
repositories, we use GitPython.

## Command line arguments

If you want to create music from a branch other than `master` (the default),
you can specify it with `--branch branchname`.

If you want to save the MIDI file to the disk, use `--file outputfile.mid`

To play your MIDI file directly, use `--play`.  This requires the `pygame`
package to be installed.

If you want to see what is happening right now (can be useful with large
repos), add `--verbose` to the command line.

To specify the scale to use, pass `--scale scalename`.  There is no default,
so you have to specify this.  To list the scale names understood by the
script, use `--scale list`.

To specify the program to use, pass `--program pragramname`.  Again, there
is no default, and you can list the available ones with `--program list`.

The volume of each note is randomized to get a more real feeling.  By
default, this means the lowest and loudest notes can have 100 units of
difference. If this is too much for you (sometimes it can be annoying),
specify a smaller number with `--volume-range N` (the valid range
i`0..255`).

Some repositories begin with a huge import, when a lot of files were added
to the repository.  This can sound awful with some programs, so you might
want to skip them.  To do so, use `--skip N`, where `N` is the number of
commits you want to skip.

## GUI

If you have GTK+ 3.X installed and have the GObject Introspection stuff
installed for Python (this is the default on many GTK based Linux desktops),
if you don’t specify a scale and a program on the command line, the GUI
window will come up.  Here you can set everything that is available from the
command line, and follow visually what is happening in the background.

## TODO

There are some features I want to add.

* Skip or shorten large commits.

## Contributing

If you find a bug or have some ideas, open an Issue on GitHub.

If you can implement it, the better!  Just go with the (GitHub) flow!  Fork
the repository, do the coding, and open a pull request.

## Code of Conduct

In general, follow
the [Open Code of Conduct](https://github.com/todogroup/opencodeofconduct)
of the [TODO Group](https://twitter.com/todogroup).
