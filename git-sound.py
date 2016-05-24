# -*- coding: utf-8

import argparse
import sys
import os

import shutil

from midiutil.MidiFile import MIDIFile
from StringIO import StringIO
from time import sleep
from git import Repo
from git.objects.blob import Blob
from git.exc import InvalidGitRepositoryError

# The original scale was: [60, 62, 64, 65, 67, 69, 71]
notes = [68, 69, 71, 72, 74, 76, 77]
notecount = len(notes)


def gen_history(log, commit):
    counter = 0
    to_process = [commit]

    while len(to_process) > 0:
        counter += 1

        if counter % 500 == 0:
            print("Done with {} commits".format(counter))

        commit = to_process.pop()

        if not commit in log:
            log.append(commit)
            to_process += commit.parents


def gen_volume(deletions, insertions, deviation=10):
    return max(
        deviation,
        min(255 - deviation,
            127 - deletions + insertions))


def sha_to_note(sha):
    note_num = reduce(lambda res, digit: res + int(digit, 16),
                  list(str(sha)), 0) % notecount

    return notes[note_num]


def get_file_sha(commit, file_name):
    elements = file_name.split(os.sep)
    t = commit.tree


    while True:
        try:
            t = t[elements.pop(0)]
        except KeyError:
            # The file has been deleted
            return '0000000000000000000000000000000000000000'

        if isinstance(t, Blob):
            break

    return t.hexsha

def gen_note(commit):
    stat = commit.stats
    note = sha_to_note(commit.hexsha)

    file_notes = []

    for file_name, file_stat in stat.files.items():
        file_notes.append({
            'note': sha_to_note(get_file_sha(commit, file_name)) - 12,
            'volume': gen_volume(file_stat['deletions'],
                                 file_stat['insertions'],
                                 deviation=10),
        })

    return {
        'commit_note': sha_to_note(commit.hexsha) - 24,
        'commit_volume': gen_volume(stat.total['deletions'],
                                    stat.total['insertions'],
                                    deviation=20),
        'file_notes': file_notes,
    }


class GitMIDI(MIDIFile):
    def __setup_midi(self, track_title=None):
        if track_title is None:
            # TODO: Change this to something that connects to the repo
            self.addTrackName(0, 0, "Sample Track")

            # TODO: Make this configurable
            self.addTempo(0, 0, 120)

    def __setup_repo(self):
        repo = Repo(self.__repo_dir)
        self.branch_head = repo.heads[self.__branch].commit

    def __init__(self, tracks=None, repository='.', branch='master'):
        if tracks is None:
            tracks = [("Sample Track", 120)]

        self.track_count = len(tracks)

        MIDIFile.__init__(self, self.track_count)

        self.__setup_midi()

        self.mem_file = StringIO()
        self.__written = False
        self.__repo_dir = repository
        self.__repo = None
        self.__branch = branch
        self.branch_head = None

        self.__setup_repo()

    def write_mem(self):
        self.writeFile(self.mem_file)
        self.__written = True

    def export_file(self, filename):
        if not self.__written:
            self.write_mem()

        with open(filename, 'w') as f:
            self.mem_file.seek(0)
            shutil.copyfileobj(self.mem_file, f)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Voice of a Repo')

    parser.add_argument('repository', type=str)
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

    args = parser.parse_args()

try:
    repo_midi = GitMIDI(repository=args.repository, branch=args.branch)

except InvalidGitRepositoryError:
    print("{} is not a valid Git repository".format(
        os.path.abspath(args.repository)))

    sys.exit(1)

except IndexError:
    print("Branch '{}' does not exist in this repo".format(args.branch))

    sys.exit(1)

orig_log = []

if args.verbose:
    print("Generating Git log…")

gen_history(orig_log, repo_midi.branch_head.commit)

if args.verbose:
    print("Sorting commits…")

orig_log.sort(key=lambda commit: commit.authored_date)

if args.verbose:
    print("Generating MIDI data…")

log = map(gen_note, orig_log)

if args.verbose:
    print("Creating MIDI…")

track = 0
time = 0
log_channel = 0
decor_channel = 1

# Duration of one note
duration = 0.3

repo_midi.addProgramChange(track, log_channel, 0, 104)
repo_midi.addProgramChange(track, decor_channel, 0, 115)

# WRITE THE SEQUENCE
for section in log:
    section_len = len(section['file_notes']) * duration

    # Add a long note
    repo_midi.addNote(track, log_channel,
                   section['commit_note'], time,
                   section_len, section['commit_volume'])

    for i, file_note in enumerate(section['file_notes']):
        repo_midi.addNote(track, decor_channel,
                       file_note['note'], time + i * duration,
                       duration, file_note['volume'])

    time += section_len

repo_midi.write_mem()

if args.file:
    if args.verbose:
        print("Saving file to {}".format(args.file))

    repo_midi.export_file(args.file)

if args.play:
    if args.verbose:
        print("Playing!")

    # Import pygame stuff here
    import pygame
    import pygame.mixer

    # PLAYBACK
    pygame.init()
    pygame.mixer.init()
    repo_midi.mem_file.seek(0)
    pygame.mixer.music.load(repo_midi.mem_file)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        sleep(1)
