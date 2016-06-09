#! /usr/bin/env python
# -*- coding: utf-8
"""
Generate sound for Git repositories
"""

from __future__ import print_function

import argparse
import sys
import os

try:
    from git_sound.gui import GitSoundWindow
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

from git.exc import InvalidGitRepositoryError

from git_sound.gitmidi import GitMIDI

SCALES = {
    'c-major': ('C Major', [60, 62, 64, 65, 67, 69, 71]),
    'a-harmonic-minor': ('A Harmonic Minor', [68, 69, 71, 72, 74, 76, 77]),
    'chromatic': ('Chromatic', [60, 61, 62, 63, 64, 65, 66, 67, 68, 69]),
    'pentatonic': ('Pentatonic', [54, 64, 72, 81, 96, 108]),
    'd-major': ('D Major', [62, 64, 65, 67, 69, 71, 72]),
}

PROGRAMS = {
    'sitar-tablah': {
        'name': 'Sitar and Tablah',
        'commit': {
            'program': 104,
            'octave': -2,
        },
        'file': {
            'program': 115,
            'octave': -1,
        },
    },
    'bells': {
        'name': 'Bells',
        'commit': {
            'program': 14,
            'octave': 0,
        },
        'file': {
            'program': 9,
            'octave': 0,
        },
    },
    'metal': {
        'name': 'Metal',
        'commit': {
            'program': 29,
            'octave': -1,
        },
        'file': {
            'program': 33,
            'octave': -3,
        },
    },
    'pure-violin': {
        'name': 'Violin',
        'commit': {
            'program': 40,
            'octave': 0,
        },
        'file': {
            'program': None,
            'octave': 0,
        },
    },
    'space': {
        'name': 'Space',
        'commit': {
            'program': 94,
            'octave': 1,
        },
        'file': {
            'program': 80,
            'octave': 1,
            'volume': -30,
        },
    },
    'sea-copter': {
        'name': 'Helicopter on the shore',
        'commit': {
            'program': 125,
            'octave': 0,
        },
        'file': {
            'program': 122,
            'octave': 0,
        },
    },
}


parser = argparse.ArgumentParser(description='Voice of a Repo',
                                 epilog='Use the special value list for ' +
                                 'scale and program to list the ' +
                                 'available program combinations')

parser.add_argument('repository', type=str, nargs='?', default='.')
parser.add_argument('--branch',
                    type=str,
                    default='master',
                    help="The branch to generate sound for [master]")
parser.add_argument('--file',
                    type=str,
                    default=None,
                    help="Save the generated MIDI sequence to this file")
parser.add_argument('--play',
                    action='store_true',
                    default=False,
                    help="Play the generated file (requires pygame with " +
                    "MIDI support)")
parser.add_argument('--verbose',
                    action='store_true',
                    default=False,
                    help="Print messages during execution")
parser.add_argument('--scale',
                    type=str,
                    default=None,
                    help="Scale to use in the generated track")
parser.add_argument('--program',
                    type=str,
                    default=None,
                    help="Program setting to use in the generated track")
parser.add_argument('--volume-range',
                    type=int,
                    default=100,
                    help="The volume range to use.")
parser.add_argument('--skip',
                    type=int,
                    default=0,
                    metavar='N',
                    help="Skip the first N commits " +
                    "(comes in handy if the repo started " +
                    "with some huge commits)")

args = parser.parse_args()

if args.scale is None and args.program is None and GUI_AVAILABLE:
    GitSoundWindow(PROGRAMS, SCALES).start()

    sys.exit(0)

if args.scale is None and args.program != 'list':
    print("Please specify a scale!")

    sys.exit(1)

if args.program is None and args.scale != 'list':
    print("Please specify a program!")

    sys.exit(1)

if args.scale == 'list':
    for scale in SCALES.keys():
        print(scale)

    sys.exit(0)

if args.program == 'list':
    for program in PROGRAMS.keys():
        print(program)

    sys.exit(0)

if args.scale not in SCALES:
    print("{} is an unknown scale.".format(args.scale))
    print("Use 'list' to list the available scales.")

    sys.exit(1)

if args.program not in PROGRAMS:
    print("{} is an unknown program.".format(args.program))
    print("Use 'list' to list the available programs.")

    sys.exit(1)

try:
    repo_midi = GitMIDI(repository=args.repository,
                        branch=args.branch,
                        verbose=args.verbose,
                        scale=SCALES[args.scale][1],
                        program=PROGRAMS[args.program],
                        volume_range=args.volume_range,
                        skip=args.skip)

except InvalidGitRepositoryError:
    print("{} is not a valid Git repository"
          .format(os.path.abspath(args.repository)))

    sys.exit(1)

except IndexError:
    print("Branch '{}' does not exist in this repo".format(args.branch))

    sys.exit(1)

repo_midi.gen_repo_data()
repo_midi.generate_midi()
repo_midi.write_mem()

if args.file:
    if args.verbose:
        print("Saving file to {}".format(args.file))

    repo_midi.export_file(args.file)

if args.play:
    repo_midi.play()
